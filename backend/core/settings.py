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
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
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

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'core.exception_handlers.api_exception_handler',
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
CORS_ALLOW_CREDENTIALS = os.getenv('CORS_ALLOW_CREDENTIALS', 'False') == 'True'

# Reverse proxy / HTTPS support.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

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
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', REDIS_URL)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_TIME_LIMIT = _get_env_int('CELERY_TASK_TIME_LIMIT', 6 * 60 * 60)       # 6 h
CELERY_TASK_SOFT_TIME_LIMIT = _get_env_int('CELERY_TASK_SOFT_TIME_LIMIT', 5 * 60 * 60)  # 5 h
CELERY_WORKER_PREFETCH_MULTIPLIER = 1   # important for long-running tasks
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# ---------------------------------------------------------------------------
# Logging — structured JSON-ready logging for production.
# ---------------------------------------------------------------------------
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
        'level': 'INFO',
    },
    'loggers': {
        'django': {'level': 'WARNING', 'propagate': True},
        'celery': {'level': 'INFO', 'propagate': True},
        'apps': {'level': 'INFO', 'propagate': True},
    },
}

