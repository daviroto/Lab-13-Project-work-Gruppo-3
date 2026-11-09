"""Test della risoluzione configurabile dei percorsi."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lab13.config import (  # noqa: E402
    DEFAULT_DATASET_PATH,
    DEFAULT_REQUESTS_PATH,
    Settings,
    resolve_input_path,
)


class PathResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.default = self.tmp / "default.csv"
        self.fallback = self.tmp / "fallback.csv"
        self.other = self.tmp / "other.csv"
        self.other.write_text("x", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_project_defaults_use_bundled_input_files(self) -> None:
        self.assertEqual(
            DEFAULT_DATASET_PATH,
            PROJECT_ROOT / "dataset (1).csv",
        )
        self.assertEqual(
            DEFAULT_REQUESTS_PATH,
            PROJECT_ROOT / "richieste_monitoraggio.csv",
        )

    def test_explicit_path_wins_even_if_missing(self) -> None:
        resolved = resolve_input_path(
            explicit=self.other,
            env_var="LAB13_TEST_PATH",
            default_path=self.default,
            local_fallback=self.fallback,
        )
        self.assertEqual(resolved.path, self.other)
        self.assertEqual(resolved.origin, "cli")
        self.assertFalse(resolved.fallback_used)

    def test_environment_wins_over_default(self) -> None:
        self.default.write_text("default", encoding="utf-8")
        self.fallback.write_text("fallback", encoding="utf-8")
        with patch.dict(os.environ, {"LAB13_TEST_PATH": str(self.other)}):
            resolved = resolve_input_path(
                explicit=None,
                env_var="LAB13_TEST_PATH",
                default_path=self.default,
                local_fallback=self.fallback,
            )
        self.assertEqual(resolved.path, self.other)
        self.assertEqual(resolved.origin, "env")
        self.assertEqual(resolved.env_var, "LAB13_TEST_PATH")

    def test_default_wins_when_present(self) -> None:
        self.default.write_text("default", encoding="utf-8")
        self.fallback.write_text("fallback", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LAB13_TEST_PATH", None)
            resolved = resolve_input_path(
                explicit=None,
                env_var="LAB13_TEST_PATH",
                default_path=self.default,
                local_fallback=self.fallback,
            )
        self.assertEqual(resolved.path, self.default)
        self.assertEqual(resolved.origin, "default")
        self.assertFalse(resolved.fallback_used)

    def test_local_fallback_is_explicit(self) -> None:
        self.fallback.write_text("fallback", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LAB13_TEST_PATH", None)
            resolved = resolve_input_path(
                explicit=None,
                env_var="LAB13_TEST_PATH",
                default_path=self.default,
                local_fallback=self.fallback,
            )
        self.assertEqual(resolved.path, self.fallback)
        self.assertEqual(resolved.origin, "local_fallback")
        self.assertTrue(resolved.fallback_used)
        self.assertIn("fallback locale", resolved.origin_label)

    def test_missing_default_has_explicit_origin(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LAB13_TEST_PATH", None)
            resolved = resolve_input_path(
                explicit=None,
                env_var="LAB13_TEST_PATH",
                default_path=self.default,
                local_fallback=self.fallback,
            )
        self.assertEqual(resolved.path, self.default)
        self.assertEqual(resolved.origin, "default_missing")
        self.assertFalse(resolved.fallback_used)

    def test_settings_warns_when_using_local_fallback(self) -> None:
        self.fallback.write_text("fallback", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LAB13_TEST_DATASET", None)
            os.environ.pop("LAB13_TEST_REQUESTS", None)
            settings = Settings(
                dataset=resolve_input_path(
                    explicit=None,
                    env_var="LAB13_TEST_DATASET",
                    default_path=self.default,
                    local_fallback=self.fallback,
                ),
                requests=resolve_input_path(
                    explicit=None,
                    env_var="LAB13_TEST_REQUESTS",
                    default_path=self.tmp / "missing_requests.csv",
                    local_fallback=self.tmp / "missing_requests_local.csv",
                ),
            )
        warnings = "\n".join(settings.warnings)
        self.assertIn("dataset: percorso predefinito non trovato", warnings)
        self.assertIn("richieste: file non trovato", warnings)


if __name__ == "__main__":
    unittest.main()
