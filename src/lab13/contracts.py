"""Contratti condivisi del Progetto 3 - ritardi nelle consegne logistiche.

Questo modulo contiene l'unica lista canonica delle 30 feature API e il
validatore del payload di inferenza. Nessun altro modulo deve duplicare
l'ordine delle feature.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

# Ordine unico e canonico: posizione 1..30 del payload e colonne del dataset.
FEATURE_NAMES: tuple[str, ...] = (
    "distanza_pianificata_km",
    "numero_fermate_pianificate",
    "indice_congestione_prevista",
    "quota_percorso_urbano_pct",
    "deviazione_prevista_km",
    "tempo_viaggio_stimato_ore",
    "pacchi_in_coda_hub",
    "occupazione_hub_pct",
    "attesa_carico_prevista_min",
    "addetti_disponibili_pct",
    "mezzi_disponibili_pct",
    "variazione_volumi_hub_pct",
    "ritardi_vettore_90g_pct",
    "ritardi_rotta_90g_pct",
    "ritardo_medio_rotta_90g_min",
    "tentativi_falliti_zona_90g_pct",
    "puntualita_vettore_90g_pct",
    "esperienza_autista_rotta_mesi",
    "pioggia_prevista_mm",
    "vento_previsto_km_h",
    "rischio_neve_previsto_pct",
    "cantieri_noti_sul_percorso",
    "tratti_con_limitazioni",
    "indice_criticita_meteo_prevista",
    "margine_piano_rispetto_scadenza_ore",
    "flessibilita_finestra_consegna_ore",
    "peso_totale_carico_kg",
    "saturazione_mezzo_pct",
    "colli_fragili_pct",
    "documenti_da_completare",
)
FEATURE_COUNT = len(FEATURE_NAMES)

RECORD_ID_COLUMN = "record_id"
SPLIT_COLUMN = "split"
TARGET_COLUMN = "target"

# Schema completo del CSV: i soli primi/metadati restano fuori dal modello.
EXPECTED_COLUMNS: tuple[str, ...] = (
    RECORD_ID_COLUMN,
    SPLIT_COLUMN,
    *FEATURE_NAMES,
    TARGET_COLUMN,
)

TRAIN_SPLIT = "train"
VALIDATION_SPLIT = "validation"
EXPECTED_SPLITS: tuple[str, ...] = (TRAIN_SPLIT, VALIDATION_SPLIT)
VALID_TARGETS = frozenset({0, 1})

# Controllo di integrità del dataset assegnato. Non è uno split da rigenerare.
EXPECTED_TOTAL_ROWS = 1000
EXPECTED_SPLIT_CLASS_COUNTS: dict[str, dict[int, int]] = {
    TRAIN_SPLIT: {0: 463, 1: 337},
    VALIDATION_SPLIT: {0: 116, 1: 84},
}

PAYLOAD_KEY = "features"


class ContractError(ValueError):
    """Violazione di un contratto dati o di un payload."""


class PayloadValidationError(ContractError):
    """Payload di inferenza non conforme al contratto."""

    def __init__(self, message: str, *, code: str = "invalid_payload") -> None:
        super().__init__(message)
        self.code = code


def validate_inference_payload(payload: Any) -> tuple[float, ...]:
    """Valida ``{"features": [30 numeri finiti]}`` e restituisce i valori.

    Il contratto è intenzionalmente rigido:

    * il payload deve essere un oggetto JSON;
    * l'unica chiave ammessa è ``features``;
    * la lista deve contenere esattamente 30 valori numerici;
    * numeri non finiti, booleani, stringhe e ``null`` sono rifiutati;
    * non viene applicata alcuna imputazione o correzione dei valori.

    L'ordine restituito è quello canonico di :data:`FEATURE_NAMES`.
    """

    if not isinstance(payload, Mapping):
        raise PayloadValidationError(
            "Il payload deve essere un oggetto JSON con la chiave 'features'.",
            code="payload_not_object",
        )

    keys = set(payload.keys())
    if PAYLOAD_KEY not in keys:
        raise PayloadValidationError(
            "Chiave 'features' mancante: il payload è incompleto.",
            code="missing_features",
        )

    unexpected = sorted(str(key) for key in keys - {PAYLOAD_KEY})
    if unexpected:
        raise PayloadValidationError(
            "Chiavi non ammesse nel payload: " + ", ".join(unexpected) + ".",
            code="unexpected_keys",
        )

    values = payload[PAYLOAD_KEY]
    if not isinstance(values, list):
        raise PayloadValidationError(
            "Il campo 'features' deve essere una lista JSON di 30 numeri.",
            code="features_not_list",
        )

    if len(values) != FEATURE_COUNT:
        raise PayloadValidationError(
            f"Il campo 'features' deve contenere {FEATURE_COUNT} valori; "
            f"ricevuti {len(values)}. Le richieste incomplete non vengono completate.",
            code="wrong_feature_count",
        )

    normalized: list[float] = []
    for position, value in enumerate(values, start=1):
        name = FEATURE_NAMES[position - 1]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PayloadValidationError(
                f"Feature {position} ('{name}'): atteso un numero, "
                f"ricevuto {type(value).__name__}.",
                code="feature_not_numeric",
            )
        try:
            numeric = float(value)
        except (OverflowError, ValueError) as exc:
            raise PayloadValidationError(
                f"Feature {position} ('{name}'): valore non rappresentabile "
                "come numero finito.",
                code="feature_not_finite",
            ) from exc
        if not math.isfinite(numeric):
            raise PayloadValidationError(
                f"Feature {position} ('{name}'): valore non finito.",
                code="feature_not_finite",
            )
        normalized.append(numeric)

    return tuple(normalized)
