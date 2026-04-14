"""
Django settings - Base configuration.
All environment-specific settings inherit from this.
"""
import os
import sys
import io
from pathlib import Path
from dotenv import load_dotenv
import importlib.util

# ──────────────────────────────────────────────
# Fix Windows console encoding for ALL loggers
# ──────────────────────────────────────────────
if sys.platform == 'win32':
    # Force UTF-8 encoding for all I/O
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    # Ensure stdout/stderr use UTF-8 encoding with line buffering
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
        except (AttributeError, ValueError, OSError):
            pass
    if hasattr(sys.stderr, 'reconfigure'):
        try:
            sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
        except (AttributeError, ValueError, OSError):
            pass
    
    # Patch all StreamHandler instances to use UTF-8
    import logging
    
    def _make_patched_emit(original_emit):
        def _patched_emit(self, record):
            try:
                # Try to set UTF-8 encoding on the stream if it's a console
                if hasattr(self.stream, 'reconfigure') and hasattr(self.stream, 'encoding'):
                    if self.stream.encoding != 'utf-8':
                        self.stream.reconfigure(encoding='utf-8', errors='replace')
            except (AttributeError, ValueError, OSError):
                pass
            return original_emit(self, record)
        return _patched_emit
    
    logging.StreamHandler.emit = _make_patched_emit(logging.StreamHandler.emit)
    
    # Patch linecache to use UTF-8 when reading source files
    import linecache
    _original_updatecache = linecache.updatecache
    def _patched_updatecache(filename, module_globals=None):
        try:
            return _original_updatecache(filename, module_globals)
        except UnicodeDecodeError:
            try:
                with open(filename, 'r', encoding='utf-8', errors='replace') as fp:
                    lines = fp.readlines()
                    if lines and not lines[-1].endswith('\n'):
                        lines.append('\n')
                    linecache.cache[filename] = (len(lines), None, lines, filename)
                    return lines
            except Exception:
                return []
    linecache.updatecache = _patched_updatecache
    linecache.checkcache = _patched_updatecache

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
    "django_extensions",
]

_HAS_DRF_SPECTACULAR = importlib.util.find_spec("drf_spectacular") is not None
if _HAS_DRF_SPECTACULAR:
    THIRD_PARTY_APPS.insert(2, "drf_spectacular")

LOCAL_APPS = [
    "apps.core",  # Core utilities and management commands (must be first)
    "apps.users",
    "apps.courses",
    "apps.rag.apps.RagConfig",  # RAG (Retrieval-Augmented Generation) with reranker preload
    "apps.conversations",
    "apps.quizzes",
    "apps.certificates",
    "apps.cache",
    "apps.websockets",
    "apps.chat",  # Chat course management
    "apps.memory",  # Memory system (history, knowledge, cache, progress)
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
# Database — PostgreSQL + pgvector (Neon)
# ──────────────────────────────────────────────
# Support both DATABASE_URL (Neon format) and individual DB_* variables
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Parse DATABASE_URL if provided (Neon format)
    import re
    db_match = re.match(
        r'postgresql://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:/]+)(?::(?P<port>\d+))?/(?P<dbname>[^?]+)(?P<params>.*)',
        DATABASE_URL
    )
    if db_match:
        db_params = db_match.groupdict()
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": db_params.get("dbname", "CourseForge"),
                "USER": db_params.get("user", "neondb_owner"),
                "PASSWORD": db_params.get("password", ""),
                "HOST": db_params.get("host", "localhost"),
                "PORT": db_params.get("port", "5432"),
                "OPTIONS": {
                    "sslmode": "require",
                    "channel_binding": "require",
                },
                "CONN_MAX_AGE": 0,  # Required for Neon pooler compatibility
                "CONN_HEALTH_CHECKS": True,  # Enable connection health checks
            }
        }
    else:
        # Fallback to individual variables if URL parsing fails
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": os.environ.get("DB_NAME", "CourseForge"),
                "USER": os.environ.get("DB_USER", "neondb_owner"),
                "PASSWORD": os.environ.get("DB_PASSWORD", ""),
                "HOST": os.environ.get("DB_HOST", "localhost"),
                "PORT": os.environ.get("DB_PORT", "5432"),
                "OPTIONS": {
                    "sslmode": "require",
                    "channel_binding": "require",
                },
                "CONN_MAX_AGE": 0,
                "CONN_HEALTH_CHECKS": True,
            }
        }
