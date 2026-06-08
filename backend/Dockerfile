FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV BUILD_VERSION=4

# Gunicorn tuning (see root Dockerfile / docker-entrypoint.sh). Threaded workers
# so slow LLM/DB calls don't exhaust the (few) worker processes.
ENV PORT=8000 \
    GUNICORN_TIMEOUT=120 \
    GUNICORN_WORKERS=3 \
    GUNICORN_THREADS=8 \
    GUNICORN_WORKER_CLASS=gthread \
    GUNICORN_GRACEFUL_TIMEOUT=60 \
    GUNICORN_KEEP_ALIVE=5 \
    GUNICORN_MAX_REQUESTS=1000 \
    GUNICORN_MAX_REQUESTS_JITTER=100

WORKDIR /app

# نصب پکیج‌های سیستم مستقیماً از مخازن رسمی دبیان
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
        fontconfig \
    && rm -rf /var/lib/apt/lists/*

# کپی کردن فایل نیازمندی‌ها
COPY requirements.txt .

# آپگرید pip و نصب پکیج‌های پایتون
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# کپی کردن کل پروژه
COPY . .

EXPOSE 8000

# migrate/collectstatic run via the env-gated entrypoint (not per-pod CMD); the
# CMD only starts a properly-tuned, threaded gunicorn.
ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
CMD ["sh", "-c", "gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000} --timeout ${GUNICORN_TIMEOUT} --workers ${GUNICORN_WORKERS} --threads ${GUNICORN_THREADS} --worker-class ${GUNICORN_WORKER_CLASS} --graceful-timeout ${GUNICORN_GRACEFUL_TIMEOUT} --keep-alive ${GUNICORN_KEEP_ALIVE} --max-requests ${GUNICORN_MAX_REQUESTS} --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER} --access-logfile - --error-logfile -"]