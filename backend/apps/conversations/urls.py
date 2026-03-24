"""Conversations app URL patterns — /api/conversations/"""
from django.urls import path
from . import views

urlpatterns = [
    path("",                     views.conversation_list,   name="conversation-list"),
    path("<uuid:session_id>/",   views.conversation_detail, name="conversation-detail"),
    path("<uuid:session_id>/delete/", views.conversation_delete, name="conversation-delete"),
]
