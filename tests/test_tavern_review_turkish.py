from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from st_harmonic_training.tavern_review_turkish import (
    TavernTurkishReviewError,
    localize_score_aware_review_package,
    translate_batch_html_to_turkish,
)


BATCH = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>TAVERN human review batch 001</title>
<style>fieldset { margin-top: .75rem; }</style></head><body>
<h1>TAVERN Stage 0-N human review — batch 001/001</h1>
<div class="notice"><strong>Human-only boundary.</strong> No option is preselected. Text equality is not consensus. Exported decisions remain evidence-only and do not authorize gold, partitioning, or training.</div>
<p>Source: TAVERN revision <code>rev</code>, CC BY-SA 4.0. Comparison evidence SHA-256: <code>abc</code>.</p>
<label>Reviewer reference (opaque ID)<input id="reviewer" type="text"></label>
<label>Review session ID<input id="session" type="text"></label>
<button id="export" type="button">Export decisions JSON</button>
<section class="card"><h2>Beethoven/B063:00:02</h2>
<div class="score-panel"><h3>Reference score phrase</h3><p class="hash">Source: Beethoven/B063/Krn/x.krn</p>
<svg class="score-svg" aria-label="Reference score for Beethoven/B063:00:02"><text>tonic c: · meter 4/4 · key [be-a-]</text><text>Treble</text><text>Bass</text><text>rest</text><text>Score SHA-256: deadbeef · TAVERN **kern pitch/onset rendering; beam/slur engraving simplified for review readability.</text></svg>
<p class="score-note"><strong>Use this score as the musical reference before choosing A or B.</strong> Horizontal spacing is normalized by aligned **kern onset rows; pitches, accidentals, staff assignment, measure boundaries and basic durations are rendered from the pinned score phrase. If visual evidence is unclear, choose AMBIGUOUS or ABSTAIN.</p></div>
<p><strong>Evidence relation:</strong> TEXT_DIFFERENT</p>
<div class="cols"><div><h3>Annotator A</h3><pre>RAW Annotator A Evidence relation: SELECT_A</pre></div><div><h3>Annotator B</h3><pre>RAW Annotator B Human decision SELECT_B</pre></div></div>
<fieldset><legend>Human decision</legend>
<label><input type="radio" name="decision-0" value="SELECT_A"> SELECT_A</label>
<label><input type="radio" name="decision-0" value="SELECT_B"> SELECT_B</label>
<label><input type="radio" name="decision-0" value="PRESERVE_VARIANTS"> PRESERVE_VARIANTS</label>
<label><input type="radio" name="decision-0" value="AMBIGUOUS"> AMBIGUOUS</label>
<label><input type="radio" name="decision-0" value="ABSTAIN"> ABSTAIN</label>
</fieldset></section>
<script>const msg='Reviewer reference and review session ID are required.'; const done=`Exported ${decisions.length} decision(s). Undecided items remain pending.`;</script>
</body></html>'''

INDEX = '''<!doctype html><html lang="en"><head><title>TAVERN human review package</title></head><body>
<h1>TAVERN Stage 0-N1 score-aware human review package</h1>
<p><strong>Evidence-only.</strong> This package never assigns teacher gold and never authorizes partitioning or training.</p>
<p>Source revision: rev<br>Raw archive SHA-256: raw<br>Comparison evidence SHA-256: comp</p>
<p>Source license: CC BY-SA 4.0. Upstream: repo.</p>
<p>Each record includes its pinned TAVERN score phrase above Annotator A/B. Open one batch at a time, enter an opaque reviewer reference, choose only decisions you actually reviewed, and export the JSON. Unselected items remain pending.</p>
<ol><li><a href="batch-001.html">Batch 001</a> — 1 records</li></ol></body></html>'''


class TavernTurkishReviewTests(unittest.TestCase):
    def test_visible_decisions_are_turkish_but_machine_codes_stay_stable(self) -> None:
        translated = translate_batch_html_to_turkish(BATCH)
        self.assertIn("A analizi daha doğru", translated)
        self.assertIn("B analizi daha doğru", translated)
        self.assertIn("Her iki analiz de müzikal olarak geçerli", translated)
        self.assertIn("Belirsiz — kesin karar veremiyorum", translated)
        self.assertIn("Atla — bu kayıt için karar vermiyorum", translated)
        self.assertIn('value="SELECT_A"', translated)
        self.assertIn('value="SELECT_B"', translated)
        self.assertNotIn('> SELECT_A</label>', translated)
        self.assertNotIn('> SELECT_B</label>', translated)

    def test_interface_and_score_reference_are_turkish(self) -> None:
        translated = translate_batch_html_to_turkish(BATCH)
        self.assertIn('<html lang="tr">', translated)
        self.assertIn("Karşılaştırma durumu:</strong> A ve B analizleri farklı", translated)
        self.assertIn("Analiz A", translated)
        self.assertIn("Analiz B", translated)
        self.assertIn("<legend>Kararın</legend>", translated)
        self.assertIn("Referans nota pasajı", translated)
        self.assertIn(">Üst porte<", translated)
        self.assertIn(">Alt porte<", translated)
        self.assertIn(">sus<", translated)
        self.assertIn("tonik c:", translated)
        self.assertIn("ölçü 4/4", translated)
        self.assertIn("donanım [be-a-]", translated)
        self.assertIn("Kararları JSON olarak kaydet", translated)

    def test_raw_annotation_pre_blocks_are_byte_identical(self) -> None:
        translated = translate_batch_html_to_turkish(BATCH)
        self.assertIn("<pre>RAW Annotator A Evidence relation: SELECT_A</pre>", translated)
        self.assertIn("<pre>RAW Annotator B Human decision SELECT_B</pre>", translated)

    def test_preselected_decision_fails_closed(self) -> None:
        bad = BATCH.replace('value="SELECT_A"', 'value="SELECT_A" checked', 1)
        with self.assertRaises(TavernTurkishReviewError):
            translate_batch_html_to_turkish(bad)

    def test_package_rehashes_final_localized_batches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            output = root / "out"
            source.mkdir()
            (source / "batch-001.html").write_text(BATCH, encoding="utf-8")
            (source / "index.html").write_text(INDEX, encoding="utf-8")
            manifest = {
                "schema_version": "st-tavern-human-review-package-v1",
                "pair_count": 1,
                "batch_size": 25,
                "batch_count": 1,
                "batches": [{"batch_number": 1, "filename": "batch-001.html", "record_count": 1, "sha256": "stale"}],
                "index_sha256": "stale",
                "gold_assignment_authorized": False,
                "partition_assignment_authorized": False,
                "training_authorized": False,
            }
            (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = localize_score_aware_review_package(source, output, expected_phrase_count=1)
            actual_batch = hashlib.sha256((output / "batch-001.html").read_bytes()).hexdigest()
            actual_index = hashlib.sha256((output / "index.html").read_bytes()).hexdigest()
            self.assertEqual(result["batches"][0]["sha256"], actual_batch)
            self.assertEqual(result["index_sha256"], actual_index)
            self.assertEqual(result["review_ui_language"], "tr")
            self.assertTrue(result["decision_codes_preserved"])
            self.assertFalse(result["training_authorized"])

    def test_same_input_produces_identical_localized_bytes(self) -> None:
        self.assertEqual(
            translate_batch_html_to_turkish(BATCH).encode("utf-8"),
            translate_batch_html_to_turkish(BATCH).encode("utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
