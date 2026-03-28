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
