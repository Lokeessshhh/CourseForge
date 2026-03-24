"""
ASGI config — Django Channels ProtocolTypeRouter.
Handles both HTTP requests and WebSocket connections.
"""
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# Get the default Django ASGI application for HTTP requests
django_asgi_app = get_asgi_application()

# Import WebSocket URL patterns (after Django is set up)
from apps.websockets.routing import websocket_urlpatterns  # noqa: E402
from services.auth.clerk import ClerkWebSocketMiddleware   # noqa: E402

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
