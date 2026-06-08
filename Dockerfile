FROM python:3.12-slim

# Install ffmpeg, ffprobe and build essentials for weasyprint/Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Environment. Defaults tuned for an I/O-bound DRF app: threaded (gthread)
# workers so a request blocked on a slow LLM/DB call frees the CPU for others.
# Concurrency = GUNICORN_WORKERS * GUNICORN_THREADS; size it against Postgres
# max_connections (workers*threads*replicas + Celery must stay under it).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    GUNICORN_TIMEOUT=120 \
    GUNICORN_WORKERS=3 \
    GUNICORN_THREADS=8 \
    GUNICORN_WORKER_CLASS=gthread \
    GUNICORN_GRACEFUL_TIMEOUT=60 \
    GUNICORN_KEEP_ALIVE=5 \
    GUNICORN_MAX_REQUESTS=1000 \
    GUNICORN_MAX_REQUESTS_JITTER=100

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000

# migrate/collectstatic are handled by the entrypoint (env-gated); the CMD only
# starts gunicorn. See backend/docker-entrypoint.sh.
ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
CMD ["sh", "-c", "gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000} --timeout ${GUNICORN_TIMEOUT} --workers ${GUNICORN_WORKERS} --threads ${GUNICORN_THREADS} --worker-class ${GUNICORN_WORKER_CLASS} --graceful-timeout ${GUNICORN_GRACEFUL_TIMEOUT} --keep-alive ${GUNICORN_KEEP_ALIVE} --max-requests ${GUNICORN_MAX_REQUESTS} --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER} --access-logfile - --error-logfile -"]
