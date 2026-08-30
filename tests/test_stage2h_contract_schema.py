from __future__ import annotations

import unittest

from st_harmonic_training.stage2h_function_event_cv import CONTRACT_SCHEMA


class Stage2HContractSchemaTests(unittest.TestCase):
    def test_contract_schema_is_frozen(self) -> None:
        self.assertEqual(CONTRACT_SCHEMA, "st-stage2h-function-event-grouped-cv-contract-v1")


if __name__ == "__main__":
    unittest.main()
