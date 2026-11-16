#!/usr/bin/env python
"""Seleziona la versione servita e registra la transizione.

Comandi:

* ``status``   mostra lo stato attivo e le ultime transizioni;
* ``activate`` attiva una versione verificata (artefatto, schema, fingerprint);
* ``rollback`` ripristina la versione precedente registrata nello stato.

Il file di stato viene scritto in modo atomico. Questo comando opera offline
sullo stato: se il server è già avviato, per il cambio a caldo usare
``POST /admin/version`` (abilitato da ``LAB13_ALLOW_VERSION_SWITCH=1``).
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lab13.config import Settings  # noqa: E402
from lab13.data import load_dataset  # noqa: E402
from lab13.model_io import load_version  # noqa: E402
from lab13.version_state import (  # noqa: E402
    DEFAULT_STATE_PATH,
    DEFAULT_TRANSITIONS_PATH,
    VersionStateError,
    apply_transition,
    read_state,
    read_transitions,
    validate_mode,
    validate_version_name,
)

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass


def _project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def _identity(model: Any) -> dict[str, Any]:
    return {
        "version": model.version,
        "run_id": model.run_id,
        "artifact_sha256": model.artifact_sha256,
    }


def _load_target(
    *, version: str, models_dir: Path, dataset: Any
) -> Any:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Trying to unpickle estimator")
        return load_version(
            models_dir / version,
            expected_version=version,
            expected_dataset_canonical_sha256=dataset.sha256_canonical,
        )


def _state_identity(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": state.get("version"),
        "run_id": state.get("run_id"),
        "artifact_sha256": state.get("artifact_sha256"),
    }


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def cmd_status(args: argparse.Namespace) -> int:
    state = read_state(_project_path(args.state), default_version=args.default_version)
    transitions = read_transitions(_project_path(args.transitions))
    _print_json(
        {
            "state_path": str(_project_path(args.state)),
            "state": state,
            "transitions_count": len(transitions),
            "last_transitions": transitions[-5:],
        }
    )
    return 0


def _transition(
    *,
    target_version: str,
    action: str,
    mode: str,
    args: argparse.Namespace,
) -> int:
    validate_version_name(target_version)
    validate_mode(mode)
    state_path = _project_path(args.state)
    transitions_path = _project_path(args.transitions)
    current_state = read_state(state_path, default_version=args.default_version)
    current_version = current_state["version"]

    if target_version == current_version:
        _print_json(
            {
                "changed": False,
                "reason": f"La versione {target_version} è già attiva.",
                "state": current_state,
            }
        )
        return 0

    settings = Settings.load(dataset_path=args.dataset)
    dataset = load_dataset(settings.dataset.path)
    models_dir = _project_path(args.models_dir)

    # Identità "prima": preferisce l'artefatto caricabile, altrimenti lo stato.
    try:
        before = _identity(
            _load_target(
                version=current_version, models_dir=models_dir, dataset=dataset
            )
        )
    except Exception:
        before = _state_identity(current_state)

    try:
        target = _load_target(
            version=target_version, models_dir=models_dir, dataset=dataset
        )
    except Exception as exc:
        print(
            f"TRANSIZIONE BLOCCATA: versione {target_version} non verificata ({exc}).",
            file=sys.stderr,
        )
        return 2

    state = apply_transition(
        state_path=state_path,
        transitions_path=transitions_path,
        before=before,
        after=_identity(target),
        action=action,
        mode=mode,
        source="switch_version-cli",
        dataset_sha256_canonical=dataset.sha256_canonical,
    )
    _print_json(
        {
            "changed": True,
            "action": action,
            "mode": mode,
            "before": before,
            "after": _identity(target),
            "dataset_sha256_canonical": dataset.sha256_canonical,
            "state_path": str(state_path),
            "transitions_path": str(transitions_path),
            "state": state,
        }
    )
    return 0


def cmd_activate(args: argparse.Namespace) -> int:
    return _transition(
        target_version=args.version, action="activate", mode=args.mode, args=args
    )


def cmd_rollback(args: argparse.Namespace) -> int:
    state = read_state(_project_path(args.state), default_version=args.default_version)
    target = args.version or state.get("previous_version")
    if not target:
        print(
            "ROLLBACK BLOCCATO: nessuna versione precedente registrata nello stato.",
            file=sys.stderr,
        )
        return 2
    return _transition(
        target_version=str(target), action="rollback", mode=args.mode, args=args
    )


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--state", default=str(DEFAULT_STATE_PATH), help="Percorso del file di stato attivo."
    )
    parser.add_argument(
        "--transitions",
        default=str(DEFAULT_TRANSITIONS_PATH),
        help="Registro JSONL delle transizioni.",
    )
    parser.add_argument(
        "--models-dir", default=str(PROJECT_ROOT / "models"), help="Cartella delle versioni."
    )
    parser.add_argument("--dataset", help="Percorso del CSV dataset.")
    parser.add_argument(
        "--default-version",
        default="v1",
        help="Versione usata se il file di stato non esiste (default v1).",
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seleziona la versione servita e registra la transizione."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Mostra stato e transizioni recenti.")
    _add_common(status)
    status.set_defaults(func=cmd_status)

    activate = subparsers.add_parser("activate", help="Attiva una versione verificata.")
    activate.add_argument("version", help="Versione da attivare (es. v2).")
    activate.add_argument(
        "--mode", choices=("normal", "drill"), default="normal", help="Modalità della transizione."
    )
    _add_common(activate)
    activate.set_defaults(func=cmd_activate)

    rollback = subparsers.add_parser("rollback", help="Ripristina la versione precedente.")
    rollback.add_argument(
        "version", nargs="?", help="Versione di ripristino (default: previous_version)."
    )
    rollback.add_argument(
        "--mode", choices=("normal", "drill"), default="normal", help="Modalità della transizione."
    )
    _add_common(rollback)
    rollback.set_defaults(func=cmd_rollback)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        return int(args.func(args))
    except VersionStateError as exc:
        print(f"TRANSIZIONE BLOCCATA: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
