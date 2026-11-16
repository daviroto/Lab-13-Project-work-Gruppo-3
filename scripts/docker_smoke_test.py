#!/usr/bin/env python
"""Build, avvio e verifica del deploy Docker del servizio.

Il test è black-box: usa soltanto la libreria standard, parla con il container
via HTTP e interroga Docker CLI. Non carica il modello in-process: verifica
l'identità servita (versione, run ID, hash artefatto, fingerprint canonico)
contro ``models/v1/model_metadata.json``.

Sequenza:

1. build dell'immagine e avvio dello stack ``docker compose``;
2. attesa di ``/health`` e dello stato Docker ``healthy``;
3. invio delle quattro richieste di ``richieste_monitoraggio.csv``;
4. verifica di status, versione servita, predizioni, request ID e log;
5. verifica delle metriche, dell'utente non privilegiato e del root read-only;
6. scrittura di ``reports/docker_deploy.json``, ``reports/docker_deploy.md`` e
   delle evidenze in ``reports/docker/``.

Il deployment serve la v1. La richiesta ``req_02`` del CSV indica ``v2`` perché
nasce per il drill S5-S6: qui viene servita dalla v1, senza cambio versione.
Il drill v1 -> v2 -> v1 resta ``scripts/drill_rollback.py`` ed è separato.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yml"
SERVICE_NAME = "api"
IMAGE_TAG = "lab13-progetto3-api:local"
EXPECTED_VERSION = "v1"
EXPECTED_STATUSES = [200, 200, 200, 422]
# Predizioni misurate con models/v1 sui tre payload validi distribuiti.
EXPECTED_PREDICTIONS: list[int | None] = [0, 1, 1, None]
REQUESTS_PATH = PROJECT_ROOT / "richieste_monitoraggio.csv"
REPORT_JSON = PROJECT_ROOT / "reports" / "docker_deploy.json"
REPORT_MD = PROJECT_ROOT / "reports" / "docker_deploy.md"
EVIDENCE_DIR = PROJECT_ROOT / "reports" / "docker"
CONTAINER_REQUEST_LOG = "/app/logs/requests.jsonl"

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class DeployError(RuntimeError):
    """Il deploy Docker non può proseguire o una verifica non è rispettata."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    timeout: float = 300.0,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise DeployError(
            "Docker CLI non trovata nel PATH: installare Docker Desktop/Engine."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise DeployError(
            f"Comando Docker scaduto dopo {timeout:.0f}s: {' '.join(command)}"
        ) from exc
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise DeployError(
            f"Comando fallito (exit {completed.returncode}): {' '.join(command)}\n"
            f"{detail}"
        )
    return completed


def _compose(
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    check: bool = True,
    timeout: float = 600.0,
) -> subprocess.CompletedProcess[str]:
    return _run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        env=env,
        timeout=timeout,
        check=check,
    )


def _docker(
    args: list[str],
    *,
    check: bool = True,
    timeout: float = 120.0,
) -> subprocess.CompletedProcess[str]:
    return _run(["docker", *args], timeout=timeout, check=check)


def _compose_env(port: int) -> dict[str, str]:
    env = os.environ.copy()
    env["LAB13_DOCKER_PORT"] = str(port)
    return env


def _down(*, remove_volumes: bool) -> None:
    args = ["down", "--remove-orphans"]
    if remove_volumes:
        args.append("-v")
    try:
        _compose(args, check=False, timeout=120.0)
    except Exception:
        # Il cleanup non deve mascherare l'errore originale (per esempio Docker
        # non disponibile all'avvio).
        pass


def _port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _http_json(
    method: str,
    url: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> tuple[int, dict[str, Any] | None, dict[str, str], str | None]:
    request = urllib.request.Request(
        url,
        data=body,
        headers=headers or {},
        method=method,
    )
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, _decode_json(raw), dict(response.headers), None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, _decode_json(raw), dict(exc.headers), None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 599, None, {}, str(exc)


def _decode_json(raw: bytes) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _header(headers: dict[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def _ensure_docker() -> dict[str, Any]:
    completed = _docker(["version", "--format", "{{json .}}"], timeout=45.0)
    try:
        version = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise DeployError(f"Risposta di `docker version` non leggibile: {exc}") from exc
    server = version.get("Server") or {}
    if not server.get("Version"):
        raise DeployError(
            "Docker Engine non raggiungibile. Avviare Docker Desktop/Engine e "
            "riprovare."
        )
    return {
        "client_version": (version.get("Client") or {}).get("Version"),
        "server_version": server.get("Version"),
        "server_os": server.get("Os"),
        "server_arch": server.get("Arch"),
    }


def _load_expected_model() -> dict[str, Any]:
    metadata_path = PROJECT_ROOT / "models" / EXPECTED_VERSION / "model_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    artifact_path = metadata_path.parent / metadata["artifact"]["filename"]
    local_hash = _sha256_file(artifact_path)
    canonical = metadata["dataset"].get("sha256_canonical")
    return {
        "version": metadata["version"],
        "run_id": metadata["mlflow"]["run_id"],
        "artifact_sha256": metadata["artifact"]["sha256"],
        "local_artifact_sha256": local_hash,
        "artifact_hash_matches_metadata": local_hash == metadata["artifact"]["sha256"],
        "dataset_sha256": metadata["dataset"]["sha256"],
        "dataset_sha256_canonical": canonical or metadata["dataset"]["sha256"],
        "metadata_path": f"models/{EXPECTED_VERSION}/model_metadata.json",
    }


def _load_requests(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"request_id", "model_version", "payload_json", "expected_status"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise DeployError(
                "Colonne mancanti in richieste_monitoraggio.csv: "
                + ", ".join(sorted(missing))
            )
        for row in reader:
            payload = json.loads(row["payload_json"])
            features = payload.get("features") if isinstance(payload, dict) else None
            rows.append(
                {
                    "request_id": row["request_id"],
                    "model_version": row["model_version"],
                    "payload": payload,
                    "feature_count": len(features) if isinstance(features, list) else None,
                    "expected_status": int(row["expected_status"]),
                }
            )
    if [item["expected_status"] for item in rows] != EXPECTED_STATUSES:
        raise DeployError(
            "Sequenza inattesa nel CSV: status "
            f"{[item['expected_status'] for item in rows]} (attesi {EXPECTED_STATUSES})."
        )
    if [item["feature_count"] for item in rows] != [30, 30, 30, 29]:
        raise DeployError(
            "Sequenza inattesa nel CSV: conteggi feature "
            f"{[item['feature_count'] for item in rows]} (attesi [30, 30, 30, 29])."
        )
    return rows


def _wait_health(
    base_url: str, container_id: str, *, timeout: float
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error: str | None = None
    while time.monotonic() < deadline:
        if not _container_running(container_id):
            logs = _docker(["logs", "--tail", "80", container_id], check=False)
            raise DeployError(
                "Il container è terminato prima di /health.\n"
                + (logs.stdout or "")
                + (logs.stderr or "")
            )
        status, payload, _, error = _http_json(
            "GET", base_url.rstrip("/") + "/health", timeout=3.0
        )
        if status == 200 and payload and payload.get("status") == "ok":
            return payload
        last_error = error or f"HTTP {status}"
        time.sleep(0.5)
    raise DeployError(f"/health non raggiungibile entro {timeout:.0f}s: {last_error}")


def _container_running(container_id: str) -> bool:
    completed = _docker(
        ["inspect", "-f", "{{.State.Running}}", container_id], check=False
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def _wait_container_healthy(
    container_id: str, *, timeout: float
) -> str:
    deadline = time.monotonic() + timeout
    status = "unknown"
    while time.monotonic() < deadline:
        completed = _docker(["inspect", container_id], check=False)
        if completed.returncode != 0:
            raise DeployError("Container non più ispezionabile durante l'attesa health.")
        state = json.loads(completed.stdout)[0]["State"]
        if not state.get("Running"):
            raise DeployError("Il container si è arrestato durante l'attesa health.")
        status = (state.get("Health") or {}).get("Status", "not-configured")
        if status == "healthy":
            return status
        time.sleep(1.0)
    return status


def _send_request(
    base_url: str, item: dict[str, Any], index: int
) -> dict[str, Any]:
    body = json.dumps(item["payload"], allow_nan=False).encode("utf-8")
    started = time.perf_counter()
    status, payload, headers, error = _http_json(
        "POST",
        base_url.rstrip("/") + "/predict",
        body=body,
        headers={
            "Content-Type": "application/json",
            "X-Request-ID": item["request_id"],
        },
    )
    duration_ms = (time.perf_counter() - started) * 1000
    response_request_id = (payload or {}).get("request_id") if payload else None
    response_header_id = _header(headers, "X-Request-ID")
    prediction = (payload or {}).get("prediction") if payload else None
    served_version = (payload or {}).get("version") if payload else None
    served_run_id = (payload or {}).get("run_id") if payload else None
    expected_prediction = EXPECTED_PREDICTIONS[index]
    return {
        "request_id": item["request_id"],
        "target_version_in_csv": item["model_version"],
        "expected_status": item["expected_status"],
        "actual_status": status,
        "status_ok": status == item["expected_status"],
        "prediction": prediction,
        "expected_prediction_v1": expected_prediction,
        "prediction_ok": (
            prediction == expected_prediction
            if expected_prediction is not None
            else prediction is None
        ),
        "served_version": served_version,
        "served_run_id": served_run_id,
        "response_request_id": response_request_id,
        "response_header_request_id": response_header_id,
        "request_id_echo_ok": (
            response_request_id == item["request_id"]
            and response_header_id == item["request_id"]
        ),
        "response_detail": (payload or {}).get("detail") if payload else None,
        "response_code": (payload or {}).get("code") if payload else None,
        "duration_ms": round(duration_ms, 3),
        "transport_error": error,
        "log_entry": None,
        "log_correlated": False,
    }


def _read_request_log(container_id: str) -> tuple[list[dict[str, Any]], str]:
    completed = _docker(
        ["exec", container_id, "cat", CONTAINER_REQUEST_LOG], check=False
    )
    if completed.returncode != 0:
        raise DeployError(
            "Log richieste non leggibile dal container: "
            + (completed.stderr or completed.stdout).strip()
        )
    entries: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries, completed.stdout


def _container_packages(container_id: str) -> dict[str, Any]:
    code = (
        "import json,platform,importlib.metadata as m;"
        "names=['numpy','scikit-learn','joblib','fastapi','uvicorn','pydantic'];"
        "print(json.dumps({'python':platform.python_version(),"
        "'packages':{n:m.version(n) for n in names}}))"
    )
    completed = _docker(["exec", container_id, "python", "-c", code], check=False)
    if completed.returncode != 0:
        return {"error": (completed.stderr or completed.stdout).strip()}
    for line in reversed(completed.stdout.splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {"error": "output non leggibile"}


def _render_markdown(report: dict[str, Any]) -> str:
    passed = report["passed"]
    if not passed and report.get("error"):
        return "\n".join(
            [
                "# Deploy Docker - verifica del servizio",
                "",
                f"Generato (UTC): `{report['generated_at_utc']}`",
                f"Ambito: {report['scope']}",
                "Esito complessivo: **NON SUPERATO**",
                "",
                "## Errore",
                "",
                f"```text\n{report['error']}\n```",
                "",
                "Il report non contiene misure valide: correggere l'errore e",
                "rieseguire `python scripts/docker_smoke_test.py`.",
                "",
            ]
        )
    checks = report["checks"]
    image = report["image"]
    container = report["container"]
    expected = report["model_expected"]
    lines = [
        "# Deploy Docker - verifica del servizio",
        "",
        f"Generato (UTC): `{report['generated_at_utc']}`",
        f"Ambito: {report['scope']}",
        f"Esito complessivo: **{'SUPERATO' if passed else 'NON SUPERATO'}**",
        "",
        "## Immagine e container",
        "",
        "| Elemento | Valore |",
        "| --- | --- |",
        f"| Immagine | `{image['tag']}` |",
        f"| Image ID | `{image['id']}` |",
        f"| Dimensione compressa (`inspect .Size`) | {image['size_mb']:.1f} MiB |",
        f"| Dimensione su disco (`docker image ls`) | {image.get('disk_size', '-')} |",
        f"| Base | `{image['base_image']}` |",
        f"| Container | `{container['name']}` (`{container['id'][:12]}`) |",
        f"| Stato | `{container['state']}` / health `{container['health']}` |",
        f"| Utente | `{container['user']}` (uid `{container['uid']}`) |",
        f"| Root filesystem read-only | {'sì' if container['readonly_rootfs'] else 'no'} |",
        f"| Capabilities rimosse (`cap_drop`) | {', '.join(container['cap_drop']) or '-'} |",
        f"| Porta pubblicata | `{container['port']}` |",
        "",
        "## Identità del modello servito",
        "",
        "| Controllo | Atteso | Servito | Esito |",
        "| --- | --- | --- | --- |",
        f"| Versione | `{expected['version']}` | `{report['health_start'].get('active_version')}` | {'✅' if checks['identity_active_version'] else '❌'} |",
        f"| Run ID | `{expected['run_id']}` | `{report['health_start'].get('run_id')}` | {'✅' if checks['identity_run_id'] else '❌'} |",
        f"| Hash artefatto | `{expected['artifact_sha256']}` | `{report['health_start'].get('artifact_sha256')}` | {'✅' if checks['identity_artifact_sha256'] else '❌'} |",
        f"| Fingerprint canonico dataset | `{expected['dataset_sha256_canonical']}` | `{report['health_start'].get('dataset_sha256_canonical')}` | {'✅' if checks['identity_dataset_canonical'] else '❌'} |",
        "",
        "## Richieste operative",
        "",
        "| # | Request ID | Versione richiesta dal CSV | Status atteso | Status reale | Predizione | Versione servita | Log correlato |",
        "| ---: | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for index, item in enumerate(report["requests"], start=1):
        prediction = "-" if item["prediction"] is None else str(item["prediction"])
        served = item["served_version"] or "-"
        correlated = "sì" if item["log_correlated"] else "no"
        lines.append(
            f"| {index} | `{item['request_id']}` | {item['target_version_in_csv']} | "
            f"{item['expected_status']} | {item['actual_status']} | {prediction} | "
            f"{served} | {correlated} |"
        )
    metrics = report["metrics"]
    lines.extend(
        [
            "",
            "`req_02` indica `v2` nel CSV perché lo stesso file serve al drill S5-S6;",
            "questo deployment resta su v1 e non cambia versione. Il drill",
            "`v1 -> v2 -> v1` è documentato separatamente in `reports/drill_s5_s6.md`.",
            "",
            "## Metriche della finestra",
            "",
            f"- Richieste `POST /predict`: {metrics.get('requests')}",
            f"- Errori HTTP ≥ 400: {metrics.get('http_errors_ge_400')}",
            f"- Error rate: {metrics.get('error_rate')}",
            f"- p95: {metrics.get('p95_ms')} ms",
            f"- Finestra: {metrics.get('window_seconds')} s",
            "",
            "Il p95 dello smoke test riguarda quattro richieste e **non** sostituisce",
            "il p95 del gate S4 (30 richieste valide).",
            "",
            "## Versioni nel container",
            "",
            "| Componente | Versione |",
            "| --- | --- |",
            f"| Python | `{report['container_packages'].get('python')}` |",
        ]
    )
    for name, version in (report["container_packages"].get("packages") or {}).items():
        lines.append(f"| `{name}` | `{version}` |")
    lines.extend(
        [
            "",
            "## Controlli",
            "",
            "| Controllo | Esito |",
            "| --- | --- |",
        ]
    )
    for name, value in checks.items():
        lines.append(f"| `{name}` | {'✅' if value else '❌'} |")
    lines.extend(
        [
            "",
            "## Evidenze",
            "",
            "- `reports/docker_deploy.json` (questo report, versione strutturata)",
            "- `reports/docker/requests.jsonl` (log richieste, senza payload)",
            "- `reports/docker/container.log` (stdout/stderr del container)",
            "- `reports/docker/container_inspect.json`",
            "- `reports/docker/image_inspect.json`",
            "",
            "## Limiti",
            "",
        ]
    )
    lines.extend(f"- {limit}" for limit in report["limits"])
    lines.append("")
    return "\n".join(lines)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build, avvio e verifica black-box del servizio su Docker."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("LAB13_DOCKER_PORT", "8000")),
        help="Porta host pubblicata (default 8000 o LAB13_DOCKER_PORT).",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Riusa l'immagine esistente invece di eseguire docker compose build.",
    )
    parser.add_argument(
        "--keep-running",
        action="store_true",
        help="Lascia lo stack avviato al termine della verifica.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=90.0,
        help="Secondi massimi di attesa per /health e per lo stato healthy.",
    )
    parser.add_argument(
        "--output", default=str(REPORT_JSON), help="Report JSON di destinazione."
    )
    parser.add_argument(
        "--markdown", default=str(REPORT_MD), help="Report Markdown di destinazione."
    )
    return parser.parse_args(argv)


def _write_reports(report: dict[str, Any], output: Path, markdown: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    markdown.write_text(_render_markdown(report), encoding="utf-8")


def _failure_report(error: str, *, port: int) -> dict[str, Any]:
    return {
        "phase": "container",
        "generated_at_utc": _now(),
        "scope": (
            "deploy Docker locale del servizio v1; non è un deployment di "
            "produzione né una nuova misura del gate S4"
        ),
        "passed": False,
        "error": error,
        "port": port,
        "checks": {},
        "requests": [],
        "limits": ["Esecuzione non completata: il report non contiene misure valide."],
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    output = Path(args.output).expanduser()
    markdown = Path(args.markdown).expanduser()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    env = _compose_env(args.port)
    base_url = f"http://127.0.0.1:{args.port}"
    container_id: str | None = None
    build_seconds: float | None = None
    build_output_tail = ""

    try:
        docker_version = _ensure_docker()
        if not COMPOSE_FILE.is_file():
            raise DeployError(f"File compose non trovato: {COMPOSE_FILE}")

        # Stack precedente rimosso: il volume dei log riparte pulito e la porta
        # non resta occupata. `--keep-running` salta solo il cleanup finale.
        _down(remove_volumes=True)
        if _port_is_open(args.port):
            raise DeployError(
                f"La porta {args.port} è già in ascolto su 127.0.0.1. "
                "Usare --port con una porta libera."
            )

        if not args.no_build:
            started = time.perf_counter()
            build = _compose(
                ["build"], env=env, timeout=900.0
            )
            build_seconds = round(time.perf_counter() - started, 3)
            build_output_tail = "\n".join(
                (build.stdout + build.stderr).strip().splitlines()[-15:]
            )

        _compose(["up", "-d", "--force-recreate", "--remove-orphans"], env=env)
        completed = _compose(["ps", "-q", SERVICE_NAME], env=env)
        container_id = completed.stdout.strip().splitlines()[0] if completed.stdout.strip() else ""
        if not container_id:
            raise DeployError("docker compose non ha restituito un container per il servizio api.")
        if not _container_running(container_id):
            logs = _docker(["logs", "--tail", "120", container_id], check=False)
            raise DeployError(
                "Il container non è in esecuzione.\n" + (logs.stdout or "") + (logs.stderr or "")
            )

        health_start = _wait_health(base_url, container_id, timeout=args.timeout)
        docker_health = _wait_container_healthy(container_id, timeout=args.timeout)

        expected = _load_expected_model()
        identity = {
            "identity_active_version": (
                health_start.get("active_version") == expected["version"]
            ),
            "identity_run_id": health_start.get("run_id") == expected["run_id"],
            "identity_artifact_sha256": (
                health_start.get("artifact_sha256") == expected["artifact_sha256"]
            ),
            "identity_dataset_canonical": (
                health_start.get("dataset_sha256_canonical")
                == expected["dataset_sha256_canonical"]
            ),
        }

        requests = _load_requests(REQUESTS_PATH)
        results = [
            _send_request(base_url, item, index)
            for index, item in enumerate(requests)
        ]

        metrics_status, metrics, _, metrics_error = _http_json(
            "GET", base_url + "/metrics", timeout=10.0
        )
        if metrics_status != 200 or metrics is None:
            raise DeployError(
                f"/metrics non disponibile (HTTP {metrics_status}): {metrics_error}"
            )

        health_end = _wait_health(base_url, container_id, timeout=args.timeout)
        log_entries, raw_log = _read_request_log(container_id)
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        (EVIDENCE_DIR / "requests.jsonl").write_text(
            raw_log if raw_log.endswith("\n") else raw_log + "\n", encoding="utf-8"
        )

        container_log = _docker(
            ["logs", "--timestamps", container_id], check=False
        )
        (EVIDENCE_DIR / "container.log").write_text(
            (container_log.stdout or "") + (container_log.stderr or ""),
            encoding="utf-8",
        )

        inspect_completed = _docker(["inspect", container_id])
        inspect_data = json.loads(inspect_completed.stdout)[0]
        (EVIDENCE_DIR / "container_inspect.json").write_text(
            json.dumps(inspect_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        image_completed = _docker(["image", "inspect", IMAGE_TAG])
        image_data = json.loads(image_completed.stdout)[0]
        (EVIDENCE_DIR / "image_inspect.json").write_text(
            json.dumps(image_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        # `inspect .Size` è la dimensione compressa dei layer; `image ls`
        # riporta lo spazio su disco non compresso. Registriamo entrambe per
        # evitare di dichiarare una sola delle due misure come "la" dimensione.
        image_ls_completed = _docker(
            ["image", "ls", "--format", "{{.Size}}", IMAGE_TAG],
            check=False,
        )
        disk_size = image_ls_completed.stdout.strip().splitlines()
        disk_size = disk_size[0].strip() if disk_size else "-"

        uid_completed = _docker(["exec", container_id, "id", "-u"], check=False)
        uid = uid_completed.stdout.strip()
        packages = _container_packages(container_id)

        # Correlazione log e assenza di payload nei log.
        by_request: dict[str, list[dict[str, Any]]] = {}
        for entry in log_entries:
            request_id = entry.get("request_id")
            if isinstance(request_id, str):
                by_request.setdefault(request_id, []).append(entry)
        for item in results:
            candidates = [
                entry
                for entry in by_request.get(item["request_id"], [])
                if entry.get("path") == "/predict"
                and entry.get("http_status") == item["actual_status"]
            ]
            if candidates:
                item["log_entry"] = candidates[-1]
                item["log_correlated"] = True

        forbidden_keys = {"payload", "features", "payload_json"}
        logs_without_payload = all(
            not (forbidden_keys & set(entry)) for entry in log_entries
        )
        raw_log_text = json.dumps(log_entries, ensure_ascii=False)
        logs_without_payload = logs_without_payload and '"features"' not in raw_log_text

        requests_count = len(results)
        errors = sum(item["actual_status"] >= 400 for item in results)
        error_rate = errors / requests_count if requests_count else 0.0
        expected_metrics = {
            "requests": requests_count,
            "http_errors_ge_400": errors,
            "error_rate": round(error_rate, 6),
        }
        metrics_ok = (
            metrics.get("requests") == expected_metrics["requests"]
            and metrics.get("http_errors_ge_400") == expected_metrics["http_errors_ge_400"]
            and abs(
                float(metrics.get("error_rate", -1))
                - expected_metrics["error_rate"]
            )
            < 1e-9
            and metrics.get("p95_ms") is not None
            and metrics.get("window_seconds") == 900
        )

        config = inspect_data.get("Config") or {}
        host_config = inspect_data.get("HostConfig") or {}
        lab13_env: dict[str, str] = {}
        for entry in config.get("Env") or []:
            key, separator, value = str(entry).partition("=")
            if separator and key.startswith("LAB13_"):
                lab13_env[key] = value
        state = inspect_data.get("State") or {}
        port_bindings = (host_config.get("PortBindings") or {}).get("8000/tcp") or []
        published = (
            f"{port_bindings[0].get('HostIp', '')}:{port_bindings[0].get('HostPort', '')}"
            if port_bindings
            else "-"
        )
        cap_drop = host_config.get("CapDrop") or []
        security_opt = host_config.get("SecurityOpt") or []
        restart_count = inspect_data.get("RestartCount", 0)

        checks = {
            **identity,
            "local_artifact_hash_matches_metadata": expected[
                "artifact_hash_matches_metadata"
            ],
            "docker_healthcheck_healthy": docker_health == "healthy",
            "health_end_ok": health_end.get("status") == "ok",
            "state_unchanged_after_smoke": (
                health_end.get("active_version") == health_start.get("active_version")
                and health_end.get("run_id") == health_start.get("run_id")
                and health_end.get("artifact_sha256")
                == health_start.get("artifact_sha256")
            ),
            "statuses_ok": all(item["status_ok"] for item in results),
            "served_version_v1": all(
                item["served_version"] == EXPECTED_VERSION
                for item in results
                if item["actual_status"] == 200
            ),
            "predictions_ok": all(item["prediction_ok"] for item in results),
            "request_id_echo_ok": all(
                item["request_id_echo_ok"] for item in results
            ),
            "logs_correlated": all(item["log_correlated"] for item in results),
            "logs_without_payload": logs_without_payload,
            "metrics_ok": metrics_ok,
            "non_root_user": uid == "10001",
            "read_only_rootfs": bool(host_config.get("ReadonlyRootfs")),
            "cap_drop_all": "ALL" in cap_drop,
            "no_new_privileges": any(
                "no-new-privileges" in option for option in security_opt
            ),
            "healthcheck_configured": bool(config.get("Healthcheck")),
            "no_restart_loop": restart_count == 0,
            "container_packages_match_artifact": (
                (packages.get("packages") or {}).get("numpy") == "2.4.6"
                and (packages.get("packages") or {}).get("scikit-learn") == "1.8.0"
                and (packages.get("packages") or {}).get("joblib") == "1.5.3"
            ),
        }
        passed = all(checks.values())

        report = {
            "phase": "container",
            "generated_at_utc": _now(),
            "scope": (
                "deploy Docker locale del servizio v1; non è un deployment di "
                "produzione né una nuova misura del gate S4"
            ),
            "passed": passed,
            "host": {
                "platform": platform.platform(),
                "python": platform.python_version(),
            },
            "docker": docker_version,
            "image": {
                "tag": IMAGE_TAG,
                "id": image_data.get("Id", inspect_data.get("Image")),
                "short_id": (image_data.get("Id") or "")[:19],
                "size_bytes": image_data.get("Size"),
                "size_mb": (image_data.get("Size") or 0) / (1024 * 1024),
                "disk_size": disk_size,
                "created": image_data.get("Created"),
                "architecture": image_data.get("Architecture"),
                "os": image_data.get("Os"),
                "base_image": image_data.get("Config", {})
                .get("Labels", {})
                .get("org.opencontainers.image.base.name", "python:3.11.9-slim"),
                "labels": (image_data.get("Config", {}) or {}).get("Labels") or {},
                "repo_digests": image_data.get("RepoDigests") or [],
                "build_seconds": build_seconds,
                "build_output_tail": build_output_tail,
            },
            "container": {
                "id": container_id,
                "name": (inspect_data.get("Name") or "").lstrip("/"),
                "image": config.get("Image"),
                "state": state.get("Status"),
                "running": state.get("Running"),
                "health": (state.get("Health") or {}).get("Status"),
                "started_at": state.get("StartedAt"),
                "restart_count": restart_count,
                "user": config.get("User"),
                "uid": uid,
                "readonly_rootfs": bool(host_config.get("ReadonlyRootfs")),
                "cap_drop": cap_drop,
                "security_opt": security_opt,
                "port": published,
                "network_mode": host_config.get("NetworkMode"),
                "mounts": inspect_data.get("Mounts") or [],
                "env": lab13_env,
            },
            "deployment": {
                "base_url": base_url,
                "port": args.port,
                "compose_file": "docker-compose.yml",
                "service": SERVICE_NAME,
                "image_tag": IMAGE_TAG,
                "logs_volume": "lab13-progetto3-logs",
                "keep_running": bool(args.keep_running),
            },
            "model_expected": expected,
            "health_start": health_start,
            "health_end": health_end,
            "requests": results,
            "metrics": metrics,
            "metrics_expected": expected_metrics,
            "container_packages": packages,
            "checks": checks,
            "limits": [
                "Docker locale single-node: non è un deployment cloud, Kubernetes o con registry esterno.",
                "Nessun TLS, autenticazione o rate limiting: la porta è pubblicata solo su 127.0.0.1.",
                "Lo smoke test non è un test di carico; il p95 su quattro richieste non sostituisce il gate S4.",
                "I dati sono sintetici e didattici: le metriche non misurano spedizioni reali.",
                "Il deployment serve la v1 e lascia /admin/version disabilitato; il drill v1 -> v2 -> v1 resta quello locale S5-S6.",
                "La validation assegnata non è un test indipendente e non simula una validazione temporale.",
            ],
        }

        _write_reports(report, output, markdown)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if not passed:
            failed = [name for name, value in checks.items() if not value]
            print(
                "DEPLOY DOCKER NON SUPERATO: " + ", ".join(failed),
                file=sys.stderr,
            )
            return 1
        print(
            "DEPLOY DOCKER SUPERATO: immagine e container sani, modello v1 "
            "verificato, 200/200/200/422, log correlati.",
            file=sys.stderr,
        )
        return 0
    except Exception as exc:
        report = _failure_report(str(exc), port=args.port)
        _write_reports(report, output, markdown)
        print(f"DEPLOY DOCKER NON SUPERATO: {exc}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_running:
            _down(remove_volumes=True)
        elif container_id:
            print(
                "Stack lasciato avviato. Per fermarlo: docker compose down -v",
                file=sys.stderr,
            )


if __name__ == "__main__":
    raise SystemExit(main())
