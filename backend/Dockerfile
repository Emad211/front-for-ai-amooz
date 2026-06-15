FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV BUILD_VERSION=3

WORKDIR /app

# نصب پکیج‌های سیستم مستقیماً از مخازن رسمی دبیان.
# گزینه‌های Retries + Pipeline-Depth=0 build را روی شبکه/پروکسی ناپایدار مقاوم
# می‌کنند (دانلود سریالی با تلاش مجدد به‌جای موازی‌کاریِ شکننده).
RUN apt-get -o Acquire::Retries=10 -o Acquire::http::Pipeline-Depth=0 update && \
    apt-get -o Acquire::Retries=10 -o Acquire::http::Pipeline-Depth=0 \
        install -y --no-install-recommends \
        ffmpeg \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
        fontconfig \
    && rm -rf /var/lib/apt/lists/*

# کپی کردن فایل نیازمندی‌ها
COPY requirements.txt .

# آپگرید pip و نصب پکیج‌های پایتون (retry/timeout برای شبکهٔ ناپایدار)
RUN pip install --retries 10 --timeout 120 --upgrade pip && \
    pip install --retries 10 --timeout 120 --no-cache-dir -r requirements.txt

# کپی کردن کل پروژه
COPY . .

# collect static
RUN python manage.py collectstatic --noinput || true

# اجرا
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000"]