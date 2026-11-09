"""Configurazione dei percorsi del progetto.

I due CSV restano configurabili senza modificare il codice:

1. argomento CLI (``--dataset`` / ``--requests``);
2. variabili d'ambiente ``LAB13_DATASET_PATH`` e ``LAB13_REQUESTS_PATH``;
3. copie dei file assegnati nella radice del progetto;
4. fallback esplicito alle copie di lavoro presenti nella radice del progetto,
   usato solo se il percorso predefinito non esiste.

Il fallback non copia né modifica i file: segnala la provenienza nel report.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DATASET_PATH = PROJECT_ROOT / "dataset (1).csv"
DEFAULT_REQUESTS_PATH = PROJECT_ROOT / "richieste_monitoraggio.csv"
LOCAL_DATASET_FALLBACK = PROJECT_ROOT / "dataset (1).csv"
LOCAL_REQUESTS_FALLBACK = PROJECT_ROOT / "richieste_monitoraggio.csv"

DATASET_ENV_VAR = "LAB13_DATASET_PATH"
REQUESTS_ENV_VAR = "LAB13_REQUESTS_PATH"

# MLflow: store locale, nessuna connessione esterna richiesta.
DEFAULT_MLFLOW_TRACKING_URI = PROJECT_ROOT / "mlruns"
DEFAULT_MLFLOW_EXPERIMENT_NAME = "lab13-progetto3-ritardi-consegne"
MLFLOW_TRACKING_URI_ENV_VAR = "LAB13_MLFLOW_TRACKING_URI"
MLFLOW_EXPERIMENT_ENV_VAR = "LAB13_MLFLOW_EXPERIMENT"

_ORIGIN_LABELS = {
    "cli": "argomento CLI",
    "env": "variabile d'ambiente",
    "default": "copia assegnata nella cartella del progetto",
    "local_fallback": "fallback locale (predefinito assegnato assente)",
    "default_missing": "predefinito assegnato non trovato",
}

# Etichette del tracking URI: non è un file assegnato, è uno store locale.
_URI_ORIGIN_LABELS = {
    "cli": "argomento CLI",
    "env": "variabile d'ambiente",
    "default": "store locale predefinito del progetto",
}


@dataclass(frozen=True, slots=True)
class InputPath:
    """Percorso risolto e provenienza della scelta."""

    path: Path
    origin: str
    default_path: Path
    fallback_used: bool = False
    env_var: str | None = None

    @property
    def origin_label(self) -> str:
        label = _ORIGIN_LABELS.get(self.origin, self.origin)
        if self.env_var:
            return f"{label} ({self.env_var})"
        return label


def resolve_input_path(
    *,
    explicit: str | Path | None,
    env_var: str,
    default_path: Path,
    local_fallback: Path,
) -> InputPath:
    """Risolve un input con precedenza CLI > ambiente > predefinito > fallback."""

    if explicit is not None:
        return InputPath(
            path=Path(explicit).expanduser(),
            origin="cli",
            default_path=default_path,
        )

    env_value = os.environ.get(env_var)
    if env_value:
        return InputPath(
            path=Path(env_value).expanduser(),
            origin="env",
            default_path=default_path,
            env_var=env_var,
        )

    if default_path.is_file():
        return InputPath(
            path=default_path,
            origin="default",
            default_path=default_path,
        )

    if local_fallback.is_file():
        return InputPath(
            path=local_fallback,
            origin="local_fallback",
            default_path=default_path,
            fallback_used=True,
        )

    return InputPath(
        path=default_path,
        origin="default_missing",
        default_path=default_path,
    )


def resolve_tracking_uri(
    *,
    explicit: str | Path | None,
    env_var: str = MLFLOW_TRACKING_URI_ENV_VAR,
    default_path: Path = DEFAULT_MLFLOW_TRACKING_URI,
) -> TrackingUri:
    """Risolve il tracking URI MLflow con precedenza CLI > ambiente > predefinito.

    Il valore è sempre locale: nessuna connessione esterna è richiesta. Sono
    ammesse una directory (``mlruns``) o un URI supportato da MLflow
    (``sqlite:///mlflow.db``); gli URI non sono convertiti in percorsi.
    """

    raw = explicit if explicit is not None else os.environ.get(env_var)
    if raw:
        value = str(raw)
        return TrackingUri(
            value=value,
            origin="cli" if explicit is not None else "env",
            default_value=str(default_path),
            env_var=None if explicit is not None else env_var,
        )
    return TrackingUri(value=str(default_path), origin="default", default_value=str(default_path))


def resolve_experiment_name(
    *,
    explicit: str | None,
    env_var: str = MLFLOW_EXPERIMENT_ENV_VAR,
    default_name: str = DEFAULT_MLFLOW_EXPERIMENT_NAME,
) -> str:
    if explicit:
        return explicit
    return os.environ.get(env_var) or default_name


def display_path(path: str | Path) -> str:
    """Formatta un percorso nei report senza pubblicare directory personali."""

    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(PROJECT_ROOT).as_posix()
    except (OSError, ValueError):
        return f"…/{candidate.name}"


@dataclass(frozen=True, slots=True)
class TrackingUri:
    """Tracking URI MLflow locale e provenienza della scelta.

    ``value`` è passato a ``mlflow.set_tracking_uri`` così com'è: una directory
    locale o un URI (``sqlite:///mlflow.db``).
    """

    value: str
    origin: str
    default_value: str = str(DEFAULT_MLFLOW_TRACKING_URI)
    env_var: str | None = None

    @property
    def origin_label(self) -> str:
        label = _URI_ORIGIN_LABELS.get(self.origin, self.origin)
        if self.env_var:
            return f"{label} ({self.env_var})"
        return label

    @property
    def display(self) -> str:
        """Versione corta da mettere nei report: gli URI non sono percorsi."""

        if "://" in self.value:
            return self.value
        return display_path(self.value)


@dataclass(frozen=True, slots=True)
class Settings:
    """Configurazione risolta per un'esecuzione."""

    dataset: InputPath
    requests: InputPath
    reports_dir: Path = PROJECT_ROOT / "reports"
    models_dir: Path = PROJECT_ROOT / "models"
    logs_dir: Path = PROJECT_ROOT / "logs"
    tracking_uri: TrackingUri = field(
        default_factory=lambda: resolve_tracking_uri(explicit=None)
    )
    mlflow_experiment_name: str = DEFAULT_MLFLOW_EXPERIMENT_NAME

    @classmethod
    def load(
        cls,
        *,
        dataset_path: str | Path | None = None,
        requests_path: str | Path | None = None,
        tracking_uri: str | Path | None = None,
        mlflow_experiment_name: str | None = None,
    ) -> "Settings":
        return cls(
            dataset=resolve_input_path(
                explicit=dataset_path,
                env_var=DATASET_ENV_VAR,
                default_path=DEFAULT_DATASET_PATH,
                local_fallback=LOCAL_DATASET_FALLBACK,
            ),
            requests=resolve_input_path(
                explicit=requests_path,
                env_var=REQUESTS_ENV_VAR,
                default_path=DEFAULT_REQUESTS_PATH,
                local_fallback=LOCAL_REQUESTS_FALLBACK,
            ),
            tracking_uri=resolve_tracking_uri(explicit=tracking_uri),
            mlflow_experiment_name=resolve_experiment_name(
                explicit=mlflow_experiment_name
            ),
        )

    @property
    def warnings(self) -> tuple[str, ...]:
        messages: list[str] = []
        for label, item in (("dataset", self.dataset), ("richieste", self.requests)):
            if item.origin == "local_fallback":
                messages.append(
                    f"{label}: percorso predefinito non trovato "
                    f"({item.default_path}); uso la copia locale {item.path}."
                )
            elif not item.path.is_file():
                messages.append(
                    f"{label}: file non trovato in {item.path} "
                    f"(origine: {item.origin_label})."
                )
        return tuple(messages)
