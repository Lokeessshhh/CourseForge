"""Certificates app URL patterns."""
from django.urls import path
from . import views

urlpatterns = [
    # User certificates
    path("",                            views.certificate_list,      name="certificate-list"),
    path("locked/",                     views.locked_certificates,   name="certificate-locked"),
    path("unlocked/",                   views.unlocked_certificates, name="certificate-unlocked"),
    
    # Course-specific certificate
    path("courses/<uuid:course_id>/",   views.course_certificate,    name="course-certificate"),
    
    # Public verification
    path("verify/<str:certificate_id>/", views.verify_certificate,   name="verify-certificate"),
]
