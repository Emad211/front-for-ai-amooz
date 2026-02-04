FROM python:3.12-slim

# محیط‌های ضروری
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# دایرکتوری کار
WORKDIR /app

# کپی و نصب dependencies (فقط از backend)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کد بک‌اند
COPY backend/ .

# پورت
EXPOSE 8000

# ران شدن (migrate و static رو در Args همروش می‌ذاریم)
CMD ["gunicorn", "ai_amooz.wsgi:application", "--bind", "0.0.0.0:$PORT"]