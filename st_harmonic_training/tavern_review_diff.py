from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import hashlib
import html
import json
import re
import shutil

SOURCE_SCHEMA = "st-tavern-score-aware-review-tr-v1"
DIFF_SCHEMA = "st-tavern-score-aware-review-tr-diff-v1"
MAX_DIFF_ROWS = 12
PRE_RE = re.compile(r"<pre>(.*?)</pre>", re.DOTALL)
RECIP_RE = re.compile(r"^\(?(\d+)(\.*)(.*)$")
KEY_RE = re.compile(r"^\*([A-Ga-g])([#-]*):$")
ROMAN_RE = re.compile(r"(?<![A-Za-z])([#-]*)(VII|VI|IV|III|II|V|I|vii|vi|iv|iii|ii|v|i)(?![A-Za-z])")
SLASH_RE = re.compile(r"(/(?:[#-]?(?:VII|VI|IV|III|II|V|I|vii|vi|iv|iii|ii|v|i))(?:/(?:[#-]?(?:VII|VI|IV|III|II|V|I|vii|vi|iv|iii|ii|v|i)))*)")
PRESELECTED_RE = re.compile(r'<input\s+[^>]*type="radio"[^>]*\schecked(?:\s|=|>)', re.IGNORECASE)
FUNC_DOC = {
    "T": "Tonik işlevi — tonal merkezi kurar; cümle sonunda dönüşü de işaretleyebilir.",
    "P": "Ön-dominant işlevi — dominantın gelişini hazırlar.",
    "D": "Dominant işlevi — tonikle karşıtlık/gerilim kurar ve çözülmeyi hazırlar.",
}
ROMAN_DEGREE = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7,
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7,
}

DIFF_CSS = """
<style id="stage0n3-diff-style">
.diff-guide{border:2px solid #555;border-radius:12px;padding:1rem;margin:1rem 0;background:#fcfcfc}.diff-guide h3{margin-top:0}.expert-note{background:#f3f3f3;padding:.75rem;border-radius:8px}.glossary{margin:.75rem 0}.glossary summary{font-weight:700;cursor:pointer}.glossary li{margin:.35rem 0}.diff-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}.diff-table{width:100%;border-collapse:collapse;min-width:900px;font-size:.9rem}.diff-table th,.diff-table td{border:1px solid #aaa;padding:.55rem;vertical-align:top;text-align:left}.diff-table th{background:#f0f0f0}.diff-table code{white-space:nowrap}.hint{font-size:.85rem;color:#555}.missing{font-style:italic;color:#666}.key-diff{padding:.55rem;background:#f7f7f7}.raw-analysis{margin:1rem 0;border:1px solid #aaa;border-radius:10px;padding:.5rem}.raw-analysis>summary{font-weight:700;cursor:pointer;padding:.45rem}@media(max-width:800px){.diff-guide{padding:.75rem}.diff-table{min-width:760px}}
</style>
"""


class TavernReviewDiffError(ValueError):
    pass


@dataclass(frozen=True)
class Event:
    measure_ord: int
    measure_label: str
    onset: Fraction | None
    row_ord: int
    chord: str
    function: str
    comments: str


@dataclass(frozen=True)
class Analysis:
    key_markers: tuple[str, ...]
    events: tuple[Event, ...]
    headers: tuple[str, ...]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _duration(token: str) -> Fraction | None:
    if not token or token == ".":
        return None
    match = RECIP_RE.match(token.strip())
    if not match:
        return None
    reciprocal = int(match.group(1))
    if reciprocal <= 0:
        return None
    duration = Fraction(4, reciprocal)
    add = duration
    for _ in match.group(2):
        add /= 2
        duration += add
    return duration


def _base_function(token: str) -> str:
    token = token.strip()
    if token in ("", "."):
        return token
    match = RECIP_RE.match(token)
    if match and match.group(3):
        return match.group(3)
    return token


