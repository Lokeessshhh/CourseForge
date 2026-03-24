"""
WebSocket routing configuration.
"""
from django.urls import re_path
from websockets.consumers import CourseChatConsumer

websocket_urlpatterns = [
    re_path(r"ws/chat/(?P<course_id>[\w-]+)/$", CourseChatConsumer.as_asgi()),
]
