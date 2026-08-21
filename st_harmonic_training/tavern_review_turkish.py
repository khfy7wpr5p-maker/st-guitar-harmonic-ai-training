from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
import re
import shutil

from .tavern_adjudication import PINNED_TAVERN_AB_PAIR_COUNT

TURKISH_REVIEW_SCHEMA = "st-tavern-score-aware-review-tr-v1"
DECISION_LABELS_TR = {
    "CONFIRM_EQUIVALENT": "İki analiz eşdeğer",
    "SELECT_A": "A analizi daha doğru",
    "SELECT_B": "B analizi daha doğru",
    "PRESERVE_VARIANTS": "Her iki analiz de müzikal olarak geçerli",
    "AMBIGUOUS": "Belirsiz — kesin karar veremiyorum",
    "ABSTAIN": "Atla — bu kayıt için karar vermiyorum",
}
RELATION_LABELS_TR = {
    "BYTE_EXACT": "A ve B metni birebir aynı",
    "TEXT_LINE_ENDING_EQUIVALENT": "Yalnız satır sonu biçimi farklı",
    "TEXT_DIFFERENT": "A ve B analizleri farklı",
}

PRE_RE = re.compile(r"<pre>.*?</pre>", re.DOTALL)
SCORE_SVG_RE = re.compile(r"<svg class=\"score-svg\".*?</svg>", re.DOTALL)
RELATION_RE = re.compile(
    r"<p><strong>Evidence relation:</strong> "
    r"(BYTE_EXACT|TEXT_LINE_ENDING_EQUIVALENT|TEXT_DIFFERENT)</p>"
)
RADIO_RE = re.compile(
    r'<label><input type="radio" name="(decision-\d+)" value="'
    r'(CONFIRM_EQUIVALENT|SELECT_A|SELECT_B|PRESERVE_VARIANTS|AMBIGUOUS|ABSTAIN)"'
    r'> (CONFIRM_EQUIVALENT|SELECT_A|SELECT_B|PRESERVE_VARIANTS|AMBIGUOUS|ABSTAIN)</label>'
)
PRESELECTED_RE = re.compile(r'<input\s+[^>]*type="radio"[^>]*\schecked(?:\s|=|>)', re.IGNORECASE)
VALUE_RE = re.compile(
    r'value="(CONFIRM_EQUIVALENT|SELECT_A|SELECT_B|PRESERVE_VARIANTS|AMBIGUOUS|ABSTAIN)"'
)
CARD_RE = re.compile(r'<section class="card"><h2>')
SCORE_PANEL_RE = re.compile(r'<div class="score-panel">')


class TavernTurkishReviewError(ValueError):
    pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _translate_score_svg(match: re.Match[str]) -> str:
    svg = match.group(0)
    replacements = (
        ('aria-label="Reference score for ', 'aria-label="Referans nota pasajı: '),
        (">Treble<", ">Üst porte<"),
        (">Bass<", ">Alt porte<"),
        (">rest<", ">sus<"),
        ("tonic ", "tonik "),
        ("meter ", "ölçü "),
        ("key ", "donanım "),
        ("Score SHA-256:", "Nota SHA-256:"),
        (
            "TAVERN **kern pitch/onset rendering; beam/slur engraving simplified for review readability.",
            "TAVERN **kern perde/başlangıç-zamanı çizimi; bağ ve legato gösterimi inceleme okunabilirliği için sadeleştirilmiştir.",
        ),
        ("SOURCE WARNING:", "KAYNAK UYARISI:"),
        (
            "pinned TAVERN source anomaly: implicit rightmost staff1 spine split",
            "sabitlenmiş TAVERN kaynak anomalisi: en sağdaki üst-porte spine ayrımı kaynakta örtük",
        ),
    )
    for old, new in replacements:
        svg = svg.replace(old, new)
    return svg


