# چک‌لیست دپلوی AI_AMOOZ — نسخه کامل

> این چک‌لیست فرض می‌کند **هیچ‌کدام** از مراحل دپلوی هنوز انجام نشده.
> پلتفرم: **Darkube (Hamravesh ‑ k8s cluster `hamravesh-c13`)**.

---

## ۰. پیش‌نیازها

- [ ] حساب Darkube فعال با دسترسی `ai-products-ai-amooz`
- [ ] داکر روی لپ‌تاپ نصب شده (بهتر است لوکال تست کنید)
- [ ] `git` و آخرین تغییرات push شده به remote

---

## ۱. تولید Secret Key جدید

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

خروجی را کپی کنید — در مرحله ۳ استفاده می‌شود.

---

## ۲. ساخت ایمیج Docker

Dockerfile کنونی:
```
FROM python:3.12-slim
# migrate + collectstatic + gunicorn
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn ..."]
```

تست لوکال:
```bash
cd backend
docker build -t aiamooz-backend .
docker run --rm -p 8000:8000 \
  -e DATABASE_URL="postgresql://ai_amooz:ai_amooz_password@host.docker.internal:5432/ai_amooz" \
  -e REDIS_URL="redis://localhost:6379/0" \
  -e DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')" \
  -e DEBUG=False \
  aiamooz-backend
```

---

## ۳. متغیرهای محیطی (Environment Variables)

در پنل Darkube → اپ Backend → تنظیمات Environment Variables, **همه** موارد زیر را ست کنید:

### الزامی (Critical)

| متغیر | مقدار | توضیح |
|--------|-------|-------|
| `DJANGO_SECRET_KEY` | *(مقدار ۶۴+ کاراکتری از مرحله ۱)* | **حتماً عوض کنید!** مقدار فعلی فقط ۱۶ کاراکتر است |
| `DEBUG` | `False` | |
| `ALLOWED_HOSTS` | `aiamoooz.darkube.app` | کاما جدا. **`*` نباشد!** |
| `DATABASE_URL` | `postgresql://postgres:IcHfBNcI0Ey8XGv2R85V@ai-amooz-db.ai-products-ai-amooz.svc:5432/postgres` | کانکشن PostgreSQL داخلی |
| `REDIS_URL` | `redis://:wTsn0gOcwynZe2VZ5pY1PoBH5PP5fzEl@aiamooz.ai-products-ai-amooz.svc:6379/0` | Redis داخلی با پسورد |
| `CORS_ALLOWED_ORIGINS` | `https://front-for-ai-amooz.vercel.app` | فرانت Vercel |
| `CSRF_TRUSTED_ORIGINS` | `https://aiamoooz.darkube.app,https://front-for-ai-amooz.vercel.app` | |
| `CORS_ALLOW_CREDENTIALS` | `True` | |

### Gunicorn (پیشنهادی برای ۱۰۰ کاربر)

| متغیر | مقدار | توضیح |
|--------|-------|-------|
| `GUNICORN_WORKERS` | `3` | ≈ 2×CPU+1. با 2 CPU = 3 عدد worker |
| `GUNICORN_TIMEOUT` | `300` | ۵ دقیقه (برای pipeline endpoints) |
| `GUNICORN_WORKER_CLASS` | `gthread` | **تغییر از `sync` به `gthread`** — یک thread pool داخل هر worker |
| `GUNICORN_KEEP_ALIVE` | `5` | ثانیه |
| `GUNICORN_GRACEFUL_TIMEOUT` | `60` | |

> **چرا `gthread`؟** هر worker سه thread دارد (worker-threads=3). با 3 worker × 3 thread = 9 concurrent request بدون blocking. برای I/O-heavy endpoints (DB queries) بسیار بهتر از `sync` است.

### دیتابیس (اتصال)

| متغیر | مقدار | توضیح |
|--------|-------|-------|
| `CONN_MAX_AGE` | `600` | ثانیه (۱۰ دقیقه). از ساخت connection جدید در هر request جلوگیری |

### Rate Limiting

| متغیر | مقدار | توضیح |
|--------|-------|-------|
| `THROTTLE_RATE_ANON` | `60/minute` | ۶۰ درخواست/دقیقه برای anonymous |
| `THROTTLE_RATE_USER` | `300/minute` | ۳۰۰ درخواست/دقیقه برای authenticated |

### SMS (Mediana)

| متغیر | مقدار | توضیح |
|--------|-------|-------|
| `MEDIANA_API_KEY` | *(کلید API مدیانا)* | بدون این، SMS ارسال نمی‌شود |

### Google AI (LLM)

| متغیر | مقدار | توضیح |
|--------|-------|-------|
| `GOOGLE_API_KEY` | *(کلید Google AI)* | برای transcription و structure |

### Pipeline

| متغیر | مقدار | توضیح |
|--------|-------|-------|
| `CLASS_PIPELINE_ASYNC` | `True` | فعال‌سازی Celery tasks |

---

## ۴. دپلوی Celery Worker (اپ جداگانه)

Celery باید به عنوان **اپ جداگانه** در Darkube دپلوی شود:

