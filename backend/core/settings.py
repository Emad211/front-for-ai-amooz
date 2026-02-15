from pathlib import Path
import os
from urllib.parse import urlparse
from dotenv import load_dotenv
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

# Ensure `backend/.env` is loaded regardless of the process working directory.
# (E.g. running `python backend/manage.py runserver` from the repo root.)
load_dotenv(dotenv_path=BASE_DIR / '.env')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-change-me-in-production')

DEBUG = os.getenv('DEBUG', 'True') == 'True'

def _split_env_list(name: str, default: str = '') -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(',') if item.strip()]


def _get_env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or '').strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_env_bool(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or '').strip().lower()
    if not raw:
        return default
    return raw in {'1', 'true', 'yes', 'on'}


ALLOWED_HOSTS = _split_env_list(
    'ALLOWED_HOSTS',
    'localhost,127.0.0.1,0.0.0.0',
)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'rest_framework_simplejwt.token_blacklist',
    'drf_spectacular',
    # Local apps
    'apps.accounts',
    'apps.authentication',
    'apps.core',
    'apps.commons',
    'apps.classes.apps.ClassesConfig',
    'apps.notification',
    'apps.chatbot',
    'apps.material',
]

AUTH_USER_MODEL = 'accounts.User'

MIDDLEWARE = [
    # Health-check middleware — MUST be first so K8s probes bypass ALLOWED_HOSTS.
    'core.middleware.HealthCheckMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'core.middleware.RequestLogMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

def _build_databases_from_url(database_url: str):
    parsed = urlparse(database_url)

    if parsed.scheme in {'postgres', 'postgresql'}:
        return {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': (parsed.path or '').lstrip('/'),
                'USER': parsed.username or '',
                'PASSWORD': parsed.password or '',
                'HOST': parsed.hostname or 'localhost',
                'PORT': str(parsed.port or 5432),
            }
        }

    if parsed.scheme == 'sqlite':
        # sqlite:///db.sqlite3 -> /db.sqlite3
        sqlite_path = (parsed.path or '').lstrip('/') or 'db.sqlite3'
        return {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / sqlite_path,
            }
        }

    raise ValueError(f'Unsupported DATABASE_URL scheme: {parsed.scheme}')


DATABASES = _build_databases_from_url(os.getenv('DATABASE_URL', 'postgresql://ai_amooz:ai_amooz_password@localhost:5432/ai_amooz'))

# Keep DB connections alive for 10 min instead of reconnecting every request.
# Critical for 100+ concurrent users — avoids ~5-10ms per-request connect overhead.
DATABASES['default']['CONN_MAX_AGE'] = _get_env_int('CONN_MAX_AGE', 600)
DATABASES['default']['CONN_HEALTH_CHECKS'] = True  # verify stale connections before use

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise — serve static files directly from Gunicorn (no nginx needed).
# Compresses and caches automatically in production.
#
# Media storage: when AWS_STORAGE_BUCKET_NAME is set, all FileField /
# ImageField uploads go to S3-compatible storage (MinIO / Hamravesh Object
# Storage / real AWS S3).  Otherwise falls back to local filesystem (dev).
# ---------------------------------------------------------------------------
_USE_S3 = bool(os.getenv('AWS_STORAGE_BUCKET_NAME'))

# Log which storage mode is active so every pod's startup logs are explicit.
import logging as _logging
_startup_logger = _logging.getLogger('core.settings')
if _USE_S3:
    _startup_logger.info(
        'S3 storage ACTIVE — bucket=%s endpoint=%s',
        os.getenv('AWS_STORAGE_BUCKET_NAME'),
        os.getenv('AWS_S3_ENDPOINT_URL'),
    )
else:
    _startup_logger.warning(
        'S3 storage INACTIVE (AWS_STORAGE_BUCKET_NAME not set) — '
        'using local FileSystemStorage. If this is production, '
        'set AWS_STORAGE_BUCKET_NAME, AWS_ACCESS_KEY_ID, '
        'AWS_SECRET_ACCESS_KEY, AWS_S3_ENDPOINT_URL on this pod.',
    )

