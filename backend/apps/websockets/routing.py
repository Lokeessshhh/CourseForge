"""WebSocket URL routing — /api/ws/chat/{session_id}/"""
from django.urls import re_path
from .consumers import ChatConsumer

websocket_urlpatterns = [
    re_path(r"api/ws/chat/(?P<session_id>[^/]+)/$", ChatConsumer.as_asgi()),
]
