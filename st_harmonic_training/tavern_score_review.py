from __future__ import annotations

import hashlib, html, re, shutil, zipfile
from pathlib import Path, PurePosixPath

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
PRESELECTED_RE = re.compile(r"<input[^>]*\schecked(?:\s|=|>)", re.IGNORECASE)
PINNED_IMPLICIT_SPLIT_PHRASES = frozenset({"Beethoven/B064:03:02", "Beethoven/B064:03:03"})
LETTER_INDEX = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}
TREBLE_BOTTOM = 4 * 7 + LETTER_INDEX["E"]
BASS_BOTTOM = 2 * 7 + LETTER_INDEX["G"]


class TavernScoreReviewError(ValueError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_root(infos: tuple[zipfile.ZipInfo, ...]) -> str:
    roots = {PurePosixPath(i.filename.replace("\\", "/")).parts[0] for i in infos if PurePosixPath(i.filename.replace("\\", "/")).parts}
    if len(roots) != 1 or not next(iter(roots)).startswith("TAVERN-"):
        raise TavernScoreReviewError("TAVERN archive must have one TAVERN-* root")
    return next(iter(roots))


def _logical(name: str, root: str) -> str:
    path = PurePosixPath(name.replace("\\", "/"))
    if not path.parts or path.parts[0] != root:
        raise TavernScoreReviewError(f"member outside TAVERN root: {name}")
    return PurePosixPath(*path.parts[1:]).as_posix() if len(path.parts) > 1 else ""


def _read_bounded(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    if info.file_size > MAX_ANALYSIS_MEMBER_BYTES:
        raise IngestSecurityError(f"score member exceeds review limit: {info.filename}")
    data = zf.read(info)
    if len(data) != info.file_size or len(data) > MAX_ANALYSIS_MEMBER_BYTES:
        raise IngestSecurityError(f"score member expanded beyond declared/allowed size: {info.filename}")
    return data


def _collect_scores(infos: tuple[zipfile.ZipInfo, ...], root: str) -> dict[str, tuple[str, zipfile.ZipInfo]]:
    result: dict[str, tuple[str, zipfile.ZipInfo]] = {}
    for info in infos:
        if info.is_dir():
            continue
        logical = _logical(info.filename, root)
        parts = PurePosixPath(logical).parts
        if len(parts) < 4 or parts[0] not in {"Beethoven", "Mozart"} or parts[2] != "Krn":
            continue
        match = SCORE_RE.search(parts[-1])
        if not match:
            continue
        key = f"{parts[0]}/{parts[1]}:{match.group(1)}:{match.group(2)}"
        if key in result:
            raise TavernScoreReviewError(f"duplicate phrase score: {key}")
        result[key] = (logical, info)
    return result


def _parse_pitch(token: str):
    match = DURATION_RE.match(token)
    if match:
        duration, dots, body, grace = int(match.group(1)), len(match.group(2)), match.group(3), False
    else:
        duration, dots, body, grace = 8, 0, token, True
    if "r" in body.lower() and not PITCH_RE.search(body.replace("r", "").replace("R", "")):
        return "rest", "", duration, dots, grace
    pitch = PITCH_RE.search(body)
    if not pitch:
        return None
    letters, modifiers = pitch.groups()
    first = letters[0]
    repeated = next((i for i, char in enumerate(letters, 1) if i == len(letters) or letters[i].lower() != first.lower()), len(letters))
    octave = 3 + repeated if first.islower() else 4 - repeated
    accidental = "♯" if "#" in modifiers else ("♭" if "-" in modifiers else ("♮" if "n" in modifiers else ""))
    return octave * 7 + LETTER_INDEX[first.upper()], accidental, duration, dots, grace


def parse_kern_for_review(text: str, phrase_key: str) -> dict[str, object]:
    spines: list[dict[str, object]] = []
    measures: list[dict[str, object]] = []
    current: dict[str, object] = {"label": "", "rows": []}
    key = meter = tonic = ""
    warnings: list[str] = []
    started = False
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not line or line.startswith("!"):
            continue
        cells = line.split("\t")
        if line.startswith("**kern"):
            spines, started = [{"staff": None, "clef": ""} for _ in cells], True
            continue
        if not started:
            continue
        if line.startswith("="):
            if current["rows"] or current["label"]:
                measures.append(current)
            number = re.search(r"(\d+)", cells[0])
            current = {"label": number.group(1) if number else "", "rows": []}
            continue
        if line.startswith("*"):
            tokens = (cells + ["*"] * len(spines))[: len(spines)]
            for i, token in enumerate(tokens):
                staff = re.match(r"\*staff(\d+)", token)
                if staff:
                    spines[i]["staff"] = int(staff.group(1))
                elif token.startswith("*clef"):
                    spines[i]["clef"] = token[5:]
                elif token.startswith("*k[") and not key:
                    key = token[2:]
                elif token.startswith("*M") and not meter:
                    meter = token[2:]
                elif re.match(r"^\*[A-Ga-g][#-]?:$", token) and not tonic:
                    tonic = token[1:]
            if any(t in {"*^", "*v", "*-"} for t in tokens):
                updated, i = [], 0
                while i < len(spines):
                    if tokens[i] == "*^":
                        updated += [dict(spines[i]), dict(spines[i])]; i += 1
                    elif tokens[i] == "*v":
                        merged, j = dict(spines[i]), i + 1
                        while j < len(spines) and tokens[j] == "*v": j += 1
                        updated.append(merged); i = j
                    elif tokens[i] == "*-": i += 1
                    else: updated.append(spines[i]); i += 1
                spines = updated
            continue
        if len(cells) != len(spines):
            if phrase_key in PINNED_IMPLICIT_SPLIT_PHRASES and len(cells) == 3 and len(spines) == 2:
                spines.append(dict(spines[-1]))
                warnings.append("pinned TAVERN source anomaly: implicit rightmost staff1 spine split")
            else:
                raise TavernScoreReviewError(f"score spine mismatch for {phrase_key}: {len(cells)} != {len(spines)}")
        row = []
        for i, cell in enumerate(cells):
            if cell == ".":
                continue
            clef = str(spines[i].get("clef") or "")
            staff = spines[i].get("staff")
            if staff is None:
                staff = 1 if clef.startswith("G") else (2 if clef.startswith("F") else (1 if i >= len(spines) / 2 else 2))
            notes = [p for token in cell.split(" ") if (p := _parse_pitch(token)) is not None]
            if notes:
                row.append({"staff": int(staff), "voice": i, "notes": notes})
        if row:
            current["rows"].append(row)
    if current["rows"] or current["label"]:
        measures.append(current)
    measures = [m for m in measures if m["rows"]]
    if not measures:
        raise TavernScoreReviewError(f"score contains no reviewable events: {phrase_key}")
    return {"measures": measures, "key": key, "meter": meter, "tonic": tonic, "warnings": sorted(set(warnings))}


def _note_y(diatonic: int, staff: int, top: float) -> float:
    return top + 40 - (diatonic - (TREBLE_BOTTOM if staff == 1 else BASS_BOTTOM)) * 5


def render_score_svg(score: dict[str, object], phrase_key: str, score_sha256: str) -> str:
    measures = list(score["measures"])
    systems, current, width_sum = [], [], 0.0
    for measure in measures:
        width = float(min(430, max(170, 55 + max(1, len(measure["rows"])) * 20)))
        if current and width_sum + width > 1120:
            systems.append(current); current, width_sum = [], 0.0
        current.append((measure, width)); width_sum += width
    if current: systems.append(current)
    height = 65 + len(systems) * 145
    out = [f'<svg class="score-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {height}" role="img" aria-label="Reference score for {html.escape(phrase_key, quote=True)}"><rect width="100%" height="100%" fill="white"/>']
    meta = [f"{name} {score[name]}" for name in ("tonic", "meter", "key") if score.get(name)]
    out.append(f'<text x="20" y="20" font-family="Arial,sans-serif" font-size="13">{html.escape(" · ".join(meta))}</text>')
    for sys_i, system in enumerate(systems):
        tt, bt, x0 = 35 + sys_i * 145, 100 + sys_i * 145, 58.0
        scale = min(1.0, (1200 - x0 - 25) / sum(w for _, w in system))
        out += [f'<text x="8" y="{tt+28}" font-family="Arial,sans-serif" font-size="11">Treble</text>', f'<text x="42" y="{tt+26}" font-family="Arial,sans-serif" font-size="12" font-weight="bold">G</text>', f'<text x="12" y="{bt+28}" font-family="Arial,sans-serif" font-size="11">Bass</text>', f'<text x="42" y="{bt+26}" font-family="Arial,sans-serif" font-size="12" font-weight="bold">F</text>']
        sw = sum(w * scale for _, w in system)
        for top in (tt, bt):
            for k in range(5): out.append(f'<line x1="58" y1="{top+k*10}" x2="{58+sw:.1f}" y2="{top+k*10}" stroke="#222"/>')
        x = x0
        for measure, raw_w in system:
            mw = raw_w * scale
            out.append(f'<line x1="{x:.1f}" y1="{tt}" x2="{x:.1f}" y2="{bt+40}" stroke="#333"/>')
            if measure.get("label"): out.append(f'<text x="{x+4:.1f}" y="{tt-5}" font-family="Arial,sans-serif" font-size="10">m.{html.escape(str(measure["label"]))}</text>')
            rows = list(measure["rows"]); count = max(1, len(rows))
            for ri, row in enumerate(rows):
                nx = x + 22 + (ri + .5) * (max(40, mw - 35) / count)
                for event in row:
                    staff = 1 if event["staff"] == 1 else 2; top = tt if staff == 1 else bt
                    pitches = [p for p in event["notes"] if p[0] != "rest"]
                    if not pitches:
                        out.append(f'<text x="{nx-4:.1f}" y="{top+24}" font-family="Arial,sans-serif" font-size="12">rest</text>'); continue
                    vo = ((int(event["voice"]) % 3) - 1) * 1.8
                    for diatonic, accidental, duration, dots, grace in pitches:
                        y = _note_y(int(diatonic), staff, top); bottom = top + 40
                        ledger = top - 10 if y < top else bottom + 10
                        if y < top:
                            while ledger >= y - 1: out.append(f'<line x1="{nx-8:.1f}" y1="{ledger:.1f}" x2="{nx+9:.1f}" y2="{ledger:.1f}" stroke="#333"/>'); ledger -= 10
                        elif y > bottom:
                            while ledger <= y + 1: out.append(f'<line x1="{nx-8:.1f}" y1="{ledger:.1f}" x2="{nx+9:.1f}" y2="{ledger:.1f}" stroke="#333"/>'); ledger += 10
                        if accidental: out.append(f'<text x="{nx-13+vo:.1f}" y="{y+4:.1f}" font-family="Arial,sans-serif" font-size="13">{html.escape(str(accidental))}</text>')
                        fill = "white" if int(duration) <= 2 else "#111"
                        out.append(f'<ellipse cx="{nx+vo:.1f}" cy="{y:.1f}" rx="5.5" ry="3.8" transform="rotate(-20 {nx+vo:.1f} {y:.1f})" fill="{fill}" stroke="#111" stroke-width="1.3"/>')
                        if int(duration) != 1:
                            mid = top + 20; stem_x = nx + (5 if y >= mid else -5) + vo; stem_end = y + (-27 if y >= mid else 27)
                            out.append(f'<line x1="{stem_x:.1f}" y1="{y:.1f}" x2="{stem_x:.1f}" y2="{stem_end:.1f}" stroke="#111"/>')
                            if int(duration) >= 8:
                                d = -1 if y >= mid else 1; out.append(f'<path d="M {stem_x:.1f} {stem_end:.1f} q {8*d:.1f} {5*d:.1f} {7*d:.1f} {13*d:.1f}" fill="none" stroke="#111"/>')
                        if int(dots): out.append(f'<circle cx="{nx+9+vo:.1f}" cy="{y-1:.1f}" r="1.4"/>')
                        if grace: out.append(f'<text x="{nx-6:.1f}" y="{y-8:.1f}" font-family="Arial,sans-serif" font-size="7">g</text>')
            x += mw
        out.append(f'<line x1="{x:.1f}" y1="{tt}" x2="{x:.1f}" y2="{bt+40}" stroke="#111" stroke-width="2"/>')
    footer = f"Score SHA-256: {score_sha256} · TAVERN **kern pitch/onset rendering; beam/slur engraving simplified for review readability."
    if score.get("warnings"): footer += " · SOURCE WARNING: " + "; ".join(str(w) for w in score["warnings"])
    out.append(f'<text x="20" y="{height-5}" font-family="Arial,sans-serif" font-size="10" fill="#666">{html.escape(footer)}</text></svg>')
    return "".join(out)


def enrich_review_package_with_scores(source_dir: str | Path, output_dir: str | Path, archive_path: str | Path, *, expected_raw_archive_sha256: str = PINNED_TAVERN_RAW_SHA256, expected_phrase_count: int = PINNED_TAVERN_AB_PAIR_COUNT) -> dict[str, object]:
    source, output, archive = Path(source_dir), Path(output_dir), Path(archive_path)
    expected = expected_raw_archive_sha256.strip().lower()
    if not SHA256_RE.fullmatch(expected): raise TavernScoreReviewError("expected archive SHA-256 must be lowercase hex")
    if archive.is_symlink() or not archive.is_file(): raise TavernScoreReviewError("archive must be a regular non-symlink file")
    observed = _sha256_file(archive)
    if observed != expected: raise TavernScoreReviewError(f"TAVERN raw archive SHA-256 mismatch: expected {expected}, observed {observed}")
    if source.is_symlink() or not source.is_dir(): raise TavernScoreReviewError("source review package must be a regular directory")
    if output.exists(): raise TavernScoreReviewError("score-aware output directory must not already exist")
    infos = inspect_zip(archive); root = _archive_root(infos); scores = _collect_scores(infos, root)
    batches = sorted(source.glob("batch-*.html"))
    if not batches or not (source / "index.html").is_file(): raise TavernScoreReviewError("source review package is incomplete")
    phrases: list[str] = []; score_hashes = {}; warnings = {}
    try:
        shutil.copytree(source, output, symlinks=False)
        with zipfile.ZipFile(archive) as zf:
            for batch in batches:
                text = batch.read_text(encoding="utf-8")
                if PRESELECTED_RE.search(text): raise TavernScoreReviewError("source review package contains a preselected decision")
                marker = ".card { border-top: 2px solid #777; padding: 1rem 0 1.5rem; }"
                if marker not in text: raise TavernScoreReviewError("unexpected Stage 0-N stylesheet contract")
                text = text.replace(marker, marker + "\n.score-panel { border: 2px solid #333; padding: .75rem; margin: .8rem 0 1rem; background: #fafafa; }\n.score-svg { width: 100%; height: auto; display: block; min-height: 150px; }\n.score-note { font-size: .82rem; color: #555; }")
                def inject(match: re.Match[str]) -> str:
                    key = html.unescape(match.group(1))
                    if not PHRASE_KEY_RE.fullmatch(key): raise TavernScoreReviewError(f"unsafe phrase key: {key!r}")
                    if key in phrases: raise TavernScoreReviewError(f"duplicate phrase in review package: {key}")
                    phrases.append(key)
                    if key not in scores: raise TavernScoreReviewError(f"reference score missing for phrase {key}")
                    logical, info = scores[key]; raw = _read_bounded(zf, info); sha = hashlib.sha256(raw).hexdigest()
                    try: parsed = parse_kern_for_review(raw.decode("utf-8-sig"), key)
                    except UnicodeDecodeError as exc: raise TavernScoreReviewError(f"score must be UTF-8: {key}") from exc
                    score_hashes[key] = sha
                    if parsed["warnings"]: warnings[key] = list(parsed["warnings"])
                    panel = '<div class="score-panel"><h3>Reference score phrase</h3>' + f'<p class="hash">Source: {html.escape(logical)}</p>' + render_score_svg(parsed, key, sha) + '<p class="score-note"><strong>Use this score as the musical reference before choosing A or B.</strong> Horizontal spacing is normalized by aligned **kern onset rows; pitches, accidentals, staff assignment, measure boundaries and basic durations are rendered from the pinned score phrase. If visual evidence is unclear, choose AMBIGUOUS or ABSTAIN.</p></div>'
                    return match.group(0) + panel
                text = PHRASE_HEADING_RE.sub(inject, text)
                (output / batch.name).write_text(text, encoding="utf-8", newline="\n")
        if len(phrases) != expected_phrase_count or len(set(phrases)) != expected_phrase_count: raise TavernScoreReviewError(f"score-aware phrase count mismatch: expected {expected_phrase_count}, observed {len(phrases)}")
        index = (output / "index.html").read_text(encoding="utf-8").replace("Stage 0-N human review package", "Stage 0-N1 score-aware human review package").replace("Open one batch at a time,", "Each record includes its pinned TAVERN score phrase above Annotator A/B. Open one batch at a time,")
        (output / "index.html").write_text(index, encoding="utf-8", newline="\n")
        return {"schema_version": SCORE_AWARE_SCHEMA, "phrase_count": len(phrases), "score_count": len(score_hashes), "source_warning_count": len(warnings), "source_warnings": warnings, "raw_archive_sha256": observed, "gold_assignment_authorized": False, "partition_assignment_authorized": False, "training_authorized": False}
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise
