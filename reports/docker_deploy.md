# Deploy Docker - verifica del servizio

Generato (UTC): `2026-11-16T11:45:42+00:00`
Ambito: deploy Docker locale del servizio v1; non è un deployment di produzione né una nuova misura del gate S4
Esito complessivo: **SUPERATO**

## Immagine e container

| Elemento | Valore |
| --- | --- |
| Immagine | `lab13-progetto3-api:local` |
| Image ID | `sha256:f96becea9ac1621b72d3817db604bed27f5a4790c26fa3b00f77c1acdaff0684` |
| Dimensione compressa (`inspect .Size`) | 129.1 MiB |
| Dimensione su disco (`docker image ls`) | 581MB |
| Base | `docker.io/library/python:3.11.9-slim` |
| Container | `lab13-progetto3-api` (`eddf7acc224c`) |
| Stato | `running` / health `healthy` |
| Utente | `lab13` (uid `10001`) |
| Root filesystem read-only | sì |
| Capabilities rimosse (`cap_drop`) | ALL |
| Porta pubblicata | `127.0.0.1:8000` |

## Identità del modello servito

| Controllo | Atteso | Servito | Esito |
| --- | --- | --- | --- |
| Versione | `v1` | `v1` | ✅ |
| Run ID | `64079619c2c947bd83699d0d552b9d78` | `64079619c2c947bd83699d0d552b9d78` | ✅ |
| Hash artefatto | `f8aea6264329d4c53d1f87e270c10ef7a3567c739c59c5796ccf116ccb7e1bd7` | `f8aea6264329d4c53d1f87e270c10ef7a3567c739c59c5796ccf116ccb7e1bd7` | ✅ |
| Fingerprint canonico dataset | `5c999d24a24126e81a033ae5ecf9b9b1049925f8abe59367883bcd171476c72f` | `5c999d24a24126e81a033ae5ecf9b9b1049925f8abe59367883bcd171476c72f` | ✅ |

## Richieste operative

| # | Request ID | Versione richiesta dal CSV | Status atteso | Status reale | Predizione | Versione servita | Log correlato |
| ---: | --- | --- | ---: | ---: | ---: | --- | --- |
| 1 | `req_01` | v1 | 200 | 200 | 0 | v1 | sì |
| 2 | `req_02` | v2 | 200 | 200 | 1 | v1 | sì |
| 3 | `req_03` | v1 | 200 | 200 | 1 | v1 | sì |
| 4 | `req_04` | v1 | 422 | 422 | - | - | sì |

`req_02` indica `v2` nel CSV perché lo stesso file serve al drill S5-S6;
questo deployment resta su v1 e non cambia versione. Il drill
`v1 -> v2 -> v1` è documentato separatamente in `reports/drill_s5_s6.md`.

## Metriche della finestra

- Richieste `POST /predict`: 4
- Errori HTTP ≥ 400: 1
- Error rate: 0.25
- p95: 2.92 ms
- Finestra: 900 s

Il p95 dello smoke test riguarda quattro richieste e **non** sostituisce
il p95 del gate S4 (30 richieste valide).

## Versioni nel container

| Componente | Versione |
| --- | --- |
| Python | `3.11.9` |
| `numpy` | `2.4.6` |
| `scikit-learn` | `1.8.0` |
| `joblib` | `1.5.3` |
| `fastapi` | `0.115.6` |
| `uvicorn` | `0.34.0` |
| `pydantic` | `2.14.3` |

## Controlli

| Controllo | Esito |
| --- | --- |
| `identity_active_version` | ✅ |
| `identity_run_id` | ✅ |
| `identity_artifact_sha256` | ✅ |
| `identity_dataset_canonical` | ✅ |
| `local_artifact_hash_matches_metadata` | ✅ |
| `docker_healthcheck_healthy` | ✅ |
| `health_end_ok` | ✅ |
| `state_unchanged_after_smoke` | ✅ |
| `statuses_ok` | ✅ |
| `served_version_v1` | ✅ |
| `predictions_ok` | ✅ |
| `request_id_echo_ok` | ✅ |
| `logs_correlated` | ✅ |
| `logs_without_payload` | ✅ |
| `metrics_ok` | ✅ |
| `non_root_user` | ✅ |
| `read_only_rootfs` | ✅ |
| `cap_drop_all` | ✅ |
| `no_new_privileges` | ✅ |
| `healthcheck_configured` | ✅ |
| `no_restart_loop` | ✅ |
| `container_packages_match_artifact` | ✅ |

## Evidenze

- `reports/docker_deploy.json` (questo report, versione strutturata)
- `reports/docker/requests.jsonl` (log richieste, senza payload)
- `reports/docker/container.log` (stdout/stderr del container)
- `reports/docker/container_inspect.json`
- `reports/docker/image_inspect.json`

## Limiti

- Docker locale single-node: non è un deployment cloud, Kubernetes o con registry esterno.
- Nessun TLS, autenticazione o rate limiting: la porta è pubblicata solo su 127.0.0.1.
- Lo smoke test non è un test di carico; il p95 su quattro richieste non sostituisce il gate S4.
- I dati sono sintetici e didattici: le metriche non misurano spedizioni reali.
- Il deployment serve la v1 e lascia /admin/version disabilitato; il drill v1 -> v2 -> v1 resta quello locale S5-S6.
- La validation assegnata non è un test indipendente e non simula una validazione temporale.
