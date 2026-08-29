# Base image via Hamravesh's Docker Hub proxy — direct Docker Hub pulls are
# unreliable from Iranian build nodes. `library/` prefix is required for
# official images (documented Darkube pattern).
FROM hub.hamdocker.ir/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Re-point apt at the in-country mirror. deb.debian.org is served by Fastly,
# which heavily throttles Iranian IPs (sanctions): the official CDN turns this
# step into a ~1-hour stall (ffmpeg + weasyprint deps ≈ 200 MB, serial fetch,
# full of Ign:/retry lines). History: a working ArvanCloud mirror block was
# dropped in e3827d3 (2026-06-05) and 598c6e5 (2026-06-15) papered over the
# resulting flakiness with retry flags instead of restoring the mirror.
# Notes:
# - python:3.12-slim is Debian 13 (trixie): apt sources live in the deb822
#   file /etc/apt/sources.list.d/debian.sources (NOT legacy
#   /etc/apt/sources.list), hence the sed rather than echo. The end-anchored
#   pattern rewrites ONLY the main repo line; the debian-security line keeps
#   its official host (tiny traffic, and the mirror's security path has been
#   unreliable historically — see the old block's "security" fix comment).
# - Retry flags stay as belt-and-braces, not as the fix.
RUN sed -i 's|https\?://deb.debian.org/debian$|https://mirror.arvancloud.ir/debian|' /etc/apt/sources.list.d/debian.sources && \
    apt-get -o Acquire::Retries=5 -o Acquire::http::Pipeline-Depth=0 update && \
    apt-get -o Acquire::Retries=5 -o Acquire::http::Pipeline-Depth=0 \
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

# Manual cache-busting knob (nothing reads it at runtime). MUST stay below the
# heavy layers: while it sat above the apt/pip layers, bumping it invalidated
# their cache and forced a full system-package re-download on every deploy.
ENV BUILD_VERSION=3

# کپی کردن کل پروژه
COPY . .

# collect static
RUN python manage.py collectstatic --noinput || true

# اجرا
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000"]