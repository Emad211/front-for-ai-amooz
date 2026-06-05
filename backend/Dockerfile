FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV BUILD_VERSION=3

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

# collect static
RUN python manage.py collectstatic --noinput || true

# اجرا
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]