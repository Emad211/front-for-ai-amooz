FROM python:3.12-slim

# نصب ffmpeg و ffprobe
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# محیط‌های ضروری
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    GUNICORN_TIMEOUT=300 \
    GUNICORN_WORKERS=3 \
    GUNICORN_WORKER_CLASS=sync \
    GUNICORN_GRACEFUL_TIMEOUT=60 \
    GUNICORN_KEEP_ALIVE=5

# دایرکتوری کار
WORKDIR /app

# کپی و نصب dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کد بک‌اند
COPY backend/ .

# پورت
EXPOSE 8000

# Run gunicorn with env-configurable settings.
CMD ["sh", "-c", "gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000} --timeout ${GUNICORN_TIMEOUT} --workers ${GUNICORN_WORKERS} --worker-class ${GUNICORN_WORKER_CLASS} --graceful-timeout ${GUNICORN_GRACEFUL_TIMEOUT} --keep-alive ${GUNICORN_KEEP_ALIVE}"]