from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import SUMMARY_SCHEMA


class Stage2HSummarySchemaTests(unittest.TestCase):
    def test_summary_schema_is_frozen(self) -> None:
        self.assertEqual(SUMMARY_SCHEMA, "st-stage2h-function-event-grouped-cv-summary-v1")


if __name__ == "__main__":
    unittest.main()