else:
    # Use individual DB_* environment variables
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "CourseForge"),
            "USER": os.environ.get("DB_USER", "neondb_owner"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "OPTIONS": {
                "sslmode": "require",
                "channel_binding": "require",
            },
            "CONN_MAX_AGE": 0,
            "CONN_HEALTH_CHECKS": True,
        }
    }

# ──────────────────────────────────────────────
# Redis (Upstash)
# ──────────────────────────────────────────────
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Upstash requires SSL connection
REDIS_UPSTASH_SSL = REDIS_URL.startswith("rediss://")

# ──────────────────────────────────────────────
# Django Channels — Redis layer
# ──────────────────────────────────────────────
# For production with Upstash, use SSL connection
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
# Cache — Redis (Upstash)
# ──────────────────────────────────────────────
# Upstash requires SSL with cert_reqs=None
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 10,  # Increased timeout for cloud
            "SOCKET_TIMEOUT": 10,
            "RETRY_ON_TIMEOUT": True,
            "RETRY_ON_TIMEOUT_SECONDS": 5,
            # Required for Upstash SSL
            "SSL_CERT_REQS": None,
        },
    }
}

# ──────────────────────────────────────────────
# Sessions — Redis-backed
# ──────────────────────────────────────────────
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

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
# OpenRouter Configuration (LLM + Embeddings + Reranker)
# ──────────────────────────────────────────────
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# LLM Model
OPENROUTER_LLM_MODEL = os.environ.get("OPENROUTER_LLM_MODEL", "qwen/qwen-2.5-7b-instruct")
OPENROUTER_MAX_TOKENS = int(os.environ.get("OPENROUTER_MAX_TOKENS", "3000"))
OPENROUTER_STREAM_TIMEOUT = int(os.environ.get("OPENROUTER_STREAM_TIMEOUT", "120"))
OPENROUTER_TIMEOUT_SECONDS = int(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "120"))
OPENROUTER_SDK_MAX_RETRIES = int(os.environ.get("OPENROUTER_SDK_MAX_RETRIES", "0"))

# Embedding Model
OPENROUTER_EMBEDDING_MODEL = os.environ.get("OPENROUTER_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "1536"))
EMBEDDING_MODEL_FALLBACK = os.environ.get(
    "EMBEDDING_MODEL_FALLBACK", "sentence-transformers/all-MiniLM-L6-v2"
)

# Reranker Model
OPENROUTER_RERANKER_MODEL = os.environ.get("OPENROUTER_RERANKER_MODEL", "cohere/rerank-v3.5")

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
# Legacy vLLM Configuration (deprecated, kept for backward compatibility)
# ──────────────────────────────────────────────
VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL", "")
VLLM_MODEL = os.environ.get("VLLM_MODEL", "")
VLLM_API_KEY = os.environ.get("VLLM_API_KEY", "")

# ──────────────────────────────────────────────
# External APIs
# ──────────────────────────────────────────────
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
TAVILY_SEARCH_DEPTH = os.environ.get("TAVILY_SEARCH_DEPTH", "advanced")  # basic, advanced, fast, ultra-fast
TAVILY_MAX_RESULTS = int(os.environ.get("TAVILY_MAX_RESULTS", "5"))

JUDGE0_API_URL = os.environ.get("JUDGE0_API_URL", "https://judge0.example.com")
JUDGE0_API_KEY = os.environ.get("JUDGE0_API_KEY", "")

# ──────────────────────────────────────────────
# Redis (for SSE pub/sub and caching)
# ──────────────────────────────────────────────
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
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
            "level": "INFO",  # Changed from DEBUG to INFO for cleaner logs
            "propagate": False,
        },
        "services": {
            "handlers": ["console"],
            "level": "INFO",  # Changed from DEBUG to INFO for cleaner logs
            "propagate": False,
        },
    },
}
