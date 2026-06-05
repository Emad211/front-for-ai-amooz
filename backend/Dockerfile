FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV BUILD_VERSION=3

WORKDIR /app

# تنظیم mirror ایران (با اصلاح آدرس بخش security)
RUN rm -f /etc/apt/sources.list.d/* && \
    echo "deb https://mirror.arvancloud.ir/debian bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb https://mirror.arvancloud.ir/debian bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb http://security.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99no-check-valid

# نصب پکیج‌های سیستم
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
        fontconfig \
    && rm -rf /var/lib/apt/lists/*

# کپی کردن فقط فایل نیازمندی‌ها برای استفاده بهتر از کش داکر
COPY requirements.txt .

# آپگرید pip و نصب پکیج‌های پایتون در یک مرحله
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# کپی کردن کل پروژه
COPY . .

# collect static
RUN python manage.py collectstatic --noinput || true

# اجرا
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]