"""Django settings - Production."""
from .base import *  # noqa: F401, F403
import os

DEBUG = False

# SSL redirect - enabled for production deployments
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True") == "True"

# Disable trailing slash redirects to prevent 301 on API calls
APPEND_SLASH = False

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
if not ALLOWED_HOSTS:
    raise RuntimeError("ALLOWED_HOSTS must be set in production")

if not SECRET_KEY or SECRET_KEY == "change-me-in-production":  # type: ignore[name-defined]  # noqa: F405
    raise RuntimeError("DJANGO_SECRET_KEY must be set to a strong value in production")

# ──────────────────────────────────────────────
# Security hardening
# ──────────────────────────────────────────────
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# HSTS (HTTP Strict Transport Security)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# SSL
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True") == "True"
SECURE_REDIRECT_EXEMPT = [r"^health/?"]

# Cookies
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# ──────────────────────────────────────────────
# CORS - Strict in production
# ──────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = []
CORS_EXTRA_ORIGINS = os.environ.get("CORS_EXTRA_ORIGINS", "")
if CORS_EXTRA_ORIGINS:
    CORS_ALLOWED_ORIGINS = [o.strip() for o in CORS_EXTRA_ORIGINS.split(",") if o.strip()]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

if not CORS_ALLOWED_ORIGINS:
    raise RuntimeError("CORS_EXTRA_ORIGINS must be set in production")

# Allow API/WebSocket calls from the frontend origin(s) via CSP.
# SECURITY_HEADERS_CSP is consumed by utils.middleware.SecurityHeadersMiddleware.
_csp_connect = " ".join(["'self'"] + CORS_ALLOWED_ORIGINS)
SECURITY_HEADERS_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    f"connect-src {_csp_connect}; "
    "frame-ancestors 'none';"
)

# ──────────────────────────────────────────────
# Rate Limiting - Enabled in production
# ──────────────────────────────────────────────
RATE_LIMIT_ENABLED = True
RATE_LIMIT_REQUESTS_PER_HOUR = 1000
RATE_LIMIT_BLOCK_DURATION = 3600

AUTH_RATE_LIMIT_ENABLED = True
AUTH_RATE_LIMIT_MAX_FAILURES = 10
AUTH_RATE_LIMIT_WINDOW = 60
AUTH_RATE_LIMIT_BLOCK_DURATION = 300

# ──────────────────────────────────────────────
# Production Middleware
# ──────────────────────────────────────────────
MIDDLEWARE = [
    "utils.middleware.SecurityHeadersMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "utils.middleware.RateLimitMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "utils.middleware.RequestLoggingMiddleware",
]

# ──────────────────────────────────────────────
# Static Files - WhiteNoise
# ──────────────────────────────────────────────
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ──────────────────────────────────────────────
# Production REST Framework
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
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "utils.exceptions.custom_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
    },
}

# ──────────────────────────────────────────────
# Production logging
# ──────────────────────────────────────────────
LOG_DIR = os.environ.get("LOG_DIR", "/var/log/learnai")
try:
    os.makedirs(LOG_DIR, exist_ok=True)
except Exception:
    # Don't crash on import if filesystem is read-only; console logging still works.
    LOG_DIR = None

if LOG_DIR:
    LOGGING["handlers"]["file"] = {  # type: ignore[name-defined]  # noqa: F405
        "class": "logging.handlers.RotatingFileHandler",
        "filename": f"{LOG_DIR}/django.log",
        "formatter": "verbose",
        "maxBytes": 10485760,  # 10MB
        "backupCount": 5,
    }
    LOGGING["handlers"]["error_file"] = {  # type: ignore[name-defined]  # noqa: F405
        "class": "logging.handlers.RotatingFileHandler",
        "filename": f"{LOG_DIR}/error.log",
        "formatter": "verbose",
        "level": "ERROR",
        "maxBytes": 10485760,
        "backupCount": 5,
    }
    LOGGING["root"]["handlers"] = ["console", "file"]  # type: ignore[name-defined]  # noqa: F405
    LOGGING["loggers"]["django"]["handlers"] = ["console", "file"]  # type: ignore[name-defined]  # noqa: F405
    LOGGING["loggers"]["apps"]["handlers"] = ["console", "file"]  # type: ignore[name-defined]  # noqa: F405
    LOGGING["loggers"]["services"]["handlers"] = ["console", "file"]  # type: ignore[name-defined]  # noqa: F405
else:
    LOGGING["root"]["handlers"] = ["console"]  # type: ignore[name-defined]  # noqa: F405
    LOGGING["loggers"]["django"]["handlers"] = ["console"]  # type: ignore[name-defined]  # noqa: F405
    LOGGING["loggers"]["apps"]["handlers"] = ["console"]  # type: ignore[name-defined]  # noqa: F405
    LOGGING["loggers"]["services"]["handlers"] = ["console"]  # type: ignore[name-defined]  # noqa: F405
LOGGING["loggers"]["django"]["level"] = "WARNING"  # type: ignore[name-defined]  # noqa: F405
LOGGING["loggers"]["apps"]["level"] = "INFO"  # type: ignore[name-defined]  # noqa: F405
LOGGING["loggers"]["services"]["level"] = "INFO"  # type: ignore[name-defined]  # noqa: F405

# ──────────────────────────────────────────────
# Email backend - Use real email in production
# ──────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.sendgrid.net")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@learnai.com")