if _USE_S3:
    # S3-compatible object storage (MinIO, Hamravesh, AWS, etc.)
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = os.getenv('AWS_S3_ENDPOINT_URL')           # e.g. http://minio:9000
    AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'us-east-1')
    AWS_S3_CUSTOM_DOMAIN = os.getenv('AWS_S3_CUSTOM_DOMAIN', '')     # public URL if different
    AWS_DEFAULT_ACL = os.getenv('AWS_DEFAULT_ACL', None)             # None = bucket default
    AWS_S3_FILE_OVERWRITE = False                                     # never silently overwrite
    AWS_QUERYSTRING_AUTH = os.getenv('AWS_QUERYSTRING_AUTH', 'True') == 'True'  # signed URLs
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    AWS_S3_ADDRESSING_STYLE = 'path'                                  # required for MinIO

    # boto3 connection config — prevent Gunicorn workers from hanging if
    # MinIO is temporarily unreachable.
    from botocore.config import Config as _BotoConfig                 # noqa: E402
    AWS_S3_CONFIG = _BotoConfig(
        connect_timeout=5,          # seconds to wait for TCP connection
        read_timeout=300,           # seconds to wait for response data (large video files)
        retries={'max_attempts': 2, 'mode': 'standard'},
    )

    STORAGES = {
        'default': {
            # ProxiedS3Storage generates /media/<key> URLs so the browser
            # always goes through Django — no need to expose MinIO publicly.
            # If AWS_S3_CUSTOM_DOMAIN is set, it falls back to standard
            # S3 public URLs automatically.
            'BACKEND': 'core.storage_backends.ProxiedS3Storage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }
    # Media URL: always /media/ — the proxy view handles S3 streaming.
    # If a public S3 domain is used, ProxiedS3Storage.url() returns full URLs instead.
    MEDIA_URL = '/media/'
else:
    # Local filesystem (development / single-pod setups).
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }
    MEDIA_URL = '/media/'

MEDIA_ROOT = BASE_DIR / 'media'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'core.exception_handlers.api_exception_handler',
    # Rate limiting — prevent abuse and protect expensive endpoints.
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.getenv('THROTTLE_RATE_ANON', '60/minute'),
        'user': os.getenv('THROTTLE_RATE_USER', '300/minute'),
    },
    # Global pagination — all list endpoints return at most PAGE_SIZE items.
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': _get_env_int('DRF_PAGE_SIZE', 50),
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'AI_AMOOZ API',
    'DESCRIPTION': 'Comprehensive API documentation for AI_AMOOZ Educational Platform',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_PATCH': True,
    'COMPONENT_SPLIT_REQUEST': True,
    'COMPONENT_NO_READ_ONLY_REQUIRED': True,
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
    },
    'SECURITY': [
        {
            'jwtAuth': [],
        }
    ],
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'jwtAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
        }
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS: allow-all by default only in DEBUG, override via env in production.
CORS_ALLOW_ALL_ORIGINS = os.getenv(
    'CORS_ALLOW_ALL_ORIGINS',
    'True' if DEBUG else 'False',
) == 'True'
CORS_ALLOWED_ORIGINS = _split_env_list('CORS_ALLOWED_ORIGINS')
CORS_ALLOW_CREDENTIALS = os.getenv('CORS_ALLOW_CREDENTIALS', 'True') == 'True'
# Ensure large file upload headers are allowed in preflight responses.
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'content-disposition',
    'cache-control',
]

# Reverse proxy / HTTPS support.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

# ---------------------------------------------------------------------------
# Production security — enabled automatically when DEBUG=False.
# ---------------------------------------------------------------------------
if not DEBUG:
    # HTTPS enforcement — default OFF because K8s ingress/reverse proxy handles SSL.
    # Set SECURE_SSL_REDIRECT=True only if your proxy does NOT handle HTTPS.
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'False') == 'True'
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # HSTS — instruct browsers to only use HTTPS for this domain.
    SECURE_HSTS_SECONDS = _get_env_int('SECURE_HSTS_SECONDS', 31536000)  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Prevent content-type sniffing & clickjacking.
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

    # Ensure SECRET_KEY is not the default insecure value.
    if 'insecure' in SECRET_KEY:
        raise ValueError(
            'DJANGO_SECRET_KEY must be set to a secure random value '
            'when DEBUG=False. Generate one with: '
            'python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"'
        )

# CSRF trusted origins for admin/UI if needed.
CSRF_TRUSTED_ORIGINS = _split_env_list('CSRF_TRUSTED_ORIGINS')

# Allow large file uploads (defaults can be overridden via env)
MAX_UPLOAD_MB = _get_env_int('MAX_UPLOAD_MB', 500)
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_MB * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_MB * 1024 * 1024

# Force large uploads to stream to disk instead of staying in memory.
# Files > 2.5 MB are written to /tmp automatically.
FILE_UPLOAD_HANDLERS = [
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
]

# Max size for transcription uploads (applies to class + exam prep step 1).
TRANSCRIPTION_MAX_UPLOAD_MB = _get_env_int('TRANSCRIPTION_MAX_UPLOAD_MB', 500)
TRANSCRIPTION_MAX_UPLOAD_BYTES = TRANSCRIPTION_MAX_UPLOAD_MB * 1024 * 1024

