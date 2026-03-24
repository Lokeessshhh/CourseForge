"""Certificates app URL patterns."""
from django.urls import path
from . import views

urlpatterns = [
    path("",                            views.certificate_list,     name="certificate-list"),
]
