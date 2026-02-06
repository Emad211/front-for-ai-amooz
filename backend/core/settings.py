from pathlib import Path
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Ensure `backend/.env` is loaded regardless of the process working directory.
# (E.g. running `python backend/manage.py runserver` from the repo root.)
load_dotenv(dotenv_path=BASE_DIR / '.env')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-change-me-in-production')

DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,0.0.0.0').split(',')
    if host.strip()
]

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

from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOW_ALL_ORIGINS = True # For development only

# Allow large file uploads (up to 250MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 250 * 1024 * 1024  # 250MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 250 * 1024 * 1024  # 250MB

# Pipeline execution: when enabled, Step 1/2 return quickly and work continues in background.
# Default is disabled to keep request/response deterministic (and test-friendly).
CLASS_PIPELINE_ASYNC = os.getenv('CLASS_PIPELINE_ASYNC', 'False') == 'True'


# ============================================================================
# CORS Settings for Frontend Connection
# ============================================================================

# لیست دامنه‌های مجاز برای درخواست‌های cross-origin
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # توسعه محلی
    "https://front-for-ai-amooz.vercel.app",  # فرانت‌اند اصلی شما
]

# اجازه ارسال کوکی‌ها و هدرهای احراز هویت
CORS_ALLOW_CREDENTIALS = True

# متدهای HTTP مجاز
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# هدرهای مجاز
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
]

# برای توسعه: اگر نیاز به دسترسی همه دامنه‌ها دارید، این خط را فعال کنید
# CORS_ALLOW_ALL_ORIGINS = True


