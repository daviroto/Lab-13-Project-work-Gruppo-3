"""Test del lettore dataset e dei controlli di schema/integrità.

Le righe sintetiche definite in questo file servono esclusivamente a testare il
lettore in file temporanei: non sostituiscono il dataset assegnato e non vengono
mai usate per training o valutazione.
"""

from __future__ import annotations

import csv
import hashlib
import re
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lab13.config import Settings  # noqa: E402
from lab13.contracts import (  # noqa: E402
    EXPECTED_COLUMNS,
    EXPECTED_SPLIT_CLASS_COUNTS,
    FEATURE_NAMES,
    RECORD_ID_COLUMN,
    SPLIT_COLUMN,
    TARGET_COLUMN,
)
from lab13.data import (  # noqa: E402
    DatasetValidationError,
    load_dataset,
    sha256_bytes,
)


def _valid_rows() -> list[list[object]]:
    """1000 righe sintetiche con i conteggi attesi, solo per test del lettore."""

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


def _write_csv(
    path: Path,
    rows: list[list[object]],
    header: tuple[str, ...] = EXPECTED_COLUMNS,
    *,
    encoding: str = "utf-8",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=encoding, newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


class DatasetReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.path = self.tmp / "dataset.csv"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_valid_dataset_with_expected_counts(self) -> None:
        _write_csv(self.path, _valid_rows())
        dataset = load_dataset(self.path)

        self.assertEqual(len(dataset), 1000)
        self.assertEqual(dataset.feature_names, FEATURE_NAMES)
        self.assertEqual(len(dataset.train), 800)
        self.assertEqual(len(dataset.validation), 200)
        self.assertEqual(
            dict(Counter(dataset.train.targets)), {0: 463, 1: 337}
        )
        self.assertEqual(
            dict(Counter(dataset.validation.targets)), {0: 116, 1: 84}
        )
        self.assertEqual(len(dataset.validation_ids), 200)
        self.assertEqual(
            dataset.counts_by_split_and_class()["all"],
            {"0": 579, "1": 421, "total": 1000},
        )
        self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", dataset.sha256))
        self.assertTrue(
            all(len(row.features) == 30 for row in dataset.rows)
        )
        self.assertNotIn("record_id", dataset.feature_names)
        self.assertNotIn("split", dataset.feature_names)
        self.assertNotIn("target", dataset.feature_names)

    def test_loader_does_not_modify_file(self) -> None:
        _write_csv(self.path, _valid_rows())
        before = self.path.read_bytes()
        load_dataset(self.path)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(sha256_bytes(before), hashlib.sha256(before).hexdigest())

    def test_columns_are_reordered_to_canonical_feature_order(self) -> None:
        features = {name: float(index) for index, name in enumerate(FEATURE_NAMES)}
        header = ("target", *reversed(FEATURE_NAMES), "split", "record_id")
        row = {
            "record_id": "r1",
            "split": "train",
            "target": 1,
            **features,
        }
        _write_csv(
            self.path,
            [[row[name] for name in header]],
            header=header,
        )
        dataset = load_dataset(self.path, enforce_expected_counts=False)
        self.assertEqual(
            dataset.rows[0].features,
            tuple(float(index) for index in range(30)),
        )

    def test_utf8_bom_is_accepted(self) -> None:
        _write_csv(self.path, _valid_rows()[:1], encoding="utf-8-sig")
        dataset = load_dataset(self.path, enforce_expected_counts=False)
        self.assertEqual(dataset.rows[0].record_id, "id_0001")

    def test_missing_file(self) -> None:
        with self.assertRaises(DatasetValidationError) as ctx:
            load_dataset(self.tmp / "assente.csv")
        self.assertIn("File non trovato", str(ctx.exception))

    def test_path_is_not_a_file(self) -> None:
        with self.assertRaises(DatasetValidationError) as ctx:
            load_dataset(self.tmp)
        self.assertIn("non è un file", str(ctx.exception))

    def test_empty_file(self) -> None:
        self.path.write_bytes(b"")
        with self.assertRaises(DatasetValidationError) as ctx:
            load_dataset(self.path)
        self.assertIn("File vuoto", str(ctx.exception))

    def test_header_only(self) -> None:
        _write_csv(self.path, [])
        with self.assertRaises(DatasetValidationError) as ctx:
            load_dataset(self.path)
        self.assertIn("Nessuna riga dati", str(ctx.exception))

    def test_duplicate_header(self) -> None:
        header = (*EXPECTED_COLUMNS, FEATURE_NAMES[0])
        _write_csv(self.path, [], header=header)
        with self.assertRaises(DatasetValidationError) as ctx:
            load_dataset(self.path)
        self.assertIn("colonne duplicate", str(ctx.exception))

    def test_missing_column(self) -> None:
        header = tuple(name for name in EXPECTED_COLUMNS if name != FEATURE_NAMES[-1])
        _write_csv(self.path, [], header=header)
        with self.assertRaises(DatasetValidationError) as ctx:
            load_dataset(self.path)
        message = str(ctx.exception)
        self.assertIn("Colonne mancanti", message)
        self.assertIn(FEATURE_NAMES[-1], message)

    def test_unexpected_column(self) -> None:
        header = (*EXPECTED_COLUMNS, "colonna_extra")
        _write_csv(self.path, [], header=header)
        with self.assertRaises(DatasetValidationError) as ctx:
            load_dataset(self.path)
        message = str(ctx.exception)
        self.assertIn("Colonne inattese", message)
        self.assertIn("colonna_extra", message)

    def test_missing_record_id(self) -> None:
        row = ["", "train", *([1.0] * 30), 0]
        _write_csv(self.path, [row])
        with self.assertRaises(DatasetValidationError) as ctx:
            load_dataset(self.path, enforce_expected_counts=False)
        self.assertIn("record_id mancante", str(ctx.exception))

    def test_duplicate_record_id(self) -> None:
        row1 = ["dup", "train", *([1.0] * 30), 0]
        row2 = ["dup", "validation", *([2.0] * 30), 1]
        _write_csv(self.path, [row1, row2])
        with self.assertRaises(DatasetValidationError) as ctx:
            load_dataset(self.path, enforce_expected_counts=False)
        self.assertIn("record_id duplicato", str(ctx.exception))

    def test_unexpected_split(self) -> None:
        row = ["r1", "test", *([1.0] * 30), 0]
        _write_csv(self.path, [row])
        with self.assertRaises(DatasetValidationError) as ctx:
            load_dataset(self.path, enforce_expected_counts=False)
        self.assertIn("split inatteso", str(ctx.exception))

    def test_invalid_target(self) -> None:
        for target in ("2", "1.0", "yes", ""):
            with self.subTest(target=target):
                row = ["r1", "train", *([1.0] * 30), target]
                _write_csv(self.path, [row])
                with self.assertRaises(DatasetValidationError) as ctx:
                    load_dataset(self.path, enforce_expected_counts=False)
                self.assertIn("target non valido", str(ctx.exception))

    def test_non_numeric_feature(self) -> None:
        features = [1.0] * 30
        features[4] = "abc"
        row = ["r1", "train", *features, 0]
        _write_csv(self.path, [row])
        with self.assertRaises(DatasetValidationError) as ctx:
            load_dataset(self.path, enforce_expected_counts=False)
        message = str(ctx.exception)
        self.assertIn(FEATURE_NAMES[4], message)
        self.assertIn("non numerica", message)

    def test_non_finite_feature(self) -> None:
        for value in ("nan", "inf", "-inf", "1e309"):
            with self.subTest(value=value):
                features = [1.0] * 30
                features[0] = value
                row = ["r1", "train", *features, 0]
                _write_csv(self.path, [row])
                with self.assertRaises(DatasetValidationError) as ctx:
                    load_dataset(self.path, enforce_expected_counts=False)
                self.assertIn("non finita", str(ctx.exception))

    def test_underscore_number_is_not_a_csv_number(self) -> None:
        features = [1.0] * 30
        features[0] = "1_000"
        row = ["r1", "train", *features, 0]
        _write_csv(self.path, [row])
        with self.assertRaises(DatasetValidationError) as ctx:
            load_dataset(self.path, enforce_expected_counts=False)
        self.assertIn("non numerica", str(ctx.exception))

    def test_wrong_field_count(self) -> None:
        row = ["r1", "train", *([1.0] * 29), 0]
        _write_csv(self.path, [row])
        with self.assertRaises(DatasetValidationError) as ctx:
            load_dataset(self.path, enforce_expected_counts=False)
        self.assertIn("campi", str(ctx.exception))

    def test_blank_row(self) -> None:
        _write_csv(self.path, [[]])
        with self.assertRaises(DatasetValidationError) as ctx:
            load_dataset(self.path, enforce_expected_counts=False)
        self.assertIn("riga vuota", str(ctx.exception))

    def test_expected_count_mismatch(self) -> None:
        _write_csv(self.path, _valid_rows()[:2])
        with self.assertRaises(DatasetValidationError) as ctx:
            load_dataset(self.path)
        self.assertIn("Totale righe 2, atteso 1000", str(ctx.exception))

    def test_validation_ids_keep_file_order(self) -> None:
        rows = [
            ["r1", "train", *([1.0] * 30), 0],
            ["r2", "validation", *([2.0] * 30), 0],
            ["r3", "validation", *([3.0] * 30), 1],
        ]
        _write_csv(self.path, rows)
        dataset = load_dataset(self.path, enforce_expected_counts=False)
        self.assertEqual(dataset.validation_ids, ("r2", "r3"))
        self.assertEqual(dataset.validation.record_ids, ("r2", "r3"))


class AssignedDatasetTests(unittest.TestCase):
    def test_assigned_dataset_if_available(self) -> None:
        settings = Settings.load()
        if not settings.dataset.path.is_file():
            self.skipTest(
                f"Dataset assegnato non disponibile: {settings.dataset.path}"
            )

        dataset = load_dataset(settings.dataset.path)
        self.assertEqual(len(dataset), 1000)
        self.assertEqual(dataset.feature_names, FEATURE_NAMES)
        self.assertEqual(
            dataset.counts_by_split_and_class()["train"],
            {
                "0": EXPECTED_SPLIT_CLASS_COUNTS["train"][0],
                "1": EXPECTED_SPLIT_CLASS_COUNTS["train"][1],
                "total": 800,
            },
        )
        self.assertEqual(
            dataset.counts_by_split_and_class()["validation"],
            {
                "0": EXPECTED_SPLIT_CLASS_COUNTS["validation"][0],
                "1": EXPECTED_SPLIT_CLASS_COUNTS["validation"][1],
                "total": 200,
            },
        )
        self.assertEqual(len(dataset.validation_ids), 200)
        self.assertEqual(len(set(dataset.validation_ids)), 200)
        self.assertEqual(len(set(row.record_id for row in dataset.rows)), 1000)
        self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", dataset.sha256))
        self.assertEqual(
            dataset.header,
            (
                RECORD_ID_COLUMN,
                SPLIT_COLUMN,
                *FEATURE_NAMES,
                TARGET_COLUMN,
            ),
        )

    def test_requests_csv_is_not_accepted_as_dataset(self) -> None:
        settings = Settings.load()
        if not settings.requests.path.is_file():
            self.skipTest(
                f"File richieste non disponibile: {settings.requests.path}"
            )

        with self.assertRaises(DatasetValidationError) as ctx:
            load_dataset(
                settings.requests.path,
                enforce_expected_counts=False,
            )
        message = str(ctx.exception)
        self.assertIn("Colonne mancanti", message)
        self.assertIn("Colonne inattese", message)


if __name__ == "__main__":
    unittest.main()