def parse_tavern_analysis(text: str) -> Analysis:
    lines = text.splitlines()
    header_index = None
    headers = None
    for index, line in enumerate(lines):
        if line.startswith("**"):
            header_index = index
            headers = [value.strip() for value in line.split("\t")]
            break
    if header_index is None or headers is None:
        raise TavernReviewDiffError("TAVERN analysis header missing")
    chord_index = next((i for i, value in enumerate(headers) if value in ("**chords", "**harm")), None)
    function_index = next((i for i, value in enumerate(headers) if value in ("**function", "**func")), None)
    comments_index = next((i for i, value in enumerate(headers) if value == "**comments"), None)
    if chord_index is None and function_index is None:
        raise TavernReviewDiffError("TAVERN analysis columns missing")
    used = [i for i in (chord_index, function_index, comments_index) if i is not None]
    max_index = max(used)
    keys: list[str] = []
    events: list[Event] = []
    measure_ord = 0
    measure_label = ""
    onset = Fraction(0)
    row_ord = 0
    for line in lines[header_index + 1 :]:
        parts = line.split("\t")
        if len(parts) <= max_index:
            parts += [""] * (max_index + 1 - len(parts))
        relevant = [parts[i].strip() for i in used]
        for value in relevant:
            if KEY_RE.fullmatch(value) and value not in keys:
                keys.append(value)
        if relevant and all((not value) or value.startswith("=") for value in relevant):
            if any(value.startswith("=") for value in relevant):
                measure_ord += 1
                measure_label = next(value for value in relevant if value.startswith("="))
                onset = Fraction(0)
                row_ord = 0
            continue
        if line.startswith("!") or line.startswith("*"):
            continue
        chord = parts[chord_index].strip() if chord_index is not None else ""
        function = parts[function_index].strip() if function_index is not None else ""
        comments = parts[comments_index].strip() if comments_index is not None else ""
        if all(value in ("", ".", "*-") for value in (chord, function, comments)):
            continue
        row_ord += 1
        duration = _duration(chord) or _duration(function)
        events.append(Event(measure_ord, measure_label, onset if duration is not None else None, row_ord, chord, function, comments))
        if duration is not None:
            onset += duration
    return Analysis(tuple(keys), tuple(events), tuple(headers))


def align_analysis_events(a: Analysis, b: Analysis) -> list[tuple[int, Fraction | None, Event | None, Event | None]]:
    by_a: dict[int, list[Event]] = defaultdict(list)
    by_b: dict[int, list[Event]] = defaultdict(list)
    for event in a.events:
        by_a[event.measure_ord].append(event)
    for event in b.events:
        by_b[event.measure_ord].append(event)
    aligned: list[tuple[int, Fraction | None, Event | None, Event | None]] = []
    for measure in sorted(set(by_a) | set(by_b)):
        aa, bb = by_a[measure], by_b[measure]
        onset_a: dict[Fraction, list[tuple[int, Event]]] = defaultdict(list)
        onset_b: dict[Fraction, list[tuple[int, Event]]] = defaultdict(list)
        for index, event in enumerate(aa):
            if event.onset is not None:
                onset_a[event.onset].append((index, event))
        for index, event in enumerate(bb):
            if event.onset is not None:
                onset_b[event.onset].append((index, event))
        used_a: set[int] = set()
        used_b: set[int] = set()
        for onset in sorted(set(onset_a) & set(onset_b)):
            if len(onset_a[onset]) == 1 and len(onset_b[onset]) == 1:
                ia, ea = onset_a[onset][0]
                ib, eb = onset_b[onset][0]
                used_a.add(ia)
                used_b.add(ib)
                aligned.append((measure, onset, ea, eb))
        remaining_a = [event for i, event in enumerate(aa) if i not in used_a]
        remaining_b = [event for i, event in enumerate(bb) if i not in used_b]
        for index in range(max(len(remaining_a), len(remaining_b))):
            ea = remaining_a[index] if index < len(remaining_a) else None
            eb = remaining_b[index] if index < len(remaining_b) else None
            onset = ea.onset if ea and ea.onset is not None else eb.onset if eb else None
            aligned.append((measure, onset, ea, eb))
    aligned.sort(key=lambda item: (item[0], float(item[1]) if item[1] is not None else 1e12, item[2].row_ord if item[2] else 999999, item[3].row_ord if item[3] else 999999))
    return aligned


