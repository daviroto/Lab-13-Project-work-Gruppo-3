"""Lettura e validazione del dataset assegnato.

Il lettore separa in modo esplicito:

* le 30 feature canoniche, unico input del modello;
* ``record_id``, ``split`` e ``target``, metadati che non entrano mai in ``X``.

Il file viene letto una sola volta in modalità binaria: i byte originali sono
usati per il fingerprint SHA-256 e non vengono mai riscritti.
"""

from __future__ import annotations

import csv
import hashlib
import io
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import (
    EXPECTED_COLUMNS,
    EXPECTED_SPLIT_CLASS_COUNTS,
    EXPECTED_SPLITS,
    EXPECTED_TOTAL_ROWS,
    FEATURE_NAMES,
    RECORD_ID_COLUMN,
    SPLIT_COLUMN,
    TARGET_COLUMN,
    TRAIN_SPLIT,
    VALIDATION_SPLIT,
)

_NUMERIC_RE = re.compile(
    r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
)
_MAX_REPORTED_ISSUES = 50


class DatasetValidationError(ValueError):
    """Il dataset non rispetta lo schema o i conteggi attesi."""

    def __init__(
        self,
        issues: list[str],
        *,
        source: Path,
        sha256: str | None = None,
    ) -> None:
        self.issues = tuple(issues)
        self.source = source
        self.sha256 = sha256
        fingerprint = f" (SHA-256: {sha256})" if sha256 else ""
        details = "\n".join(f"  - {issue}" for issue in issues)
        super().__init__(f"Dataset non valido: {source}{fingerprint}\n{details}")


@dataclass(frozen=True, slots=True)
class DatasetRow:
    """Una riga validata; le feature sono già nell'ordine canonico."""

    record_id: str
    split: str
    target: int
    features: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class DatasetSplit:
    """Vista immutabile di uno split, pronta per il training."""

    name: str
    record_ids: tuple[str, ...]
    features: tuple[tuple[float, ...], ...]
    targets: tuple[int, ...]

    def __len__(self) -> int:
        return len(self.record_ids)


@dataclass(frozen=True, slots=True)
class LoadedDataset:
    """Dataset validato con metadati di provenienza e integrità."""

    source: Path
    sha256: str
    header: tuple[str, ...]
    feature_names: tuple[str, ...]
    rows: tuple[DatasetRow, ...]

    def __len__(self) -> int:
        return len(self.rows)

    def split(self, name: str) -> DatasetSplit:
        if name not in EXPECTED_SPLITS:
            raise ValueError(
                f"Split '{name}' non previsto; ammessi: {', '.join(EXPECTED_SPLITS)}."
            )
        selected = tuple(row for row in self.rows if row.split == name)
        return DatasetSplit(
            name=name,
            record_ids=tuple(row.record_id for row in selected),
            features=tuple(row.features for row in selected),
            targets=tuple(row.target for row in selected),
        )

    @property
    def train(self) -> DatasetSplit:
        return self.split(TRAIN_SPLIT)

    @property
    def validation(self) -> DatasetSplit:
        return self.split(VALIDATION_SPLIT)

    @property
    def validation_ids(self) -> tuple[str, ...]:
        return tuple(
            row.record_id for row in self.rows if row.split == VALIDATION_SPLIT
        )

    def counts_by_split_and_class(self) -> dict[str, dict[str, int]]:
        """Restituisce conteggi ``target 0/1/total`` per split e complessivi."""

        counts: dict[str, dict[str, int]] = {
            name: {"0": 0, "1": 0, "total": 0} for name in EXPECTED_SPLITS
        }
        counts["all"] = {"0": 0, "1": 0, "total": 0}
        for row in self.rows:
            key = str(row.target)
            counts[row.split][key] += 1
            counts[row.split]["total"] += 1
            counts["all"][key] += 1
            counts["all"]["total"] += 1
        return counts


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    source = Path(path).expanduser()
    with source.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _fail(
    issues: list[str],
    *,
    source: Path,
    sha256: str | None = None,
    max_reported: int = _MAX_REPORTED_ISSUES,
) -> None:
    if not issues:
        return
    shown = issues[:max_reported]
    hidden = len(issues) - len(shown)
    if hidden > 0:
        shown.append(f"... altri {hidden} errori non mostrati.")
    raise DatasetValidationError(shown, source=source, sha256=sha256)