def _translate_non_pre_segment(segment: str) -> str:
    segment = SCORE_SVG_RE.sub(_translate_score_svg, segment)

    def relation(match: re.Match[str]) -> str:
        code = match.group(1)
        return (
            "<p><strong>Karşılaştırma durumu:</strong> "
            + html.escape(RELATION_LABELS_TR[code])
            + "</p>"
        )

    segment = RELATION_RE.sub(relation, segment)

    def radio(match: re.Match[str]) -> str:
        name, value, visible = match.groups()
        if value != visible:
            raise TavernTurkishReviewError("decision value/visible-code mismatch")
        label = html.escape(DECISION_LABELS_TR[value])
        return (
            f'<label class="decision-option"><input type="radio" '
            f'name="{name}" value="{value}"> {label}</label>'
        )

    segment = RADIO_RE.sub(radio, segment)

    replacements = (
        ('<html lang="en">', '<html lang="tr">'),
        ("TAVERN human review batch ", "TAVERN insan incelemesi — bölüm "),
        ("TAVERN Stage 0-N human review — batch ", "TAVERN insan incelemesi — bölüm "),
        (
            '<div class="notice"><strong>Human-only boundary.</strong> No option is preselected. Text equality is not consensus. Exported decisions remain evidence-only and do not authorize gold, partitioning, or training.</div>',
            '<div class="notice"><strong>Yalnız insan incelemesi.</strong> Hiçbir seçenek otomatik seçilmemiştir. Metin benzerliği tek başına fikir birliği anlamına gelmez. Kaydedilen kararlar tek başına teacher-gold, veri bölme veya eğitim yetkisi vermez.</div>',
        ),
        ("<p>Source: TAVERN revision ", "<p>Kaynak: TAVERN sürümü "),
        (", CC BY-SA 4.0. Comparison evidence SHA-256: ", ", CC BY-SA 4.0. Karşılaştırma kanıtı SHA-256: "),
        ("Reviewer reference (opaque ID)", "İnceleyen kişi kodu (kişisel bilgi yazmayın)"),
        ("Review session ID", "İnceleme oturumu kimliği"),
        ("Export decisions JSON", "Kararları JSON olarak kaydet"),
        ("Annotator A", "Analiz A"),
        ("Annotator B", "Analiz B"),
        ("<legend>Human decision</legend>", "<legend>Kararın</legend>"),
        ("Reference score phrase", "Referans nota pasajı"),
        ('<p class="hash">Source: ', '<p class="hash">Kaynak: '),
        (
            "<strong>Use this score as the musical reference before choosing A or B.</strong> Horizontal spacing is normalized by aligned **kern onset rows; pitches, accidentals, staff assignment, measure boundaries and basic durations are rendered from the pinned score phrase. If visual evidence is unclear, choose AMBIGUOUS or ABSTAIN.",
            "<strong>A veya B hakkında karar vermeden önce bu notayı müzikal referans olarak kullan.</strong> Yatay yerleşim **kern başlangıç satırlarına göre normalize edilmiştir; perdeler, arızalar, porte atamaları, ölçü sınırları ve temel süreler sabitlenmiş nota pasajından çizilmiştir. Görsel kanıt yeterince açık değilse ‘Belirsiz’ veya ‘Atla’ seçeneğini kullan.",
        ),
        ("Reviewer reference and review session ID are required.", "İnceleyen kişi kodu ve inceleme oturumu kimliği zorunludur."),
        ("Exported ${decisions.length} decision(s). Undecided items remain pending.", "${decisions.length} karar kaydedildi. Seçilmemiş kayıtlar beklemede kaldı."),
    )
    for old, new in replacements:
        segment = segment.replace(old, new)

    style_marker = "fieldset { margin-top: .75rem; }"
    if style_marker in segment:
        segment = segment.replace(
            style_marker,
            style_marker
            + "\n.decision-option { display:block; border:1px solid #aaa; padding:.55rem .7rem; margin:.4rem 0; border-radius:6px; cursor:pointer; }"
            + "\n.decision-option:hover { background:#f3f3f3; }"
            + "\n.decision-option input { margin-right:.45rem; }",
            1,
        )
    return segment


def translate_batch_html_to_turkish(text: str) -> str:
    if PRESELECTED_RE.search(text):
        raise TavernTurkishReviewError("preselected review decision rejected")
    original_pre = PRE_RE.findall(text)
    original_values = VALUE_RE.findall(text)
    if not original_values:
        raise TavernTurkishReviewError("review batch has no decision controls")
    if not SCORE_PANEL_RE.search(text):
        raise TavernTurkishReviewError("review batch has no score reference panels")

    parts: list[str] = []
    position = 0
    for match in PRE_RE.finditer(text):
        parts.append(_translate_non_pre_segment(text[position : match.start()]))
        parts.append(match.group(0))
        position = match.end()
    parts.append(_translate_non_pre_segment(text[position:]))
    translated = "".join(parts)

    if PRE_RE.findall(translated) != original_pre:
        raise TavernTurkishReviewError("raw annotation text changed during localization")
    if VALUE_RE.findall(translated) != original_values:
        raise TavernTurkishReviewError("machine decision codes changed during localization")
    if PRESELECTED_RE.search(translated):
        raise TavernTurkishReviewError("localization introduced a preselected decision")

    visible_only = PRE_RE.sub("", translated)
    if (
        "Evidence relation:" in visible_only
        or "Annotator A" in visible_only
        or "Human decision" in visible_only
    ):
        raise TavernTurkishReviewError("English review UI marker remained after localization")
    for code in DECISION_LABELS_TR:
        if f"> {code}</label>" in visible_only:
            raise TavernTurkishReviewError(
                f"visible decision code remained after localization: {code}"
            )
    return translated


