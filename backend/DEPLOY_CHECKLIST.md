# چک‌لیست دپلوی AI_AMOOZ — Hamravesh (Darkube K8s)

> **پلتفرم**: Hamravesh — Kubernetes cluster `hamravesh-c13`
> **Namespace**: `ai-products-ai-amooz`
> **Backend domain**: `aiamoooz.darkube.app`
> **Frontend**: Vercel — `front-for-ai-amooz.vercel.app`

---

## ۰. وضعیت فعلی

| سرویس | وضعیت | آدرس |
|--------|--------|-------|
| Backend (Django + Gunicorn) | ✅ دپلوی شده | `aiamoooz.darkube.app` |
| PostgreSQL | ✅ ساخته شده | `ai-amooz-db.ai-products-ai-amooz.svc:5432` (داخلی) |
| Redis | ✅ ساخته شده | `2bd19fdd-bd09-43d9-9cc4-9c48c29009d2.hsvc.ir:24484` (خارجی) |
| Frontend (Next.js) | ✅ Vercel | `front-for-ai-amooz.vercel.app` |
| **Celery Worker** | ❌ **هنوز ساخته نشده** | باید اپ جداگانه بسازید |

---

## ۱. Push آخرین تغییرات به GitHub

```bash
cd path/to/AI_AMOOZ
git add -A
git commit -m "prod: whitenoise, gthread threads, SSL redirect fix"
git push origin main
```

**تغییرات مهم این سشن:**
- ✅ `whitenoise` اضافه شد → static files بدون nginx کار می‌کند
- ✅ `STORAGES` dict (Django 5.x compatible) جایگزین `STATICFILES_STORAGE` شد
- ✅ `SECURE_SSL_REDIRECT` default → `False` (K8s ingress خودش SSL handle می‌کند)
- ✅ `GUNICORN_THREADS=4` اضافه شد → gthread واقعاً multi-thread شد
- ✅ `GUNICORN_WORKER_CLASS` default → `gthread`

---

## ۲. ری‌بیلد ایمیج Backend

بعد از push به GitHub، در پنل Hamravesh:

1. **اپ Backend** → **Deployments** → **New Deployment** (یا Auto-deploy اگر فعال است)
2. Hamravesh از GitHub repo ایمیج می‌سازد
3. **Dockerfile path**: `backend/Dockerfile`
4. **Build context**: `backend/`

> ⚠️ اگر ایمیج به صورت دستی build می‌کنید:
> ```bash
> cd backend
> docker build -t registry.hamdocker.ir/ai-products-ai-amooz/aiamooz-backend:latest .
> docker push registry.hamdocker.ir/ai-products-ai-amooz/aiamooz-backend:latest
> ```

---

## ۳. متغیرهای محیطی Backend

در پنل Hamravesh → اپ Backend → **Environment Variables**:

### ۳.۱. Django Core (الزامی)

| متغیر | مقدار | توضیح |
|--------|-------|-------|
| `DEBUG` | `False` | |
| `DJANGO_SECRET_KEY` | `WNktgCA4...` (مقدار فعلی شما) | ⚠️ **پیشنهاد**: یک کلید ۶۴+ کاراکتری جدید بسازید |
| `ALLOWED_HOSTS` | `*` | ⚠️ **پیشنهاد**: به `aiamoooz.darkube.app` تغییر دهید |

### ۳.۲. دیتابیس

| متغیر | مقدار |
|--------|-------|
| `DATABASE_URL` | `postgresql://postgres:IcHfBNcI0Ey8XGv2R85V@ai-amooz-db.ai-products-ai-amooz.svc:5432/postgres` |
| `CONN_MAX_AGE` | `600` (پیش‌فرض — نیازی به ست کردن نیست) |

### ۳.۳. Redis

| متغیر | مقدار |
|--------|-------|
| `CHAT_REDIS_URL` | `redis://wTsn0gOcwynZe2VZ5pY1PoBH5PP5fzEl@2bd19fdd-bd09-43d9-9cc4-9c48c29009d2.hsvc.ir:24484/0` |

