# Contratto dei dati e dell'inferenza

Fase S1 del Laboratorio 13 - Progetto 3, previsione dei ritardi nelle consegne
logistiche. Il documento descrive il contratto condiviso; non implementa il
servizio di inferenza, il training o la candidata v2.

## Momento della previsione

La previsione è disponibile **alla partenza della spedizione**. Tutte le 30
feature sono informazioni note in quel momento; i tempi e i ritardi storici si
riferiscono soltanto a consegne precedenti. Non sono ammessi dati raccolti
durante il viaggio o dopo la consegna.

## Schema del dataset

Il CSV assegnato contiene 1.000 righe e 33 colonne:

| Gruppo | Colonne | Uso |
| --- | --- | --- |
| Identificativo | `record_id` | Tracciabilità; mai input del modello |
| Split | `split` (`train`, `validation`) | Valutazione; mai input del modello |
| Feature | 30 colonne canoniche | Unico input del modello |
| Etichetta | `target` (`0`, `1`) | Solo valutazione; mai input del modello |

Il lettore accetta le colonne in un ordine diverso, ma restituisce sempre le
feature nell'ordine canonico. `record_id`, `split` e `target` vengono separati
e non sono mai inclusi nella matrice delle feature.

Lo split distribuito non va rigenerato né modificato. I conteggi attesi sono:

| Split | target 0 | target 1 | Totale |
| --- | ---: | ---: | ---: |
| train | 463 | 337 | 800 |
| validation | 116 | 84 | 200 |

## Lista canonica delle 30 feature API

La fonte eseguibile è `src/lab13/contracts.py` (`FEATURE_NAMES`). La tabella
seguente è la documentazione dello stesso ordine; nessun modulo deve mantenere
una seconda lista di feature.

| Posizione | Nome |
| ---: | --- |
| 1 | `distanza_pianificata_km` |
| 2 | `numero_fermate_pianificate` |
| 3 | `indice_congestione_prevista` |
| 4 | `quota_percorso_urbano_pct` |
| 5 | `deviazione_prevista_km` |
| 6 | `tempo_viaggio_stimato_ore` |
| 7 | `pacchi_in_coda_hub` |
| 8 | `occupazione_hub_pct` |
| 9 | `attesa_carico_prevista_min` |
| 10 | `addetti_disponibili_pct` |
| 11 | `mezzi_disponibili_pct` |
| 12 | `variazione_volumi_hub_pct` |
| 13 | `ritardi_vettore_90g_pct` |
| 14 | `ritardi_rotta_90g_pct` |
| 15 | `ritardo_medio_rotta_90g_min` |
| 16 | `tentativi_falliti_zona_90g_pct` |
| 17 | `puntualita_vettore_90g_pct` |
| 18 | `esperienza_autista_rotta_mesi` |
| 19 | `pioggia_prevista_mm` |
| 20 | `vento_previsto_km_h` |
| 21 | `rischio_neve_previsto_pct` |
| 22 | `cantieri_noti_sul_percorso` |
| 23 | `tratti_con_limitazioni` |
| 24 | `indice_criticita_meteo_prevista` |
| 25 | `margine_piano_rispetto_scadenza_ore` |
| 26 | `flessibilita_finestra_consegna_ore` |
| 27 | `peso_totale_carico_kg` |
| 28 | `saturazione_mezzo_pct` |
| 29 | `colli_fragili_pct` |
| 30 | `documenti_da_completare` |

## Contratto del payload

Un payload valido è un oggetto JSON con una sola chiave:

```text
{"features": [30 numeri nell'ordine canonico]}
```

Regole di validazione:

1. il payload deve essere un oggetto JSON;
2. la chiave `features` è obbligatoria;
3. non sono ammesse altre chiavi;
4. `features` deve essere una lista JSON;
5. la lista deve contenere **esattamente 30** valori;
6. ogni valore deve essere un numero JSON finito; stringhe numeriche,
   booleani, `null`, `NaN`, `Infinity` e `-Infinity` sono rifiutati;
7. l'ordine è quello della tabella precedente;
8. non viene applicata alcuna imputazione, sostituzione o coercizione.

Un payload con 29 valori non è completato con un valore di default: è
incompleto e deve essere respinto. Nel servizio previsto dalle fasi successive
la validazione del payload produce una risposta HTTP 422; in S1 la funzione
`validate_inference_payload` riconosce e respinge il payload senza invocare
alcun modello.

### Esempio valido

Il payload seguente è la richiesta operativa `req_01` del file
`richieste_monitoraggio.csv`. È riportato solo come esempio di contratto: non è
una riga di training né un dato di valutazione.

```json
{"features": [72.567, 11.0, 33.061, 12.844, 0.0, 3.35, 277.0, 50.356, 12.556, 89.676, 100.0, -20.083, 15.654, 22.897, 37.687, 13.971, 84.346, 3.0, 14.648, 17.618, 20.686, 3.0, 1.0, 44.878, 3.875, 4.786, 677.345, 82.573, 39.544, 3.0]}
```

### Esempio incompleto

`req_04` contiene 29 valori. Il validatore restituisce l'errore
`wrong_feature_count` e non aggiunge il trentesimo valore. Il servizio delle
fasi successive dovrà rispondere 422.

### Codici di errore del validatore

| Codice | Condizione |
| --- | --- |
| `payload_not_object` | Il payload non è un oggetto |
| `missing_features` | Manca la chiave `features` |
| `unexpected_keys` | Sono presenti chiavi diverse da `features` |
| `features_not_list` | `features` non è una lista |
| `wrong_feature_count` | Il numero di valori è diverso da 30 |
| `feature_not_numeric` | Un valore non è un numero (o è un booleano) |
| `feature_not_finite` | Un valore è `NaN` o infinito |

## Separazione dal file richieste

`richieste_monitoraggio.csv` contiene esclusivamente input operativi per le
prove API. Non è un dataset di training o di valutazione, non contiene
etichette e non deve essere passato al lettore del dataset. Il lettore accetta
un solo percorso dataset e non legge il file delle richieste.
