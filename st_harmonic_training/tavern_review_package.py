from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import html
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
from typing import Any
import zipfile

from .safe_ingest import IngestSecurityError, inspect_zip, load_bounded_json
from .tavern_ab_compare import (
    ANALYSIS_RE,
    MAX_ANALYSIS_MEMBER_BYTES,
    canonical_ab_comparison_json,
)
from .tavern_adjudication import (
    ADJUDICATION_INPUT_SCHEMA,
    PINNED_TAVERN_AB_COMPARISON_SHA256,
    PINNED_TAVERN_AB_PAIR_COUNT,
    build_tavern_adjudication_gate,
)
from .tavern_structure import PINNED_TAVERN_RAW_SHA256, PINNED_TAVERN_REVISION

REVIEW_MANIFEST_SCHEMA = "st-tavern-human-review-package-v1"
DEFAULT_BATCH_SIZE = 25
MAX_BATCH_SIZE = 50
PHRASE_KEY_RE = re.compile(r"^[A-Za-z]+/[A-Za-z0-9]+:[0-9]{2}:[0-9]{2}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DOCUMENTED_ANNOTATORS = frozenset({"A", "B"})

DECISIONS_BY_RELATION = {
    "BYTE_EXACT": (
        "CONFIRM_EQUIVALENT",
        "PRESERVE_VARIANTS",
        "AMBIGUOUS",
        "ABSTAIN",
    ),
    "TEXT_LINE_ENDING_EQUIVALENT": (
        "CONFIRM_EQUIVALENT",
        "PRESERVE_VARIANTS",
        "AMBIGUOUS",
        "ABSTAIN",
    ),
    "TEXT_DIFFERENT": (
        "SELECT_A",
        "SELECT_B",
        "PRESERVE_VARIANTS",
        "AMBIGUOUS",
        "ABSTAIN",
    ),
}


class TavernReviewPackageError(ValueError):
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
        raise TavernReviewPackageError("TAVERN archive must have exactly one top-level root")
    root = next(iter(roots))
    if not root.startswith("TAVERN-"):
        raise TavernReviewPackageError(f"unexpected TAVERN archive root: {root}")
    return root


def _logical_path(name: str, root: str) -> str:
    path = PurePosixPath(name.replace("\\", "/"))
    if not path.parts or path.parts[0] != root:
        raise TavernReviewPackageError(f"member outside TAVERN root: {name}")
    if len(path.parts) == 1:
        return ""
    return PurePosixPath(*path.parts[1:]).as_posix()


def _read_member_bounded(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    if info.file_size > MAX_ANALYSIS_MEMBER_BYTES:
        raise IngestSecurityError(f"analysis member exceeds review limit: {info.filename}")
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
                    f"analysis member expanded beyond declared/allowed size: {info.filename}"
                )
            chunks.append(chunk)
    return b"".join(chunks)


def _decode_display_text(data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise TavernReviewPackageError("analysis member must be valid UTF-8") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _canonical_comparison_sha256(comparison: dict[str, object]) -> str:
    payload = canonical_ab_comparison_json(comparison).encode("utf-8")
    return _sha256_bytes(payload)


def _validate_comparison_for_review(
    comparison: object,
    *,
    expected_comparison_sha256: str,
    expected_pair_count: int,
) -> dict[str, object]:
    if not isinstance(comparison, dict):
        raise TavernReviewPackageError("comparison evidence must be an object")
    expected_sha = expected_comparison_sha256.strip().lower()
    if not SHA256_RE.fullmatch(expected_sha):
        raise TavernReviewPackageError("expected comparison SHA-256 must be lowercase hex")
    if not isinstance(expected_pair_count, int) or expected_pair_count < 1:
        raise TavernReviewPackageError("expected_pair_count must be a positive integer")

    # Reuse the Stage 0-M validator with an empty human decision set. This keeps
    # review-package admission bound to exactly the same evidence contract that
    # later adjudication will consume.
    observed_sha = _canonical_comparison_sha256(comparison)
    empty_human = {
        "schema_version": ADJUDICATION_INPUT_SCHEMA,
        "source_corpus": "TAVERN",
        "source_revision": PINNED_TAVERN_REVISION,
        "reviewer_type": "HUMAN",
        "reviewer_ref": "stage0n-package-validation",
        "review_session_id": "stage0n-package-validation",
        "comparison_evidence_sha256": observed_sha,
        "decisions": [],
    }
    try:
        build_tavern_adjudication_gate(
            comparison,
            empty_human,
            expected_comparison_sha256=expected_sha,
            expected_pair_count=expected_pair_count,
        )
    except ValueError as exc:
        raise TavernReviewPackageError(str(exc)) from exc
    return comparison


def _collect_analysis_members(
    infos: tuple[zipfile.ZipInfo, ...],
    root: str,
) -> dict[str, dict[str, zipfile.ZipInfo]]:
    analyses: dict[str, dict[str, zipfile.ZipInfo]] = defaultdict(dict)
    for info in infos:
        if info.is_dir():
            continue
        logical = _logical_path(info.filename, root)
        parts = PurePosixPath(logical).parts
        if (
            len(parts) < 5
            or parts[0] not in {"Beethoven", "Mozart"}
            or parts[2] != "Encodings"
            or not parts[3].startswith("Encoder_")
            or not parts[-1].endswith(".krn")
        ):
            continue
        match = ANALYSIS_RE.search(parts[-1])
        if not match:
            raise TavernReviewPackageError(f"unparseable primary analysis filename: {logical}")
        annotator = match.group(3).upper()
        directory_annotator = parts[3].removeprefix("Encoder_").upper()
        if directory_annotator != annotator:
            raise TavernReviewPackageError(f"analysis annotator path/filename mismatch: {logical}")
        if annotator not in DOCUMENTED_ANNOTATORS:
            continue
        work_id = f"{parts[0]}/{parts[1]}"
        phrase_key = f"{work_id}:{match.group(1)}:{match.group(2)}"
        if annotator in analyses[phrase_key]:
            raise TavernReviewPackageError(
                f"duplicate analysis:{annotator} for phrase {phrase_key}"
            )
        analyses[phrase_key][annotator] = info
    return analyses


def _comparison_records(comparison: dict[str, object]) -> list[dict[str, Any]]:
    raw_records = comparison.get("comparisons")
    if not isinstance(raw_records, list):
        raise TavernReviewPackageError("comparison records missing")
    records: list[dict[str, Any]] = []
    for item in raw_records:
        if not isinstance(item, dict):
            raise TavernReviewPackageError("comparison record must be an object")
        phrase_key = item.get("phrase_key")
        relation = item.get("relation")
        if not isinstance(phrase_key, str) or not PHRASE_KEY_RE.fullmatch(phrase_key):
            raise TavernReviewPackageError(f"unsafe phrase key: {phrase_key!r}")
        if relation not in DECISIONS_BY_RELATION:
            raise TavernReviewPackageError(f"unsupported comparison relation: {relation!r}")
        records.append(item)
    return sorted(records, key=lambda item: item["phrase_key"])


def build_tavern_review_records(
    archive_path: str | Path,
    comparison_evidence: object,
    *,
    expected_raw_archive_sha256: str = PINNED_TAVERN_RAW_SHA256,
    expected_comparison_sha256: str = PINNED_TAVERN_AB_COMPARISON_SHA256,
    expected_pair_count: int = PINNED_TAVERN_AB_PAIR_COUNT,
) -> tuple[list[dict[str, object]], str, str]:
    comparison = _validate_comparison_for_review(
        comparison_evidence,
        expected_comparison_sha256=expected_comparison_sha256,
        expected_pair_count=expected_pair_count,
    )
    expected_raw = expected_raw_archive_sha256.strip().lower()
    if not SHA256_RE.fullmatch(expected_raw):
        raise TavernReviewPackageError("expected raw archive SHA-256 must be lowercase hex")

    archive = Path(archive_path)
    if archive.is_symlink() or not archive.is_file():
        raise TavernReviewPackageError("archive must be a regular non-symlink file")
    observed_raw = _sha256_file(archive)
    if observed_raw != expected_raw:
        raise TavernReviewPackageError(
            f"TAVERN raw archive SHA-256 mismatch: expected {expected_raw}, observed {observed_raw}"
        )

    infos = inspect_zip(archive)
    root = _archive_root(infos)
    logical_names = {
        _logical_path(info.filename, root) for info in infos if not info.is_dir()
    }
    for required in ("README.md", "LICENSE"):
        if required not in logical_names:
            raise TavernReviewPackageError(f"required TAVERN source file missing: {required}")
    analyses = _collect_analysis_members(infos, root)

    records: list[dict[str, object]] = []
    with zipfile.ZipFile(archive) as zf:
        for comparison_record in _comparison_records(comparison):
            phrase_key = comparison_record["phrase_key"]
            members = analyses.get(phrase_key)
            if members is None or not DOCUMENTED_ANNOTATORS.issubset(members):
                raise TavernReviewPackageError(f"A/B members missing for phrase {phrase_key}")
            a_raw = _read_member_bounded(zf, members["A"])
            b_raw = _read_member_bounded(zf, members["B"])
            a_hash = _sha256_bytes(a_raw)
            b_hash = _sha256_bytes(b_raw)
            if a_hash != comparison_record.get("annotator_A_raw_sha256"):
                raise TavernReviewPackageError(f"annotator A hash mismatch for phrase {phrase_key}")
            if b_hash != comparison_record.get("annotator_B_raw_sha256"):
                raise TavernReviewPackageError(f"annotator B hash mismatch for phrase {phrase_key}")
            records.append(
                {
                    "phrase_key": phrase_key,
                    "relation": comparison_record["relation"],
                    "annotator_A_raw_sha256": a_hash,
                    "annotator_B_raw_sha256": b_hash,
                    "annotator_A_text": _decode_display_text(a_raw),
                    "annotator_B_text": _decode_display_text(b_raw),
                    "allowed_decisions": list(
                        DECISIONS_BY_RELATION[comparison_record["relation"]]
                    ),
                }
            )

    if len(records) != expected_pair_count:
        raise TavernReviewPackageError(
            f"review record count mismatch: expected {expected_pair_count}, observed {len(records)}"
        )
    return records, observed_raw, _canonical_comparison_sha256(comparison)


def _batch_html(
    records: list[dict[str, object]],
    *,
    batch_number: int,
    batch_count: int,
    comparison_sha256: str,
) -> str:
    cards: list[str] = []
    metadata: list[dict[str, str]] = []
    for index, record in enumerate(records):
        phrase_key = str(record["phrase_key"])
        relation = str(record["relation"])
        a_hash = str(record["annotator_A_raw_sha256"])
        b_hash = str(record["annotator_B_raw_sha256"])
        allowed = tuple(str(value) for value in record["allowed_decisions"])
        metadata.append(
            {
                "phrase_key": phrase_key,
                "annotator_A_raw_sha256": a_hash,
                "annotator_B_raw_sha256": b_hash,
            }
        )
        options = "".join(
            f'<label><input type="radio" name="decision-{index}" value="{html.escape(decision)}"> '
            f'{html.escape(decision)}</label>'
            for decision in allowed
        )
        cards.append(
            "<section class=\"card\">"
            f"<h2>{html.escape(phrase_key)}</h2>"
            f"<p><strong>Evidence relation:</strong> {html.escape(relation)}</p>"
            "<div class=\"cols\">"
            "<div><h3>Annotator A</h3>"
            f"<p class=\"hash\">SHA-256: {a_hash}</p>"
            f"<pre>{html.escape(str(record['annotator_A_text']), quote=False)}</pre></div>"
            "<div><h3>Annotator B</h3>"
            f"<p class=\"hash\">SHA-256: {b_hash}</p>"
            f"<pre>{html.escape(str(record['annotator_B_text']), quote=False)}</pre></div>"
            "</div>"
            f"<fieldset><legend>Human decision</legend>{options}</fieldset>"
            "</section>"
        )

    metadata_json = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; img-src 'none'; media-src 'none'; object-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TAVERN human review batch {batch_number:03d}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 1.25rem; max-width: 1500px; }}