> **نکته**: `REDIS_URL`، `CELERY_BROKER_URL` و `CELERY_RESULT_BACKEND` ست نشده‌اند — کد به‌صورت خودکار از `CHAT_REDIS_URL` fallback می‌کند. ✅ درست است.

### ۳.۴. AI / LLM

| متغیر | مقدار |
|--------|-------|
| `AVALAI_API_KEY` | `av-...` (کلید شما) |
| `AVALAI_BASE_URL` | `https://api.avalai.ir/v1` |
| `MODE` | `avalai` |
| `MODEL_NAME` | `gpt-4o-mini` |
| `GEMINI_API_KEY` | `AIza...` (کلید شما) |
| `TRANSCRIPTION_MODEL` | `models/gemini-2.5-flash` |
| `REWRITE_MODEL` | `models/gemini-2.5-flash` |
| `IMAGE_MODEL` | `models/gemini-2.0-flash` |
| `EMBEDDING_MODEL_NAME` | `models/gemini-embedding-001` |
| `GENAI_HTTP_TIMEOUT` | `1000` |
| `TRANSCRIBE_CHUNK_SECONDS` | `20` |
| `FRAME_MAX_FRAMES_FOR_MODEL` | `40` |
| `FRAME_HARD_CAP` | `16` |
| `MAX_TOTAL_FRAME_BYTES_MB` | `3` |
| `FRAME_EXTRACTION_FPS` | `0.25` |

### ۳.۵. SMS

| متغیر | مقدار |
|--------|-------|
| `MEDIANA_API_KEY` | `...` (کلید شما) |

### ۳.۶. CORS / CSRF

| متغیر | مقدار |
|--------|-------|
| `CORS_ALLOW_ALL_ORIGINS` | `False` |
| `CORS_ALLOWED_ORIGINS` | `https://front-for-ai-amooz.vercel.app` |
| `CORS_ALLOW_CREDENTIALS` | `True` |
| `CSRF_TRUSTED_ORIGINS` | `https://aiamoooz.darkube.app,https://front-for-ai-amooz.vercel.app` |

### ۳.۷. Gunicorn

| متغیر | مقدار | توضیح |
|--------|-------|-------|
| `GUNICORN_WORKERS` | `3` | ≈ 2×CPU + 1 |
| `GUNICORN_WORKER_CLASS` | `gthread` | |
| `GUNICORN_THREADS` | `4` | **جدید — اضافه کنید!** 3 worker × 4 thread = **12 concurrent** |
| `GUNICORN_TIMEOUT` | `300` | ۵ دقیقه (برای pipeline) |

### ۳.۸. Pipeline

| متغیر | مقدار |
|--------|-------|
| `CLASS_PIPELINE_ASYNC` | `True` |

---

## ۴. ساخت اپ Celery Worker (اپ جداگانه در Hamravesh)

### ۴.۱. تنظیمات اپ

| فیلد | مقدار |
|------|-------|
| **نام اپ** | `aiamooz-celery-worker` |
| **آدرس ایمیج** | همان ایمیج Backend (همان repo/registry) |
| **تگ ایمیج** | همان تگ Backend (مثلاً `latest` یا commit hash) |
| **پورت سرویس** | `8000` (Hamravesh ممکن است الزامی کند — Celery استفاده نمی‌کند) |

### ۴.۲. دستور اجرایی (Command Override)

```
celery -A core worker --loglevel=info --concurrency=2 --max-tasks-per-child=50
```

> **توضیح پارامترها:**
> - `-A core` → ماژول Celery در `core/celery.py`
> - `--concurrency=2` → ۲ worker process همزمان (با ۲GB RAM کافی)
> - `--max-tasks-per-child=50` → بعد از ۵۰ task، child ریستارت (جلوگیری از memory leak)
> - `--loglevel=info` → سطح لاگ

### ۴.۳. متغیرهای محیطی

**دقیقاً همان env vars بخش ۳** را کپی کنید، **بجز** موارد Gunicorn:

