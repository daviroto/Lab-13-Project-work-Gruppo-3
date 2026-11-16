"""Test statici degli asset Docker, senza richiedere Docker in esecuzione."""

from __future__ import annotations

import ast
import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = PROJECT_ROOT / "Dockerfile"
DOCKERIGNORE = PROJECT_ROOT / ".dockerignore"
COMPOSE = PROJECT_ROOT / "docker-compose.yml"
SERVING_REQUIREMENTS = PROJECT_ROOT / "requirements-serving.txt"
SMOKE_SCRIPT = PROJECT_ROOT / "scripts" / "docker_smoke_test.py"
METADATA = PROJECT_ROOT / "models" / "v1" / "model_metadata.json"


def _non_comment_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


class DockerfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dockerfile = DOCKERFILE.read_text(encoding="utf-8")
        cls.metadata = json.loads(METADATA.read_text(encoding="utf-8"))

    def test_base_image_matches_artifact_python(self) -> None:
        expected = (
            f"FROM python:{self.metadata['environment']['python']}-slim"
        )
        self.assertIn(expected, self.dockerfile)

    def test_serves_on_port_8000_with_healthcheck(self) -> None:
        self.assertIn("EXPOSE 8000", self.dockerfile)
        self.assertIn("HEALTHCHECK", self.dockerfile)
        self.assertIn("/health", self.dockerfile)
        self.assertIn("lab13.service:app", self.dockerfile)
        self.assertIn("--host\", \"0.0.0.0\"", self.dockerfile)

    def test_runs_as_non_root_user(self) -> None:
        self.assertIn("--uid 10001", self.dockerfile)
        self.assertIn("USER lab13", self.dockerfile)

    def test_copies_runtime_content(self) -> None:
        for name in ("src", "config", "models", "dataset (1).csv"):
            self.assertIn(name, self.dockerfile)

    def test_reports_execute_instructions(self) -> None:
        for name in (
            "PYTHONDONTWRITEBYTECODE=1",
            "PYTHONUNBUFFERED=1",
            "LAB13_ALLOW_VERSION_SWITCH=0",
            "LAB13_REQUEST_LOG=",
        ):
            self.assertIn(name, self.dockerfile)


class ServingRequirementsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lines = _non_comment_lines(SERVING_REQUIREMENTS)
        cls.packages = {}
        for line in cls.lines:
            name, separator, version = line.partition("==")
            if separator:
                cls.packages[name.lower()] = version
        cls.metadata = json.loads(METADATA.read_text(encoding="utf-8"))

    def test_all_lines_are_pinned(self) -> None:
        self.assertTrue(self.lines)
        for line in self.lines:
            self.assertIn("==", line, f"Dipendenza non pinnata: {line}")

    def test_numeric_stack_matches_artifact_metadata(self) -> None:
        expected = self.metadata["environment"]["packages"]
        for package in ("numpy", "scikit-learn", "joblib"):
            self.assertEqual(self.packages.get(package), expected[package])

    def test_mlflow_is_not_in_serving_image(self) -> None:
        self.assertNotIn("mlflow", self.packages)
        self.assertIn("MLflow non è incluso", SERVING_REQUIREMENTS.read_text(encoding="utf-8"))


class ComposeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compose = COMPOSE.read_text(encoding="utf-8")

    def test_service_and_port(self) -> None:
        self.assertIn("name: lab13-progetto3", self.compose)
        self.assertIn("container_name: lab13-progetto3-api", self.compose)
        self.assertIn("127.0.0.1:${LAB13_DOCKER_PORT:-8000}:8000", self.compose)
        self.assertIn("image: lab13-progetto3-api:local", self.compose)

    def test_container_hardening(self) -> None:
        for expected in (
            "read_only: true",
            "no-new-privileges:true",
            "- ALL",
            "LAB13_ALLOW_VERSION_SWITCH: \"0\"",
            "lab13_logs:/app/logs",
        ):
            self.assertIn(expected, self.compose)

    def test_healthcheck_is_declared(self) -> None:
        self.assertIn("healthcheck:", self.compose)
        self.assertIn("http://127.0.0.1:8000/health", self.compose)


class SmokeScriptTests(unittest.TestCase):
    def test_uses_only_standard_library(self) -> None:
        tree = ast.parse(SMOKE_SCRIPT.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
        third_party = imported - set(sys.stdlib_module_names)
        self.assertEqual(third_party, set())

    def test_covers_http_contract_and_evidence(self) -> None:
        content = SMOKE_SCRIPT.read_text(encoding="utf-8")
        for expected in (
            "/health",
            "/metrics",
            "/predict",
            "richieste_monitoraggio.csv",
            "EXPECTED_STATUSES = [200, 200, 200, 422]",
            "reports/docker",
        ):
            self.assertIn(expected, content)


class DockerIgnoreTests(unittest.TestCase):
    def test_context_is_minimal_and_keeps_runtime_inputs(self) -> None:
        entries = set(_non_comment_lines(DOCKERIGNORE))
        for excluded in (".git", "mlruns", "reports", "tests", "__pycache__"):
            self.assertIn(excluded, entries)
        for required in ("dataset (1).csv", "models", "config", "src"):
            self.assertNotIn(required, entries)


if __name__ == "__main__":
    unittest.main()