def _key_tr(marker: str) -> str:
    match = KEY_RE.fullmatch(marker or "")
    if not match:
        return marker
    note_names = {"C": "Do", "D": "Re", "E": "Mi", "F": "Fa", "G": "Sol", "A": "La", "B": "Si"}
    value = note_names[match.group(1).upper()]
    if match.group(2):
        value += " " + " ".join("diyez" if symbol == "#" else "bemol" for symbol in match.group(2))
    return value + (" majör" if match.group(1).isupper() else " minör")


def _roman_root(chord: str) -> tuple[str, int] | None:
    raw = chord.strip()
    match = RECIP_RE.match(raw)
    if match and match.group(3):
        raw = match.group(3)
    raw = raw.strip("()")
    match = ROMAN_RE.search(raw)
    if not match:
        return None
    numeral = match.group(2)
    degree = ROMAN_DEGREE.get(numeral)
    return (numeral, degree) if degree is not None else None


def _slash_targets(text: str) -> tuple[str, ...]:
    if not text:
        return ()
    return tuple(match.group(1) for match in SLASH_RE.finditer(text))


def _function_explanation(token: str) -> str:
    base = _base_function(token)
    if base in FUNC_DOC:
        return FUNC_DOC[base]
    if base in ("", "."):
        return "Nokta/boş değer: bu satırda yeni işlev etiketi yok; önceki etiket sürüyor olabilir."
    return f"`{base}` işlev etiketi pinned TAVERN 2015 **func tanımındaki T/P/D kümesinde yer almıyor; otomatik Türkçeleştirilmedi."


def _event_cell(event: Event | None) -> str:
    if event is None:
        return '<span class="missing">Bu konumda ayrı analiz olayı yok.</span>'
    bits: list[str] = []
    if event.chord:
        bits.append(f'<strong>Akor:</strong> <code>{html.escape(event.chord)}</code>')
    if event.function:
        bits.append(f'<strong>İşlev:</strong> <code>{html.escape(event.function)}</code><br><span class="hint">{html.escape(_function_explanation(event.function))}</span>')
    if event.comments and event.comments != ".":
        comment = event.comments if len(event.comments) <= 90 else event.comments[:87] + "..."
        bits.append(f'<strong>Yorum:</strong> <code>{html.escape(comment)}</code>')
    return "<br>".join(bits) if bits else '<span class="missing">Etiket yok.</span>'


def _difference_explanation(a: Event | None, b: Event | None) -> str:
    if a is None or b is None:
        return "Annotatörlerden biri bu konumda diğerinde bulunmayan ayrı bir analiz olayı kullanmış."
    parts: list[str] = []
    if a.chord != b.chord:
        root_a, root_b = _roman_root(a.chord), _roman_root(b.chord)
        if root_a and root_b and root_a[1] == root_b[1]:
            parts.append(f"Akor etiketi ayrıntıda farklı; iki etiket de {root_a[1]}. derece köküne işaret ediyor.")
        else:
            parts.append("Akor/Romen rakamı etiketi farklı.")
    function_a, function_b = _base_function(a.function), _base_function(b.function)
    if function_a != function_b:
        if {function_a, function_b} == {"P", "PD"}:
            parts.append("İşlev etiketi P/PD olarak farklı. TAVERN 2015 makalesi P'yi ön-dominant olarak tanımlar; PD aynı **func tanımında listelenmediği için otomatik eşdeğer sayılmadı.")
        else:
            parts.append("İşlev etiketi farklı.")
            known = {"", ".", "T", "P", "D"}
            if function_a not in known or function_b not in known:
                parts.append("T/P/D dışındaki işlev kodu kaynak sözleşmede açıklanmadığından ham bırakıldı.")
    if a.comments != b.comments:
        parts.append("Yorum/bağlam sütunu farklı.")
    chord_a, chord_b = set(_slash_targets(a.chord)), set(_slash_targets(b.chord))
    comments_a, comments_b = set(_slash_targets(a.comments)), set(_slash_targets(b.comments))
    moved = (chord_a & comments_b) | (chord_b & comments_a)
    if moved:
        tokens = ", ".join(sorted(moved))
        parts.append(f"{tokens} bağlam işareti iki anotasyonda farklı sütunlarda görünüyor; bu yalnız gösterim farkı olabilir, fakat otomatik olarak müzikal eşdeğer kabul edilmedi.")
    return " ".join(parts) or "Ham satırlar farklı; otomatik müzikal hüküm verilmedi."


