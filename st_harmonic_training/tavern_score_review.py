from __future__ import annotations

from collections import defaultdict
import hashlib
import html
from pathlib import Path, PurePosixPath
import re
import shutil
from typing import Any
import zipfile

from .safe_ingest import IngestSecurityError, inspect_zip
from .tavern_ab_compare import MAX_ANALYSIS_MEMBER_BYTES
from .tavern_adjudication import PINNED_TAVERN_AB_PAIR_COUNT
from .tavern_structure import PINNED_TAVERN_RAW_SHA256, SCORE_RE

SCORE_AWARE_SCHEMA = "st-tavern-score-aware-review-v1"
PHRASE_HEADING_RE = re.compile(r'<section class="card"><h2>([^<]+)</h2>')
PHRASE_KEY_RE = re.compile(r"^[A-Za-z]+/[A-Za-z0-9]+:[0-9]{2}:[0-9]{2}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DURATION_RE = re.compile(r"^[^0-9]*?(\d+)(\.*)(.*)$")
PITCH_RE = re.compile(r"([A-Ga-g]+)([#n-]*)")

PINNED_IMPLICIT_SPLIT_PHRASES = frozenset({
    "Beethoven/B064:03:02",
    "Beethoven/B064:03:03",
})

LETTER_INDEX = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}
TREBLE_BOTTOM = 4 * 7 + LETTER_INDEX["E"]
BASS_BOTTOM = 2 * 7 + LETTER_INDEX["G"]


