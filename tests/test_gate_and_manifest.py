"""Test del gate congelato e del manifest delle dipendenze."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

GATE_PATH = PROJECT_ROOT / "config" / "gate.json"
REQUIREMENTS_PATH = PROJECT_ROOT / "requirements.txt"


class GatePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gate = json.loads(GATE_PATH.read_text(encoding="utf-8"))

    def test_policy_is_frozen(self) -> None:
        self.assertEqual(self.gate["policy_id"], "lab13-gate-v1")
        self.assertTrue(self.gate["frozen"])

    def test_accuracy_rule(self) -> None:
        accuracy = self.gate["requirements"]["accuracy"]
        self.assertEqual(accuracy["operator"], ">=")
        self.assertEqual(accuracy["threshold_from"], "accuracy_v1")
        self.assertEqual(accuracy["margin"], 0.0)

    def test_latency_threshold(self) -> None:
        latency = self.gate["requirements"]["latency_p95_ms"]
        self.assertEqual(latency["operator"], "<=")
        self.assertEqual(latency["threshold"], 120)
        self.assertEqual(latency["unit"], "ms")

    def test_error_rate_threshold(self) -> None:
        error_rate = self.gate["requirements"]["error_rate"]
        self.assertEqual(error_rate["operator"], "<=")
        self.assertEqual(error_rate["threshold"], 0.01)
        self.assertEqual(error_rate["denominator"], "richieste valide")


class DependencyManifestTests(unittest.TestCase):
    def test_manifest_contains_expected_packages_without_versions(self) -> None:
        content = REQUIREMENTS_PATH.read_text(encoding="utf-8")
        packages = {
            line.strip().lower()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        expected = {
            "numpy",
            "scikit-learn",
            "mlflow",
            "fastapi",
            "pydantic",
            "httpx",
            "uvicorn",
        }
        self.assertEqual(packages, expected)
        self.assertIn("versioni reali", content.lower())
        self.assertIn("docker", content.lower())


if __name__ == "__main__":
    unittest.main()
