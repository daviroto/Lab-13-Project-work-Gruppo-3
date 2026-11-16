# Coerenza del fingerprint del dataset (S5)

## Problema

Lo stesso CSV assegnato può essere letto con line ending diversi a seconda del
checkout Git. Il contenuto logico non cambia, ma lo SHA-256 dei byte cambia:

| Variante | SHA-256 dei byte | SHA-256 canonico (CRLF/LF normalizzati) |
| --- | --- | --- |
| `dataset (1).csv` con CRLF (checkout Windows) | `afee41161484c561feb59576f464321f3f0453c00acb9752a9173a7755e97c79` | `5c999d24a24126e81a033ae5ecf9b9b1049925f8abe59367883bcd171476c72f` |
| `dataset (1).csv` con LF | `5c999d24a24126e81a033ae5ecf9b9b1049925f8abe59367883bcd171476c72f` | `5c999d24a24126e81a033ae5ecf9b9b1049925f8abe59367883bcd171476c72f` |

Senza questa distinzione il servizio avrebbe rifiutato v2 sul checkout CRLF,
perché i metadati di v2 dichiarano l'hash LF, e sarebbe stato impossibile
eseguire il drill `v1 -> v2 -> v1`.

## Soluzione adottata

Il lettore calcola due impronte:

- `sha256`: SHA-256 dei byte raw, conservato come evidenza storica;
- `sha256_canonical`: SHA-256 dei byte con `CRLF` normalizzato a `LF`.

Il caricatore e il servizio verificano il fingerprint canonico. I metadati di
`models/v1`, `models/v2` e `comparison_baseline/models/v1` conservano lo SHA-256
raw originale e aggiungono `sha256_canonical`. Nessun modello, dato o split è
stato rigenerato; gli hash raw e i run ID restano invariati.

## Verifica eseguita

| Controllo | v1 | v2 |
| --- | --- | --- |
| Caricamento con fingerprint canonico | ok | ok |
| Run ID | `64079619c2c947bd83699d0d552b9d78` | `5258ffae2cec4803b81e47220dd2137e` |
| SHA-256 artefatto | `f8aea6264329d4c53d1f87e270c10ef7a3567c739c59c5796ccf116ccb7e1bd7` | `5b9dc55028ac824b0602da7e9bf4a090a4f5eb30753bfb1d83b1037601856e63` |
| Differenze rispetto alle predizioni salvate (200 ID) | 0 | 0 |
| Accuracy ricalcolata | 0.7350 | 0.7350 |

Comando di verifica (dalla radice del progetto):

```powershell
python -c "import sys,json,warnings; sys.path.insert(0,'src'); warnings.filterwarnings('ignore'); from lab13.data import load_dataset; from lab13.model_io import load_version; d=load_dataset('dataset (1).csv'); print('raw',d.sha256); print('canonico',d.sha256_canonical); [print(v, load_version('models/'+v, expected_version=v, expected_dataset_canonical_sha256=d.sha256_canonical).run_id) for v in ('v1','v2')]"
```

## Relazione con il gate S4

Il gate S4 resta quello registrato in `reports/gate_s4.*`: è stato misurato con
la baseline v1 isolata `comparison_baseline/models/v1` e non è stato ricalcolato
dopo i risultati. Il fingerprint canonico dimostra che la v1 originale e la
baseline isolata hanno lo stesso contenuto logico; entrambe hanno accuracy
0.735, quindi la decisione `SUPERATO` non cambia. Le soglie di
`config/gate.json` non sono state modificate.
