#!/usr/bin/env python
"""Valuta il gate congelato e produce il report senza modificare lo stato attivo."""

from __future__ import annotations

import json
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def decide(accuracy_ok: bool | None, p95_ok: bool | None, error_ok: bool | None,
           comparable: bool) -> tuple[str, list[str]]:
    missing = []
    if not comparable:
        missing.append("comparabilità v1/v2 (fingerprint e ID validation)")
    for label, value in (("accuracy v2 vs v1", accuracy_ok), ("p95 HTTP", p95_ok), ("error rate HTTP", error_ok)):
        if value is None:
            missing.append(label)
    if missing:
        return "BLOCCATO", missing
    if not all((accuracy_ok, p95_ok, error_ok)):
        return "NON SUPERATO", []
    return "SUPERATO", []


def _read(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Valuta S4 rispetto alla baseline selezionata.")
    parser.add_argument("--baseline-report", default="reports/v1_valutazione.json")
    parser.add_argument("--baseline-model-dir", default="models/v1")
    parser.add_argument("--candidate-report", default="reports/v2_valutazione.json")
    parser.add_argument("--candidate-model-dir", default="models/v2")
    parser.add_argument("--probe-report", default="reports/probe_v2.json")
    args = parser.parse_args()

    def project_path(value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else ROOT / path

    baseline_report_path = project_path(args.baseline_report)
    baseline_model_dir = project_path(args.baseline_model_dir)
    candidate_report_path = project_path(args.candidate_report)
    candidate_model_dir = project_path(args.candidate_model_dir)
    baseline = _read(baseline_report_path)
    candidate = _read(candidate_report_path)
    probe = _read(project_path(args.probe_report))
    gate = _read(ROOT / "config" / "gate.json") or {}
    v1_meta = _read(baseline_model_dir / "model_metadata.json") or {}
    v2_meta = _read(candidate_model_dir / "model_metadata.json") or {}
    v1_ids = v1_meta.get("validation", {}).get("ids")
    v2_ids = v2_meta.get("validation", {}).get("ids")
    v1_sha = (baseline or {}).get("dataset", {}).get("sha256")
    v2_sha = (candidate or {}).get("dataset", {}).get("sha256")
    comparable = bool(v1_ids and v2_ids and v1_ids == v2_ids and v1_sha and v1_sha == v2_sha)
    v1_acc = (baseline or {}).get("metrics", {}).get("accuracy")
    v2_acc = (candidate or {}).get("metrics", {}).get("accuracy")
    accuracy_ok = (v2_acc >= v1_acc) if comparable and v1_acc is not None and v2_acc is not None else None
    http = (probe or {}).get("http") if probe else None
    http_identity_ok = bool(http and http.get("identity_verified"))
    p95_limit = gate.get("requirements", {}).get("latency_p95_ms", {}).get("threshold", 120)
    error_limit = gate.get("requirements", {}).get("error_rate", {}).get("threshold", 0.01)
    p95 = http.get("p95_ms") if http_identity_ok else None
    http_error_rate = http.get("error_rate") if http_identity_ok else None
    p95_ok = p95 <= p95_limit if p95 is not None else None
    error_ok = http_error_rate <= error_limit if http_error_rate is not None else None
    decision, missing = decide(accuracy_ok, p95_ok, error_ok, comparable)
    if http is None:
        missing.append("probe HTTP locale della candidata")
        decision = "BLOCCATO"
    elif not http_identity_ok:
        missing.append("identità server HTTP non corrispondente all'artefatto v2")
        decision = "BLOCCATO"
    report = {
        "phase": "S4",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "policy_id": gate.get("policy_id", "lab13-gate-v1"),
        "frozen_policy": gate.get("frozen", True),
        "decision": decision,
        "missing": missing,
        "criteria": {
            "accuracy": {"v1": v1_acc, "v2": v2_acc, "operator": ">=", "threshold": "accuracy v1", "passed": accuracy_ok},
            "http_p95_ms": {"measured": p95, "operator": "<=", "threshold": p95_limit, "passed": p95_ok},
            "http_error_rate": {"measured": http_error_rate, "operator": "<=", "threshold": error_limit, "denominator": "30 richieste HTTP valide", "passed": error_ok},
        },
        "comparability": {"same_validation_ids": bool(v1_ids and v2_ids and v1_ids == v2_ids), "same_dataset_sha256": bool(v1_sha and v1_sha == v2_sha), "passed": comparable},
        "candidate": {
            "run_id": (candidate or {}).get("mlflow", {}).get("run_id"),
            "artifact_sha256": (candidate or {}).get("artifact", {}).get("sha256"),
            "dataset_sha256": v2_sha,
            "validation_metrics": (candidate or {}).get("metrics"),
        },
        "baseline": {
            "report_path": str(baseline_report_path.relative_to(ROOT)) if baseline_report_path.is_relative_to(ROOT) else baseline_report_path.name,
            "model_directory": str(baseline_model_dir.relative_to(ROOT)) if baseline_model_dir.is_relative_to(ROOT) else baseline_model_dir.name,
            "run_id": (baseline or {}).get("mlflow", {}).get("run_id"),
            "artifact_sha256": (baseline or {}).get("artifact", {}).get("sha256"),
            "dataset_sha256": v1_sha,
            "is_original_v1": baseline_model_dir == ROOT / "models" / "v1",
            "comparison_basis": (
                "artefatti v1 originali"
                if baseline_model_dir == ROOT / "models" / "v1"
                else "baseline isolata riaddestrata sul CSV incluso; artefatti v1 originali non usati"
            ),
            "original_v1_dataset_sha256": (
                (_read(ROOT / "models" / "v1" / "model_metadata.json") or {})
                .get("dataset", {}).get("sha256")
            ),
        },
        "probe": {
            "in_process": (probe or {}).get("in_process"),
            "http": http,
            "http_probe_required_for_gate": True,
            "server_identity_verified": http_identity_ok,
        },
        "active_version_changed": False,
        "limitations": [
            "Soglie lette da config/gate.json e mai ricalibrate dopo i risultati.",
            "La latenza del solo pipeline.predict in-process non sostituisce il p95 HTTP richiesto.",
            "v2 resta candidata; nessuna attivazione o prova di rollback è stata eseguita.",
        ],
    }
    output_json = ROOT / "reports" / "gate_s4.json"
    output_md = ROOT / "reports" / "gate_s4.md"
    output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Decisione gate S4", "", f"- Decisione: **{decision}**",
        f"- Policy: `{report['policy_id']}` (congelata: sì)",
        f"- Accuracy baseline selezionata: {v1_acc if v1_acc is not None else 'non disponibile'}; v2: {v2_acc if v2_acc is not None else 'non disponibile'}; soglia: v2 ≥ baseline",
        f"- p95 HTTP v2: {p95 if p95 is not None else 'non misurato'} ms; soglia ≤ {p95_limit} ms",
        f"- Error rate HTTP: {http_error_rate if http_error_rate is not None else 'non misurato'}; soglia ≤ {error_limit}",
        f"- Dataset e ID validation comparabili: {'sì' if comparable else 'no/non dimostrato'}",
    ]
    if missing:
        lines.extend(["", "Misure mancanti o non comparabili:", ""])
        lines.extend(f"- {item}" for item in missing)
    lines.extend(["", f"Baseline di confronto: `{report['baseline']['model_directory']}` (originale v1: {'sì' if report['baseline']['is_original_v1'] else 'no; riaddestrata sul CSV incluso'}).", f"Hash CSV incluso: `{v2_sha}`; hash dichiarato dagli artefatti v1 originali: `{report['baseline']['original_v1_dataset_sha256']}`.", "La versione attiva non è stata modificata. v2 non è stata attivata e il drill S5-S6 non è stato eseguito.", ""])
    output_md.write_text("\n".join(lines), encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