def _parse_feature(raw: str) -> tuple[float | None, str | None]:
    text = raw.strip()
    if not text:
        return None, "mancante"
    try:
        value = float(text)
    except ValueError:
        return None, f"non numerica (valore {raw!r})"
    if not math.isfinite(value):
        return None, f"non finita (valore {raw!r})"
    if _NUMERIC_RE.fullmatch(text) is None:
        return None, f"non numerica (valore {raw!r})"
    return value, None


def _check_expected_counts(
    rows: tuple[DatasetRow, ...],
) -> list[str]:
    issues: list[str] = []
    if len(rows) != EXPECTED_TOTAL_ROWS:
        issues.append(
            f"Totale righe {len(rows)}, atteso {EXPECTED_TOTAL_ROWS}."
        )

    actual: dict[str, dict[int, int]] = {
        name: {0: 0, 1: 0} for name in EXPECTED_SPLITS
    }
    for row in rows:
        actual[row.split][row.target] += 1

    for split_name in EXPECTED_SPLITS:
        expected = EXPECTED_SPLIT_CLASS_COUNTS[split_name]
        expected_total = sum(expected.values())
        actual_total = sum(actual[split_name].values())
        if actual_total != expected_total:
            issues.append(
                f"Split '{split_name}': totale {actual_total}, "
                f"atteso {expected_total}."
            )
        for target in (0, 1):
            if actual[split_name][target] != expected[target]:
                issues.append(
                    f"Split '{split_name}', target {target}: "
                    f"{actual[split_name][target]}, atteso {expected[target]}."
                )
    return issues


