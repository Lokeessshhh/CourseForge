"""
ASGI config — Django Channels ProtocolTypeRouter.
Handles both HTTP requests and WebSocket connections.
"""
import os
import logging
from django.core.asgi import get_asgi_application
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

# Set development settings for ASGI
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("[ASGI] Starting with settings: %s", os.environ.get("DJANGO_SETTINGS_MODULE"))

# Get the default Django ASGI application for HTTP requests
django_asgi_app = get_asgi_application()

# Wrap with static files handler for serving Django admin static files
django_asgi_app = ASGIStaticFilesHandler(django_asgi_app)

logger.info("[ASGI] HTTP application loaded")

# Import WebSocket URL patterns (after Django is set up)
from apps.websockets.routing import websocket_urlpatterns  # noqa: E402
from services.auth.clerk import ClerkWebSocketMiddleware   # noqa: E402

logger.info("[ASGI] WebSocket patterns loaded")

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            ClerkWebSocketMiddleware(
                URLRouter(websocket_urlpatterns)
            )
        ),
    }
)

logger.info("[ASGI] ProtocolTypeRouter configured")
