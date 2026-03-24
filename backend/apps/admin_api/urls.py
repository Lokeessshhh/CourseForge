"""Admin API URL patterns."""
from django.urls import path
from . import views

urlpatterns = [
    path("stats/", views.admin_stats, name="admin-stats"),
    path("users/", views.admin_users, name="admin-users"),
]
