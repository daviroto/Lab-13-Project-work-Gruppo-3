#!/usr/bin/env python
"""Drill locale v1 -> v2 -> v1 con rollback e prova dello stato finale.

Il drill usa ``richieste_monitoraggio.csv`` nell'ordine distribuito:

1. ``req_01`` su v1, attesa 200;
2. ``req_02`` su v2, attesa 200;
3. rollback a v1;
4. ``req_03`` su v1, attesa 200;
5. ``req_04`` incompleta (29 feature), attesa 422 dal contratto.

Per ogni richiesta registra versione realmente servita, request ID, status HTTP,
predizione e correlazione con il log delle richieste. Il report distingue il
drill dalla probe/gate: qui 3 risposte valide e 1 errore atteso su 4 richieste,
quindi error rate 0,25; non è la misura del gate (0/30 sulla probe valida).

Con ``--base-url`` usa un server già avviato (deve avere
``LAB13_ALLOW_VERSION_SWITCH=1``). Senza ``--base-url`` avvia e arresta uvicorn
automaticamente.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lab13.config import Settings, display_path  # noqa: E402
from lab13.contracts import (  # noqa: E402
    PayloadValidationError,
    validate_inference_payload,
)
from lab13.data import load_dataset  # noqa: E402
from lab13.model_io import load_version, software_versions  # noqa: E402
from lab13.version_state import (  # noqa: E402
    DEFAULT_STATE_PATH,
    DEFAULT_TRANSITIONS_PATH,
    read_state,
    read_transitions,
)

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass

EXPECTED_VERSIONS = ["v1", "v2", "v1", "v1"]
EXPECTED_STATUSES = [200, 200, 200, 422]
DRILL_REPORT_JSON = PROJECT_ROOT / "reports" / "drill_s5_s6.json"
DRILL_REPORT_MD = PROJECT_ROOT / "reports" / "drill_s5_s6.md"
DRILL_DIR = PROJECT_ROOT / "reports" / "drill"
DRILL_REQUEST_LOG = DRILL_DIR / "requests.jsonl"
DRILL_LOG_EXTRACT = DRILL_DIR / "request_log_extract.jsonl"
SERVER_LOG = DRILL_DIR / "server.log"


class DrillError(RuntimeError):
    """Il drill non può proseguire o un'attesa non è rispettata."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_requests(path: str | Path) -> list[dict[str, Any]]:
    """Legge il CSV operativo preservando l'ordine e decodificando i payload."""

    requests: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"request_id", "model_version", "payload_json", "expected_status"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise DrillError(
                "Colonne mancanti in richieste_monitoraggio.csv: "
                + ", ".join(sorted(missing))
            )
        for row in reader:
            payload = json.loads(row["payload_json"])
            try:
                validate_inference_payload(payload)
                payload_valid = True
                validation_error = None
            except PayloadValidationError as exc:
                payload_valid = False
                validation_error = f"{exc.code}: {exc}"
            requests.append(
                {
                    "request_id": row["request_id"],
                    "model_version": row["model_version"],
                    "payload": payload,
                    "payload_valid": payload_valid,
                    "payload_validation_error": validation_error,
                    "expected_status": int(row["expected_status"]),
                }
            )
    if not requests:
        raise DrillError("richieste_monitoraggio.csv non contiene richieste.")
    return requests


def check_sequence(requests: list[dict[str, Any]]) -> None:
    versions = [item["model_version"] for item in requests]
    statuses = [item["expected_status"] for item in requests]
    if versions != EXPECTED_VERSIONS or statuses != EXPECTED_STATUSES:
        raise DrillError(
            "Sequenza inattesa nel CSV: "
            f"versioni {versions} (attese {EXPECTED_VERSIONS}), "
            f"status {statuses} (attesi {EXPECTED_STATUSES})."
        )
    if [item["payload_valid"] for item in requests] != [True, True, True, False]:
        raise DrillError(
            "Il contratto non riconosce la sequenza attesa: le prime tre "
            "richieste devono essere valide e l'ultima incompleta."
        )


