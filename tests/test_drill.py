"""Test della logica pura del drill S5-S6 (senza avviare il server)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from drill_rollback import (  # noqa: E402
    DrillError,
    _compute_rates,
    check_sequence,
    load_requests,
)


class DrillLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.requests = load_requests(ROOT / "richieste_monitoraggio.csv")

    def test_requests_preserve_assigned_order(self) -> None:
        self.assertEqual(
            [item["request_id"] for item in self.requests],
            ["req_01", "req_02", "req_03", "req_04"],
        )
        self.assertEqual(
            [item["model_version"] for item in self.requests],
            ["v1", "v2", "v1", "v1"],
        )
        self.assertEqual(
            [item["expected_status"] for item in self.requests],
            [200, 200, 200, 422],
        )

    def test_only_last_request_is_incomplete(self) -> None:
        self.assertEqual(
            [item["payload_valid"] for item in self.requests],
            [True, True, True, False],
        )
        self.assertIsNotNone(self.requests[-1]["payload_validation_error"])

    def test_assigned_sequence_is_accepted(self) -> None:
        check_sequence(self.requests)

    def test_wrong_sequence_is_rejected(self) -> None:
        broken = [dict(item) for item in self.requests]
        broken[1]["model_version"] = "v1"
        with self.assertRaises(DrillError):
            check_sequence(broken)

    def test_drill_error_rate_is_computed_on_all_requests(self) -> None:
        results = [
            {"expected_status": 200, "actual_status": 200},
            {"expected_status": 200, "actual_status": 200},
            {"expected_status": 200, "actual_status": 200},
            {"expected_status": 422, "actual_status": 422},
        ]
        drill, valid = _compute_rates(results)
        self.assertEqual(drill["requests"], 4)
        self.assertEqual(drill["http_errors_ge_400"], 1)
        self.assertEqual(drill["value"], 0.25)
        self.assertEqual(valid["requests"], 3)
        self.assertEqual(valid["http_errors_ge_400"], 0)
        self.assertEqual(valid["value"], 0.0)

    def test_valid_request_failure_is_counted(self) -> None:
        results = [
            {"expected_status": 200, "actual_status": 200},
            {"expected_status": 200, "actual_status": 500},
            {"expected_status": 200, "actual_status": 200},
            {"expected_status": 422, "actual_status": 422},
        ]
        drill, valid = _compute_rates(results)
        self.assertEqual(drill["http_errors_ge_400"], 2)
        self.assertEqual(valid["http_errors_ge_400"], 1)


if __name__ == "__main__":
    unittest.main()
