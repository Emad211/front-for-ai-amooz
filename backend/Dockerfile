FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# کپی requirements و نصب
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کل کد بک‌اند
COPY . .

EXPOSE 8000

# CMD ساده (migrate و collectstatic رو در تنظیمات Args می‌ذاریم)
CMD ["gunicorn", "ai_amooz.wsgi:application", "--bind", "0.0.0.0:8000"]