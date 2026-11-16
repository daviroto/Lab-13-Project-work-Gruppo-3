# Drill S5-S6 - cambio versione e rollback

Generato (UTC): `2026-11-16T00:25:08+00:00`
Ambito: drill locale di cambio versione e rollback; non è un deployment di produzione e non sostituisce la probe/gate S4
Server: `http://127.0.0.1:8000` (auto-started)

## Sequenza delle richieste

| # | Request ID | Versione attesa | Status atteso | Status reale | Predizione | Versione servita | Log correlato |
| ---: | --- | --- | ---: | ---: | ---: | --- | --- |
| 1 | `req_01` | v1 | 200 | 200 | 0 | v1 | sì |
| 2 | `req_02` | v2 | 200 | 200 | 1 | v2 | sì |
| 3 | `req_03` | v1 | 200 | 200 | 1 | v1 | sì |
| 4 | `req_04` | v1 | 422 | 422 | - | - | sì |

## Transizioni registrate

| Timestamp | Azione | Modalità | Prima | Dopo | Run ID (dopo) |
| --- | --- | --- | --- | --- | --- |
| `2026-11-16T00:25:08+00:00` | activate | drill | v1 | v2 | `5258ffae2cec4803b81e47220dd2137e` |
| `2026-11-16T00:25:08+00:00` | rollback | drill | v2 | v1 | `64079619c2c947bd83699d0d552b9d78` |

## Esiti

- Sequenza attesa rispettata: sì
- Tutti gli status attesi rispettati: sì
- Error rate drill: 1/4 = 0.25
- Error rate sulle richieste valide: 0/3 = 0.00
- Il gate S4 usa la probe HTTP della candidata (30 richieste valide, error rate 0/30). Il drill ha 3 risposte valide e 1 errore atteso su 4 richieste: il suo 0,25 non sostituisce la misura del gate.

## Prova dello stato finale

- Versione attiva nello stato: `v1`
- Versione attiva da `/health`: `v1`
- Run ID atteso da `models/v1`: `64079619c2c947bd83699d0d552b9d78`
- Run ID servito: `64079619c2c947bd83699d0d552b9d78`
- Hash artefatto atteso: `f8aea6264329d4c53d1f87e270c10ef7a3567c739c59c5796ccf116ccb7e1bd7`
- Hash artefatto servito: `f8aea6264329d4c53d1f87e270c10ef7a3567c739c59c5796ccf116ccb7e1bd7`
- Identità finale verificata: sì

## Limiti

- Dati sintetici e didattici: il drill non misura spedizioni reali.
- Il cambio versione è locale e abilitato solo con LAB13_ALLOW_VERSION_SWITCH=1.
- Nessun container o deployment esterno è stato eseguito.
- Lo stato finale è v1; v2 resta una candidata approvata dal gate ma non attiva.
