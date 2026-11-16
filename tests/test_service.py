"""Verifiche di contratto e telemetria del servizio, se FastAPI è installato."""

from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


try:
    from fastapi.testclient import TestClient

    from lab13.service import create_app
except ImportError:
    TestClient = None
    create_app = None


@unittest.skipIf(create_app is None, "FastAPI non installato")
class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        fake_model = SimpleNamespace(
            version="v-test",
            run_id="test-run",
            artifact_sha256="test-hash",
            dataset_sha256="dataset-hash",
            metadata={"dataset": {"sha256_canonical": "canonical-hash"}},
            pipeline=SimpleNamespace(predict=lambda rows: [1]),
        )
        self.app = create_app(loaded_model=fake_model)

    def test_app_registers_observability_and_inference_routes(self) -> None:
        paths = {route.path for route in self.app.routes}
        self.assertTrue({"/health", "/metrics", "/predict"}.issubset(paths))
        self.assertEqual(self.app.state.loaded_model.version, "v-test")

    def test_version_switch_is_disabled_by_default(self) -> None:
        with TestClient(self.app) as client:
            response = client.post(
                "/admin/version", json={"version": "v2", "action": "activate"}
            )
        self.assertEqual(response.status_code, 404)

    def test_enabled_version_switch_validates_action(self) -> None:
        app = create_app(
            loaded_model=self.app.state.loaded_model,
            allow_version_switch=True,
        )
        with TestClient(app) as client:
            response = client.post(
                "/admin/version", json={"version": "v2", "action": "deploy"}
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Azione non valida", response.json()["detail"])

    def test_health_reports_loaded_model_and_fingerprints(self) -> None:
        with TestClient(self.app) as client:
            response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["active_version"], "v-test")
        self.assertEqual(body["run_id"], "test-run")
        self.assertEqual(body["dataset_sha256"], "dataset-hash")
        self.assertEqual(body["dataset_sha256_canonical"], "canonical-hash")


if __name__ == "__main__":
    unittest.main()
