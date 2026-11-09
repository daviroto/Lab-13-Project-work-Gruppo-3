"""Test del versionamento e del caricatore con controlli.

Gli artefatti sono scritti in cartelle temporanee con le righe sintetiche di
``_fixtures.py``: ``models/v1`` del progetto non è toccato.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _path in (PROJECT_ROOT / "src", Path(__file__).parent):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

try:
    import joblib

    from _fixtures import write_dataset_csv
    from lab13.contracts import FEATURE_COUNT, FEATURE_NAMES
    from lab13.data import load_dataset, sha256_file
    from lab13.model_io import (
        ARTIFACT_FILENAME,
        METADATA_FILENAME,
        ArtifactConflictError,
        ModelLoadError,
        load_version,
        save_version,
    )
    from lab13.training import BaselineConfig, build_baseline_pipeline, fit_train

    IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover - ambiente senza dipendenze
    IMPORT_ERROR = str(exc)


def _metadata(*, version: str, dataset_sha256: str) -> dict[str, Any]:
    """Metadati minimi con le chiavi che il caricatore pretende."""

    return {
        "version": version,
        "model": {"params": BaselineConfig().params},
        "feature_names": list(FEATURE_NAMES),
        "feature_count": FEATURE_COUNT,
        "classes": {"order": [0, 1], "positive_class": 1},
        "dataset": {"sha256": dataset_sha256},
        "validation": {"ids": ["id_0001"]},
        "artifact": {},
        "mlflow": {"run_id": "run-test-1"},
    }


@unittest.skipUnless(IMPORT_ERROR is None, f"dipendenze mancanti: {IMPORT_ERROR}")
class VersionArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.models = self.tmp / "models"
        self.dataset = load_dataset(write_dataset_csv(self.tmp / "dataset.csv"))
        self.pipeline = fit_train(
            build_baseline_pipeline(BaselineConfig()), self.dataset.train
        )
        self.rows = [
            {"record_id": rid, "target": target, "prediction": 1}
            for rid, target in zip(self.dataset.validation_ids, self.dataset.validation.targets)
        ]

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _save(self, version: str = "v1") -> Any:
        return save_version(
            version=version,
            models_dir=self.models,
            pipeline=self.pipeline,
            metadata=_metadata(version=version, dataset_sha256=self.dataset.sha256),
            prediction_rows=self.rows,
        )

    def test_save_writes_pipeline_metadata_and_predictions(self) -> None:
        saved = self._save()
        self.assertTrue(saved.artifact_path.is_file())
        metadata = json.loads(saved.metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["version"], "v1")
        self.assertEqual(metadata["mlflow"]["run_id"], "run-test-1")
        self.assertEqual(metadata["dataset"]["sha256"], self.dataset.sha256)
        self.assertEqual(metadata["artifact"]["sha256"], saved.artifact_sha256)
        self.assertEqual(metadata["artifact"]["sha256"], sha256_file(saved.artifact_path))
        self.assertEqual(metadata["feature_names"], list(FEATURE_NAMES))
        self.assertEqual(metadata["validation"]["ids"], ["id_0001"])
        self.assertEqual(metadata["model"]["params"]["random_state"], 1303)
        self.assertTrue(saved.predictions_path.is_file())

    def test_loaded_model_is_the_full_pipeline(self) -> None:
        saved = self._save()
        loaded = load_version(
            saved.directory,
            expected_version="v1",
            expected_dataset_sha256=self.dataset.sha256,
        )
        self.assertEqual(loaded.version, "v1")
        self.assertEqual(loaded.run_id, "run-test-1")
        self.assertEqual(loaded.artifact_sha256, saved.artifact_sha256)
        self.assertEqual([name for name, _ in loaded.pipeline.steps], ["scaler", "classifier"])
        self.assertEqual(loaded.pipeline.n_features_in_, FEATURE_COUNT)
        prediction = loaded.pipeline.predict(
            np.asarray(self.dataset.validation.features[:1], dtype=float)
        )
        self.assertIn(int(prediction[0]), (0, 1))

    def test_second_run_does_not_overwrite_the_version(self) -> None:
        saved = self._save()
        before = sha256_file(saved.artifact_path)
        with self.assertRaises(ArtifactConflictError) as caught:
            self._save()
        message = str(caught.exception)
        self.assertIn("esiste già", message)
        self.assertIn("--version", message)
        self.assertIn("--models-dir", message)
        self.assertEqual(sha256_file(saved.artifact_path), before)
        self.assertTrue(saved.metadata_path.is_file())

    def test_metadata_can_be_loaded_with_expected_fingerprint(self) -> None:
        saved = self._save()
        loaded = load_version(
            saved.directory, expected_dataset_sha256=self.dataset.sha256
        )
        self.assertEqual(loaded.dataset_sha256, self.dataset.sha256)

    def test_fingerprint_mismatch_is_named(self) -> None:
        saved = self._save()
        with self.assertRaises(ModelLoadError) as caught:
            load_version(saved.directory, expected_dataset_sha256="0" * 64)
        self.assertIn("Controllo 'fingerprint del dataset'", str(caught.exception))

    def test_missing_expected_fingerprint_is_named(self) -> None:
        saved = self._save()
        with self.assertRaises(ModelLoadError) as caught:
            load_version(saved.directory)
        self.assertIn("fingerprint atteso non fornito", str(caught.exception))

    def test_tampered_artifact_is_named(self) -> None:
        saved = self._save()
        with saved.artifact_path.open("ab") as handle:
            handle.write(b"tampered")
        with self.assertRaises(ModelLoadError) as caught:
            load_version(
                saved.directory, expected_dataset_sha256=self.dataset.sha256
            )
        self.assertIn("Controllo 'hash dell'artefatto'", str(caught.exception))

    def test_feature_order_mismatch_is_named(self) -> None:
        saved = self._save()
        metadata = json.loads(saved.metadata_path.read_text(encoding="utf-8"))
        metadata["feature_names"] = list(reversed(metadata["feature_names"]))
        saved.metadata_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        with self.assertRaises(ModelLoadError) as caught:
            load_version(
                saved.directory, expected_dataset_sha256=self.dataset.sha256
            )
        self.assertIn("Controllo 'schema e ordine feature'", str(caught.exception))

    def test_version_folder_and_metadata_must_agree(self) -> None:
        saved = self._save()
        metadata = json.loads(saved.metadata_path.read_text(encoding="utf-8"))
        metadata["version"] = "v7"
        saved.metadata_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        with self.assertRaises(ModelLoadError) as caught:
            load_version(
                saved.directory, expected_dataset_sha256=self.dataset.sha256
            )
        self.assertIn("Controllo 'versione'", str(caught.exception))
        with self.assertRaises(ModelLoadError) as caught:
            load_version(
                saved.directory,
                expected_version="v2",
                expected_dataset_sha256=self.dataset.sha256,
            )
        self.assertIn("attesa 'v2'", str(caught.exception))

    def test_missing_metadata_keys_are_named(self) -> None:
        saved = self._save()
        metadata = json.loads(saved.metadata_path.read_text(encoding="utf-8"))
        del metadata["model"]
        del metadata["mlflow"]
        saved.metadata_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        with self.assertRaises(ModelLoadError) as caught:
            load_version(
                saved.directory, expected_dataset_sha256=self.dataset.sha256
            )
        message = str(caught.exception)
        self.assertIn("Controllo 'metadati'", message)
        self.assertIn("'model'", message)
        self.assertIn("'mlflow'", message)

    def test_artifact_without_pipeline_contract_is_named(self) -> None:
        """Un artefatto serializzato ma non una Pipeline è rifiutato (hash coerente)."""

        saved = self._save()
        classifier = self.pipeline.named_steps["classifier"]
        joblib.dump(classifier, saved.directory / ARTIFACT_FILENAME)
        metadata = json.loads(saved.metadata_path.read_text(encoding="utf-8"))
        metadata["artifact"]["sha256"] = sha256_file(saved.directory / ARTIFACT_FILENAME)
        saved.metadata_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        with self.assertRaises(ModelLoadError) as caught:
            load_version(
                saved.directory, expected_dataset_sha256=self.dataset.sha256
            )
        self.assertIn("Controllo 'contratto pipeline'", str(caught.exception))
        self.assertIn("non è una", str(caught.exception))

    def test_artifact_with_wrong_feature_width_is_named(self) -> None:
        narrow = build_baseline_pipeline(BaselineConfig())
        narrow.fit(np.zeros((12, FEATURE_COUNT - 1)), np.arange(12) % 2)
        saved = save_version(
            version="v1",
            models_dir=self.models,
            pipeline=narrow,
            metadata=_metadata(version="v1", dataset_sha256=self.dataset.sha256),
            prediction_rows=self.rows,
        )
        with self.assertRaises(ModelLoadError) as caught:
            load_version(
                saved.directory, expected_dataset_sha256=self.dataset.sha256
            )
        self.assertIn("ammette 29 feature", str(caught.exception))

    def test_missing_artifact_file_is_named(self) -> None:
        saved = self._save()
        (saved.directory / ARTIFACT_FILENAME).unlink()
        with self.assertRaises(ModelLoadError) as caught:
            load_version(
                saved.directory, expected_dataset_sha256=self.dataset.sha256
            )
        self.assertIn("non presente", str(caught.exception))

    def test_missing_metadata_file_is_named(self) -> None:
        saved = self._save()
        (saved.directory / METADATA_FILENAME).unlink()
        with self.assertRaises(ModelLoadError) as caught:
            load_version(saved.directory)
        self.assertIn("Controllo 'metadati'", str(caught.exception))

    def test_invalid_version_name_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            save_version(
                version="latest",
                models_dir=self.models,
                pipeline=self.pipeline,
                metadata=_metadata(version="latest", dataset_sha256=self.dataset.sha256),
                prediction_rows=self.rows,
            )


if __name__ == "__main__":
    unittest.main()
