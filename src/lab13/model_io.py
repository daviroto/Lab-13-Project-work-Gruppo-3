"""Versionamento degli artefatti e caricatore con controlli.

Ogni versione vive in una cartella distinta (``models/v1``, ``models/v2``) e non
viene mai sovrascritta: una seconda esecuzione sulla stessa versione termina con
un errore esplicito. Il caricatore controlla versione, schema/ordine feature,
fingerprint del dataset e hash SHA-256 dell'artefatto **prima** di restituire il
modello; ogni controllo fallito produce un messaggio che nomina il controllo.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from typing import Any

import joblib
from sklearn.pipeline import Pipeline

from .contracts import FEATURE_COUNT, FEATURE_NAMES
from .data import sha256_file
from .training import BASELINE_STEP_NAMES

ARTIFACT_FILENAME = "pipeline.joblib"
METADATA_FILENAME = "model_metadata.json"
PREDICTIONS_FILENAME = "validation_predictions.json"

_VERSION_RE = re.compile(r"v\d+")

# Chiavi che il caricatore deve trovare prima di fidarsi dell'artefatto.
# ``model`` porta i parametri della pipeline (StandardScaler + LogisticRegression).
REQUIRED_METADATA_KEYS: tuple[str, ...] = (
    "version",
    "model",
    "feature_names",
    "feature_count",
    "classes",
    "dataset",
    "validation",
    "artifact",
    "mlflow",
)

SOFTWARE_PACKAGES: tuple[str, ...] = (
    "numpy",
    "scikit-learn",
    "mlflow",
    "joblib",
)


class ArtifactConflictError(RuntimeError):
    """La versione richiesta esiste già: gli artefatti non si sovrascrivono."""


class ModelLoadError(RuntimeError):
    """Un controllo del caricatore non è superato; il modello non è restituito."""


@dataclass(frozen=True, slots=True)
class SavedVersion:
    """Esito del salvataggio di una versione."""

    version: str
    directory: Path
    artifact_path: Path
    artifact_sha256: str
    metadata_path: Path
    predictions_path: Path


@dataclass(frozen=True, slots=True)
class LoadedModel:
    """Modello verificato, pronto per il serving."""

    version: str
    pipeline: Pipeline
    metadata: dict[str, Any]
    run_id: str
    dataset_sha256: str
    artifact_sha256: str
    feature_names: tuple[str, ...]


def software_versions() -> dict[str, str]:
    """Versioni software effettivamente disponibili in questo ambiente."""

    installed: dict[str, str] = {}
    for name in SOFTWARE_PACKAGES:
        try:
            installed[name] = package_version(name)
        except PackageNotFoundError:
            installed[name] = "non disponibile"
    return {
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "packages": installed,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def require_new_version(*, version: str, models_dir: str | Path) -> Path:
    """Cartella di una versione nuova; errore esplicito se esiste già.

    Usato sia dallo script sia da :func:`save_version`, così il messaggio di
    non-sovrascrittura ha una sola fonte.
    """

    if not _VERSION_RE.fullmatch(version):
        raise ValueError(
            f"Versione non valida {version!r}: atteso v1, v2, ... (v + numero)."
        )
    directory = Path(models_dir).expanduser() / version
    if directory.exists():
        raise ArtifactConflictError(
            f"La versione '{version}' esiste già in {directory}. Gli artefatti "
            "non vengono cancellati né sovrascritti: usa --version per una "
            "versione nuova oppure --models-dir per una cartella diversa."
        )
    return directory


def save_version(
    *,
    version: str,
    models_dir: str | Path,
    pipeline: Pipeline,
    metadata: dict[str, Any],
    prediction_rows: list[dict[str, Any]],
) -> SavedVersion:
    """Scrive una versione nuova in ``models/<version>/``, senza sovrascrivere.

    ``metadata`` è il dizionario costruito dallo script; qui vengono aggiunti
    solo l'hash SHA-256 dell'artefatto e i nomi dei file versionati.
    """

    directory = require_new_version(version=version, models_dir=models_dir)
    try:
        # ``mkdir`` senza exist_ok rivendica la cartella: una corsa concorrente
        # fallisce invece di scrivere sopra la versione già prodotta.
        directory.mkdir(parents=True)
    except FileExistsError as exc:
        raise ArtifactConflictError(
            f"La versione '{version}' è stata creata da un'altra esecuzione "
            f"in {directory}; non viene sovrascritta."
        ) from exc
    try:
        artifact_path = directory / ARTIFACT_FILENAME
        joblib.dump(pipeline, artifact_path)
        artifact_sha256 = sha256_file(artifact_path)

        predictions_path = directory / PREDICTIONS_FILENAME
        _write_json(
            predictions_path,
            {
                "version": version,
                "class_order": [0, 1],
                "rows": prediction_rows,
            },
        )

        version_metadata = {
            **metadata,
            "artifact": {
                "filename": ARTIFACT_FILENAME,
                "sha256": artifact_sha256,
                "size_bytes": artifact_path.stat().st_size,
            },
            "files": {
                "artifact": ARTIFACT_FILENAME,
                "metadata": METADATA_FILENAME,
                "predictions": PREDICTIONS_FILENAME,
            },
        }
        metadata_path = directory / METADATA_FILENAME
        _write_json(metadata_path, version_metadata)
    except Exception:
        # Una versione scritta a metà non deve bloccare le esecuzioni successive.
        shutil.rmtree(directory, ignore_errors=True)
        raise

    return SavedVersion(
        version=version,
        directory=directory,
        artifact_path=artifact_path,
        artifact_sha256=artifact_sha256,
        metadata_path=metadata_path,
        predictions_path=predictions_path,
    )


def load_version(
    version_dir: str | Path,
    *,
    expected_version: str | None = None,
    expected_dataset_sha256: str | None = None,
) -> LoadedModel:
    """Carica una versione solo se tutti i controlli sono superati.

    Controlli, nell'ordine: metadati, versione, schema/ordine feature,
    fingerprint del dataset, hash dell'artefatto, contratto della pipeline.
    """

    directory = Path(version_dir).expanduser()
    metadata_path = directory / METADATA_FILENAME
    artifact_path = directory / ARTIFACT_FILENAME

    if not metadata_path.is_file():
        raise ModelLoadError(
            f"Controllo 'metadati' non superato: {metadata_path} non presente."
        )
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelLoadError(
            f"Controllo 'metadati' non superato: {metadata_path} illeggibile ({exc})."
        ) from exc
    missing = [key for key in REQUIRED_METADATA_KEYS if key not in metadata]
    if missing:
        raise ModelLoadError(
            "Controllo 'metadati' non superato: chiavi mancanti "
            + ", ".join(repr(key) for key in missing)
            + "."
        )

    declared_version = metadata["version"]
    if expected_version is not None and declared_version != expected_version:
        raise ModelLoadError(
            f"Controllo 'versione' non superato: metadati dichiarano "
            f"{declared_version!r}, attesa {expected_version!r}."
        )
    if directory.name != declared_version:
        raise ModelLoadError(
            f"Controllo 'versione' non superato: cartella {directory.name!r}, "
            f"metadati dichiarano {declared_version!r}."
        )

    feature_names = tuple(metadata["feature_names"])
    if feature_names != FEATURE_NAMES:
        first_diff = next(
            (
                index
                for index, (name, expected) in enumerate(
                    zip(feature_names, FEATURE_NAMES), start=1
                )
                if name != expected
            ),
            None,
        )
        raise ModelLoadError(
            "Controllo 'schema e ordine feature' non superato: la lista dei "
            f"metadati non coincide con la lista canonica ({FEATURE_COUNT} "
            f"feature di contracts.py)"
            + (
                f"; prima differenza alla posizione {first_diff}."
                if first_diff is not None
                else f"; feature dichiarate {len(feature_names)}."
            )
        )
    if metadata["feature_count"] != len(feature_names):
        raise ModelLoadError(
            "Controllo 'schema e ordine feature' non superato: feature_count "
            f"{metadata['feature_count']!r} ≠ numero di nomi dichiarati "
            f"({len(feature_names)})."
        )

    declared_dataset_sha = metadata["dataset"]["sha256"]
    if expected_dataset_sha256 is None:
        raise ModelLoadError(
            "Controllo 'fingerprint del dataset' non superato: fingerprint "
            "atteso non fornito (passare expected_dataset_sha256)."
        )
    if declared_dataset_sha != expected_dataset_sha256:
        raise ModelLoadError(
            "Controllo 'fingerprint del dataset' non superato: metadati "
            f"dichiarano {declared_dataset_sha}, dataset atteso "
            f"{expected_dataset_sha256}."
        )

    if not artifact_path.is_file():
        raise ModelLoadError(
            f"Controllo 'hash dell'artefatto' non superato: {artifact_path} "
            "non presente."
        )
    artifact_sha256 = sha256_file(artifact_path)
    if artifact_sha256 != metadata["artifact"]["sha256"]:
        raise ModelLoadError(
            "Controllo 'hash dell'artefatto' non superato: artefatto calcolato "
            f"{artifact_sha256}, metadati dichiarano {metadata['artifact']['sha256']}."
        )

    pipeline = joblib.load(artifact_path)
    if not isinstance(pipeline, Pipeline):
        raise ModelLoadError(
            "Controllo 'contratto pipeline' non superato: l'artefatto non è una "
            "Pipeline scikit-learn."
        )
    steps = tuple(name for name, _ in pipeline.steps)
    if steps != BASELINE_STEP_NAMES:
        raise ModelLoadError(
            "Controllo 'contratto pipeline' non superato: passi dichiarati "
            f"{steps}, attesi {BASELINE_STEP_NAMES}."
        )
    if pipeline.n_features_in_ != FEATURE_COUNT:
        raise ModelLoadError(
            "Controllo 'schema e ordine feature' non superato: l'artefatto addestrato "
            f"ammette {pipeline.n_features_in_} feature, attese {FEATURE_COUNT}."
        )

    return LoadedModel(
        version=str(declared_version),
        pipeline=pipeline,
        metadata=metadata,
        run_id=str(metadata["mlflow"]["run_id"]),
        dataset_sha256=str(declared_dataset_sha),
        artifact_sha256=artifact_sha256,
        feature_names=feature_names,
    )