class TavernScoreReviewError(ValueError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _archive_root(infos: tuple[zipfile.ZipInfo, ...]) -> str:
    roots: set[str] = set()
    for info in infos:
        parts = PurePosixPath(info.filename.replace("\\", "/")).parts
        if parts:
            roots.add(parts[0])
    if len(roots) != 1:
        raise TavernScoreReviewError("TAVERN archive must have exactly one top-level root")
    root = next(iter(roots))
    if not root.startswith("TAVERN-"):
        raise TavernScoreReviewError(f"unexpected TAVERN archive root: {root}")
    return root


def _logical_path(name: str, root: str) -> str:
    path = PurePosixPath(name.replace("\\", "/"))
    if not path.parts or path.parts[0] != root:
        raise TavernScoreReviewError(f"member outside TAVERN root: {name}")
    return PurePosixPath(*path.parts[1:]).as_posix() if len(path.parts) > 1 else ""


def _read_member_bounded(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    if info.file_size > MAX_ANALYSIS_MEMBER_BYTES:
        raise IngestSecurityError(f"score member exceeds review limit: {info.filename}")
    chunks: list[bytes] = []
    observed = 0
    with zf.open(info, "r") as source:
        while True:
            chunk = source.read(64 * 1024)
            if not chunk:
                break
            observed += len(chunk)
            if observed > MAX_ANALYSIS_MEMBER_BYTES or observed > info.file_size:
                raise IngestSecurityError(
                    f"score member expanded beyond declared/allowed size: {info.filename}"
                )
            chunks.append(chunk)
    return b"".join(chunks)


def _collect_scores(
    infos: tuple[zipfile.ZipInfo, ...], root: str
) -> dict[str, tuple[str, zipfile.ZipInfo]]:
    scores: dict[str, tuple[str, zipfile.ZipInfo]] = {}
    for info in infos:
        if info.is_dir():
            continue
        logical = _logical_path(info.filename, root)
        parts = PurePosixPath(logical).parts
        if len(parts) < 4 or parts[0] not in {"Beethoven", "Mozart"} or parts[2] != "Krn":
            continue
        match = SCORE_RE.search(parts[-1])
        if not match:
            continue
        phrase_key = f"{parts[0]}/{parts[1]}:{match.group(1)}:{match.group(2)}"
        if phrase_key in scores:
            raise TavernScoreReviewError(f"duplicate phrase score: {phrase_key}")
        scores[phrase_key] = (logical, info)
    return scores


def _parse_pitch(token: str) -> tuple[int | str, str | None, int, int, bool] | None:
    match = DURATION_RE.match(token)
    grace = False
    if match:
        duration = int(match.group(1))
        dots = len(match.group(2))
        body = match.group(3)
    else:
        body = token
        duration = 8
        dots = 0
        grace = True
    if "r" in body.lower() and not PITCH_RE.search(body.replace("r", "").replace("R", "")):
        return ("rest", None, duration, dots, grace)
    pitch = PITCH_RE.search(body)
    if not pitch:
        return None
    letters = pitch.group(1)
    first = letters[0]
    repeated = 0
    for char in letters:
        if char.lower() == first.lower():
            repeated += 1
        else:
            break
    octave = 3 + repeated if first.islower() else 4 - repeated
    diatonic = octave * 7 + LETTER_INDEX[first.upper()]
    modifiers = pitch.group(2)
    accidental = "♯" if "#" in modifiers else ("♭" if "-" in modifiers else ("♮" if "n" in modifiers else ""))
    return (diatonic, accidental, duration, dots, grace)


def parse_kern_for_review(text: str, phrase_key: str) -> dict[str, object]:
    spines: list[dict[str, object]] = []
    key = ""
    meter = ""
    tonic = ""
    measures: list[dict[str, object]] = []
    current: dict[str, object] = {"label": "", "rows": []}
    warnings: list[str] = []
    started = False

    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not raw_line or raw_line.startswith("!"):
            continue
        cells = raw_line.split("\t")
        if raw_line.startswith("**kern"):
            spines = [{"staff": None, "clef": None} for _ in cells]
            started = True
            continue
        if not started:
            continue
        if raw_line.startswith("="):
            if current["rows"] or current["label"]:
                measures.append(current)
            number = re.search(r"(\d+)", cells[0])
            current = {"label": number.group(1) if number else "", "rows": []}
            continue
        if raw_line.startswith("*"):
            interpreted = (cells + ["*"] * len(spines))[: len(spines)]
            for index, token in enumerate(interpreted):
                staff_match = re.match(r"\*staff(\d+)", token)
                if staff_match:
                    spines[index]["staff"] = int(staff_match.group(1))
                elif token.startswith("*clef"):
                    spines[index]["clef"] = token[5:]
                elif token.startswith("*k[") and not key:
                    key = token[2:]
                elif (token.startswith("*M") or re.match(r"^\*\d+/\d+$", token)) and not meter:
                    meter = token[2:] if token.startswith("*M") else token[1:]
                elif re.match(r"^\*[A-Ga-g][#-]?:$", token) and not tonic:
                    tonic = token[1:]
            if any(token in {"*^", "*v", "*-"} for token in interpreted):
                updated: list[dict[str, object]] = []
                index = 0
                while index < len(spines):
                    token = interpreted[index]
                    if token == "*^":
                        updated.extend((dict(spines[index]), dict(spines[index])))
                        index += 1
                    elif token == "*v":
                        merged = dict(spines[index])
                        lookahead = index + 1
                        while lookahead < len(spines) and interpreted[lookahead] == "*v":
                            lookahead += 1
                        updated.append(merged)
                        index = lookahead
                    elif token == "*-":
                        index += 1
                    else:
                        updated.append(spines[index])
                        index += 1
                spines = updated
            continue

        if len(cells) != len(spines):
            if (
                phrase_key in PINNED_IMPLICIT_SPLIT_PHRASES
                and len(cells) == 3
                and len(spines) == 2
                and spines
            ):
                spines.append(dict(spines[-1]))
                warnings.append("pinned TAVERN source anomaly: implicit rightmost staff1 spine split")
            else:
                raise TavernScoreReviewError(
                    f"score spine mismatch for {phrase_key}: {len(cells)} != {len(spines)}"
                )

        row: list[dict[str, object]] = []
        for index, cell in enumerate(cells):
            if cell == ".":
                continue
            staff = spines[index].get("staff")
            clef = str(spines[index].get("clef") or "")
            if staff is None:
                staff = 1 if clef.startswith("G") else (2 if clef.startswith("F") else (1 if index >= len(spines) / 2 else 2))
            notes = [parsed for subtoken in cell.split(" ") if (parsed := _parse_pitch(subtoken)) is not None]
            if notes:
                row.append({"staff": int(staff), "notes": notes, "voice": index})
        if row:
            current["rows"].append(row)

    if current["rows"] or current["label"]:
        measures.append(current)
    measures = [measure for measure in measures if measure["rows"]]
    if not measures:
        raise TavernScoreReviewError(f"score contains no reviewable events: {phrase_key}")
    return {
        "measures": measures,
        "key": key,
        "meter": meter,
        "tonic": tonic,
        "warnings": sorted(set(warnings)),
    }


def _note_y(diatonic: int, staff: int, top: float) -> float:
    bottom_y = top + 40
    bottom_diatonic = TREBLE_BOTTOM if staff == 1 else BASS_BOTTOM
    return bottom_y - (diatonic - bottom_diatonic) * 5


def _measure_width(measure: dict[str, object]) -> float:
    count = max(1, len(measure["rows"]))
    return float(min(430, max(170, 55 + count * 20)))


def render_score_svg(score: dict[str, object], phrase_key: str, score_sha256: str) -> str:
    measures = list(score["measures"])
    systems: list[list[tuple[dict[str, object], float]]] = []
    current: list[tuple[dict[str, object], float]] = []
    current_width = 0.0
    for measure in measures:
        width = _measure_width(measure)
        if current and current_width + width > 1120:
            systems.append(current)
            current = []
            current_width = 0.0
        current.append((measure, width))
        current_width += width
    if current:
        systems.append(current)

    system_height = 145
    height = 45 + len(systems) * system_height + 20
    width = 1200
    output = [
        f'<svg class="score-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Reference score for {html.escape(phrase_key, quote=True)}">',
        '<rect width="100%" height="100%" fill="white"/>',
    ]
    metadata = []
    if score.get("tonic"):
        metadata.append(f"tonic {score['tonic']}")
    if score.get("meter"):
        metadata.append(f"meter {score['meter']}")
    if score.get("key"):
        metadata.append(f"key {score['key']}")
    output.append(
        f'<text x="20" y="20" font-family="Arial,sans-serif" font-size="13" fill="#333">{html.escape(" · ".join(metadata))}</text>'
    )

    base_y = 35
    for system_index, system in enumerate(systems):
        treble_top = base_y + system_index * system_height
        bass_top = treble_top + 65
        x_start = 58.0
        total_width = sum(item[1] for item in system)
        scale = min(1.0, (width - x_start - 25) / total_width)
        output.extend((
            f'<text x="8" y="{treble_top + 28}" font-family="Arial,sans-serif" font-size="11">Treble</text>',
            f'<text x="42" y="{treble_top + 26}" font-family="Arial,sans-serif" font-size="12" font-weight="bold">G</text>',
            f'<text x="12" y="{bass_top + 28}" font-family="Arial,sans-serif" font-size="11">Bass</text>',
            f'<text x="42" y="{bass_top + 26}" font-family="Arial,sans-serif" font-size="12" font-weight="bold">F</text>',
        ))
        system_width = sum(item[1] * scale for item in system)
        for staff_top in (treble_top, bass_top):
            for line_index in range(5):
                y = staff_top + line_index * 10
                output.append(f'<line x1="58" y1="{y}" x2="{58 + system_width:.1f}" y2="{y}" stroke="#222" stroke-width="1"/>')

        x = x_start
        for measure, unscaled_width in system:
            measure_width = unscaled_width * scale
            output.append(f'<line x1="{x:.1f}" y1="{treble_top}" x2="{x:.1f}" y2="{bass_top + 40}" stroke="#333" stroke-width="1.2"/>')
            if measure.get("label"):
                output.append(f'<text x="{x + 4:.1f}" y="{treble_top - 5}" font-family="Arial,sans-serif" font-size="10" fill="#555">m.{html.escape(str(measure["label"]))}</text>')
            rows = list(measure["rows"])
            row_count = max(1, len(rows))
            for row_index, row in enumerate(rows):
                note_x = x + 22 + (row_index + 0.5) * (max(40, measure_width - 35) / row_count)
                for event in row:
                    staff = 1 if event["staff"] == 1 else 2
                    staff_top = treble_top if staff == 1 else bass_top
                    pitches = [item for item in event["notes"] if item[0] != "rest"]
                    rests = [item for item in event["notes"] if item[0] == "rest"]
                    if rests and not pitches:
                        output.append(f'<text x="{note_x - 4:.1f}" y="{staff_top + 24}" font-family="Arial,sans-serif" font-size="12" fill="#555">rest</text>')
                        continue
                    voice_offset = ((int(event["voice"]) % 3) - 1) * 1.8
                    for diatonic, accidental, duration, dots, grace in pitches:
                        y = _note_y(int(diatonic), staff, staff_top)
                        bottom = staff_top + 40
                        if y < staff_top - 1:
                            ledger = staff_top - 10
                            while ledger >= y - 1:
                                output.append(f'<line x1="{note_x - 8:.1f}" y1="{ledger:.1f}" x2="{note_x + 9:.1f}" y2="{ledger:.1f}" stroke="#333" stroke-width="1"/>')
                                ledger -= 10
                        elif y > bottom + 1:
                            ledger = bottom + 10
                            while ledger <= y + 1:
                                output.append(f'<line x1="{note_x - 8:.1f}" y1="{ledger:.1f}" x2="{note_x + 9:.1f}" y2="{ledger:.1f}" stroke="#333" stroke-width="1"/>')
                                ledger += 10
                        if accidental:
                            output.append(f'<text x="{note_x - 13 + voice_offset:.1f}" y="{y + 4:.1f}" font-family="Arial,sans-serif" font-size="13">{html.escape(str(accidental))}</text>')
                        fill = "white" if int(duration) <= 2 else "#111"
                        output.append(f'<ellipse cx="{note_x + voice_offset:.1f}" cy="{y:.1f}" rx="5.5" ry="3.8" transform="rotate(-20 {note_x + voice_offset:.1f} {y:.1f})" fill="{fill}" stroke="#111" stroke-width="1.3"/>')
                        if int(duration) != 1:
                            middle = staff_top + 20
                            if y >= middle:
                                stem_x = note_x + 5 + voice_offset
                                stem_end = y - 27
                            else:
                                stem_x = note_x - 5 + voice_offset
                                stem_end = y + 27
                            output.append(f'<line x1="{stem_x:.1f}" y1="{y:.1f}" x2="{stem_x:.1f}" y2="{stem_end:.1f}" stroke="#111" stroke-width="1.2"/>')
                            if int(duration) >= 8:
                                direction = -1 if y >= middle else 1
                                output.append(f'<path d="M {stem_x:.1f} {stem_end:.1f} q {8 * direction:.1f} {5 * direction:.1f} {7 * direction:.1f} {13 * direction:.1f}" fill="none" stroke="#111" stroke-width="1.3"/>')
                        if int(dots):
                            output.append(f'<circle cx="{note_x + 9 + voice_offset:.1f}" cy="{y - 1:.1f}" r="1.4" fill="#111"/>')
                        if grace:
                            output.append(f'<text x="{note_x - 6:.1f}" y="{y - 8:.1f}" font-family="Arial,sans-serif" font-size="7" fill="#666">g</text>')
            x += measure_width
        output.append(f'<line x1="{x:.1f}" y1="{treble_top}" x2="{x:.1f}" y2="{bass_top + 40}" stroke="#111" stroke-width="2"/>')

    footer = (
        f"Score SHA-256: {score_sha256} · TAVERN **kern pitch/onset rendering; "
        "beam/slur engraving simplified for review readability."
    )
    if score.get("warnings"):
        footer += " · SOURCE WARNING: " + "; ".join(str(item) for item in score["warnings"])
    output.append(f'<text x="20" y="{height - 5}" font-family="Arial,sans-serif" font-size="10" fill="#666">{html.escape(footer)}</text>')
    output.append("</svg>")
    return "".join(output)


def enrich_review_package_with_scores(
    source_dir: str | Path,
    output_dir: str | Path,
    archive_path: str | Path,
    *,
    expected_raw_archive_sha256: str = PINNED_TAVERN_RAW_SHA256,
    expected_phrase_count: int = PINNED_TAVERN_AB_PAIR_COUNT,
) -> dict[str, object]:
    source = Path(source_dir)
    output = Path(output_dir)
    archive = Path(archive_path)
    expected_hash = expected_raw_archive_sha256.strip().lower()
    if not SHA256_RE.fullmatch(expected_hash):
        raise TavernScoreReviewError("expected archive SHA-256 must be lowercase hex")
    if archive.is_symlink() or not archive.is_file():
        raise TavernScoreReviewError("archive must be a regular non-symlink file")
    observed_hash = _sha256_file(archive)
    if observed_hash != expected_hash:
        raise TavernScoreReviewError(
            f"TAVERN raw archive SHA-256 mismatch: expected {expected_hash}, observed {observed_hash}"
        )
    if source.is_symlink() or not source.is_dir():
        raise TavernScoreReviewError("source review package must be a regular directory")
    if output.exists():
        raise TavernScoreReviewError("score-aware output directory must not already exist")

    infos = inspect_zip(archive)
    root = _archive_root(infos)
    scores = _collect_scores(infos, root)
    batch_paths = sorted(source.glob("batch-*.html"))
    if not batch_paths or not (source / "index.html").is_file():
        raise TavernScoreReviewError("source review package is incomplete")

    try:
        shutil.copytree(source, output, symlinks=False)
        phrase_keys: list[str] = []
        score_hashes: dict[str, str] = {}
        source_warnings: dict[str, list[str]] = {}
        with zipfile.ZipFile(archive) as zf:
            for batch_path in batch_paths:
                text = batch_path.read_text(encoding="utf-8")
                if "checked" in text.lower():
                    raise TavernScoreReviewError("source review package contains a preselected decision")
                marker = ".card { border-top: 2px solid #777; padding: 1rem 0 1.5rem; }"
                if marker in text:
                    text = text.replace(
                        marker,
                        marker
                        + "\n.score-panel { border: 2px solid #333; padding: .75rem; margin: .8rem 0 1rem; background: #fafafa; }"
                        + "\n.score-svg { width: 100%; height: auto; display: block; min-height: 150px; }"
                        + "\n.score-note { font-size: .82rem; color: #555; }",
                    )
                else:
                    raise TavernScoreReviewError("unexpected Stage 0-N stylesheet contract")

                def replace_card(match: re.Match[str]) -> str:
                    phrase_key = html.unescape(match.group(1))
                    if not PHRASE_KEY_RE.fullmatch(phrase_key):
                        raise TavernScoreReviewError(f"unsafe phrase key in review package: {phrase_key!r}")
                    if phrase_key in phrase_keys:
                        raise TavernScoreReviewError(f"duplicate phrase in review package: {phrase_key}")
                    phrase_keys.append(phrase_key)
                    score_entry = scores.get(phrase_key)
                    if score_entry is None:
                        raise TavernScoreReviewError(f"reference score missing for phrase {phrase_key}")
                    logical_path, info = score_entry
                    raw = _read_member_bounded(zf, info)
                    score_sha = _sha256_bytes(raw)
                    try:
                        decoded = raw.decode("utf-8-sig")
                    except UnicodeDecodeError as exc:
                        raise TavernScoreReviewError(f"score must be UTF-8: {phrase_key}") from exc
                    parsed = parse_kern_for_review(decoded, phrase_key)
                    svg = render_score_svg(parsed, phrase_key, score_sha)
                    score_hashes[phrase_key] = score_sha
                    if parsed["warnings"]:
                        source_warnings[phrase_key] = list(parsed["warnings"])
                    panel = (
                        '<div class="score-panel"><h3>Reference score phrase</h3>'
                        f'<p class="hash">Source: {html.escape(logical_path)}</p>{svg}'
                        '<p class="score-note"><strong>Use this score as the musical reference before choosing A or B.</strong> '
                        'Horizontal spacing is normalized by aligned **kern onset rows; pitches, accidentals, staff assignment, '
                        'measure boundaries and basic durations are rendered from the pinned score phrase. If visual evidence is '
                        'unclear, choose AMBIGUOUS or ABSTAIN.</p></div>'
                    )
                    return match.group(0) + panel

                text = PHRASE_HEADING_RE.sub(replace_card, text)
                (output / batch_path.name).write_text(text, encoding="utf-8", newline="\n")

        if len(phrase_keys) != expected_phrase_count or len(set(phrase_keys)) != expected_phrase_count:
            raise TavernScoreReviewError(
                f"score-aware phrase count mismatch: expected {expected_phrase_count}, observed {len(phrase_keys)}"
            )
        index = (output / "index.html").read_text(encoding="utf-8")
        index = index.replace("Stage 0-N human review package", "Stage 0-N1 score-aware human review package")
        index = index.replace(
            "Open one batch at a time,",
            "Each record includes its pinned TAVERN score phrase above Annotator A/B. Open one batch at a time,",
        )
        (output / "index.html").write_text(index, encoding="utf-8", newline="\n")
        return {
            "schema_version": SCORE_AWARE_SCHEMA,
            "phrase_count": len(phrase_keys),
            "score_count": len(score_hashes),
            "source_warning_count": len(source_warnings),
            "source_warnings": source_warnings,
            "raw_archive_sha256": observed_hash,
            "gold_assignment_authorized": False,
            "partition_assignment_authorized": False,
            "training_authorized": False,
        }
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise
