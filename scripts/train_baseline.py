#!/usr/bin/env python
"""Training della baseline v1 (S2): fit sul train, valutazione e artefatti.

Il comando è ripetibile: stesse righe di ``train``, stessa pipeline, stesso seed.
La validation distribuita serve solo alla valutazione. La versione richiesta non
viene mai sovrascritta; MLflow scrive in un store locale configurabile.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lab13.config import Settings, display_path  # noqa: E402
from lab13.contracts import (  # noqa: E402
    CLASS_ORDER,
    FEATURE_COUNT,
    FEATURE_NAMES,
    POSITIVE_CLASS,
)
from lab13.data import DatasetValidationError, load_dataset  # noqa: E402

# Le dipendenze del training (scikit-learn, joblib, mlflow) servono solo qui:
# l'audit S1 continua a funzionare con la sola libreria standard.
try:
    from lab13.model_io import (
        ArtifactConflictError,
        require_new_version,
        save_version,
        software_versions,
    )
    from lab13.tracking import TrackingUnavailable, log_run, tracked_run
    from lab13.training import (
        BASELINE_SEED,
        BaselineConfig,
        build_baseline_pipeline,
        evaluate,
        fit_train,
    )
except ImportError as _exc:  # pragma: no cover - ambiente senza dipendenze
    DEPENDENCY_ERROR = str(_exc)
else:
    DEPENDENCY_ERROR = None

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass

STATUS = (
    "Baseline valutata sulla validation distribuita. Serving API, candidata v2, "
    "gate misurato, attivazione e rollback non sono implementati: v1 non è "
    "dichiarata pronta al deployment."
)

REQUESTS_NOTE = (
    "richieste_monitoraggio.csv è input operativo per le prove API: non è entrato "
    "nel fit né nella valutazione."
)


def _format_metric(value: float | None) -> str:
    return "n/d (denominatore 0)" if value is None else f"{value:.4f}"


def _metrics_for_tracking(evaluation: Any, dataset: Any) -> dict[str, float]:
    counts = evaluation.counts
    metrics: dict[str, float] = {
        "accuracy": evaluation.accuracy,
        "precision_class_1": evaluation.precision,
        "recall_class_1": evaluation.recall,
        "confusion_tp": counts["tp"],
        "confusion_fp": counts["fp"],
        "confusion_fn": counts["fn"],
        "confusion_tn": counts["tn"],
        "train_rows": len(dataset.train),
        "validation_rows": len(dataset.validation),
    }
    return {key: float(value) for key, value in metrics.items() if value is not None}


def _build_metadata(
    *,
    config: BaselineConfig,
    dataset: Any,
    settings: Settings,
    evaluation: Any,
    run: Any,
    generated_at: str,
) -> dict[str, Any]:
    """Metadati versionati: versione, run, fingerprint, feature, split, metriche."""

    return {
        "version": config.version,
        "phase": "S2",
        "created_at_utc": generated_at,
        "status": STATUS,
        "model": {
            "params": config.params,
            "random_state": config.seed,
            "reproducibility": {
                "seed": config.seed,
                "claim": (
                    "due esecuzioni sugli stessi dati con gli stessi parametri "
                    "producono le stesse predizioni; verificato in "
                    "tests/test_training.py"
                ),
            },
        },
        "feature_names": list(FEATURE_NAMES),
        "feature_count": FEATURE_COUNT,
        "feature_order_source": "src/lab13/contracts.py (FEATURE_NAMES)",
        "classes": {
            "order": list(CLASS_ORDER),
            "positive_class": POSITIVE_CLASS,
            "labels": {
                "0": "consegna entro la scadenza promessa",
                "1": "consegna dopo la scadenza promessa",
            },
        },
        "dataset": {
            "path": display_path(settings.dataset.path),
            "default_path": display_path(settings.dataset.default_path),
            "origin": settings.dataset.origin,
            "origin_label": settings.dataset.origin_label,
            "sha256": dataset.sha256,
            "row_count": len(dataset),
            "header": list(dataset.header),
            "excluded_from_X": ["record_id", "split", "target"],
        },
        "split": {
            "column": "split",
            "regenerated": False,
            "train_rows": len(dataset.train),
            "validation_rows": len(dataset.validation),
            "counts_by_split_and_class": dataset.counts_by_split_and_class(),
        },
        "training_policy": {
            "fit_split": "train",
            "scaler_fit_on": "train",
            "validation_used_for": "valutazione didattica",
            "validation_used_for_fit": False,
            "validation_used_for_tuning_or_param_choice": False,
            "requests_csv_used_for_training": False,
            "requests_note": REQUESTS_NOTE,
        },
        "validation": {
            "ids": list(evaluation.record_ids),
            "predictions_file": "validation_predictions.json",
            "metrics": evaluation.as_dict(),
        },
        "mlflow": {
            "tracking_uri": settings.tracking_uri.display,
            "tracking_uri_origin": settings.tracking_uri.origin_label,
            "external_connection_required": False,
            "experiment_name": run.experiment_name,
            "experiment_id": run.experiment_id,
            "run_id": run.run_id,
            "run_name": run.run_name,
            "logged_params": config.params,
            "logged_metrics": _metrics_for_tracking(evaluation, dataset),
        },
        "environment": software_versions(),
        "requests_file": {
            "path": display_path(settings.requests.path),
            "used_for_training": False,
        },
        "checker": "src/lab13/model_io.py:load_version",
    }


def _build_report(
    *,
    metadata: dict[str, Any],
    saved: Any,
    settings: Settings,
    report_paths: dict[str, Path],
    generated_at: str,
) -> dict[str, Any]:
    """Report di valutazione: metriche, run ID, file dati, split e artefatto."""

    return {
        "phase": "S2",
        "version": metadata["version"],
        "generated_at_utc": generated_at,
        "status": STATUS,
        "mlflow": metadata["mlflow"],
        "dataset": {
            "path": metadata["dataset"]["path"],
            "origin_label": metadata["dataset"]["origin_label"],
            "sha256": metadata["dataset"]["sha256"],
        },
        "split": metadata["split"],
        "training_policy": metadata["training_policy"],
        "pipeline": metadata["model"],
        "metrics": metadata["validation"]["metrics"],
        "artifact": {
            "filename": saved.artifact_path.name,
            "sha256": saved.artifact_sha256,
            "size_bytes": saved.artifact_path.stat().st_size,
        },
        "artifacts": {
            "directory": display_path(saved.directory),
            "pipeline": display_path(saved.artifact_path),
            "metadata": display_path(saved.metadata_path),
            "predictions": display_path(saved.predictions_path),
            "report_json": display_path(report_paths["json"]),
            "report_markdown": display_path(report_paths["markdown"]),
        },
        "warnings": list(settings.warnings),
        "limits": [
            "Dati interamente sintetici: le metriche non misurano spedizioni reali.",
            "La validation assegnata non è un test indipendente.",
            "Il gate (config/gate.json) non è misurato in S2: mancano servizio, "
            "candidata, p95 ed error rate.",
            "v1 non è attivata: S3-S6 non sono implementate.",
        ],
    }


def _render_markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    counts = metrics["counts"]
    mlflow = report["mlflow"]
    artifact = report["artifact"]
    matrix = metrics["confusion_matrix"]
    params = report["pipeline"]["params"]

    lines: list[str] = [
        f"# Valutazione baseline {report['version']} - S2",
        "",
        f"Generato (UTC): `{report['generated_at_utc']}`",
        f"Stato: {report['status']}",
        "",
        "## Run MLflow",
        "",
        f"- Run ID: `{mlflow['run_id']}` (`{mlflow['run_name']}`)",
        f"- Experiment: `{mlflow['experiment_name']}` (id {mlflow['experiment_id']})",
        f"- Tracking URI locale: `{mlflow['tracking_uri']}` ({mlflow['tracking_uri_origin']})",
        "- Connessione esterna richiesta: no",
        "",
        "## Dati e split",
        "",
        f"- File dataset: `{report['dataset']['path']}` ({report['dataset']['origin_label']})",
        f"- SHA-256 CSV: `{report['dataset']['sha256']}`",
        f"- Righe di fit: {report['split']['train_rows']} (`train`)",
        f"- Righe di valutazione: {report['split']['validation_rows']} (`validation`)",
        "- Split distribuito non rigenerato: sì",
        "- Validation mai usata per fit, tuning o scelta dei parametri: sì",
        "- `record_id`, `split`, `target` esclusi da `X`: sì",
        f"- File richieste: {REQUESTS_NOTE}",
        "",
        "## Pipeline salvata",
        "",
        f"- Passi: {' → '.join(params['pipeline_steps'])}",
        f"- Parametri: `{json.dumps(params, ensure_ascii=False)}`",
        f"- Seed registrato: {report['pipeline']['random_state']}",
        "",
        "## Metriche sulla validation",
        "",
        "| Metrica | Valore |",
        "| --- | ---: |",
        f"| Accuracy | {_format_metric(metrics['accuracy'])} |",
        f"| Precision classe 1 | {_format_metric(metrics['precision_class_1'])} |",
        f"| Recall classe 1 | {_format_metric(metrics['recall_class_1'])} |",
        "",
        "## Matrice di confusione (ordine classi [0, 1])",
        "",
        "Righe = classe reale, colonne = classe predetta.",
        "",
        "| | Predetto 0 | Predetto 1 |",
        "| --- | ---: | ---: |",
        f"| Reale 0 | {matrix[0][0]} (TN) | {matrix[0][1]} (FP) |",
        f"| Reale 1 | {matrix[1][0]} (FN) | {matrix[1][1]} (TP) |",
        "",
        f"Conteggi: TN={counts['tn']}, FP={counts['fp']}, "
        f"FN={counts['fn']}, TP={counts['tp']} su {metrics['rows']} righe.",
        "",
        "## Artefatti",
        "",
        f"- Cartella versione: `{report['artifacts']['directory']}`",
        f"- Pipeline serializzata: `{report['artifacts']['pipeline']}` "
        f"({artifact['size_bytes']} byte)",
        f"- SHA-256 artefatto: `{artifact['sha256']}`",
        f"- Metadati: `{report['artifacts']['metadata']}`",
        f"- Predizioni e ID validation: `{report['artifacts']['predictions']}`",
        f"- Report JSON: `{report['artifacts']['report_json']}`",
        "",
        "## Ripetere l'esecuzione",
        "",
        "```powershell",
        f"python scripts/train_baseline.py --dataset \".\\dataset (1).csv\" --version {report['version']}",
        "```",
        "Una seconda esecuzione sulla stessa versione termina con errore esplicito e "
        "non tocca la cartella già salvata. Per una prova senza toccare v1 usare "
        "`--version v2` (fase 3) o `--models-dir` e `--report-dir` di prova.",
        "",
        "## Limiti",
        "",
    ]
    lines.extend(f"- {limit}" for limit in report["limits"])
    if report["warnings"]:
        lines.extend(["", "## Avvisi", ""])
        lines.extend(f"- {warning}" for warning in report["warnings"])
    lines.append("")
    return "\n".join(lines)


def _print_summary(report: dict[str, Any]) -> None:
    metrics = report["metrics"]
    counts = metrics["counts"]
    print(f"Training baseline {report['version']} - Progetto 3")
    print(f"Dataset: {report['dataset']['path']} ({report['dataset']['origin_label']})")
    print(f"SHA-256 CSV: {report['dataset']['sha256']}")
    print(
        f"Fit: {report['split']['train_rows']} righe train; "
        f"valutazione: {report['split']['validation_rows']} righe validation"
    )
    print(f"Run MLflow: {report['mlflow']['run_id']} ({report['mlflow']['tracking_uri']})")
    print(f"Accuracy: {_format_metric(metrics['accuracy'])}")
    print(f"Precision classe 1: {_format_metric(metrics['precision_class_1'])}")
    print(f"Recall classe 1: {_format_metric(metrics['recall_class_1'])}")
    print(
        f"Confusione [0,1]: TN={counts['tn']} FP={counts['fp']} "
        f"FN={counts['fn']} TP={counts['tp']}"
    )
    print(f"Artefatto: {report['artifacts']['pipeline']} ({report['artifact']['sha256']})")
    print(f"Metadati: {report['artifacts']['metadata']}")
    print(f"Report: {report['artifacts']['report_markdown']}")
    print(f"Report: {report['artifacts']['report_json']}")
    for warning in report["warnings"]:
        print(f"AVVISO: {warning}")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Addestra la baseline S2, la valuta sulla validation e la versiona."
    )
    parser.add_argument("--dataset", help="Percorso del CSV dataset.")
    parser.add_argument("--version", default="v1", help="Versione da creare (default v1).")
    parser.add_argument(
        "--models-dir", default=str(PROJECT_ROOT / "models"), help="Cartella delle versioni."
    )
    parser.add_argument(
        "--report-dir", default=str(PROJECT_ROOT / "reports"), help="Cartella dei report."
    )
    parser.add_argument(
        "--tracking-uri",
        help="Tracking URI MLflow locale (default: mlruns nel progetto o l'ambiente).",
    )
    parser.add_argument(
        "--experiment", help="Nome dell'esperimento MLflow (default: LAB13_MLFLOW_EXPERIMENT)."
    )
    parser.add_argument(
        "--seed", type=int, default=BASELINE_SEED, help="Seed del classificatore."
    )
    parser.add_argument("--C", type=float, default=1.0, help="C di LogisticRegression.")
    parser.add_argument("--solver", default="liblinear", help="Solver di LogisticRegression.")
    parser.add_argument("--max-iter", type=int, default=1000, help="max_iter del classificatore.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if DEPENDENCY_ERROR is not None:
        print(
            "TRAINING BLOCCATO: dipendenze mancanti (scikit-learn, joblib, mlflow).\n"
            f"Errore di import: {DEPENDENCY_ERROR}\n"
            "Installare i pacchetti di requirements.txt e rieseguire.",
            file=sys.stderr,
        )
        return 3

    args = _parse_args(argv)
    settings = Settings.load(
        dataset_path=args.dataset,
        tracking_uri=args.tracking_uri,
        mlflow_experiment_name=args.experiment,
    )

    try:
        dataset = load_dataset(settings.dataset.path)
    except DatasetValidationError as exc:
        print("TRAINING FALLITO: dataset non valido", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 2

    config = BaselineConfig(
        version=args.version,
        seed=args.seed,
        C=args.C,
        solver=args.solver,
        max_iter=args.max_iter,
    )

    train = dataset.train
    validation = dataset.validation
    try:
        pipeline = fit_train(build_baseline_pipeline(config), train)
        evaluation = evaluate(pipeline, validation)
    except Exception as exc:
        print(f"TRAINING FALLITO: {exc}", file=sys.stderr)
        return 1

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    report_paths = {
        "json": Path(args.report_dir).expanduser() / f"{config.version}_valutazione.json",
        "markdown": Path(args.report_dir).expanduser() / f"{config.version}_valutazione.md",
    }

    # La versione è rivendicata prima di aprire il run: una ripetizione non
    # produce un fit né un run MLflow vuoto sopra la baseline già salvata.
    try:
        require_new_version(version=config.version, models_dir=args.models_dir)
    except ArtifactConflictError as exc:
        print(f"TRAINING BLOCCATO: {exc}", file=sys.stderr)
        return 4

    # Anche i report della versione non si sovrascrivono: il report deve restare
    # agganciato al run che ha prodotto l'artefatto.
    for report_path in (report_paths["json"], report_paths["markdown"]):
        if report_path.exists():
            print(
                f"TRAINING BLOCCATO: il report {display_path(report_path)} esiste già "
                "e non viene sovrascritto. Usa --report-dir per una cartella di prova "
                "oppure --version per una versione nuova.",
                file=sys.stderr,
            )
            return 4

    # Il run MLflow è aperto prima del salvataggio: il run ID entra nei metadati.
    saved: Any = None
    try:
        with tracked_run(
            tracking_uri=settings.tracking_uri.value,
            experiment_name=settings.mlflow_experiment_name,
            run_name=f"{config.version}-baseline",
        ) as run:
            metadata = _build_metadata(
                config=config,
                dataset=dataset,
                settings=settings,
                evaluation=evaluation,
                run=run,
                generated_at=generated_at,
            )
            saved = save_version(
                version=config.version,
                models_dir=args.models_dir,
                pipeline=pipeline,
                metadata=metadata,
                prediction_rows=evaluation.prediction_rows(),
            )
            report = _build_report(
                metadata=metadata,
                saved=saved,
                settings=settings,
                report_paths=report_paths,
                generated_at=generated_at,
            )
            report_dir = report_paths["json"].parent
            report_dir.mkdir(parents=True, exist_ok=True)
            report_json = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
            report_paths["json"].write_text(report_json, encoding="utf-8")
            report_paths["markdown"].write_text(
                _render_markdown(report), encoding="utf-8"
            )
            log_run(
                params={
                    **config.params,
                    "version": config.version,
                    "feature_count": FEATURE_COUNT,
                    "train_rows": len(train),
                    "validation_rows": len(validation),
                    "dataset_sha256": dataset.sha256,
                    "dataset_path": display_path(settings.dataset.path),
                },
                metrics=_metrics_for_tracking(evaluation, dataset),
                tags={
                    "phase": "S2",
                    "version": config.version,
                    "dataset_sha256": dataset.sha256,
                    "split_column": "split (distribuito, non rigenerato)",
                    "fit_split": "train",
                    "validation_used_for": "valutazione didattica (no fit, no tuning)",
                    "requests_csv_used": "false",
                    "artifact_sha256": saved.artifact_sha256,
                    "artifact_path": display_path(saved.artifact_path),
                    "metadata_path": display_path(saved.metadata_path),
                    "config": json.dumps(config.params, ensure_ascii=False),
                    "status": STATUS,
                },
                artifacts=[
                    saved.artifact_path,
                    saved.metadata_path,
                    saved.predictions_path,
                    report_paths["json"],
                ],
            )
    except ArtifactConflictError as exc:
        print(f"TRAINING BLOCCATO: {exc}", file=sys.stderr)
        return 4
    except TrackingUnavailable as exc:
        # Una versione senza run coerente non va lasciata in ``models/``: si
        # rimuove solo ciò che questa esecuzione ha scritto.
        if saved is not None:
            shutil.rmtree(saved.directory, ignore_errors=True)
        print(
            f"TRAINING BLOCCATO: tracciamento MLflow non disponibile.\n{exc}\n"
            f"Nessuna versione conservata: {config.version} rimossa.",
            file=sys.stderr,
        )
        return 3
    except OSError as exc:
        if saved is not None:
            shutil.rmtree(saved.directory, ignore_errors=True)
        print(
            f"TRAINING FALLITO: scrittura artefatti/report fallita ({exc}). "
            f"Nessuna versione conservata: {config.version} rimossa.",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        if saved is not None:
            shutil.rmtree(saved.directory, ignore_errors=True)
        print(f"TRAINING FALLITO: {exc}\nNessuna versione conservata.", file=sys.stderr)
        return 1

    _print_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
