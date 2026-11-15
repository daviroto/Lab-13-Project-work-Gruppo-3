"""Test puri della logica di decisione S4."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from evaluate_gate import decide  # noqa: E402


class GateDecisionTests(unittest.TestCase):
    def test_missing_measurement_blocks_gate(self) -> None:
        decision, missing = decide(True, None, None, True)
        self.assertEqual(decision, "BLOCCATO")
        self.assertEqual(len(missing), 2)

    def test_measured_threshold_failure_does_not_pass(self) -> None:
        decision, missing = decide(True, False, True, True)
        self.assertEqual(decision, "NON SUPERATO")
        self.assertEqual(missing, [])

    def test_incomparable_models_block_gate(self) -> None:
        decision, missing = decide(True, True, True, False)
        self.assertEqual(decision, "BLOCCATO")
        self.assertIn("comparabilità v1/v2 (fingerprint e ID validation)", missing)

    def test_all_frozen_criteria_pass(self) -> None:
        self.assertEqual(decide(True, True, True, True), ("SUPERATO", []))


if __name__ == "__main__":
    unittest.main()