def translate_index_html_to_turkish(text: str) -> str:
    replacements = (
        ('<html lang="en">', '<html lang="tr">'),
        ("TAVERN human review package", "TAVERN insan inceleme paketi"),
        ("TAVERN Stage 0-N1 score-aware human review package", "TAVERN nota-referanslı insan inceleme paketi"),
        ("TAVERN Stage 0-N human review package", "TAVERN insan inceleme paketi"),
        ("<strong>Evidence-only.</strong> This package never assigns teacher gold and never authorizes partitioning or training.", "<strong>Yalnız inceleme kanıtıdır.</strong> Bu paket otomatik teacher-gold atamaz; veri bölme veya eğitim yetkisi vermez."),
        ("Source revision:", "Kaynak sürümü:"),
        ("Raw archive SHA-256:", "Ham arşiv SHA-256:"),
        ("Comparison evidence SHA-256:", "Karşılaştırma kanıtı SHA-256:"),
        ("Source license:", "Kaynak lisansı:"),
        ("Upstream:", "Kaynak depo:"),
        ("Each record includes its pinned TAVERN score phrase above Annotator A/B. Open one batch at a time, enter an opaque reviewer reference, choose only decisions you actually reviewed, and export the JSON. Unselected items remain pending.", "Her kayıtta referans nota pasajı ile Analiz A ve Analiz B birlikte gösterilir. Bölümleri sırayla aç, yalnız gerçekten incelediğin kayıtlar için karar ver ve JSON dosyasını kaydet. Seçilmemiş kayıtlar beklemede kalır."),
        ("Open one batch at a time, enter an opaque reviewer reference, choose only decisions you actually reviewed, and export the JSON. Unselected items remain pending.", "Bölümleri sırayla aç, yalnız gerçekten incelediğin kayıtlar için karar ver ve JSON dosyasını kaydet. Seçilmemiş kayıtlar beklemede kalır."),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    text = re.sub(r">Batch (\d{3})</a> — (\d+) records", r">Bölüm \1</a> — \2 kayıt", text)
    return text


def localize_score_aware_review_package(
    source_dir: str | Path,
    output_dir: str | Path,
    *,
    expected_phrase_count: int = PINNED_TAVERN_AB_PAIR_COUNT,
) -> dict[str, object]:
    source = Path(source_dir)
    output = Path(output_dir)
    if source.is_symlink() or not source.is_dir():
        raise TavernTurkishReviewError("source review package must be a regular directory")
    if output.exists():
        raise TavernTurkishReviewError("localized output directory must not already exist")
    manifest_path = source / "manifest.json"
    index_path = source / "index.html"
    if not manifest_path.is_file() or not index_path.is_file():
        raise TavernTurkishReviewError("source review package is incomplete")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise TavernTurkishReviewError("source manifest must be an object")
    if manifest.get("pair_count") != expected_phrase_count:
        raise TavernTurkishReviewError(
            f"phrase count mismatch: expected {expected_phrase_count}, observed {manifest.get('pair_count')}"
        )
    for field in (
        "gold_assignment_authorized",
        "partition_assignment_authorized",
        "training_authorized",
    ):
        if manifest.get(field) is not False:
            raise TavernTurkishReviewError(f"review authority must remain false: {field}")

    batches = sorted(source.glob("batch-*.html"))
    if not batches:
        raise TavernTurkishReviewError("source review package has no batches")
    observed_cards = 0
    observed_scores = 0
    try:
        output.mkdir(parents=True, exist_ok=False)
        localized_batches: list[dict[str, object]] = []
        for batch_number, source_batch in enumerate(batches, start=1):
            original = source_batch.read_text(encoding="utf-8")
            cards = len(CARD_RE.findall(original))
            scores = len(SCORE_PANEL_RE.findall(original))
            if cards < 1 or scores != cards:
                raise TavernTurkishReviewError(
                    f"score/card mismatch in {source_batch.name}: {scores} != {cards}"
                )
            observed_cards += cards
            observed_scores += scores
            translated = translate_batch_html_to_turkish(original)
            payload = translated.encode("utf-8")
            target = output / source_batch.name
            target.write_bytes(payload)
            localized_batches.append(
                {
                    "batch_number": batch_number,
                    "filename": source_batch.name,
                    "record_count": cards,
                    "sha256": _sha256_bytes(payload),
                }
            )

        if observed_cards != expected_phrase_count or observed_scores != expected_phrase_count:
            raise TavernTurkishReviewError(
                f"localized phrase coverage mismatch: cards={observed_cards}, scores={observed_scores}"
            )

        index_payload = translate_index_html_to_turkish(
            index_path.read_text(encoding="utf-8")
        ).encode("utf-8")
        (output / "index.html").write_bytes(index_payload)

        final_manifest = dict(manifest)
        final_manifest.update(
            {
                "schema_version": TURKISH_REVIEW_SCHEMA,
                "review_ui_language": "tr",
                "score_aware": True,
                "decision_codes_preserved": True,
                "visible_decision_labels_localized": True,
                "decisions_preselected": False,
                "pair_count": observed_cards,
                "batch_count": len(localized_batches),
                "batches": localized_batches,
                "index_sha256": _sha256_bytes(index_payload),
                "gold_assignment_authorized": False,
                "partition_assignment_authorized": False,
                "training_authorized": False,
            }
        )
        manifest_payload = (
            json.dumps(final_manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n"
        ).encode("utf-8")
        (output / "manifest.json").write_bytes(manifest_payload)
        return final_manifest
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise
