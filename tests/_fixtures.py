"""Fixture sintetiche per i test S2+.

Queste righe servono solo a testare training e versionamento in cartelle
temporanee: non sostituiscono il dataset assegnato e non sono mai usate per il
training reale o per la valutazione.
"""

from __future__ import annotations

import csv
from pathlib import Path

from lab13.contracts import EXPECTED_COLUMNS


def synthetic_rows() -> list[list[object]]:
    """1000 righe con i conteggi attesi per split e classe."""

    rows: list[list[object]] = []
    serial = 0
    for split, target, count in (
        ("train", 0, 463),
        ("train", 1, 337),
        ("validation", 0, 116),
        ("validation", 1, 84),
    ):
        for _ in range(count):
            serial += 1
            features = [float(serial % 1300 + 10)] + [float(serial % 7)] * 29
            rows.append([f"id_{serial:04d}", split, *features, target])
    return rows


def write_dataset_csv(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(EXPECTED_COLUMNS)
        writer.writerows(synthetic_rows())
    return path
