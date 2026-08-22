from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from st_harmonic_training.tavern_review_diff import (
    DIFF_SCHEMA,
    TavernReviewDiffError,
    build_difference_panel,
    enhance_review_html,
    enhance_review_package,
    parse_tavern_analysis,
)


A = """!!!COM: Beethoven
**chords\t**function\t**comments
*M4/4\t*M4/4\t*M4/4
*c:\t*c:\t*c:
=1\t=1\t=1
2I6/III\tT\tm
2V42/III\t.\tm
8ii6/III\tP\tm
4C64/III\tD\tm
4V/III\t.\tm
*-\t*-\t*-
"""

B = """!!!COM: Beethoven
**chords\t**function\t**comments
*M4/4\t*M4/4\t*M4/4
*Eb:\t*Eb:\t*Eb:
=1\t=1\t=1
2I6\tT\t/III
2V2\t.\t/III
8ii6\tPD\t/III
4C64\tD\t/III
4V7\t.\t/III
*-\t*-\t*-
"""


def batch_html(a: str = A, b: str = B) -> str:
    return f'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><style></style></head><body>
<section class="card"><h2>Beethoven/B063:06:02</h2>
<div class="score-panel"><h3>Referans nota pasajı</h3><svg class="score-svg"></svg></div>
<p><strong>Karşılaştırma durumu:</strong> A ve B analizleri farklı</p>
<div class="cols"><div><h3>Analiz A</h3><pre>{a}</pre></div><div><h3>Analiz B</h3><pre>{b}</pre></div></div>
<fieldset><legend>Kararın</legend>
<label><input type="radio" name="decision-0" value="SELECT_A"> A analizi daha doğru</label>
<label><input type="radio" name="decision-0" value="SELECT_B"> B analizi daha doğru</label>
<label><input type="radio" name="decision-0" value="PRESERVE_VARIANTS"> Her iki analiz de müzikal olarak geçerli</label>
<label><input type="radio" name="decision-0" value="AMBIGUOUS"> Belirsiz</label>
<label><input type="radio" name="decision-0" value="ABSTAIN"> Atla</label>
</fieldset></section><script>const stable='SELECT_A';</script></body></html>'''


INDEX = '<!doctype html><html lang="tr"><head></head><body><h1>TAVERN Türkçe inceleme</h1></body></html>'


class TavernReviewDiffTests(unittest.TestCase):
    def test_documented_function_symbols_get_source_bounded_turkish_help(self) -> None:
        panel, count = build_difference_panel(A, B)
        self.assertGreater(count, 0)
        self.assertIn("Tonik işlevi", panel)
        self.assertIn("Ön-dominant işlevi", panel)
        self.assertIn("Dominant işlevi", panel)
        self.assertIn("A ve B “cevap anahtarı” değildir", panel)

    def test_undocumented_pd_is_not_auto_equated_with_p(self) -> None:
        panel, _ = build_difference_panel(A, B)
        self.assertIn("P/PD olarak farklı", panel)
        self.assertIn("otomatik eşdeğer sayılmadı", panel)
        self.assertIn("PD", panel)

    def test_slash_context_moved_between_columns_is_only_surfaced(self) -> None:
        panel, _ = build_difference_panel(A, B)
        self.assertIn("/III", panel)
        self.assertIn("farklı sütunlarda", panel)
        self.assertIn("otomatik olarak müzikal eşdeğer kabul edilmedi", panel)

    def test_raw_pre_blocks_and_machine_codes_are_preserved(self) -> None:
        source = batch_html()
        enhanced, cards, _ = enhance_review_html(source)
        self.assertEqual(cards, 1)
        self.assertIn(f"<pre>{A}</pre>", enhanced)
        self.assertIn(f"<pre>{B}</pre>", enhanced)
        self.assertIn('value="SELECT_A"', enhanced)
        self.assertIn('value="SELECT_B"', enhanced)
        self.assertIn("Ham TAVERN analizlerini göster", enhanced)

    def test_derived_diff_panel_escapes_untrusted_raw_tokens(self) -> None:
        malicious = B.replace("/III", "&lt;img src=x onerror=alert(1)&gt;", 1)
        enhanced, _, _ = enhance_review_html(batch_html(b=malicious))
        diff_panel = enhanced.split('<details class="raw-analysis">', 1)[0]
        self.assertNotIn("<img src=x onerror=alert(1)>", diff_panel)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", diff_panel)

    def test_preselected_decision_fails_closed(self) -> None:
        bad = batch_html().replace('value="SELECT_A"', 'value="SELECT_A" checked', 1)
        with self.assertRaises(TavernReviewDiffError):
            enhance_review_html(bad)

    def test_missing_analysis_columns_fail_closed(self) -> None:
        with self.assertRaises(TavernReviewDiffError):
            parse_tavern_analysis("**foo\t**bar\nx\ty\n")

    def test_same_html_is_deterministic(self) -> None:
        first = enhance_review_html(batch_html())
        second = enhance_review_html(batch_html())
        self.assertEqual(first, second)

    def test_package_rehashes_and_keeps_authority_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            output = root / "output"
            source.mkdir()
            (source / "batch-001.html").write_text(batch_html(), encoding="utf-8")
            (source / "index.html").write_text(INDEX, encoding="utf-8")
            manifest = {
                "schema_version": "st-tavern-score-aware-review-tr-v1",
                "review_ui_language": "tr",
                "pair_count": 1,
                "batch_count": 1,
                "batch_size": 25,
                "batches": [{"batch_number": 1, "filename": "batch-001.html", "record_count": 1, "sha256": "stale"}],
                "index_sha256": "stale",
                "decisions_preselected": False,
                "gold_assignment_authorized": False,
                "partition_assignment_authorized": False,
                "training_authorized": False,
            }
            (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = enhance_review_package(source, output, expected_pair_count=1)
            self.assertEqual(result["schema_version"], DIFF_SCHEMA)
            self.assertEqual(result["semantic_glossary_policy"], "SOURCE_DOCUMENTED_ONLY")
            self.assertFalse(result["undocumented_function_tokens_interpreted"])
            self.assertFalse(result["gold_assignment_authorized"])
            self.assertFalse(result["partition_assignment_authorized"])
            self.assertFalse(result["training_authorized"])
            self.assertEqual(result["batches"][0]["sha256"], hashlib.sha256((output / "batch-001.html").read_bytes()).hexdigest())
            self.assertEqual(result["index_sha256"], hashlib.sha256((output / "index.html").read_bytes()).hexdigest())

    def test_existing_output_directory_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            output = root / "output"
            source.mkdir()
            output.mkdir()
            with self.assertRaises(TavernReviewDiffError):
                enhance_review_package(source, output, expected_pair_count=1)


if __name__ == "__main__":
    unittest.main()
