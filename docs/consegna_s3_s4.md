# Passaggio di consegne - S3 e S4

## Stato consegnato

S3 (servizio FastAPI e telemetria) e S4 (candidata v2 e gate) sono implementate.
La suite locale riporta 83 test superati. Il probe HTTP ha verificato l'identità
dell'artefatto v2 e ha misurato 30 richieste valide dopo 3 warm-up.

| Controllo | Risultato |
| --- | ---: |
| Accuracy baseline di confronto | 0.735 |
| Accuracy candidata v2 | 0.735 |
| p95 HTTP v2 | 28.3657 ms |
| Error rate HTTP | 0 / 30 = 0.0 |
| Identità server/artefatto | verificata |
| Decisione S4 | SUPERATO rispetto alla baseline isolata |

## Discrepanza dei dati da mantenere visibile

Il CSV incluso ha SHA-256 `5c999d24a24126e81a033ae5ecf9b9b1049925f8abe59367883bcd171476c72f`;
gli artefatti v1 originali dichiarano `afee41161484c561feb59576f464321f3f0453c00acb9752a9173a7755e97c79`.
Per questo confronto è stata riaddestrata una baseline isolata in
`comparison_baseline/models/v1/` sul CSV incluso. Il gate superato usa quella
baseline e gli stessi ID di validation della v2. Non rappresenta un confronto
con l'artefatto v1 originale.

La baseline isolata è identificata dal run MLflow
`c771dbca820f4af48dd58dd7655225cc`; la candidata v2 dal run
`5258ffae2cec4803b81e47220dd2137e`. Sono conservati i relativi store MLflow e
gli artefatti nel progetto.

## Versione attiva e perimetro

`config/active_version.json` continua a indicare `v1`. v2 non è stata attivata.
Non sono stati eseguiti il drill di cambio/ripristino, il rollback o le attività
di S5-S6. Chi continua il lab deve trattare l'attivazione come un passaggio
separato e riferirsi alle istruzioni della fase successiva.

## File utili

- `src/lab13/service.py`: API, caricamento verificato da configurazione, request ID, log e metriche.
- `models/v2/`: artefatto candidato, metadati e predizioni validation.
- `comparison_baseline/models/v1/`: baseline isolata, separata dalla v1 originale.
- `reports/v2_valutazione.*`, `reports/probe_v2.json`, `reports/gate_s4.*`: metriche e decisione.
- `mlruns/` e `comparison_baseline/mlruns/`: run MLflow della candidata e della baseline isolata.
- `config/gate.json`: policy congelata usata per S4.

## Ripetere il confronto S4

Dalla radice del progetto, con l'ambiente virtuale attivato:

```powershell
python -m unittest discover -s tests -v
python scripts/probe_service.py
python scripts/evaluate_gate.py --baseline-report .\comparison_baseline\reports\v1_valutazione.json --baseline-model-dir .\comparison_baseline\models\v1
```

Per una nuova misura HTTP, avviare il server su v2 con una configurazione
temporanea `LAB13_ACTIVE_VERSION_PATH`, mantenendo invariato
`config/active_version.json`, quindi passare `--base-url` a `probe_service.py`.
