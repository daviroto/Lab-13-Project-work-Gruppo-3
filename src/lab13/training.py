"""Training ripetibile della baseline e valutazione sulla validation distribuita.

Il fit usa esclusivamente le righe ``split == "train"``: lo ``StandardScaler`` è
stimato solo su quelle righe e la validation è lettura sola per la valutazione
didattica. Nessuna scelta di parametri o tuning è faite sui dati di validation.

Le feature sono l'unico input di ``X``; ``record_id``, ``split`` e ``target``
restano metadati e non entrano mai nella matrice. L'ordine delle colonne è
quello canonico restituito dal lettore di S1 (``contracts.FEATURE_NAMES``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .contracts import CLASS_ORDER, FEATURE_COUNT, POSITIVE_CLASS, TRAIN_SPLIT
from .data import DatasetSplit

# Seed unico della baseline: riusato in ogni esecuzione e registrato nei
# metadati e in MLflow. Coerente con la provenienza dei dati (README: seed 1303).
BASELINE_SEED = 1303

# Nome dei passi della pipeline: il caricatore verifica l'artefatto contro questo.
BASELINE_STEP_NAMES: tuple[str, ...] = ("scaler", "classifier")


@dataclass(frozen=True, slots=True)
class BaselineConfig:
    """Configurazione esplicita della baseline; i valori vanno nei metadati."""

    version: str = "v1"
    seed: int = BASELINE_SEED
    C: float = 1.0
    solver: str = "liblinear"
    max_iter: int = 1000

    @property
    def params(self) -> dict[str, Any]:
        return {
            "pipeline_steps": list(BASELINE_STEP_NAMES),
            "scaler": "StandardScaler",
            "classifier": "LogisticRegression",
            "C": self.C,
            "solver": self.solver,
            "max_iter": self.max_iter,
            "random_state": self.seed,
        }


def build_baseline_pipeline(config: BaselineConfig) -> Pipeline:
    """Pipeline completa: lo scaler è parte dell'artefatto, non un passo esterno."""

    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    C=config.C,
                    solver=config.solver,
                    max_iter=config.max_iter,
                    random_state=config.seed,
                ),
            ),
        ]
    )


def fit_train(pipeline: Pipeline, train: DatasetSplit) -> Pipeline:
    """Addestra solo sulle righe di ``train``."""

    if train.name != TRAIN_SPLIT:
        raise ValueError(
            f"Il fit ammette solo lo split '{TRAIN_SPLIT}', ricevuto '{train.name}'."
        )
    X = np.asarray(train.features, dtype=float)
    y = np.asarray(train.targets, dtype=int)
    if X.size == 0:
        raise ValueError("Split 'train' vuoto: nessun dato per il fit.")
    if X.shape[1] != FEATURE_COUNT:
        raise ValueError(
            f"Feature ricevute {X.shape[1]}, attese {FEATURE_COUNT}."
        )
    return pipeline.fit(X, y)


@dataclass(frozen=True, slots=True)
class Evaluation:
    """Metriche di validation più predizioni e ID, per ricostruire il report."""

    record_ids: tuple[str, ...]
    targets: tuple[int, ...]
    predictions: tuple[int, ...]
    confusion: tuple[tuple[int, int], ...]
    accuracy: float | None
    precision: float | None
    recall: float | None

    @property
    def counts(self) -> dict[str, int]:
        tn, fp = self.confusion[0]
        fn, tp = self.confusion[1]
        return {"tn": tn, "fp": fp, "fn": fn, "tp": tp}

    def prediction_rows(self) -> list[dict[str, Any]]:
        return [
            {"record_id": record_id, "target": target, "prediction": prediction}
            for record_id, target, prediction in zip(
                self.record_ids, self.targets, self.predictions
            )
        ]

    def as_dict(self) -> dict[str, Any]:
        return {
            "class_order": list(CLASS_ORDER),
            "positive_class": POSITIVE_CLASS,
            "rows": len(self.record_ids),
            "accuracy": self.accuracy,
            "precision_class_1": self.precision,
            "recall_class_1": self.recall,
            "confusion_matrix": [list(row) for row in self.confusion],
            "confusion_matrix_semantics": (
                "righe = classe reale, colonne = classe predetta, ordine [0, 1]"
            ),
            "counts": self.counts,
        }


def evaluate(pipeline: Pipeline, validation: DatasetSplit) -> Evaluation:
    """Valuta la pipeline salvata sulle righe di validation, senza re-fit."""

    X = np.asarray(validation.features, dtype=float)
    y = np.asarray(validation.targets, dtype=int)
    if X.size == 0:
        raise ValueError("Split 'validation' vuoto: nessuna valutazione possibile.")
    if X.shape[1] != FEATURE_COUNT:
        raise ValueError(
            f"Feature ricevute {X.shape[1]}, attese {FEATURE_COUNT}."
        )

    predictions = tuple(int(value) for value in pipeline.predict(X))
    matrix = confusion_matrix(y, np.asarray(predictions, dtype=int), labels=list(CLASS_ORDER))
    tn, fp = int(matrix[0][0]), int(matrix[0][1])
    fn, tp = int(matrix[1][0]), int(matrix[1][1])
    total = tn + fp + fn + tp
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    accuracy = (tn + tp) / total if total else None

    return Evaluation(
        record_ids=validation.record_ids,
        targets=tuple(int(value) for value in y),
        predictions=predictions,
        confusion=((tn, fp), (fn, tp)),
        accuracy=accuracy,
        precision=precision,
        recall=recall,
    )
