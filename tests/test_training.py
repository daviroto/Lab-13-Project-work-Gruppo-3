"""Test del training S2: fit solo sul train, metriche e ripetibilità.

Le righe sono quelle sintetiche di ``_fixtures.py``, scritte in cartelle
temporanee: il dataset assegnato non è toccato.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _path in (PROJECT_ROOT / "src", Path(__file__).parent):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

try:
    import numpy as np

    from _fixtures import write_dataset_csv
    from lab13.contracts import FEATURE_COUNT
    from lab13.data import load_dataset
    from lab13.training import (
        BASELINE_SEED,
        BaselineConfig,
        build_baseline_pipeline,
        evaluate,
        fit_train,
    )

    IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover - ambiente senza dipendenze
    IMPORT_ERROR = str(exc)


@unittest.skipUnless(IMPORT_ERROR is None, f"dipendenze mancanti: {IMPORT_ERROR}")
class BaselineTrainingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.dataset = load_dataset(write_dataset_csv(self.tmp / "dataset.csv"))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_pipeline_is_scaler_plus_classifier(self) -> None:
        pipeline = build_baseline_pipeline(BaselineConfig())
        self.assertEqual(
            [name for name, _ in pipeline.steps], ["scaler", "classifier"]
        )
        self.assertEqual(pipeline.named_steps["scaler"].__class__.__name__, "StandardScaler")
        self.assertEqual(
            pipeline.named_steps["classifier"].__class__.__name__, "LogisticRegression"
        )

    def test_scaler_is_fit_only_on_train_rows(self) -> None:
        train = self.dataset.train
        pipeline = fit_train(build_baseline_pipeline(BaselineConfig()), train)
        X_train = np.asarray(train.features, dtype=float)
        np.testing.assert_allclose(pipeline.named_steps["scaler"].mean_, X_train.mean(axis=0))
        self.assertEqual(pipeline.n_features_in_, FEATURE_COUNT)
        self.assertEqual(pipeline.named_steps["scaler"].n_samples_seen_, len(train))

    def test_metrics_are_consistent_with_confusion_matrix(self) -> None:
        pipeline = fit_train(build_baseline_pipeline(BaselineConfig()), self.dataset.train)
        evaluation = evaluate(pipeline, self.dataset.validation)
        counts = evaluation.counts
        rows = len(evaluation.record_ids)

        self.assertEqual(rows, 200)
        self.assertEqual(evaluation.record_ids, self.dataset.validation_ids)
        self.assertEqual(
            evaluation.accuracy, (counts["tn"] + counts["tp"]) / rows
        )
        self.assertEqual(
            evaluation.precision, counts["tp"] / (counts["tp"] + counts["fp"])
        )
        self.assertEqual(evaluation.recall, counts["tp"] / (counts["tp"] + counts["fn"]))
        # Ordine dichiarato [0, 1]: righe = reale, colonne = predetto.
        self.assertEqual(evaluation.as_dict()["class_order"], [0, 1])
        self.assertEqual(
            evaluation.as_dict()["confusion_matrix"],
            [[counts["tn"], counts["fp"]], [counts["fn"], counts["tp"]]],
        )

    def test_same_config_reproduces_the_same_predictions(self) -> None:
        config = BaselineConfig()
        first = evaluate(
            fit_train(build_baseline_pipeline(config), self.dataset.train),
            self.dataset.validation,
        )
        second = evaluate(
            fit_train(build_baseline_pipeline(config), self.dataset.train),
            self.dataset.validation,
        )
        self.assertEqual(first.predictions, second.predictions)
        self.assertEqual(first.as_dict(), second.as_dict())

    def test_config_params_and_seed_are_recorded(self) -> None:
        params = BaselineConfig().params
        self.assertEqual(params["random_state"], BASELINE_SEED)
        self.assertEqual(params["scaler"], "StandardScaler")
        self.assertEqual(params["classifier"], "LogisticRegression")
        self.assertEqual(len(params["pipeline_steps"]), 2)

    def test_fit_rejects_other_splits_and_wrong_width(self) -> None:
        pipeline = build_baseline_pipeline(BaselineConfig())
        with self.assertRaises(ValueError):
            fit_train(pipeline, self.dataset.validation)


if __name__ == "__main__":
    unittest.main()