def _position_label(measure: int, a: Event | None, b: Event | None) -> str:
    label = ""
    for event in (a, b):
        if event and event.measure_label:
            digits = re.sub(r"[^0-9]", "", event.measure_label)
            if digits:
                label = f"Ölçü {digits}"
                break
    if not label:
        label = f"Ölçü bölümü {measure if measure else 1}"
    row_a, row_b = a.row_ord if a else None, b.row_ord if b else None
    if row_a == row_b and row_a is not None:
        return f"{label} · olay {row_a}"
    values: list[str] = []
    if row_a is not None:
        values.append(f"A olay {row_a}")
    if row_b is not None:
        values.append(f"B olay {row_b}")
    return label + (" · " + " / ".join(values) if values else "")


def build_difference_panel(a_text: str, b_text: str, *, max_rows: int = MAX_DIFF_ROWS) -> tuple[str, int]:
    if not isinstance(max_rows, int) or not 1 <= max_rows <= 50:
        raise TavernReviewDiffError("max_rows must be an integer from 1 through 50")
    a, b = parse_tavern_analysis(a_text), parse_tavern_analysis(b_text)
    differences: list[tuple[int, Fraction | None, Event | None, Event | None]] = []
    for measure, onset, event_a, event_b in align_analysis_events(a, b):
        value_a = (event_a.chord, event_a.function, event_a.comments) if event_a else None
        value_b = (event_b.chord, event_b.function, event_b.comments) if event_b else None
        if value_a != value_b:
            differences.append((measure, onset, event_a, event_b))
    key_line = ""
    if a.key_markers != b.key_markers:
        key_a = ", ".join(_key_tr(value) for value in a.key_markers) or "açık anahtar etiketi yok"
        key_b = ", ".join(_key_tr(value) for value in b.key_markers) or "açık anahtar etiketi yok"
        key_line = f'<p class="key-diff"><strong>Tonal bağlam etiketi:</strong> A: {html.escape(key_a)} · B: {html.escape(key_b)}. Bu fark otomatik olarak doğru/yanlış sayılmaz.</p>'
    rows: list[str] = []
    for measure, _onset, event_a, event_b in differences[:max_rows]:
        rows.append("<tr>" f"<td>{html.escape(_position_label(measure, event_a, event_b))}</td>" f"<td>{_event_cell(event_a)}</td>" f"<td>{_event_cell(event_b)}</td>" f"<td>{html.escape(_difference_explanation(event_a, event_b))}</td>" "</tr>")
    if not differences:
        body = "<p><strong>Satır düzeyinde fark bulunmadı.</strong> Bu durum otomatik olarak teacher-gold veya consensus anlamına gelmez.</p>"
    else:
        body = (f"<p><strong>{len(differences)} karşılaştırma noktası farklı.</strong> Aşağıdaki hizalama yalnız incelemeyi kolaylaştırır; müzikal karar değildir.</p>" + key_line + '<div class="diff-scroll"><table class="diff-table"><thead><tr><th>Konum</th><th>Analiz A</th><th>Analiz B</th><th>Ne farklı?</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")
        remaining = len(differences) - len(rows)
        if remaining > 0:
            body += f'<p class="hint">İlk {len(rows)} fark gösteriliyor; {remaining} ek fark için alttaki ham TAVERN analizlerini aç.</p>'
    glossary = ('<details class="glossary"><summary>Hızlı TAVERN sözlüğü</summary><ul>'
        '<li><code>T</code> (işlev sütunu): tonik.</li><li><code>P</code> (işlev sütunu): ön-dominant.</li><li><code>D</code> (işlev sütunu): dominant.</li>'
        '<li><code>.</code>: başka bir sütun değişirken önceki etiketin sürdüğünü / yeni etiket olmadığını gösterir.</li>'
        '<li>Romen rakamları <code>I–VII</code>: akor kökünün tonal derece konumunu gösterir.</li>'
        '<li>Akor etiketindeki <code>/</code>: başka bir tonal alan/dereceye göre ikincil ilişkiyi gösterir (ör. <code>V7/ii</code>).</li>'
        '<li><code>PD</code>, <code>A</code> gibi T/P/D dışı işlev kodları bu açıklama katmanında yorumlanmaz; ham değer korunur.</li></ul></details>')
    panel = ('<div class="diff-guide"><h3>A/B fark özeti</h3><p class="expert-note"><strong>A ve B “cevap anahtarı” değildir.</strong> TAVERN çalışmasında iki uzman anotatör bağımsız analiz yapmıştır; anlaşmazlıklar veri setinin beklenen bir parçasıdır. Bu ekran yalnız farkları görünür kılar ve hiçbir tarafı otomatik seçmez.</p>' + glossary + body + "</div>")
    return panel, len(differences)


def _find_matching_div_end(text: str, start: int) -> int:
    tag_re = re.compile(r"<div\b[^>]*>|</div>", re.IGNORECASE)
    depth = 0
    for match in tag_re.finditer(text, start):
        if match.group(0).lower().startswith("<div"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return match.end()
    raise TavernReviewDiffError("unbalanced review HTML div structure")


def enhance_review_html(text: str) -> tuple[str, int, int]:
    original_pre = PRE_RE.findall(text)
    if not original_pre or len(original_pre) % 2:
        raise TavernReviewDiffError("review HTML must contain A/B raw annotation pairs")
    if 'id="stage0n3-diff-style"' in text:
        raise TavernReviewDiffError("review HTML already contains Stage 0-N3 diff layer")
    if PRESELECTED_RE.search(text.split("<script", 1)[0]):
        raise TavernReviewDiffError("preselected human decision rejected")
    if "</head>" not in text:
        raise TavernReviewDiffError("review HTML head terminator missing")
    text = text.replace("</head>", DIFF_CSS + "</head>", 1)
    first_card = text.find('<section class="card">')
    if first_card < 0:
        raise TavernReviewDiffError("review HTML card missing")
    global_note = '<div class="notice"><strong>Okuma yardımı:</strong> A ve B bağımsız uzman analizleridir; hiçbiri otomatik “doğru cevap” değildir. Önce nota ve A/B fark özetini incele; gerekirse ham TAVERN metnini aç.</div>'
    text = text[:first_card] + global_note + text[first_card:]
    position = 0
    pieces: list[str] = []
    card_count = 0
    difference_count = 0
    while True:
        start = text.find('<section class="card">', position)
        if start < 0:
            pieces.append(text[position:])
            break
        pieces.append(text[position:start])
        end = text.find("</section>", start)
        if end < 0:
            raise TavernReviewDiffError("review HTML card terminator missing")
        end += len("</section>")
        card = text[start:end]
        pre = PRE_RE.findall(card)
        if len(pre) != 2:
            raise TavernReviewDiffError("each review card must contain exactly two raw annotation blocks")
        a_text, b_text = html.unescape(pre[0]), html.unescape(pre[1])
        panel, card_differences = build_difference_panel(a_text, b_text)
        columns_start = card.find('<div class="cols">')
        if columns_start < 0:
            raise TavernReviewDiffError("A/B review columns missing")
        columns_end = _find_matching_div_end(card, columns_start)
        columns = card[columns_start:columns_end]
        wrapped = panel + '<details class="raw-analysis"><summary>Ham TAVERN analizlerini göster (ileri seviye)</summary>' + columns + "</details>"
        card = card[:columns_start] + wrapped + card[columns_end:]
        pieces.append(card)
        card_count += 1
        difference_count += card_differences
        position = end
    result = "".join(pieces)
    if PRE_RE.findall(result) != original_pre:
        raise TavernReviewDiffError("raw A/B annotation text changed during diff enhancement")
    if PRESELECTED_RE.search(result.split("<script", 1)[0]):
        raise TavernReviewDiffError("diff enhancement introduced a preselected decision")
    return result, card_count, difference_count


def enhance_review_package(source_dir: str | Path, output_dir: str | Path, *, expected_pair_count: int = 937) -> dict[str, object]:
    source, output = Path(source_dir), Path(output_dir)
    if source.is_symlink() or not source.is_dir():
        raise TavernReviewDiffError("source review package must be a regular directory")
    if output.exists():
        raise TavernReviewDiffError("output directory must not already exist")
    manifest_path = source / "manifest.json"
    if not manifest_path.is_file():
        raise TavernReviewDiffError("source review manifest missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SOURCE_SCHEMA:
        raise TavernReviewDiffError("unexpected source review schema")
    if manifest.get("review_ui_language") != "tr":
        raise TavernReviewDiffError("Stage 0-N3 requires the Turkish Stage 0-N2 package")
    if manifest.get("pair_count") != expected_pair_count:
        raise TavernReviewDiffError("unexpected source pair count")
    if manifest.get("decisions_preselected") is not False:
        raise TavernReviewDiffError("source package contains preselected decisions")
    for field in ("gold_assignment_authorized", "partition_assignment_authorized", "training_authorized"):
        if manifest.get(field) is not False:
            raise TavernReviewDiffError(f"source package must keep {field}=false")
    try:
        shutil.copytree(source, output, symlinks=False)
        total_cards = 0
        total_differences = 0
        batches = []
        for batch in manifest.get("batches", []):
            filename = batch.get("filename")
            if not isinstance(filename, str) or not re.fullmatch(r"batch-\d{3}\.html", filename):
                raise TavernReviewDiffError("unsafe batch filename")
            path = output / filename
            original = path.read_text(encoding="utf-8")
            enhanced, card_count, difference_count = enhance_review_html(original)
            path.write_text(enhanced, encoding="utf-8", newline="\n")
            total_cards += card_count
            total_differences += difference_count
            updated = dict(batch)
            updated["sha256"] = _sha256(path)
            updated["difference_point_count"] = difference_count
            batches.append(updated)
        if total_cards != expected_pair_count:
            raise TavernReviewDiffError(f"diff-enhanced record count mismatch: expected {expected_pair_count}, observed {total_cards}")
        index_path = output / "index.html"
        index_text = index_path.read_text(encoding="utf-8")
        note = '<p><strong>Stage 0-N3:</strong> Her kayıtta nota ile A/B ham analizleri arasına Türkçe, kaynakla sınırlı bir fark özeti eklenmiştir. Özet otomatik müzikal karar vermez.</p>'
        if "<body>" not in index_text:
            raise TavernReviewDiffError("review index body missing")
        index_text = index_text.replace("<body>", "<body>" + note, 1)
        index_path.write_text(index_text, encoding="utf-8", newline="\n")
        manifest["schema_version"] = DIFF_SCHEMA
        manifest["batches"] = batches
        manifest["index_sha256"] = _sha256(index_path)
        manifest["difference_explanations_present"] = True
        manifest["difference_point_count"] = total_differences
        manifest["raw_annotations_preserved"] = True
        manifest["semantic_glossary_policy"] = "SOURCE_DOCUMENTED_ONLY"
        manifest["undocumented_function_tokens_interpreted"] = False
        manifest["decision_codes_preserved"] = True
        manifest["decisions_preselected"] = False
        manifest["gold_assignment_authorized"] = False
        manifest["partition_assignment_authorized"] = False
        manifest["training_authorized"] = False
        (output / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
        return manifest
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise
