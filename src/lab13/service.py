"""API FastAPI osservabile per la classificazione delle consegne."""

from __future__ import annotations

import json
import logging
import math
import os
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import PROJECT_ROOT
from .contracts import PayloadValidationError, validate_inference_payload
from .version_state import (
    DEFAULT_TRANSITIONS_PATH,
    VersionStateError,
    apply_transition,
    read_state,
    validate_action,
    validate_mode,
    validate_version_name,
)

WINDOW_SECONDS = 15 * 60
MAX_REQUEST_ID_LENGTH = 128
logger = logging.getLogger("lab13.service")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = getattr(record, "event_fields", {})
        return json.dumps(fields, ensure_ascii=False, separators=(",", ":"))


if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _request_id(request: Request) -> str:
    supplied = request.headers.get("X-Request-ID", "").strip()
    if supplied and len(supplied) <= MAX_REQUEST_ID_LENGTH and all(
        char.isprintable() and char not in "\r\n" for char in supplied
    ):
        return supplied
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def create_app(
    *,
    active_config_path: str | Path | None = None,
    loaded_model: Any | None = None,
    allow_version_switch: bool | None = None,
    transitions_path: str | Path | None = None,
) -> FastAPI:
    """Crea l'app; in produzione il modello viene caricato allo startup.

    ``loaded_model`` consente test in-process isolati dal filesystem degli
    artefatti. Il percorso di produzione verifica invece stato, fingerprint e
    artefatto quando il server si avvia. Il cambio di versione a caldo è
    disponibile solo se ``LAB13_ALLOW_VERSION_SWITCH=1`` (o se il parametro
    ``allow_version_switch`` è esplicitamente vero): è un'operazione locale per
    il drill, non un endpoint di produzione.
    """
    import sys

    if str(PROJECT_ROOT / "src") not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
    state_path = Path(
        active_config_path
        or os.environ.get("LAB13_ACTIVE_VERSION_PATH", PROJECT_ROOT / "config" / "active_version.json")
    ).expanduser()
    if allow_version_switch is None:
        allow_version_switch = os.environ.get("LAB13_ALLOW_VERSION_SWITCH", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
    transitions_file = Path(
        transitions_path
        or os.environ.get("LAB13_TRANSITIONS_PATH", DEFAULT_TRANSITIONS_PATH)
    ).expanduser()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.loaded_model is None:
            from .data import load_dataset
            from .model_io import load_version

            try:
                state = read_state(state_path, default_version="v1")
                version = state["version"]
            except VersionStateError as exc:
                raise RuntimeError(str(exc)) from exc
            dataset_path = Path(
                os.environ.get("LAB13_DATASET_PATH", PROJECT_ROOT / "dataset (1).csv")
            )
            dataset = load_dataset(dataset_path)
            app.state.loaded_model = load_version(
                PROJECT_ROOT / "models" / version,
                expected_version=version,
                expected_dataset_canonical_sha256=dataset.sha256_canonical,
            )
        yield

    app = FastAPI(
        title="Lab 13 - servizio inferenza", version="1.0.0", lifespan=lifespan
    )
    app.state.loaded_model = loaded_model
    app.state.active_config_path = str(state_path)
    app.state.transitions_path = str(transitions_file)
    app.state.allow_version_switch = bool(allow_version_switch)
    app.state.prediction_events = deque()
    app.state.metric_lock = Lock()
    app.state.version_lock = Lock()

    def log_event(request_id: str, status: int, duration_ms: float, is_prediction: bool) -> None:
        model = app.state.loaded_model
        event = {
            "timestamp": _now(),
            "request_id": request_id,
            "version": model.version if model is not None else None,
            "run_id": model.run_id if model is not None else None,
            "http_status": status,
            "duration_ms": round(duration_ms, 3),
            "path": "/predict" if is_prediction else "other",
        }
        logger.info("request", extra={"event_fields": event})
        log_path = Path(os.environ.get("LAB13_REQUEST_LOG", PROJECT_ROOT / "logs" / "requests.jsonl"))
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        except OSError:
            logger.exception("Impossibile scrivere il log richieste")
        if is_prediction:
            with app.state.metric_lock:
                app.state.prediction_events.append((time.monotonic(), status, duration_ms))

    @app.middleware("http")
    async def observe_request(request: Request, call_next: Any) -> Any:
        request_id = _request_id(request)
        request.state.request_id = request_id
        is_prediction = request.url.path == "/predict" and request.method == "POST"
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            log_event(request_id, 500, duration_ms, is_prediction)
            raise
        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        log_event(request_id, response.status_code, duration_ms, is_prediction)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=422,
            content={"detail": "Richiesta JSON non conforme al contratto.", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        model = app.state.loaded_model
        if model is None:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return {
            "status": "ok",
            "active_version": model.version,
            "run_id": model.run_id,
            "artifact_sha256": model.artifact_sha256,
            "dataset_sha256": getattr(model, "dataset_sha256", None),
            "dataset_sha256_canonical": (
                model.metadata.get("dataset", {}).get("sha256_canonical")
                if getattr(model, "metadata", None)
                else None
            ),
        }

    @app.post("/admin/version")
    async def switch_version(request: Request) -> JSONResponse:
        """Cambia la versione servita (solo drill locale) e registra la transizione."""
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        if not app.state.allow_version_switch:
            return JSONResponse(
                status_code=404,
                content={
                    "detail": "Cambio versione disabilitato: impostare LAB13_ALLOW_VERSION_SWITCH=1.",
                    "request_id": request_id,
                },
            )
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"detail": "Corpo JSON non valido.", "request_id": request_id},
            )
        if not isinstance(body, dict):
            return JSONResponse(
                status_code=400,
                content={"detail": "Atteso un oggetto JSON.", "request_id": request_id},
            )

        action = body.get("action", "activate")
        mode = body.get("mode", "drill")
        try:
            validate_action(action)
            validate_mode(mode)
            state = read_state(app.state.active_config_path, default_version="v1")
            if action == "rollback":
                target_version = body.get("version") or state.get("previous_version")
                if not target_version:
                    return JSONResponse(
                        status_code=409,
                        content={
                            "detail": "Nessuna versione precedente registrata per il rollback.",
                            "request_id": request_id,
                        },
                    )
            else:
                target_version = body.get("version")
            validate_version_name(target_version)
        except VersionStateError as exc:
            return JSONResponse(
                status_code=400,
                content={"detail": str(exc), "request_id": request_id},
            )

        model = app.state.loaded_model
        if model is None:
            return JSONResponse(
                status_code=503,
                content={"detail": "Modello non pronto", "request_id": request_id},
            )
        if target_version == model.version:
            return JSONResponse(
                content={
                    "changed": False,
                    "active_version": model.version,
                    "run_id": model.run_id,
                    "artifact_sha256": model.artifact_sha256,
                    "request_id": request_id,
                }
            )

        from .data import load_dataset
        from .model_io import load_version

        dataset_path = Path(
            os.environ.get("LAB13_DATASET_PATH", PROJECT_ROOT / "dataset (1).csv")
        )
        with app.state.version_lock:
            before = app.state.loaded_model
            try:
                dataset = load_dataset(dataset_path)
                new_model = load_version(
                    PROJECT_ROOT / "models" / target_version,
                    expected_version=target_version,
                    expected_dataset_canonical_sha256=dataset.sha256_canonical,
                )
            except Exception as exc:
                return JSONResponse(
                    status_code=409,
                    content={
                        "detail": f"Versione {target_version} non caricabile: {exc}",
                        "request_id": request_id,
                    },
                )

            before_identity = {
                "version": before.version,
                "run_id": before.run_id,
                "artifact_sha256": before.artifact_sha256,
            }
            after_identity = {
                "version": new_model.version,
                "run_id": new_model.run_id,
                "artifact_sha256": new_model.artifact_sha256,
            }
            app.state.loaded_model = new_model
            try:
                new_state = apply_transition(
                    state_path=app.state.active_config_path,
                    transitions_path=app.state.transitions_path,
                    before=before_identity,
                    after=after_identity,
                    action=action,
                    mode=mode,
                    source="service-admin",
                    dataset_sha256_canonical=dataset.sha256_canonical,
                )
            except Exception as exc:
                app.state.loaded_model = before
                return JSONResponse(
                    status_code=500,
                    content={
                        "detail": f"Transizione non registrata: {exc}",
                        "request_id": request_id,
                    },
                )

        return JSONResponse(
            content={
                "changed": True,
                "previous_version": before.version,
                "active_version": new_model.version,
                "run_id": new_model.run_id,
                "artifact_sha256": new_model.artifact_sha256,
                "dataset_sha256_canonical": dataset.sha256_canonical,
                "mode": mode,
                "action": action,
                "state": new_state,
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )

    @app.get("/metrics")
    async def metrics() -> dict[str, Any]:
        cutoff = time.monotonic() - WINDOW_SECONDS
        with app.state.metric_lock:
            while app.state.prediction_events and app.state.prediction_events[0][0] < cutoff:
                app.state.prediction_events.popleft()
            events = list(app.state.prediction_events)
        total = len(events)
        errors = sum(status >= 400 for _, status, _ in events)
        durations = sorted(duration for _, _, duration in events)
        p95 = durations[math.ceil(0.95 * total) - 1] if total else None
        return {
            "window_seconds": WINDOW_SECONDS,
            "window_semantics": "finestra mobile: richieste POST /predict completate negli ultimi 15 minuti",
            "requests": total,
            "http_errors_ge_400": errors,
            "error_rate": errors / total if total else 0.0,
            "p95_ms": round(p95, 3) if p95 is not None else None,
        }

    @app.post("/predict")
    async def predict(request: Request) -> JSONResponse:
        request_id = request.state.request_id
        model = app.state.loaded_model
        if model is None:
            return JSONResponse(status_code=503, content={"detail": "Modello non pronto", "request_id": request_id})
        try:
            payload = await request.json()
            features = validate_inference_payload(payload)
        except PayloadValidationError as exc:
            return JSONResponse(
                status_code=422,
                content={"detail": str(exc), "code": exc.code, "request_id": request_id},
                headers={"X-Request-ID": request_id},
            )
        except Exception:
            return JSONResponse(
                status_code=422,
                content={"detail": "Corpo non è JSON valido.", "request_id": request_id},
                headers={"X-Request-ID": request_id},
            )
        prediction = int(model.pipeline.predict([features])[0])
        return JSONResponse(
            content={
                "prediction": prediction,
                "version": model.version,
                "run_id": model.run_id,
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )

    return app


app = create_app()