| حذف کنید (لازم نیست) |
|----------------------|
| `GUNICORN_WORKERS` |
| `GUNICORN_WORKER_CLASS` |
| `GUNICORN_THREADS` |
| `GUNICORN_TIMEOUT` |
| `GUNICORN_KEEP_ALIVE` |
| `GUNICORN_GRACEFUL_TIMEOUT` |

### ۴.۴. Readiness Probe

Celery Worker سرور HTTP نیست. **HTTP readiness probe کار نمی‌کند.**

**گزینه ۱ (پیشنهادی)** — Exec Probe:
```
celery -A core inspect ping --timeout 10
```
> پاسخ سالم: `pong`

**گزینه ۲** — اگر Hamravesh فقط HTTP probe دارد:
Probe را غیرفعال کنید یا به TCP روی پورت قرار دهید.

### ۴.۵. Resource Limits

| منبع | مقدار پیشنهادی |
|------|----------------|
| **RAM** | `2 GB` |
| **CPU** | `1 core` |

### ۴.۶. دامنه / پورت

| فیلد | مقدار |
|------|-------|
| **آدرس دامنه** | ❌ لازم نیست (Celery Worker سرور HTTP ندارد) |
| **Port mapping** | ❌ لازم نیست |
| **Custom Config** | ❌ لازم نیست |

---

## ۵. تأیید دپلوی

### ۵.۱. Health Check

```bash
curl -s https://aiamoooz.darkube.app/api/health/
```

**پاسخ مورد انتظار:**
```json
{"status": "healthy", "database": "connected", "redis": "connected"}
```

| مشکل | بررسی |
|------|--------|
| `database: error` | `DATABASE_URL` — host باید `*.svc` داخلی باشد |
| `redis: error` | `CHAT_REDIS_URL` — password و port صحیح باشد |
| `502 Bad Gateway` | Pod هنوز آماده نیست — ۱-۲ دقیقه صبر کنید |
| `301 Redirect Loop` | `SECURE_SSL_REDIRECT` باید `False` باشد |

### ۵.۲. Static Files

```bash
curl -s -o /dev/null -w "%{http_code}" https://aiamoooz.darkube.app/static/rest_framework/css/default.css
```

**باید `200` برگرداند.** اگر `404`: whitenoise نصب نشده یا `collectstatic` اجرا نشده.

### ۵.۳. Admin Panel

```
https://aiamoooz.darkube.app/admin/
```
باید صفحه لاگین Django Admin **با CSS درست** نمایش داده شود.

### ۵.۴. Swagger / API Docs

```
https://aiamoooz.darkube.app/api/schema/swagger-ui/
```

### ۵.۵. Celery Worker

از Hamravesh shell (اپ Backend):
```bash
celery -A core inspect ping
```

**پاسخ سالم:**
```
-> celery@<hostname>: OK
        pong
```

اگر پاسخی نگرفتید:
1. لاگ Celery worker را بررسی کنید
2. `CHAT_REDIS_URL` در هر دو اپ یکسان باشد
3. Redis accessible باشد

### ۵.۶. Pipeline End-to-End Test

1. از Admin یا Frontend یک **Class Session** جدید بسازید
2. فایل ویدیو/صوت آپلود و Step 1 را شروع کنید
3. لاگ Celery: باید task `process_class_step1_transcription` اجرا شود
4. صبر تا pipeline تمام شود → بررسی نتیجه

---

## ۶. ساخت Superuser

از Hamravesh shell (اپ Backend):
```bash
python manage.py createsuperuser
```

---

## ۷. Media Files — Persistent Volume

> ⚠️ **بسیار مهم**: در K8s، فایل‌های داخل container با هر restart/redeploy **حذف** می‌شوند!

### اقدام:

1. پنل Hamravesh → **Volumes** → ساخت volume جدید
   - **Size**: حداقل `10 GB` (بسته به حجم ویدیوها)
   - **Mount Path**: `/app/media`
2. این Volume را به **اپ Backend** وصل کنید
3. همین Volume را به **اپ Celery Worker** هم Mount کنید (ReadWriteMany اگر پشتیبانی شود)

