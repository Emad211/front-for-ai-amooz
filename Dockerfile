FROM python:3.12-slim

# نصب ffmpeg و ffprobe
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# محیط‌های ضروری
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# دایرکتوری کار
WORKDIR /app

# کپی و نصب dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کد بک‌اند
COPY backend/ .

# پورت
EXPOSE 8000

# ران شدن با timeout بیشتر
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:$PORT", "--timeout", "300", "--workers", "3", "--worker-class", "sync"]