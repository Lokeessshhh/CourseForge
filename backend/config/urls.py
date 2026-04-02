"""
Master URL configuration.
All app URL files are included here with the /api/ prefix.
API docs served at /api/docs/ (Swagger) and /api/schema/ (OpenAPI JSON).
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from django.conf import settings
from django.conf.urls.static import static
try:
    from drf_spectacular.views import (
        SpectacularAPIView,
        SpectacularRedocView,
        SpectacularSwaggerView,
    )
except Exception:
    SpectacularAPIView = None
    SpectacularRedocView = None
    SpectacularSwaggerView = None
import httpx
import logging
import time

logger = logging.getLogger(__name__)


def health_check(request):
    """
    Health check endpoint - no auth required.
    Checks: database, redis, vLLM, Celery.
    """
    from django.conf import settings

    services = {}
    status = "ok"

    # Database check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        services["database"] = "ok"
    except Exception as e:
        services["database"] = "error"
        status = "degraded"
        logger.error("Health check: database error: %s", e)

    # Redis check
    try:
        cache.set("health_check", "ok", 10)
        if cache.get("health_check") == "ok":
            services["redis"] = "ok"
        else:
            services["redis"] = "error"
            status = "degraded"
    except Exception as e:
        services["redis"] = "error"
        status = "degraded"
        logger.error("Health check: redis error: %s", e)

    # vLLM check
    try:
        vllm_url = getattr(settings, "VLLM_BASE_URL", "http://localhost:8000")
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{vllm_url}/health")
            if resp.status_code == 200:
                services["vllm"] = "ok"
            else:
                services["vllm"] = "error"
                status = "degraded"
    except Exception as e:
        services["vllm"] = "error"
        status = "degraded"
        logger.warning("Health check: vLLM error: %s", e)

    # Celery check (via Redis)
    try:
        from config.celery import app as celery_app
        inspect = celery_app.control.inspect()
        active = inspect.active()
        if active:
            services["celery"] = "ok"
        else:
            services["celery"] = "degraded"
            if status == "ok":
                status = "degraded"
    except Exception as e:
        services["celery"] = "error"
        status = "degraded"
        logger.warning("Health check: celery error: %s", e)

    return JsonResponse({
        "status": status,
        "services": services,
        "version": "1.0.0",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })


urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),

    # Health check (no auth)
    path("api/health/", health_check),

    # OpenAPI schema + docs (optional)
    *(
        [
            path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
            path(
                "api/docs/",
                SpectacularSwaggerView.as_view(url_name="schema"),
                name="swagger-ui",
            ),
            path(
                "api/redoc/",
                SpectacularRedocView.as_view(url_name="schema"),
                name="redoc",
            ),
        ]
        if SpectacularAPIView is not None
        else []
    ),

    # App routers
    path("api/users/",         include("apps.users.urls")),
    path("api/courses/",       include("apps.courses.urls")),
    path("api/rag/",           include("apps.rag.urls")),
    path("api/conversations/", include("apps.conversations.urls")),
    path("api/quizzes/",       include("apps.quizzes.urls")),
    path("api/certificates/",  include("apps.certificates.urls")),
    path("api/webhooks/",      include("apps.users.webhook_urls")),
    path("api/admin/",         include("apps.admin_api.urls")),
    path("api/chat/",          include("apps.chat.urls")),  # Chat course management
]

# Static files for admin
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
