FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    GUNICORN_TIMEOUT=300 \
    GUNICORN_WORKERS=4 \
    GUNICORN_THREADS=4 \
    GUNICORN_WORKER_CLASS=gthread \
    GUNICORN_GRACEFUL_TIMEOUT=60 \
    GUNICORN_KEEP_ALIVE=5 \
    GUNICORN_MAX_REQUESTS=1000 \
    GUNICORN_MAX_REQUESTS_JITTER=50

WORKDIR /app

# ✅ Use Iran mirror instead of deb.debian.org
RUN rm -f /etc/apt/sources.list.d/* && \
    echo "deb https://mirror.arvancloud.ir/debian bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb https://mirror.arvancloud.ir/debian bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://mirror.arvancloud.ir/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        shared-mime-info \
        fontconfig \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ─────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ────────────────────────────────────────────────
COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && python manage.py setup_s3_bucket 2>/dev/null || true && exec gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000} --timeout ${GUNICORN_TIMEOUT} --workers ${GUNICORN_WORKERS} --threads ${GUNICORN_THREADS} --worker-class ${GUNICORN_WORKER_CLASS} --graceful-timeout ${GUNICORN_GRACEFUL_TIMEOUT} --keep-alive ${GUNICORN_KEEP_ALIVE} --max-requests ${GUNICORN_MAX_REQUESTS} --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER} --worker-tmp-dir /dev/shm"]
