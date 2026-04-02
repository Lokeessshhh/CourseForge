"""
Chat app URLs for course management.
"""
from django.urls import path
from .views import (
    chat_course_management,
    chat_create_course,
)

urlpatterns = [
    # Main chat endpoint for course management (handles list, create, delete with confirmation, show)
    path("", chat_course_management, name="chat-course-management"),

    # Course creation endpoint (if all details provided via form)
    path("create/", chat_create_course, name="chat-create-course"),
]
