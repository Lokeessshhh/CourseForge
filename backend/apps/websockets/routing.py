"""
WebSocket URL routing for LearnAI AI Tutor.

URL patterns:
ws/chat/                           → global chat (all courses context)
ws/chat/{course_id}/               → course-specific chat
ws/chat/{course_id}/{week}/{day}/  → day-specific chat

Query params:
?token=<jwt>       → Clerk JWT (required)
&session_id=<uuid> → Resume existing session (optional)
&include_sources=true → Include source references (optional)
"""
from django.urls import re_path
from .consumers import ChatConsumer

websocket_urlpatterns = [
    # Global chat - all courses context
    re_path(r"^ws/chat/$", ChatConsumer.as_asgi()),
    
    # Course-specific chat
    re_path(r"^ws/chat/(?P<course_id>[0-9a-f-]+)/$", ChatConsumer.as_asgi()),
    
    # Day-specific chat (course + week + day)
    re_path(
        r"^ws/chat/(?P<course_id>[0-9a-f-]+)/(?P<week>\d+)/(?P<day>\d+)/$",
        ChatConsumer.as_asgi()
    ),
]
