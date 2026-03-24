"""Clerk webhook URL — /api/webhooks/clerk/"""
from django.urls import path
from .webhooks import clerk_webhook

urlpatterns = [
    path("clerk/", clerk_webhook, name="clerk-webhook"),
]
