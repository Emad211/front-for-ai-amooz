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

# ── System dependencies ─────────────────────────────────────────────
# ffmpeg / ffprobe  → media compression & splitting
# WeasyPrint native → PDF generation (pango, cairo, gdk-pixbuf, fontconfig)
# Vazirmatn font    → Persian/Arabic text in PDFs
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        shared-mime-info \
        fontconfig \
        wget \
    && \
    # ── Download Vazirmatn Persian font ──────────────────────────────
    mkdir -p /usr/share/fonts/truetype/vazirmatn && \
    wget -q -O /usr/share/fonts/truetype/vazirmatn/Vazirmatn-Regular.ttf \
        "https://raw.githubusercontent.com/rastikerdar/vazirmatn/v33.003/fonts/ttf/Vazirmatn-Regular.ttf" && \
    wget -q -O /usr/share/fonts/truetype/vazirmatn/Vazirmatn-Bold.ttf \
        "https://raw.githubusercontent.com/rastikerdar/vazirmatn/v33.003/fonts/ttf/Vazirmatn-Bold.ttf" && \
    fc-cache -fv && \
    # ── Cleanup ──────────────────────────────────────────────────────
    apt-get purge -y wget && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# ── Python dependencies ─────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ────────────────────────────────────────────────
COPY . .

EXPOSE 8000

# Run migrate, collectstatic, then start gunicorn.
# --worker-tmp-dir /dev/shm  → avoids disk I/O races on K8s ephemeral storage
# --max-requests             → recycle workers to prevent memory leaks
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && exec gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000} --timeout ${GUNICORN_TIMEOUT} --workers ${GUNICORN_WORKERS} --threads ${GUNICORN_THREADS} --worker-class ${GUNICORN_WORKER_CLASS} --graceful-timeout ${GUNICORN_GRACEFUL_TIMEOUT} --keep-alive ${GUNICORN_KEEP_ALIVE} --max-requests ${GUNICORN_MAX_REQUESTS} --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER} --worker-tmp-dir /dev/shm"]