# Pipeline execution: when enabled, Step 1/2 return quickly and work continues in background.
# Default is disabled to keep request/response deterministic (and test-friendly).
CLASS_PIPELINE_ASYNC = os.getenv(
    'CLASS_PIPELINE_ASYNC',
    'True' if not DEBUG else 'False',
) == 'True'

# ---------------------------------------------------------------------------
# Celery (task queue) – used for heavy AI / transcription workloads.
# ---------------------------------------------------------------------------
REDIS_URL = os.getenv('REDIS_URL') or os.getenv('CHAT_REDIS_URL') or 'redis://localhost:6379/0'

# ---------------------------------------------------------------------------
# Cache — shared Redis cache for throttle counters, sessions, and app caching.
# Using LocMemCache in local dev falls back automatically if Redis is unavailable.
# ---------------------------------------------------------------------------
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
        'KEY_PREFIX': 'aiamooz',
        'TIMEOUT': 300,  # 5 min default TTL
    }
}

# Use cache-backed sessions instead of DB — saves a DB round-trip per request.
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', REDIS_URL)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# CRITICAL: Celery's built-in default queue is named "celery", but the
# worker command uses  -Q default,pipeline .  Without the line below,
# any task NOT listed in CELERY_TASK_ROUTES (e.g. SMS tasks) would be
# published to the "celery" queue — which no worker ever consumes.
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_TIME_LIMIT = _get_env_int('CELERY_TASK_TIME_LIMIT', 2 * 60 * 60)       # 2 h
CELERY_TASK_SOFT_TIME_LIMIT = _get_env_int('CELERY_TASK_SOFT_TIME_LIMIT', 100 * 60)  # 100 min
CELERY_WORKER_PREFETCH_MULTIPLIER = 1   # important for long-running tasks
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Route heavy pipeline tasks to a dedicated queue so SMS / fast tasks
# are never starved.  Workers MUST listen on both queues:
#   celery -A core worker -Q default,pipeline --concurrency=2
# NOTE: Hamravesh Celery CMD must include: -Q default,pipeline
CELERY_TASK_ROUTES = {
    'apps.classes.tasks.process_class_full_pipeline': {'queue': 'pipeline'},
    'apps.classes.tasks.process_class_step1_transcription': {'queue': 'pipeline'},
    'apps.classes.tasks.process_class_step2_structure': {'queue': 'pipeline'},
    'apps.classes.tasks.process_class_step3_prerequisites': {'queue': 'pipeline'},
    'apps.classes.tasks.process_class_step4_prereq_teaching': {'queue': 'pipeline'},
    'apps.classes.tasks.process_class_step5_recap': {'queue': 'pipeline'},
    'apps.classes.tasks.process_exam_prep_full_pipeline': {'queue': 'pipeline'},
    'apps.classes.tasks.process_exam_prep_step1_transcription': {'queue': 'pipeline'},
    'apps.classes.tasks.process_exam_prep_step2_structure': {'queue': 'pipeline'},
    # SMS and lightweight tasks explicitly on the default queue.
    'apps.classes.tasks.send_publish_sms_task': {'queue': 'default'},
    'apps.classes.tasks.send_new_invites_sms_task': {'queue': 'default'},
    'apps.classes.tasks.cleanup_stale_sessions': {'queue': 'default'},
}
CELERY_TASK_REJECT_ON_WORKER_LOST = True  # requeue tasks if worker is killed (OOM)

# Periodic tasks (celery beat) — run cleanup_stale_sessions every 30 min.
CELERY_BEAT_SCHEDULE = {
    'cleanup-stale-sessions': {
        'task': 'apps.classes.tasks.cleanup_stale_sessions',
        'schedule': 30 * 60,  # every 30 minutes
    },
}

# ---------------------------------------------------------------------------
# Logging — structured JSON-ready logging for production.
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
LOG_HTTP = _get_env_bool('LOG_HTTP', True)
LOG_SQL = _get_env_bool('LOG_SQL', False)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {'level': 'WARNING', 'propagate': True},
        'django.request': {'level': 'INFO' if LOG_HTTP else 'WARNING', 'propagate': True},
        'django.server': {'level': 'INFO' if LOG_HTTP else 'WARNING', 'propagate': True},
        'core.request': {'level': 'INFO' if LOG_HTTP else 'WARNING', 'propagate': True},
        # Suppress noisy DisallowedHost errors from scanners/bots.
        'django.security.DisallowedHost': {
            'level': 'CRITICAL',
            'propagate': False,
        },
        'celery': {'level': 'INFO', 'propagate': True},
        'celery.app.trace': {'level': 'INFO', 'propagate': True},
        'apps': {'level': 'INFO', 'propagate': True},
    },
}

if LOG_SQL:
    LOGGING['loggers']['django.db.backends'] = {
        'level': 'DEBUG',
        'propagate': True,
    }