def load_dataset(
    path: str | Path,
    *,
    enforce_expected_counts: bool = True,
    max_reported_issues: int = _MAX_REPORTED_ISSUES,
) -> LoadedDataset:
    """Legge e valida il CSV del dataset.

    Solleva :class:`DatasetValidationError` con l'elenco degli errori trovati.
    Non applica imputazioni, non riordina le righe e non rigenera lo split.
    Le colonne possono essere in un ordine diverso dallo schema, ma le feature
    restituite sono sempre nell'ordine canonico di ``FEATURE_NAMES``.

    ``enforce_expected_counts=False`` disattiva soltanto il confronto con i
    conteggi attesi del dataset assegnato; tutti gli altri controlli restano
    attivi. L'opzione serve ai test del lettore, non al flusso di training.
    """

    source = Path(path).expanduser()

    if not source.exists():
        raise DatasetValidationError(
            [f"File non trovato: {source}"], source=source
        )
    if not source.is_file():
        raise DatasetValidationError(
            [f"Il percorso non è un file: {source}"], source=source
        )

    try:
        raw = source.read_bytes()
    except OSError as exc:
        raise DatasetValidationError(
            [f"Impossibile leggere il file: {exc}"], source=source
        ) from exc

    if not raw:
        raise DatasetValidationError(
            ["File vuoto (0 byte)."], source=source, sha256=sha256_bytes(raw)
        )

    fingerprint = sha256_bytes(raw)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DatasetValidationError(
            [f"File non decodificabile come UTF-8: {exc}"],
            source=source,
            sha256=fingerprint,
        ) from exc

    try:
        records = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise DatasetValidationError(
            [f"CSV non valido: {exc}"], source=source, sha256=fingerprint
        ) from exc

    if not records:
        raise DatasetValidationError(
            ["Intestazione mancante: file privo di righe."],
            source=source,
            sha256=fingerprint,
        )

    header = tuple(records[0])
    if not header:
        raise DatasetValidationError(
            ["Intestazione mancante."], source=source, sha256=fingerprint
        )

    duplicate_counts = Counter(header)
    duplicates = [
        f"'{name}' ({count} volte)"
        for name, count in duplicate_counts.items()
        if count > 1
    ]
    if duplicates:
        raise DatasetValidationError(
            ["Intestazione con colonne duplicate: " + ", ".join(duplicates) + "."],
            source=source,
            sha256=fingerprint,
        )

    expected_set = set(EXPECTED_COLUMNS)
    header_set = set(header)
    missing = [name for name in EXPECTED_COLUMNS if name not in header_set]
    unexpected = [name for name in header if name not in expected_set]
    if missing or unexpected:
        issues: list[str] = []
        if missing:
            issues.append("Colonne mancanti: " + ", ".join(missing) + ".")
        if unexpected:
            issues.append(
                "Colonne inattese: "
                + ", ".join(repr(name) for name in unexpected)
                + "."
            )
        raise DatasetValidationError(
            issues, source=source, sha256=fingerprint
        )

    column_index = {name: index for index, name in enumerate(header)}
    id_index = column_index[RECORD_ID_COLUMN]
    split_index = column_index[SPLIT_COLUMN]
    target_index = column_index[TARGET_COLUMN]
    feature_indices = tuple(column_index[name] for name in FEATURE_NAMES)

    issues = []
    rows: list[DatasetRow] = []
    seen_ids: dict[str, int] = {}

    for line_number, record in enumerate(records[1:], start=2):
        if not record or all(cell.strip() == "" for cell in record):
            issues.append(f"Riga {line_number}: riga vuota.")
            continue

        if len(record) != len(header):
            issues.append(
                f"Riga {line_number}: {len(record)} campi, "
                f"attesi {len(header)}."
            )
            continue

        record_id = record[id_index]
        if not record_id.strip():
            issues.append(f"Riga {line_number}: record_id mancante.")
            continue
        if record_id in seen_ids:
            issues.append(
                f"Riga {line_number}: record_id duplicato '{record_id}' "
                f"(prima occorrenza alla riga {seen_ids[record_id]})."
            )
            continue
        seen_ids[record_id] = line_number

        split = record[split_index]
        if split not in EXPECTED_SPLITS:
            issues.append(
                f"Riga {line_number}: split inatteso {split!r}; "
                f"attesi {', '.join(EXPECTED_SPLITS)}."
            )
            continue

        target_raw = record[target_index].strip()
        if target_raw not in {"0", "1"}:
            issues.append(
                f"Riga {line_number}: target non valido {record[target_index]!r}; "
                "atteso 0 o 1."
            )
            continue
        target = int(target_raw)

        feature_values: list[float] = []
        row_valid = True
        for name, index in zip(FEATURE_NAMES, feature_indices):
            value, error = _parse_feature(record[index])
            if error is not None:
                issues.append(
                    f"Riga {line_number}: feature '{name}' {error}."
                )
                row_valid = False
                continue
            assert value is not None
            feature_values.append(value)

        if not row_valid:
            continue

        rows.append(
            DatasetRow(
                record_id=record_id,
                split=split,
                target=target,
                features=tuple(feature_values),
            )
        )

    if not rows and not issues:
        issues.append("Nessuna riga dati oltre all'intestazione.")

    if enforce_expected_counts:
        issues.extend(_check_expected_counts(tuple(rows)))

    _fail(
        issues,
        source=source,
        sha256=fingerprint,
        max_reported=max_reported_issues,
    )

    return LoadedDataset(
        source=source,
        sha256=fingerprint,
        header=header,
        feature_names=FEATURE_NAMES,
        rows=tuple(rows),
    )


def dataset_audit_dict(dataset: LoadedDataset) -> dict[str, Any]:
    """Riepilogo serializzabile per il report di audit."""

    return {
        "dataset_path": str(dataset.source),
        "dataset_sha256": dataset.sha256,
        "row_count": len(dataset),
        "feature_count": len(dataset.feature_names),
        "feature_names": list(dataset.feature_names),
        "counts_by_split_and_class": dataset.counts_by_split_and_class(),
        "validation_ids": list(dataset.validation_ids),
    }
