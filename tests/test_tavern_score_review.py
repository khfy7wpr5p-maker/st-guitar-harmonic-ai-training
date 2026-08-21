from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from st_harmonic_training.tavern_score_review import (
    PINNED_IMPLICIT_SPLIT_PHRASES,
    TavernScoreReviewError,
    enrich_review_package_with_scores,
    parse_kern_for_review,
)


PHRASE = "Beethoven/B063:00:01"
SCORE = """**kern\t**kern
*staff2\t*staff1
*clefF4\t*clefG2
*k[b-e-a-]\t*k[b-e-a-]
*M4/4\t*M4/4
*c:\t*c:
=-\t=-
2C 2E- 2G\t4cc
.\t4b-
=2\t=2
2G\t2dd
*-\t*-
"""


class TavernScoreReviewTests(unittest.TestCase):
    def make_archive(self, root: Path, *, score: str = SCORE, include_score: bool = True) -> Path:
        path = root / "TAVERN.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("TAVERN-fixture/README.md", "fixture")
            zf.writestr("TAVERN-fixture/LICENSE", "fixture")
            if include_score:
                zf.writestr(
                    "TAVERN-fixture/Beethoven/B063/Krn/B063_00_01_score.krn",
                    score,
                )
        return path

    def make_source(self, root: Path, *, phrase: str = PHRASE, preselected: bool = False) -> Path:
        source = root / "source"
        source.mkdir()
        (source / "index.html").write_text(
            "<h1>Stage 0-N human review package</h1><p>Open one batch at a time, review.</p>",
            encoding="utf-8",
        )
        checked = " checked" if preselected else ""
        # The export script legitimately reads .checked. This must not be mistaken for a preselected radio.
        batch = f'''<!doctype html><style>.card {{ border-top: 2px solid #777; padding: 1rem 0 1.5rem; }}</style>
<section class="card"><h2>{phrase}</h2>
<div class="cols"><pre>Annotator A</pre><pre>Annotator B</pre></div>
<input type="radio" name="decision-0" value="SELECT_A"{checked}>
<script>const chosen = document.querySelector("input:checked"); if (chosen) console.log(chosen.checked);</script>
</section>'''
        (source / "batch-001.html").write_text(batch, encoding="utf-8")
        return source

    def digest(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_score_is_injected_without_preselecting_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self.make_archive(root)
            source = self.make_source(root)
            output = root / "out"
            summary = enrich_review_package_with_scores(
                source,
                output,
                archive,
                expected_raw_archive_sha256=self.digest(archive),
                expected_phrase_count=1,
            )
            page = (output / "batch-001.html").read_text(encoding="utf-8")
            self.assertIn("Reference score phrase", page)
            self.assertIn('<svg class="score-svg"', page)
            self.assertIn("Treble", page)
            self.assertIn("Bass", page)
            self.assertNotIn('value="SELECT_A" checked', page)
            self.assertEqual(summary["phrase_count"], 1)
            self.assertEqual(summary["score_count"], 1)
            self.assertFalse(summary["gold_assignment_authorized"])
            self.assertFalse(summary["partition_assignment_authorized"])
            self.assertFalse(summary["training_authorized"])

    def test_legitimate_checked_javascript_is_not_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self.make_archive(root)
            source = self.make_source(root)
            output = root / "out"
            enrich_review_package_with_scores(
                source, output, archive,
                expected_raw_archive_sha256=self.digest(archive),
                expected_phrase_count=1,
            )
            self.assertTrue((output / "batch-001.html").is_file())

    def test_preselected_radio_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self.make_archive(root)
            source = self.make_source(root, preselected=True)
            output = root / "out"
            with self.assertRaises(TavernScoreReviewError):
                enrich_review_package_with_scores(
                    source, output, archive,
                    expected_raw_archive_sha256=self.digest(archive),
                    expected_phrase_count=1,
                )
            self.assertFalse(output.exists())

    def test_score_comments_cannot_inject_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            malicious = "!!<script>alert(1)</script>\n" + SCORE
            archive = self.make_archive(root, score=malicious)
            source = self.make_source(root)
            output = root / "out"
            enrich_review_package_with_scores(
                source, output, archive,
                expected_raw_archive_sha256=self.digest(archive),
                expected_phrase_count=1,
            )
            page = (output / "batch-001.html").read_text(encoding="utf-8")
            self.assertNotIn("alert(1)", page)

    def test_missing_score_fails_closed_and_cleans_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self.make_archive(root, include_score=False)
            source = self.make_source(root)
            output = root / "out"
            with self.assertRaises(TavernScoreReviewError):
                enrich_review_package_with_scores(
                    source, output, archive,
                    expected_raw_archive_sha256=self.digest(archive),
                    expected_phrase_count=1,
                )
            self.assertFalse(output.exists())

    def test_wrong_archive_hash_fails_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self.make_archive(root)
            source = self.make_source(root)
            output = root / "out"
            with self.assertRaises(TavernScoreReviewError):
                enrich_review_package_with_scores(
                    source, output, archive,
                    expected_raw_archive_sha256="0" * 64,
                    expected_phrase_count=1,
                )
            self.assertFalse(output.exists())

    def test_unexpected_spine_mismatch_fails_closed(self) -> None:
        bad = "**kern\t**kern\n*staff2\t*staff1\n4C\t4c\t8g\n*-\t*-\n"
        with self.assertRaises(TavernScoreReviewError):
            parse_kern_for_review(bad, PHRASE)

    def test_only_pinned_implicit_split_is_allowed(self) -> None:
        phrase = next(iter(PINNED_IMPLICIT_SPLIT_PHRASES))
        anomalous = "**kern\t**kern\n*staff2\t*staff1\n4C\t4c\t8g\n*\t*v\t*v\n*-\t*-\n"
        parsed = parse_kern_for_review(anomalous, phrase)
        self.assertEqual(len(parsed["warnings"]), 1)
        with self.assertRaises(TavernScoreReviewError):
            parse_kern_for_review(anomalous, PHRASE)

    def test_same_inputs_produce_identical_batch_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self.make_archive(root)
            source = self.make_source(root)
            kwargs = {
                "expected_raw_archive_sha256": self.digest(archive),
                "expected_phrase_count": 1,
            }
            left, right = root / "left", root / "right"
            enrich_review_package_with_scores(source, left, archive, **kwargs)
            enrich_review_package_with_scores(source, right, archive, **kwargs)
            self.assertEqual(
                (left / "batch-001.html").read_bytes(),
                (right / "batch-001.html").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
