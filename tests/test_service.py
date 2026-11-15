"""Verifiche di contratto e telemetria del servizio, se FastAPI è installato."""

from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


try:
    from lab13.service import create_app
except ImportError:
    create_app = None


@unittest.skipIf(create_app is None, "FastAPI non installato")
class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        fake_model = SimpleNamespace(
            version="v-test",
            run_id="test-run",
            artifact_sha256="test-hash",
            pipeline=SimpleNamespace(predict=lambda rows: [1]),
        )
        self.app = create_app(loaded_model=fake_model)

    def test_app_registers_observability_and_inference_routes(self) -> None:
        paths = {route.path for route in self.app.routes}
        self.assertTrue({"/health", "/metrics", "/predict"}.issubset(paths))
        self.assertEqual(self.app.state.loaded_model.version, "v-test")


if __name__ == "__main__":
    unittest.main()
