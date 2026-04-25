FROM python:3.12-slim

# جلوگیری از ساخت pyc و بافر لاگ
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# تنظیم mirror ایران + حل مشکل Release expired
RUN rm -f /etc/apt/sources.list.d/* && \
    echo "deb https://mirror.arvancloud.ir/debian bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb https://mirror.arvancloud.ir/debian bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://mirror.arvancloud.ir/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99no-check-valid

# نصب پکیج‌های سیستم
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

# آپدیت pip
RUN pip install --upgrade pip

# کپی requirements
COPY backend/requirements.txt .

# نصب پکیج‌های پایتون
RUN pip install --no-cache-dir -r requirements.txt

# کپی کل پروژه
COPY backend/ .

# جمع‌آوری static
RUN python manage.py collectstatic --noinput || true

# اجرای سرور
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
