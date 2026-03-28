"""
Django settings - Base configuration.
All environment-specific settings inherit from this.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
import importlib.util

load_dotenv()

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ──────────────────────────────────────────────
# Security
# ──────────────────────────────────────────────
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "change-me-in-production")
DEBUG = False
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")

# ──────────────────────────────────────────────
# Application definition
# ──────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "channels",
    "django_celery_beat",
    "django_celery_results",
    "django_extensions",
]

_HAS_DRF_SPECTACULAR = importlib.util.find_spec("drf_spectacular") is not None
if _HAS_DRF_SPECTACULAR:
    THIRD_PARTY_APPS.insert(2, "drf_spectacular")

LOCAL_APPS = [
    "apps.users",
    "apps.courses",
    "apps.rag",
    "apps.conversations",
    "apps.quizzes",
    "apps.certificates",
    "apps.cache",
    "apps.websockets",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # must be high up
    "utils.middleware.SecurityHeadersMiddleware",  # Security headers
    "utils.middleware.RequestLoggingMiddleware",  # Request logging
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ──────────────────────────────────────────────
# Database — PostgreSQL + pgvector
# ──────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "learnai"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "OPTIONS": {
            "options": "-c search_path=public",
        },
    }
}

# ──────────────────────────────────────────────
# Redis
# ──────────────────────────────────────────────
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# ──────────────────────────────────────────────
# Django Channels — Redis layer
# ──────────────────────────────────────────────
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
            "capacity": 1500,
            "expiry": 10,
        },
    }
}

# ──────────────────────────────────────────────
# Cache — Redis
# ──────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "RETRY_ON_TIMEOUT": True,
        },
    }
}

# ──────────────────────────────────────────────
# Sessions — Redis-backed
# ──────────────────────────────────────────────
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# ──────────────────────────────────────────────
# Celery
# ──────────────────────────────────────────────
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = "django-db"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# ──────────────────────────────────────────────
# Django REST Framework
# ──────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "services.auth.clerk.ClerkAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "EXCEPTION_HANDLER": "utils.exceptions.custom_exception_handler",
}

if _HAS_DRF_SPECTACULAR:
    REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] = "drf_spectacular.openapi.AutoSchema"

# ──────────────────────────────────────────────
# drf-spectacular (API docs)
# ──────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE": "LearnAI API",
    "DESCRIPTION": "AI-powered course generation and tutoring backend.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# ──────────────────────────────────────────────
# CORS
# ──────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]
CORS_ALLOW_CREDENTIALS = True
CORS_EXTRA_ORIGINS = os.environ.get("CORS_EXTRA_ORIGINS", "")
if CORS_EXTRA_ORIGINS:
    CORS_ALLOWED_ORIGINS += [o.strip() for o in CORS_EXTRA_ORIGINS.split(",") if o.strip()]

# ──────────────────────────────────────────────
# Password validation
# ──────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ──────────────────────────────────────────────
# Internationalisation
# ──────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ──────────────────────────────────────────────
# Static files
# ──────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Whitenoise configuration
WHITENOISE_STATIC_ROOT = STATIC_ROOT

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ──────────────────────────────────────────────
# Clerk Authentication
# ──────────────────────────────────────────────
CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY", "")
CLERK_JWKS_URL = os.environ.get(
    "CLERK_JWKS_URL", "https://api.clerk.com/v1/jwks"
)
CLERK_WEBHOOK_SECRET = os.environ.get("CLERK_WEBHOOK_SECRET", "")

# ──────────────────────────────────────────────
# vLLM Server Configuration
# ──────────────────────────────────────────────
VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL", "http://localhost:8000")
VLLM_MODEL = os.environ.get("VLLM_MODEL", "qwen-coder")
VLLM_API_KEY = os.environ.get("VLLM_API_KEY", "none")
VLLM_MAX_TOKENS = int(os.environ.get("VLLM_MAX_TOKENS", "3000"))
VLLM_STREAM_TIMEOUT = int(os.environ.get("VLLM_STREAM_TIMEOUT", "120"))
VLLM_TIMEOUT_SECONDS = int(os.environ.get("VLLM_TIMEOUT_SECONDS", "120"))
VLLM_SDK_MAX_RETRIES = int(os.environ.get("VLLM_SDK_MAX_RETRIES", "0"))

# Generation parameters for different use cases
GENERATION_PARAMS = {
    "course":   {"temperature": 0.3, "max_tokens": 3000, "top_p": 0.9},
    "quiz":     {"temperature": 0.4, "max_tokens": 2000, "top_p": 0.85},
    "content":  {"temperature": 0.5, "max_tokens": 3000, "top_p": 0.9},
    "chat":     {"temperature": 0.7, "max_tokens": 1000, "top_p": 0.95},
    "code":     {"temperature": 0.2, "max_tokens": 2000, "top_p": 0.85},
    "test":     {"temperature": 0.3, "max_tokens": 3000, "top_p": 0.85},
    "topic":    {"temperature": 0.1, "max_tokens": 50, "top_p": 0.9},
}

# ──────────────────────────────────────────────
# Embedding models
# ──────────────────────────────────────────────
EMBEDDING_MODEL_PRIMARY = os.environ.get(
    "EMBEDDING_MODEL_PRIMARY", "Qwen/Qwen3-Embedding"
)
EMBEDDING_MODEL_FALLBACK = os.environ.get(
    "EMBEDDING_MODEL_FALLBACK", "sentence-transformers/all-MiniLM-L6-v2"
)
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "384"))

# ──────────────────────────────────────────────
# External APIs
# ──────────────────────────────────────────────
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
JUDGE0_API_URL = os.environ.get("JUDGE0_API_URL", "https://judge0.example.com")
JUDGE0_API_KEY = os.environ.get("JUDGE0_API_KEY", "")

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "services": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
