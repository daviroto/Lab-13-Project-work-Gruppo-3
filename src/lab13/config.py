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
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DATASET_PATH = PROJECT_ROOT / "dataset (1).csv"
DEFAULT_REQUESTS_PATH = PROJECT_ROOT / "richieste_monitoraggio.csv"
LOCAL_DATASET_FALLBACK = PROJECT_ROOT / "dataset (1).csv"
LOCAL_REQUESTS_FALLBACK = PROJECT_ROOT / "richieste_monitoraggio.csv"

DATASET_ENV_VAR = "LAB13_DATASET_PATH"
REQUESTS_ENV_VAR = "LAB13_REQUESTS_PATH"

_ORIGIN_LABELS = {
    "cli": "argomento CLI",
    "env": "variabile d'ambiente",
    "default": "copia assegnata nella cartella del progetto",
    "local_fallback": "fallback locale (predefinito assegnato assente)",
    "default_missing": "predefinito assegnato non trovato",
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


@dataclass(frozen=True, slots=True)
class Settings:
    """Configurazione risolta per un'esecuzione."""

    dataset: InputPath
    requests: InputPath
    reports_dir: Path = PROJECT_ROOT / "reports"
    models_dir: Path = PROJECT_ROOT / "models"
    logs_dir: Path = PROJECT_ROOT / "logs"

    @classmethod
    def load(
        cls,
        *,
        dataset_path: str | Path | None = None,
        requests_path: str | Path | None = None,
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