### مرحله‌ها:
1. **ساخت اپ جدید** در Darkube → نام: `aiamooz-celery-worker`
2. **همان ایمیج Docker** Backend را استفاده کنید
3. **Command override** (در تنظیمات اپ):
   ```
   celery -A core worker --loglevel=info --concurrency=2 --max-tasks-per-child=50
   ```
4. **متغیرهای محیطی**: دقیقاً همان env vars بالا (بجز Gunicorn)
5. **Resource limits**:
   - RAM: 2GB
   - CPU: 1 core

> `--max-tasks-per-child=50` جلوگیری از memory leak در worker ها.

### تنظیمات اضافی Celery (اختیاری):

| متغیر | مقدار | توضیح |
|--------|-------|-------|
| `CELERY_TASK_TIME_LIMIT` | `21600` | ۶ ساعت حداکثر |
| `CELERY_TASK_SOFT_TIME_LIMIT` | `18000` | ۵ ساعت soft limit |

---

## ۵. مایگریشن دیتابیس

مایگریشن **خودکار** اجرا می‌شود چون `migrate --noinput` در CMD داکرفایل هست.

**بعد از اولین دپلوی** بررسی کنید:
```bash
# از طریق Darkube shell یا exec:
python manage.py showmigrations
```

اگر migration های اعمال‌نشده دیدید:
```bash
python manage.py migrate --noinput
```

> ⚠️ ایندکس‌های جدید (روی `status`, `is_published`, `pipeline_type`, `phone`, `invite_code`) در migration بعدی اضافه شده‌اند.

---

## ۶. ساخت Superuser (برای admin)

```bash
# از طریق Darkube shell:
python manage.py createsuperuser
```

---

## ۷. تست Health Check

```bash
curl https://aiamoooz.darkube.app/api/health/
# باید 200 برگرداند:
# {"status": "ok", "db": "ok", "redis": "ok"}
```

اگر `redis: error` گرفتید: `REDIS_URL` را بررسی کنید.
اگر `db: error` گرفتید: `DATABASE_URL` را بررسی کنید.

---

## ۸. Frontend (Vercel)

فرانت از قبل روی Vercel دپلوی شده. مطمئن شوید:

1. **`NEXT_PUBLIC_API_URL`** در Vercel = `https://aiamoooz.darkube.app`
2. بعد از دپلوی Backend, یک تست end-to-end انجام دهید:
   - ثبت‌نام → لاگین → دسترسی به API → خروج

---

## ۹. مانیتورینگ

### لاگ‌ها
```bash
# Darkube dashboard → Logs tab
# یا:
darkube logs aiamooz-backend --tail 100
darkube logs aiamooz-celery-worker --tail 100
```

### معیارهای کلیدی برای ۱۰۰ کاربر
- **Response time**: p95 < 500ms برای list endpoints
- **Error rate**: < 1%
- **DB connections**: با `CONN_MAX_AGE=600` باید ≤ 3 connection فعال ببینید
- **Memory**: < 3GB برای backend, < 1.5GB برای celery
- **Celery queue**: `celery inspect active` — queue خالی = خوب

---

## ۱۰. چک‌لیست نهایی قبل از Go-Live

- [ ] `DJANGO_SECRET_KEY` عوض شده (۶۴+ کاراکتر)
- [ ] `DEBUG=False`
- [ ] `ALLOWED_HOSTS` فقط دامنه خودتان (نه `*`)
- [ ] `CORS_ALLOWED_ORIGINS` فقط فرانت Vercel
- [ ] `CSRF_TRUSTED_ORIGINS` شامل backend + frontend
- [ ] Health check : `GET /api/health/` → `200 {"status": "ok"}`
- [ ] Celery worker running: `celery inspect ping` از Darkube shell
- [ ] SMS test: یک جلسه publish کنید و تأیید بگیرید SMS رسیده
- [ ] Migration applied: `python manage.py showmigrations` → همه `[X]`
- [ ] لاگ‌ها بدون error: `darkube logs --tail 50`
- [ ] Rate limiting فعال: بیش از ۶۰ request/min بدون auth → `429`
- [ ] فرانت وصل شده: لاگین از Vercel و دریافت JWT

---

## ۱۱. Rollback Plan

اگر مشکلی پیش آمد:
1. **Darkube** → اپ Backend → Deployments → Rollback to previous version
2. اگر migration مشکل‌ساز شد:
   ```bash
   python manage.py migrate classes <previous_migration_number>
   ```
3. **Celery worker** را هم rollback کنید

---

## ۱۲. Performance Tuning (بعد از Go-Live)

اگر بعد از Go-Live با ۱۰۰ کاربر مشکل دیدید:

| مشکل | راه‌حل |
|-------|--------|
| Response time بالا | `GUNICORN_WORKERS` را به 4 افزایش دهید |
| DB connection error | `CONN_MAX_AGE=None` + نصب pgbouncer |
| Memory بالا | `GUNICORN_WORKERS` را کاهش + `--max-memory-per-child=500000` |
| Celery queue پر | `--concurrency=4` در worker |
| 429 Too Many Requests | `THROTTLE_RATE_USER=500/minute` |
