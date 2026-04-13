"""Django settings - Development."""
from .base import *  # noqa: F401, F403
import os

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# Disable SSL redirect in development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Allow any CORS origin in development
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# Disable rate limiting for testing
RATE_LIMIT_ENABLED = False
AUTH_RATE_LIMIT_ENABLED = False

# Development middleware (add security headers but no rate limiting)
MIDDLEWARE = [
    "utils.middleware.SecurityHeadersMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "utils.middleware.RequestLoggingMiddleware",
]

# Reduce SQL query noise in console
LOGGING["loggers"]["django.db.backends"] = {  # type: ignore[name-defined]  # noqa: F405
    "handlers": ["console"],
    "level": "WARNING",
    "propagate": False,
}

# Enhanced logging for development - show INFO level for background tasks
LOGGING["root"] = {  # type: ignore[name-defined]
    "handlers": ["console"],
    "level": "INFO",  # Show INFO logs (needed for task logs)
}

# Show Django server logs
LOGGING["loggers"]["django"] = {  # type: ignore[name-defined]
    "handlers": ["console"],
    "level": "INFO",
    "propagate": False,
}

# Show WebSocket logs
LOGGING["loggers"]["websockets"] = {  # type: ignore[name-defined]
    "handlers": ["console"],
    "level": "INFO",
    "propagate": False,
}

# Show Channels logs
LOGGING["loggers"]["channels"] = {  # type: ignore[name-defined]
    "handlers": ["console"],
    "level": "INFO",
    "propagate": False,
}

# Show course generation logs (IMPORTANT - shows weekly test progress)
LOGGING["loggers"]["apps.courses"] = {  # type: ignore[name-defined]
    "handlers": ["console"],
    "level": "INFO",
    "propagate": False,
}

# Show WebSocket consumer logs
LOGGING["loggers"]["apps.websockets"] = {  # type: ignore[name-defined]
    "handlers": ["console"],
    "level": "INFO",
    "propagate": False,
}

# Show SSE and course tasks logs
LOGGING["loggers"]["apps.courses.tasks"] = {  # type: ignore[name-defined]
    "handlers": ["console"],
    "level": "INFO",
    "propagate": False,
}

# Show Tavily web search logs
LOGGING["loggers"]["services.web_search"] = {  # type: ignore[name-defined]
    "handlers": ["console"],
    "level": "INFO",
    "propagate": False,
}

LOGGING["loggers"]["services.web_search.tavily_client"] = {  # type: ignore[name-defined]
    "handlers": ["console"],
    "level": "INFO",
    "propagate": False,
}

# Show course web search logs
LOGGING["loggers"]["services.course"] = {  # type: ignore[name-defined]
    "handlers": ["console"],
    "level": "INFO",
    "propagate": False,
}

LOGGING["loggers"]["services.course.web_search"] = {  # type: ignore[name-defined]
    "handlers": ["console"],
    "level": "INFO",
    "propagate": False,
}

# Show LLM client logs (shows API calls)
LOGGING["loggers"]["services.llm"] = {  # type: ignore[name-defined]
    "handlers": ["console"],
    "level": "INFO",
    "propagate": False,
}

# Show course generator logs (shows test/question generation)
LOGGING["loggers"]["services.course.generator"] = {  # type: ignore[name-defined]
    "handlers": ["console"],
    "level": "INFO",
    "propagate": False,
}

# HIDE noisy debug logs
LOGGING["loggers"]["httpx"] = {  # type: ignore[name-defined]
    "handlers": ["console"],
    "level": "WARNING",  # Hide HTTP debug logs
    "propagate": False,
}

LOGGING["loggers"]["httpcore"] = {  # type: ignore[name-defined]
    "handlers": ["console"],
    "level": "WARNING",  # Hide HTTP connection logs
    "propagate": False,
}

LOGGING["loggers"]["django.db.backends"] = {  # type: ignore[name-defined]
    "handlers": ["console"],
    "level": "WARNING",  # Hide SQL query logs
    "propagate": False,
}

# Development REST framework - allow any for testing
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "services.auth.clerk.ClerkAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "utils.exceptions.custom_exception_handler",
}

# Simplified email backend for dev
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# vLLM development URL
VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL", "http://localhost:8000")

# Static files for admin
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = []

# Use in-memory channel layer for development (no Redis required)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}

# Note: Logging is configured via Django's LOGGING dict above.
# Do NOT call logging.basicConfig() here as it will override the proper configuration.