def _http_json(
    method: str,
    url: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> tuple[int, dict[str, Any] | None, str | None]:
    request = urllib.request.Request(
        url, data=body, headers=headers or {}, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            try:
                payload = json.loads(raw.decode("utf-8")) if raw else None
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = None
            return response.status, payload, None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        return exc.code, payload, None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 599, None, str(exc)


def wait_health(base_url: str, *, timeout: float = 40.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error: str | None = None
    while time.monotonic() < deadline:
        status, payload, error = _http_json("GET", base_url.rstrip("/") + "/health")
        if status == 200 and payload and payload.get("status") == "ok":
            return payload
        last_error = error or f"HTTP {status}"
        time.sleep(0.25)
    raise DrillError(f"/health non raggiungibile entro {timeout:.0f}s: {last_error}")


def _identity_matches(health: dict[str, Any], expected: Any) -> bool:
    return (
        health.get("active_version") == expected.version
        and health.get("run_id") == expected.run_id
        and health.get("artifact_sha256") == expected.artifact_sha256
    )


def _model_identity(model: Any) -> dict[str, Any]:
    return {
        "version": model.version,
        "run_id": model.run_id,
        "artifact_sha256": model.artifact_sha256,
    }


def _load_model(version: str, dataset: Any) -> Any:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Trying to unpickle estimator")
        return load_version(
            PROJECT_ROOT / "models" / version,
            expected_version=version,
            expected_dataset_canonical_sha256=dataset.sha256_canonical,
        )


def _switch(
    base_url: str,
    *,
    version: str,
    action: str,
    mode: str = "drill",
) -> dict[str, Any]:
    status, payload, error = _http_json(
        "POST",
        base_url.rstrip("/") + "/admin/version",
        body=json.dumps(
            {"version": version, "action": action, "mode": mode}
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    if status == 404:
        raise DrillError(
            "Endpoint /admin/version disabilitato: avviare il server con "
            "LAB13_ALLOW_VERSION_SWITCH=1."
        )
    if status != 200 or not payload:
        detail = (payload or {}).get("detail") if payload else error
        raise DrillError(f"Cambio versione a {version} fallito (HTTP {status}): {detail}")
    if payload.get("changed") and payload.get("active_version") != version:
        raise DrillError(
            f"Il server dichiara {payload.get('active_version')} invece di {version}."
        )
    return payload


def _find_log_entry(
    path: Path, request_id: str, *, timeout: float = 3.0
) -> dict[str, Any] | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in reversed(lines):
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (
                    entry.get("request_id") == request_id
                    and entry.get("path") == "/predict"
                ):
                    return entry
        time.sleep(0.1)
    return None


def _send_request(
    base_url: str, item: dict[str, Any], request_log: Path
) -> dict[str, Any]:
    body = json.dumps(item["payload"], allow_nan=False).encode("utf-8")
    started = time.perf_counter()
    status, payload, error = _http_json(
        "POST",
        base_url.rstrip("/") + "/predict",
        body=body,
        headers={
            "Content-Type": "application/json",
            "X-Request-ID": item["request_id"],
        },
    )
    duration_ms = (time.perf_counter() - started) * 1000
    log_entry = _find_log_entry(request_log, item["request_id"])
    response_request_id = (payload or {}).get("request_id") if payload else None
    result: dict[str, Any] = {
        "request_id": item["request_id"],
        "target_version": item["model_version"],
        "expected_status": item["expected_status"],
        "actual_status": status,
        "status_ok": status == item["expected_status"],
        "duration_ms": round(duration_ms, 3),
        "response": payload,
        "transport_error": error,
        "request_id_echo_ok": response_request_id == item["request_id"],
        "payload_valid": item["payload_valid"],
        "payload_validation_error": item["payload_validation_error"],
        "log": log_entry,
        "log_correlated": log_entry is not None,
    }
    if status == 200 and payload:
        result["prediction"] = payload.get("prediction")
        result["served_version"] = payload.get("version")
        result["served_run_id"] = payload.get("run_id")
    else:
        result["prediction"] = None
        result["served_version"] = None
        result["served_run_id"] = None
    return result


def _start_server(
    *,
    port: int,
    state_path: Path,
    transitions_path: Path,
    request_log: Path,
    dataset_path: str | None,
) -> subprocess.Popen[bytes]:
    DRILL_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LAB13_ALLOW_VERSION_SWITCH"] = "1"
    env["LAB13_ACTIVE_VERSION_PATH"] = str(state_path)
    env["LAB13_TRANSITIONS_PATH"] = str(transitions_path)
    env["LAB13_REQUEST_LOG"] = str(request_log)
    if dataset_path:
        env["LAB13_DATASET_PATH"] = dataset_path
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "lab13.service:app",
        "--app-dir",
        str(PROJECT_ROOT / "src"),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    handle = SERVER_LOG.open("w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            command,
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    finally:
        handle.close()
    return process


def _stop_server(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _compute_rates(requests: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    total = len(requests)
    errors = sum(item["actual_status"] >= 400 for item in requests)
    valid = [item for item in requests if item["expected_status"] == 200]
    valid_errors = sum(item["actual_status"] >= 400 for item in valid)
    drill_rate = {
        "requests": total,
        "http_errors_ge_400": errors,
        "value": errors / total if total else 0.0,
        "definition": (
            "error rate del drill su tutte le 4 richieste: 3 risposte valide "
            "e 1 errore atteso (422). Non sostituisce l'error rate del gate."
        ),
    }
    valid_rate = {
        "requests": len(valid),
        "http_errors_ge_400": valid_errors,
        "value": valid_errors / len(valid) if valid else 0.0,
        "definition": "error rate sulle sole richieste con esito atteso 200.",
    }
    return drill_rate, valid_rate


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Drill S5-S6 - cambio versione e rollback",
        "",
        f"Generato (UTC): `{report['generated_at_utc']}`",
        f"Ambito: {report['scope']}",
        f"Server: `{report['base_url']}` ({report['server']['mode']})",
        "",
        "## Sequenza delle richieste",
        "",
        "| # | Request ID | Versione attesa | Status atteso | Status reale | Predizione | Versione servita | Log correlato |",
        "| ---: | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for index, item in enumerate(report["requests"], start=1):
        prediction = "-" if item["prediction"] is None else str(item["prediction"])
        served = item["served_version"] or "-"
        correlated = "sì" if item["log_correlated"] else "no"
        lines.append(
            f"| {index} | `{item['request_id']}` | {item['target_version']} | "
            f"{item['expected_status']} | {item['actual_status']} | {prediction} | "
            f"{served} | {correlated} |"
        )
    lines.extend(
        [
            "",
            "## Transizioni registrate",
            "",
            "| Timestamp | Azione | Modalità | Prima | Dopo | Run ID (dopo) |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    journal = report.get("transitions_journal") or report["transitions"]
    for record in journal:
        before = (record.get("before") or {}).get("version") or "-"
        after = (record.get("after") or {}).get("version") or "-"
        run_id = (record.get("after") or {}).get("run_id") or "-"
        lines.append(
            f"| `{record.get('timestamp')}` | {record.get('action')} | "
            f"{record.get('mode')} | {before} | {after} | `{run_id}` |"
        )
    drill = report["drill_error_rate"]
    valid = report["valid_requests_error_rate"]
    lines.extend(
        [
            "",
            "## Esiti",
            "",
            f"- Sequenza attesa rispettata: {'sì' if report['sequence_ok'] else 'no'}",
            f"- Tutti gli status attesi rispettati: {'sì' if report['statuses_ok'] else 'no'}",
            f"- Error rate drill: {drill['http_errors_ge_400']}/{drill['requests']} = {drill['value']:.2f}",
            f"- Error rate sulle richieste valide: {valid['http_errors_ge_400']}/{valid['requests']} = {valid['value']:.2f}",
            f"- {report['gate_relation']}",
            "",
            "## Prova dello stato finale",
            "",
            f"- Versione attiva nello stato: `{report['final_state'].get('version')}`",
            f"- Versione attiva da `/health`: `{report['final_health'].get('active_version')}`",
            f"- Run ID atteso da `models/v1`: `{report['final_artifact']['metadata_run_id']}`",
            f"- Run ID servito: `{report['final_health'].get('run_id')}`",
            f"- Hash artefatto atteso: `{report['final_artifact']['metadata_artifact_sha256']}`",
            f"- Hash artefatto servito: `{report['final_health'].get('artifact_sha256')}`",
            f"- Identità finale verificata: {'sì' if report['final_artifact']['matches_health'] else 'no'}",
            "",
            "## Limiti",
            "",
        ]
    )
    lines.extend(f"- {limit}" for limit in report["limits"])
    lines.append("")
    return "\n".join(lines)


def run_drill(
    *,
    base_url: str,
    state_path: Path,
    transitions_path: Path,
    request_log: Path,
    requests: list[dict[str, Any]],
    dataset: Any,
    models: dict[str, Any],
    server_mode: str,
    start_health: dict[str, Any],
) -> dict[str, Any]:
    """Esegue il drill su un server già raggiungibile."""

    state = read_state(state_path, default_version="v1")
    current_version = state["version"]
    transitions: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    if current_version != "v1":
        response = _switch(base_url, version="v1", action="activate")
        transitions.append(
            {
                "timestamp": _now(),
                "action": "prepare",
                "mode": "drill",
                "before": _model_identity(models[current_version]),
                "after": _model_identity(models["v1"]),
                "response": response,
            }
        )
        state = read_state(state_path, default_version="v1")
        current_version = state["version"]
        health = wait_health(base_url)
        if not _identity_matches(health, models["v1"]):
            raise DrillError("Il server non serve la v1 attesa dopo la preparazione.")

    for item in requests:
        target = item["model_version"]
        if target != current_version:
            # In questo progetto v1 è la baseline: tornare a v1 da un'altra
            # versione è un rollback, andare verso v2 è un'attivazione.
            action = (
                "rollback"
                if target == "v1" and current_version != "v1"
                else "activate"
            )
            response = _switch(base_url, version=target, action=action)
            transitions.append(
                {
                    "timestamp": _now(),
                    "action": action,
                    "mode": "drill",
                    "before": _model_identity(models[current_version]),
                    "after": _model_identity(models[target]),
                    "response": response,
                }
            )
            state = read_state(state_path, default_version="v1")
            current_version = state["version"]
            health = wait_health(base_url)
            if not _identity_matches(health, models[target]):
                raise DrillError(
                    f"Identità del server non coerente con models/{target} dopo il cambio."
                )

        result = _send_request(base_url, item, request_log)
        results.append(result)

    final_health = wait_health(base_url)
    final_state = read_state(state_path, default_version="v1")
    expected = models["v1"]
    final_artifact = {
        "version": "v1",
        "metadata_run_id": expected.run_id,
        "metadata_artifact_sha256": expected.artifact_sha256,
        "metadata_dataset_sha256_canonical": dataset.sha256_canonical,
        "matches_health": _identity_matches(final_health, expected),
    }

    drill_rate, valid_rate = _compute_rates(results)
    statuses_ok = all(item["status_ok"] for item in results)
    sequence_ok = [item["target_version"] for item in results] == EXPECTED_VERSIONS
    final_ok = (
        final_state.get("version") == "v1"
        and final_health.get("active_version") == "v1"
        and final_artifact["matches_health"]
    )

    return {
        "phase": "S5-S6",
        "generated_at_utc": _now(),
        "scope": (
            "drill locale di cambio versione e rollback; non è un deployment di "
            "produzione e non sostituisce la probe/gate S4"
        ),
        "base_url": base_url,
        "server": {
            "mode": server_mode,
            "start_health": start_health,
            "start_version": start_health.get("active_version"),
        },
        "requests": results,
        "transitions": transitions,
        "state_after_requests": final_state,
        "final_state": final_state,
        "final_health": final_health,
        "final_artifact": final_artifact,
        "sequence_ok": sequence_ok,
        "statuses_ok": statuses_ok,
        "final_ok": final_ok,
        "drill_error_rate": drill_rate,
        "valid_requests_error_rate": valid_rate,
        "gate_relation": (
            "Il gate S4 usa la probe HTTP della candidata (30 richieste valide, "
            "error rate 0/30). Il drill ha 3 risposte valide e 1 errore atteso su "
            "4 richieste: il suo 0,25 non sostituisce la misura del gate."
        ),
        "environment": software_versions(),
        "limits": [
            "Dati sintetici e didattici: il drill non misura spedizioni reali.",
            "Il cambio versione è locale e abilitato solo con LAB13_ALLOW_VERSION_SWITCH=1.",
            "Nessun container o deployment esterno è stato eseguito.",
            "Lo stato finale è v1; v2 resta una candidata approvata dal gate ma non attiva.",
        ],
    }


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Esegue il drill locale v1 -> v2 -> v1 con rollback."
    )
    parser.add_argument(
        "--base-url",
        help="Server già avviato (default: avvia uvicorn su 127.0.0.1:8000).",
    )
    parser.add_argument("--port", type=int, default=8000, help="Porta per il server automatico.")
    parser.add_argument(
        "--state", default=str(DEFAULT_STATE_PATH), help="File di stato della versione attiva."
    )
    parser.add_argument(
        "--transitions",
        default=str(DEFAULT_TRANSITIONS_PATH),
        help="Registro JSONL delle transizioni.",
    )
    parser.add_argument("--dataset", help="Percorso del CSV dataset.")
    parser.add_argument(
        "--output", default=str(DRILL_REPORT_JSON), help="Report JSON del drill."
    )
    parser.add_argument(
        "--markdown", default=str(DRILL_REPORT_MD), help="Report Markdown del drill."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    state_path = Path(args.state).expanduser()
    transitions_path = Path(args.transitions).expanduser()
    settings = Settings.load(dataset_path=args.dataset)
    dataset = load_dataset(settings.dataset.path)
    requests = load_requests(settings.requests.path)
    check_sequence(requests)

    models = {version: _load_model(version, dataset) for version in ("v1", "v2")}
    for item in requests:
        if item["expected_status"] == 200 and not item["payload_valid"]:
            raise DrillError(f"{item['request_id']} doveva essere valida ma non lo è.")
        if item["expected_status"] == 422 and item["payload_valid"]:
            raise DrillError(f"{item['request_id']} doveva essere incompleta ma è valida.")

    DRILL_DIR.mkdir(parents=True, exist_ok=True)
    request_log = DRILL_REQUEST_LOG
    if args.base_url is None:
        # Il log del drill automatico è per-esecuzione: si riparte puliti.
        request_log.unlink(missing_ok=True)
    process: subprocess.Popen[bytes] | None = None
    server_mode = "external"
    base_url = args.base_url

    try:
        if base_url is None:
            base_url = f"http://127.0.0.1:{args.port}"
            server_mode = "auto-started"
            process = _start_server(
                port=args.port,
                state_path=state_path,
                transitions_path=transitions_path,
                request_log=request_log,
                dataset_path=args.dataset,
            )
        start_health = wait_health(base_url)
        report = run_drill(
            base_url=base_url,
            state_path=state_path,
            transitions_path=transitions_path,
            request_log=request_log,
            requests=requests,
            dataset=dataset,
            models=models,
            server_mode=server_mode,
            start_health=start_health,
        )
        report["transitions_journal"] = read_transitions(transitions_path)
    except Exception:
        # Best effort: non lasciare il server locale su v2 se il drill si interrompe.
        if base_url is not None and process is not None and process.poll() is None:
            try:
                current = read_state(state_path, default_version="v1").get("version")
                if current != "v1":
                    _switch(base_url, version="v1", action="activate")
            except Exception:
                pass
        _stop_server(process)
        raise
    finally:
        _stop_server(process)

    output = Path(args.output).expanduser()
    markdown = Path(args.markdown).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    markdown.write_text(_render_markdown(report), encoding="utf-8")

    # Estratto del log correlato: solo metadati, nessun payload.
    extract = [
        item["log"] for item in report["requests"] if item["log"] is not None
    ]
    DRILL_LOG_EXTRACT.write_text(
        "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in extract),
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2, ensure_ascii=False))
    ok = (
        report["sequence_ok"]
        and report["statuses_ok"]
        and report["final_ok"]
        and all(item["log_correlated"] for item in report["requests"])
        and all(item["request_id_echo_ok"] for item in report["requests"])
    )
    if not ok:
        print(
            "DRILL NON SUPERATO: controllare status, correlazione log o stato finale.",
            file=sys.stderr,
        )
        return 1
    print(
        "DRILL SUPERATO: v1 -> v2 -> v1, attese 200/200/200/422, stato finale v1.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