.notice {{ border: 2px solid currentColor; padding: 1rem; margin-bottom: 1rem; }}
.controls {{ display: grid; grid-template-columns: 1fr 1fr auto; gap: .75rem; align-items: end; margin: 1rem 0; }}
label {{ display: inline-block; margin: .35rem .65rem .35rem 0; }}
input[type=text] {{ width: 100%; padding: .45rem; box-sizing: border-box; }}
button {{ padding: .6rem 1rem; }}
.card {{ border-top: 2px solid #777; padding: 1rem 0 1.5rem; }}
.cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }}
pre {{ white-space: pre-wrap; overflow-wrap: anywhere; border: 1px solid #aaa; padding: .75rem; max-height: 28rem; overflow: auto; }}
.hash {{ font-family: monospace; overflow-wrap: anywhere; font-size: .82rem; }}
fieldset {{ margin-top: .75rem; }}
@media (max-width: 800px) {{ .cols, .controls {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<h1>TAVERN Stage 0-N human review — batch {batch_number:03d}/{batch_count:03d}</h1>
<div class="notice"><strong>Human-only boundary.</strong> No option is preselected. Text equality is not consensus. Exported decisions remain evidence-only and do not authorize gold, partitioning, or training.</div>
<p>Source: TAVERN revision <code>{PINNED_TAVERN_REVISION}</code>, CC BY-SA 4.0. Comparison evidence SHA-256: <code>{comparison_sha256}</code>.</p>
<div class="controls">
<label>Reviewer reference (opaque ID)<input id="reviewer" type="text" autocomplete="off"></label>
<label>Review session ID<input id="session" type="text" value="tavern-stage0n-batch-{batch_number:03d}" autocomplete="off"></label>
<button id="export" type="button">Export decisions JSON</button>
</div>
<div id="status" role="status"></div>
{''.join(cards)}
<script type="application/json" id="review-metadata">{metadata_json}</script>
<script>
(() => {{
  'use strict';
  const metadata = JSON.parse(document.getElementById('review-metadata').textContent);
  const reviewer = document.getElementById('reviewer');
  const session = document.getElementById('session');
  const status = document.getElementById('status');
  document.getElementById('export').addEventListener('click', () => {{
    const reviewerRef = reviewer.value.trim();
    const sessionId = session.value.trim();
    if (!reviewerRef || !sessionId) {{
      status.textContent = 'Reviewer reference and review session ID are required.';
      return;
    }}
    const decisions = [];
    metadata.forEach((item, index) => {{
      const selected = document.querySelector(`input[name="decision-${{index}}"]:checked`);
      if (selected) {{
        decisions.push({{
          phrase_key: item.phrase_key,
          decision: selected.value,
          annotator_A_raw_sha256: item.annotator_A_raw_sha256,
          annotator_B_raw_sha256: item.annotator_B_raw_sha256,
        }});
      }}
    }});
    const payload = {{
      schema_version: '{ADJUDICATION_INPUT_SCHEMA}',
      source_corpus: 'TAVERN',
      source_revision: '{PINNED_TAVERN_REVISION}',
      reviewer_type: 'HUMAN',
      reviewer_ref: reviewerRef,
      review_session_id: sessionId,
      comparison_evidence_sha256: '{comparison_sha256}',
      decisions,
    }};
    const blob = new Blob([JSON.stringify(payload, null, 2) + '\\n'], {{type: 'application/json'}});
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'stage0m_adjudication_batch_{batch_number:03d}.json';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    status.textContent = `Exported ${{decisions.length}} decision(s). Undecided items remain pending.`;
  }});
}})();
</script>
</body>
</html>
"""


def _index_html(manifest: dict[str, object]) -> str:
    links = "".join(
        f'<li><a href="{html.escape(str(batch["filename"]))}">Batch {batch["batch_number"]:03d}</a> '
        f'— {batch["record_count"]} records</li>'
        for batch in manifest["batches"]
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>TAVERN human review package</title>
<style>body{{font-family:system-ui,sans-serif;max-width:900px;margin:2rem}}code{{overflow-wrap:anywhere}}</style></head>
<body><h1>TAVERN Stage 0-N human review package</h1>
<p><strong>Evidence-only.</strong> This package never assigns teacher gold and never authorizes partitioning or training.</p>
<p>Source revision: <code>{manifest['source_revision']}</code><br>Raw archive SHA-256: <code>{manifest['raw_archive_sha256']}</code><br>Comparison evidence SHA-256: <code>{manifest['comparison_evidence_sha256']}</code></p>
<p>Source license: CC BY-SA 4.0. Upstream: <code>https://github.com/jcdevaney/TAVERN</code>.</p>
<p>Open one batch at a time, enter an opaque reviewer reference, choose only decisions you actually reviewed, and export the JSON. Unselected items remain pending.</p>
<ol>{links}</ol>
</body></html>"""


def _ensure_output_directory(output_dir: Path) -> None:
    if output_dir.is_symlink():
        raise TavernReviewPackageError("symlink output directory rejected")
    if output_dir.exists():
        if not output_dir.is_dir():
            raise TavernReviewPackageError("output path must be a directory")
        if any(output_dir.iterdir()):
            raise TavernReviewPackageError("output directory must be empty")
    else:
        output_dir.mkdir(parents=True, exist_ok=False)


def write_tavern_review_package(
    archive_path: str | Path,
    comparison_evidence: object,
    output_dir: str | Path,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    expected_raw_archive_sha256: str = PINNED_TAVERN_RAW_SHA256,
    expected_comparison_sha256: str = PINNED_TAVERN_AB_COMPARISON_SHA256,
    expected_pair_count: int = PINNED_TAVERN_AB_PAIR_COUNT,
) -> dict[str, object]:
    if not isinstance(batch_size, int) or not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise TavernReviewPackageError(
            f"batch_size must be an integer from 1 through {MAX_BATCH_SIZE}"
        )
    output = Path(output_dir)
    _ensure_output_directory(output)
    try:
        records, raw_sha, comparison_sha = build_tavern_review_records(
            archive_path,
            comparison_evidence,
            expected_raw_archive_sha256=expected_raw_archive_sha256,
            expected_comparison_sha256=expected_comparison_sha256,
            expected_pair_count=expected_pair_count,
        )
        batch_count = math.ceil(len(records) / batch_size)
        batches: list[dict[str, object]] = []
        relation_counts: Counter[str] = Counter(str(item["relation"]) for item in records)
        for batch_index in range(batch_count):
            start = batch_index * batch_size
            batch_records = records[start : start + batch_size]
            filename = f"batch-{batch_index + 1:03d}.html"
            payload = _batch_html(
                batch_records,
                batch_number=batch_index + 1,
                batch_count=batch_count,
                comparison_sha256=comparison_sha,
            ).encode("utf-8")
            (output / filename).write_bytes(payload)
            batches.append(
                {
                    "batch_number": batch_index + 1,
                    "filename": filename,
                    "record_count": len(batch_records),
                    "sha256": _sha256_bytes(payload),
                }
            )

        manifest: dict[str, object] = {
            "schema_version": REVIEW_MANIFEST_SCHEMA,
            "source_corpus": "TAVERN",
            "source_revision": PINNED_TAVERN_REVISION,
            "source_url": "https://github.com/jcdevaney/TAVERN",
            "license_id": "CC-BY-SA-4.0",
            "raw_archive_sha256": raw_sha,
            "comparison_evidence_sha256": comparison_sha,
            "pair_count": len(records),
            "relation_counts": {key: relation_counts[key] for key in sorted(relation_counts)},
            "batch_size": batch_size,
            "batch_count": batch_count,
            "batches": batches,
            "raw_annotation_text_in_ephemeral_package": True,
            "raw_annotation_text_committed": False,
            "decisions_preselected": False,
            "gold_assignment_authorized": False,
            "partition_assignment_authorized": False,
            "training_authorized": False,
        }
        index_payload = _index_html(manifest).encode("utf-8")
        (output / "index.html").write_bytes(index_payload)
        manifest["index_sha256"] = _sha256_bytes(index_payload)
        manifest_payload = (
            json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n"
        ).encode("utf-8")
        (output / "manifest.json").write_bytes(manifest_payload)
        return manifest
    except Exception:
        # Never leave a half-built review package that could be mistaken for a
        # validated human-review artifact.
        shutil.rmtree(output, ignore_errors=True)
        raise


def write_tavern_review_package_from_files(
    archive_path: str | Path,
    comparison_path: str | Path,
    output_dir: str | Path,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, object]:
    return write_tavern_review_package(
        archive_path,
        load_bounded_json(comparison_path),
        output_dir,
        batch_size=batch_size,
    )
