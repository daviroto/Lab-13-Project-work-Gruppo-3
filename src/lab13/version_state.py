"""Stato della versione servita e registro delle transizioni.

Lo stato attivo è un piccolo JSON (``config/active_version.json``) scritto in
modo atomico: il file temporaneo viene creato nella stessa cartella e sostituito
con :func:`os.replace`, quindi un lettore vede sempre la versione precedente o
quella nuova, mai un file a metà.

Ogni attivazione o rollback produce una riga JSONL nel registro delle
transizioni con timestamp, azione, modalità, identità prima/dopo, run ID e hash
dell'artefatto. Lo stato è la fonte di verità per il serving; il registro è
l'evidenza storica.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_PATH = PROJECT_ROOT / "config" / "active_version.json"
DEFAULT_TRANSITIONS_PATH = PROJECT_ROOT / "reports" / "drill" / "transitions.jsonl"

SCHEMA_VERSION = 1
VALID_ACTIONS = ("prepare", "activate", "rollback")
VALID_MODES = ("normal", "drill")

_VERSION_RE = re.compile(r"v\d+")


class VersionStateError(RuntimeError):
    """Stato attivo o transizione non validi."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_version_name(version: Any) -> str:
    if not isinstance(version, str) or _VERSION_RE.fullmatch(version) is None:
        raise VersionStateError(
            f"Versione non valida {version!r}: atteso v1, v2, ... (v + numero)."
        )
    return version


def validate_mode(mode: Any) -> str:
    if mode not in VALID_MODES:
        raise VersionStateError(
            f"Modalità non valida {mode!r}: ammesse {', '.join(VALID_MODES)}."
        )
    return str(mode)


def validate_action(action: Any) -> str:
    if action not in VALID_ACTIONS:
        raise VersionStateError(
            f"Azione non valida {action!r}: ammesse {', '.join(VALID_ACTIONS)}."
        )
    return str(action)


def read_state(
    path: str | Path = DEFAULT_STATE_PATH,
    *,
    default_version: str = "v1",
) -> dict[str, Any]:
    """Legge lo stato attivo; se il file manca restituisce la versione default."""

    state_path = Path(path).expanduser()
    if not state_path.is_file():
        return {
            "schema_version": SCHEMA_VERSION,
            "version": validate_version_name(default_version),
            "previous_version": None,
            "mode": "normal",
            "action": "prepare",
            "source": "default",
            "updated_at": None,
        }
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VersionStateError(
            f"Configurazione versione attiva non valida: {state_path} ({exc})."
        ) from exc
    if not isinstance(state, dict):
        raise VersionStateError(
            f"Configurazione versione attiva non valida: {state_path} non è un oggetto."
        )
    validate_version_name(state.get("version"))
    return state


def write_state_atomic(path: str | Path, state: Mapping[str, Any]) -> Path:
    """Scrive lo stato su file temporaneo e lo sostituisce atomicamente."""

    state_path = Path(path).expanduser()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(state)
    payload.setdefault("schema_version", SCHEMA_VERSION)
    validate_version_name(payload.get("version"))
    if payload.get("previous_version") is not None:
        validate_version_name(payload["previous_version"])

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{state_path.name}.", suffix=".tmp", dir=str(state_path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, state_path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise
    return state_path


def build_state(
    *,
    version: str,
    previous_version: str | None,
    action: str,
    mode: str,
    run_id: str | None,
    artifact_sha256: str | None,
    dataset_sha256_canonical: str | None,
    source: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "version": validate_version_name(version),
        "previous_version": (
            None if previous_version is None else validate_version_name(previous_version)
        ),
        "action": validate_action(action),
        "mode": validate_mode(mode),
        "updated_at": timestamp or utc_now(),
        "run_id": run_id,
        "artifact_sha256": artifact_sha256,
        "dataset_sha256_canonical": dataset_sha256_canonical,
        "source": source,
    }


def build_transition(
    *,
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any],
    action: str,
    mode: str,
    source: str,
    dataset_sha256_canonical: str | None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Record di transizione con identità prima/dopo sempre esplicite."""

    def identity(item: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if item is None:
            return None
        return {
            "version": item.get("version"),
            "run_id": item.get("run_id"),
            "artifact_sha256": item.get("artifact_sha256"),
        }

    return {
        "timestamp": timestamp or utc_now(),
        "action": validate_action(action),
        "mode": validate_mode(mode),
        "source": source,
        "before": identity(before),
        "after": identity(after),
        "dataset_sha256_canonical": dataset_sha256_canonical,
    }


def append_transition(
    path: str | Path,
    record: Mapping[str, Any],
) -> Path:
    """Accoda una riga JSONL al registro delle transizioni."""

    transitions_path = Path(path).expanduser()
    transitions_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(record), ensure_ascii=False, separators=(",", ":"))
    with transitions_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return transitions_path


def read_transitions(path: str | Path = DEFAULT_TRANSITIONS_PATH) -> list[dict[str, Any]]:
    transitions_path = Path(path).expanduser()
    if not transitions_path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        transitions_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise VersionStateError(
                f"Registro transizioni non valido alla riga {line_number}: {exc}."
            ) from exc
    return records


def apply_transition(
    *,
    state_path: str | Path,
    transitions_path: str | Path,
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any],
    action: str,
    mode: str,
    source: str,
    dataset_sha256_canonical: str | None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Aggiorna lo stato e registra la transizione, restituendo il nuovo stato.

    L'ordine è: stato atomico (fonte di verità per il serving) e poi registro.
    Se la scrittura del registro fallisce, lo stato resta valido ma l'errore
    viene propagato per non perdere evidenza silenziosamente.
    """

    moment = timestamp or utc_now()
    state = build_state(
        version=str(after["version"]),
        previous_version=(
            None if before is None else str(before.get("version"))
        ),
        action=action,
        mode=mode,
        run_id=after.get("run_id"),
        artifact_sha256=after.get("artifact_sha256"),
        dataset_sha256_canonical=dataset_sha256_canonical,
        source=source,
        timestamp=moment,
    )
    write_state_atomic(state_path, state)
    record = build_transition(
        before=before,
        after=after,
        action=action,
        mode=mode,
        source=source,
        dataset_sha256_canonical=dataset_sha256_canonical,
        timestamp=moment,
    )
    append_transition(transitions_path, record)
    return state
