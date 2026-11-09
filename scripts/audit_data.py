#!/usr/bin/env python
"""Audit S1 del dataset: schema, integrità, conteggi e fingerprint."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lab13.config import Settings, display_path  # noqa: E402
from lab13.data import (  # noqa: E402
    DatasetValidationError,
    dataset_audit_dict,
    load_dataset,
    sha256_file,
)

# Il report è UTF-8; allineiamo anche l'output della console su Windows.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass

REQUESTS_USAGE_NOTE = (
    "File operativo per le prove API: non è un dataset di training o valutazione "
    "e non deve essere passato al lettore del dataset."
)


def _requests_info(settings: Settings) -> dict[str, Any]:
    item = settings.requests
    exists = item.path.is_file()
    info: dict[str, Any] = {
        "requests_path": display_path(item.path),
        "default_path": display_path(item.default_path),
        "origin": item.origin,
        "origin_label": item.origin_label,
        "exists": exists,
        "size_bytes": None,
        "sha256": None,
        "usage_note": REQUESTS_USAGE_NOTE,
    }
    if exists:
        try:
            info["size_bytes"] = item.path.stat().st_size
            info["sha256"] = sha256_file(item.path)
        except OSError as exc:
            info["error"] = f"Impossibile calcolare i metadati: {exc}"
    return info


def _build_report(
    settings: Settings,
    dataset_report: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    return {
        "phase": "S1",
        "generated_at_utc": generated_at,
        "dataset": {
            **dataset_report,
            "dataset_path": display_path(dataset_report["dataset_path"]),
            "default_path": display_path(settings.dataset.default_path),
            "origin": settings.dataset.origin,
            "origin_label": settings.dataset.origin_label,
            "fallback_used": settings.dataset.fallback_used,
            "source_header": list(dataset_report.get("source_header", [])),
        },
        "requests": _requests_info(settings),
        "checks": {
            "file_present_and_not_empty": "ok",
            "header_unique_and_complete": "ok",
            "record_ids_present_and_unique": "ok",
            "splits_train_validation": "ok",
            "targets_binary": "ok",
            "features_numeric_and_finite": "ok",
            "expected_counts": "ok",
            "feature_order_canonical": "ok",
        },
        "warnings": list(settings.warnings),
    }


def _render_markdown(report: dict[str, Any]) -> str:
    dataset = report["dataset"]
    requests = report["requests"]
    counts = dataset["counts_by_split_and_class"]

    lines: list[str] = [
        "# Audit dati - S1",
        "",
        f"Generato (UTC): `{report['generated_at_utc']}`",
        "",
        "## Dataset",
        "",
        f"- Percorso: `{dataset['dataset_path']}`",
        f"- Provenienza: {dataset['origin_label']}",
        f"- SHA-256 dei byte CSV: `{dataset['dataset_sha256']}`",
        f"- Righe: {dataset['row_count']}",
        f"- Feature canoniche: {dataset['feature_count']}",
        "",
        "## Conteggi per split e classe",
        "",
        "| Split | target 0 | target 1 | Totale |",
        "| --- | ---: | ---: | ---: |",
    ]
    for split_name in ("train", "validation", "all"):
        row = counts[split_name]
        lines.append(
            f"| {split_name} | {row['0']} | {row['1']} | {row['total']} |"
        )

    lines.extend(
        [
            "",
            "## ID delle righe di validation",
            "",
            f"Totale: {len(dataset['validation_ids'])}",
            "",
            "```text",
            *dataset["validation_ids"],
            "```",
            "",
            "## File richieste",
            "",
            f"- Percorso: `{requests['requests_path']}`",
            f"- Presente: {'sì' if requests['exists'] else 'no'}",
        ]
    )
    if requests["sha256"]:
        lines.append(f"- SHA-256: `{requests['sha256']}`")
    lines.extend(
        [
            f"- Uso: {REQUESTS_USAGE_NOTE}",
            "",
            "## Controlli superati",
            "",
        ]
    )
    for check, status in report["checks"].items():
        lines.append(f"- `{check}`: {status}")
    if report["warnings"]:
        lines.extend(["", "## Avvisi", ""])
        lines.extend(f"- {warning}" for warning in report["warnings"])
    lines.append("")
    return "\n".join(lines)


def _print_summary(report: dict[str, Any], report_dir: Path | None) -> None:
    dataset = report["dataset"]
    requests = report["requests"]
    counts = dataset["counts_by_split_and_class"]

    print("Audit dati S1 - Progetto 3 (ritardi nelle consegne logistiche)")
    print(f"Dataset: {dataset['dataset_path']}")
    print(f"Origine: {dataset['origin_label']}")
    print(f"SHA-256: {dataset['dataset_sha256']}")
    print(f"Righe: {dataset['row_count']}; feature canoniche: {dataset['feature_count']}")
    for split_name in ("train", "validation"):
        row = counts[split_name]
        print(
            f"  {split_name}: {row['total']} "
            f"(target 0={row['0']}, target 1={row['1']})"
        )
    print(f"ID validation: {len(dataset['validation_ids'])} (elenco nei report)")
    print(f"Richieste: {requests['requests_path']}")
    print(f"  {REQUESTS_USAGE_NOTE}")
    for warning in report["warnings"]:
        print(f"AVVISO: {warning}")
    if report_dir is not None:
        print(f"Report: {report_dir / 'data_audit.json'}")
        print(f"Report: {report_dir / 'data_audit.md'}")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Valida il dataset S1 e produce il report di audit."
    )
    parser.add_argument(
        "--dataset",
        help="Percorso del CSV dataset (predefinito: percorso assegnato o fallback locale).",
    )
    parser.add_argument(
        "--requests",
        help="Percorso del CSV richieste (solo inventario; non usato per training).",
    )
    parser.add_argument(
        "--report-dir",
        default=str(PROJECT_ROOT / "reports"),
        help="Cartella in cui scrivere data_audit.json e data_audit.md.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Esegue i controlli senza scrivere i report.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = Settings.load(
        dataset_path=args.dataset,
        requests_path=args.requests,
    )

    try:
        dataset = load_dataset(settings.dataset.path)
    except DatasetValidationError as exc:
        print("AUDIT FALLITO", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 2

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    dataset_report = dataset_audit_dict(dataset)
    dataset_report["source_header"] = list(dataset.header)
    report = _build_report(settings, dataset_report, generated_at)

    report_dir: Path | None = None
    if not args.no_write:
        report_dir = Path(args.report_dir).expanduser()
        try:
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / "data_audit.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (report_dir / "data_audit.md").write_text(
                _render_markdown(report), encoding="utf-8"
            )
        except OSError as exc:
            print(f"Impossibile scrivere i report: {exc}", file=sys.stderr)
            return 1

    _print_summary(report, report_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
