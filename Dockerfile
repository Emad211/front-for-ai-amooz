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

# ✅ ران شدن با نام صحیح پروژه و اضافه کردن عملیات ضروری
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --timeout 120"]