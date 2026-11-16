#!/usr/bin/env python
"""Probe ripetibile della candidata: 3 warm-up e 30 misure."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lab13.config import Settings  # noqa: E402
from lab13.contracts import validate_inference_payload  # noqa: E402
from lab13.data import load_dataset  # noqa: E402
from lab13.model_io import load_version  # noqa: E402

WARMUPS = 3
MEASUREMENTS = 30


def percentile95(values: list[float]) -> float | None:
    return sorted(values)[math.ceil(0.95 * len(values)) - 1] if values else None


def load_candidate_payload(path: Path) -> tuple[dict[str, Any], str]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    candidate = next((row for row in rows if row.get("model_version") == "v2"), None)
    if candidate is None:
        raise ValueError("richieste_monitoraggio.csv non contiene una richiesta v2.")
    payload = json.loads(candidate["payload_json"])
    validate_inference_payload(payload)
    return payload, candidate.get("request_id", "probe-v2")


def run_in_process(model: Any, payload: dict[str, Any]) -> dict[str, Any]:
    features = validate_inference_payload(payload)
    for _ in range(WARMUPS):
        model.pipeline.predict([features])
    durations: list[float] = []
    for _ in range(MEASUREMENTS):
        started = time.perf_counter()
        model.pipeline.predict([features])
        durations.append((time.perf_counter() - started) * 1000)
    return {
        "scope": "solo pipeline.predict in-process; esclude HTTP, parsing e middleware",
        "warmups": WARMUPS,
        "measurements": MEASUREMENTS,
        "p95_ms": percentile95(durations),
        "error_rate": 0.0,
        "errors": 0,
    }


def run_http(base_url: str, payload: dict[str, Any], candidate: Any) -> dict[str, Any]:
    durations: list[float] = []
    errors = 0
    statuses: list[int] = []
    identity: dict[str, Any] | None = None
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/health", timeout=10) as response:
            identity = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        identity = None
    identity_verified = bool(
        identity
        and identity.get("active_version") == candidate.version
        and identity.get("run_id") == candidate.run_id
        and identity.get("artifact_sha256") == candidate.artifact_sha256
    )
    for index in range(WARMUPS + MEASUREMENTS):
        body = json.dumps(payload, allow_nan=False).encode("utf-8")
        request = urllib.request.Request(
            base_url.rstrip("/") + "/predict",
            data=body,
            headers={"Content-Type": "application/json", "X-Request-ID": f"probe-v2-{index:03d}"},
            method="POST",
        )
        started = time.perf_counter()
        status = 0
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                status = response.status
                response.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.read()
        except (urllib.error.URLError, TimeoutError):
            status = 599
        elapsed = (time.perf_counter() - started) * 1000
        if index >= WARMUPS:
            durations.append(elapsed)
            statuses.append(status)
            errors += status >= 400
    return {
        "scope": "POST /predict in HTTP locale; warm-up esclusi dalle 30 misure",
        "warmups": WARMUPS,
        "measurements": MEASUREMENTS,
        "p95_ms": percentile95(durations),
        "error_rate": errors / MEASUREMENTS,
        "errors": errors,
        "statuses": statuses,
        "server_identity": identity,
        "identity_verified": identity_verified,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", help="URL di un server FastAPI già avviato.")
    parser.add_argument("--output", default=str(ROOT / "reports" / "probe_v2.json"))
    args = parser.parse_args()
    settings = Settings.load()
    payload, source_request_id = load_candidate_payload(settings.requests.path)
    dataset = load_dataset(settings.dataset.path)
    candidate = load_version(
        ROOT / "models" / "v2",
        expected_version="v2",
        expected_dataset_canonical_sha256=dataset.sha256_canonical,
    )
    report: dict[str, Any] = {
        "phase": "S3-S4",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version": candidate.version,
        "run_id": candidate.run_id,
        "artifact_sha256": candidate.artifact_sha256,
        "dataset_sha256": dataset.sha256,
        "dataset_sha256_canonical": dataset.sha256_canonical,
        "request_source": str(settings.requests.path.name),
        "request_id_source": source_request_id,
        "in_process": run_in_process(candidate, payload),
        "http": run_http(args.base_url, payload, candidate) if args.base_url else None,
        "http_status": "measured" if args.base_url else "not run: avviare uvicorn e passare --base-url",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