> بدون Persistent Volume، تمام فایل‌های آپلود شده (ویدیو، تصاویر) با هر deploy از بین می‌روند!

---

## ۸. Frontend (Vercel)

مطمئن شوید در **Vercel Dashboard → Environment Variables**:

| متغیر | مقدار |
|--------|-------|
| `NEXT_PUBLIC_API_URL` | `https://aiamoooz.darkube.app` |

**تست:**
1. `https://front-for-ai-amooz.vercel.app` → صفحه لاگین
2. ثبت‌نام → لاگین → دریافت JWT
3. فراخوانی API → `200` + داده
4. Logout → Token blacklisted

---

## ۹. بررسی امنیتی نهایی

- [ ] `DJANGO_SECRET_KEY` — حداقل ۵۰ کاراکتر رندوم
- [ ] `DEBUG=False` ✅
- [ ] `ALLOWED_HOSTS` — فقط `aiamoooz.darkube.app` (**نه `*`**)
- [ ] `CORS_ALLOWED_ORIGINS` — فقط frontend دامنه
- [ ] `CSRF_TRUSTED_ORIGINS` — backend + frontend
- [ ] `SECURE_SSL_REDIRECT=False` — K8s ingress handles SSL
- [ ] `SESSION_COOKIE_SECURE=True` — خودکار با `DEBUG=False`
- [ ] `CSRF_COOKIE_SECURE=True` — خودکار با `DEBUG=False`

### Secret Key جدید بسازید:
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

## ۱۰. مانیتورینگ

| معیار | مقدار سالم |
|-------|------------|
| Response time p95 | < 500ms (بجز pipeline endpoints) |
| Error rate | < 1% |
| DB connections | ≤ 3 فعال |
| Memory — Backend | < 2GB |
| Memory — Celery | < 1.5GB |
| Celery queue | خالی (tasks پردازش شده) |

---

## ۱۱. Rollback

1. Hamravesh → اپ → **Deployments** → **Rollback** به version قبلی
2. Migration rollback: `python manage.py migrate <app> <prev_number>`
3. Celery worker را هم rollback کنید

---

## ۱۲. ترتیب دقیق اقدامات

```
 1. git add + commit + push (آخرین تغییرات)
 2. ری‌بیلد ایمیج Backend در Hamravesh
 3. env var جدید اضافه کنید: GUNICORN_THREADS=4
 4. صبر تا Pod آماده شود (۱-۲ دقیقه)
 5. curl /api/health/ → {"status": "healthy"}
 6. چک Admin panel + static files (CSS)
 7. ساخت اپ Celery Worker (بخش ۴)
 8. ساخت Persistent Volume برای /app/media (بخش ۷)
 9. ساخت superuser
10. تست Pipeline (upload → celery → result)
11. تست Frontend E2E (login → API → logout)
12. بررسی امنیت (بخش ۹)
```

---

## ۱۳. Troubleshooting

| مشکل | علت احتمالی | راه‌حل |
|------|------------|--------|
| `502 Bad Gateway` | Pod crash یا slow startup | لاگ Pod چک کنید — `migrate` ممکن است زمان ببرد |
| `301 Redirect Loop` | `SECURE_SSL_REDIRECT=True` | به `False` تغییر دهید |
| Static files `404` | `collectstatic` اجرا نشده | ری‌بیلد ایمیج — CMD شامل `collectstatic` هست |
| Admin بدون CSS | whitenoise نصب نیست | `requirements.txt` شامل `whitenoise>=6.0.0` باشد |
| Celery tasks اجرا نمی‌شوند | Worker روشن نیست | اپ Celery Worker بسازید (بخش ۴) |
| Redis connection error | Password/port اشتباه | `CHAT_REDIS_URL` format: `redis://PASSWORD@HOST:PORT/DB` |
| Media files حذف شدند | بدون PV | Persistent Volume بسازید (بخش ۷) |
| Memory بالا | Worker/concurrency زیاد | `GUNICORN_WORKERS=2` یا `--concurrency=1` |
| Response time بالا | Worker کم | `GUNICORN_WORKERS=4` + `GUNICORN_THREADS=4` |
