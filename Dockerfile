# syntax=docker/dockerfile:1
#
# Immagine di serving del progetto Lab 13.
#
# Scelte principali:
# - base python:3.11.9-slim, la stessa versione Python usata per serializzare
#   gli artefatti in models/v1 e models/v2;
# - dipendenze pinnate in requirements-serving.txt (senza MLflow);
# - utente non privilegiato (uid/gid 10001);
# - filesystem radice di sola lettura nel docker-compose, con un volume
#   scrivibile solo per /app/logs;
# - healthcheck sull'endpoint /health;
# - dataset, config, modelli e sorgenti copiati nell'immagine, così il
#   container è autosufficiente e non dipende dal filesystem dell'host.

FROM python:3.11.9-slim

LABEL org.opencontainers.image.base.name="docker.io/library/python:3.11.9-slim"
LABEL org.opencontainers.image.title="Lab 13 - Progetto 3 - API ritardi consegne"
LABEL org.opencontainers.image.description="Servizio FastAPI per la previsione dei ritardi nelle consegne logistiche (dati sintetici didattici)."
LABEL org.opencontainers.image.version="v1"
LABEL lab13.project="progetto3-ritardi-consegne"
LABEL lab13.model.version="v1"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    XDG_CACHE_HOME=/tmp/.cache \
    LAB13_DATASET_PATH="/app/dataset (1).csv" \
    LAB13_REQUESTS_PATH="/app/richieste_monitoraggio.csv" \
    LAB13_REQUEST_LOG="/app/logs/requests.jsonl" \
    LAB13_ALLOW_VERSION_SWITCH=0

WORKDIR /app

# Utente non privilegiato e directory dei log scrivibile dal solo servizio.
RUN groupadd --gid 10001 lab13 \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin lab13 \
    && mkdir -p /app/logs \
    && chown lab13:lab13 /app/logs

# Layer delle dipendenze separato: un cambio di codice non reinstalla tutto.
COPY requirements-serving.txt ./
RUN python -m pip install --no-cache-dir --only-binary=:all: -r requirements-serving.txt

# Contenuto versionato e necessario al serving.
COPY --chown=lab13:lab13 src ./src
COPY --chown=lab13:lab13 config ./config
COPY --chown=lab13:lab13 models ./models
COPY --chown=lab13:lab13 ["dataset (1).csv", "./dataset (1).csv"]
COPY --chown=lab13:lab13 ["richieste_monitoraggio.csv", "./richieste_monitoraggio.csv"]

USER lab13

EXPOSE 8000

# Il container è sano solo se il modello è stato caricato e /health risponde ok.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)); raise SystemExit(0 if d.get('status') == 'ok' else 1)"

CMD ["python", "-m", "uvicorn", "lab13.service:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--log-level", "warning"]
