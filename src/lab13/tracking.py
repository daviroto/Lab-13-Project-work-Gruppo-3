"""Tracciamento MLflow locale.

Il tracking URI è un percorso locale configurabile (CLI > ambiente > ``mlruns``
nella radice del progetto): nessuna connessione esterna è richiesta. Il run MLflow
viene aperto **prima** del salvataggio degli artefatti, così il run ID finisce nei
metadati versionati e gli artefatti sono riferiti dal run.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

MISSING_MLFLOW_MESSAGE = (
    "MLflow non installato: il training della fase S2 richiede il tracciamento. "
    "Installare mlflow (vedi requirements.txt) e rieseguire lo script."
)

# MLflow 3.x mette il store su file in "maintenance mode" e rifiuta './mlruns'
# senza opt-out. Il laboratorio usa uno store locale senza rete: l'opt-out è
# impostato qui (sovrascrivibile dall'ambiente) e si può passare un URI
# alternativo, ad esempio --tracking-uri sqlite:///mlflow.db.
LOCAL_STORE_ENV = {
    "MLFLOW_ALLOW_FILE_STORE": "true",
    "MLFLOW_DISABLE_AGENT_HINT": "1",
}


class TrackingUnavailable(RuntimeError):
    """Il tracciamento MLflow non è disponibile o non è completato."""


@dataclass(frozen=True, slots=True)
class RunInfo:
    """Identificatori del run MLflow attivo."""

    tracking_uri: str
    experiment_name: str
    experiment_id: str
    run_id: str
    run_name: str


def _import_mlflow() -> Any:
    # Le variabili vanno impostate prima dell'import: mlflow le legge a import-time.
    for key, value in LOCAL_STORE_ENV.items():
        os.environ.setdefault(key, value)
    try:
        import mlflow
    except ImportError as exc:
        raise TrackingUnavailable(MISSING_MLFLOW_MESSAGE) from exc
    return mlflow


@contextmanager
def tracked_run(
    *, tracking_uri: str, experiment_name: str, run_name: str
) -> Iterator[RunInfo]:
    """Run MLflow locale; il corpo esegue con il run attivo."""

    mlflow = _import_mlflow()
    try:
        mlflow.set_tracking_uri(tracking_uri)
        experiment = mlflow.set_experiment(experiment_name)
        run = mlflow.start_run(run_name=run_name)
    except Exception as exc:
        raise TrackingUnavailable(
            f"Impossibile aprire il run MLflow locale ({tracking_uri}): {exc}"
        ) from exc

    try:
        yield RunInfo(
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
            experiment_id=str(experiment.experiment_id),
            run_id=run.info.run_id,
            run_name=run.info.run_name or run_name,
        )
    finally:
        mlflow.end_run()


def log_run(
    *,
    params: dict[str, Any],
    metrics: dict[str, float],
    tags: dict[str, str],
    artifacts: list[Path],
) -> None:
    """Log di parametri, metriche, configurazione e artefatti nel run attivo."""

    mlflow = _import_mlflow()
    scalar_params = {
        key: value if isinstance(value, (int, float, bool)) or isinstance(value, str) else str(value)
        for key, value in params.items()
    }
    logged_metrics = {
        key: float(value) for key, value in metrics.items() if value is not None
    }
    try:
        mlflow.log_params(scalar_params)
        mlflow.log_metrics(logged_metrics)
        for key, value in tags.items():
            mlflow.set_tag(key, value)
        for path in artifacts:
            mlflow.log_artifact(str(path))
    except Exception as exc:
        raise TrackingUnavailable(
            f"Tracciamento MLflow non completato ({exc}); gli artefatti scritti "
            "non hanno un run coerente e vanno rieseguiti in una cartella nuova."
        ) from exc
