"""Quizzes app URL patterns (included via courses URLs or standalone)."""
from django.urls import path
from . import views

urlpatterns = [
    # These patterns are mounted under courses app URLs:
    # /api/courses/{id}/weeks/{w}/days/{d}/quiz/
    path(
        "courses/<uuid:course_id>/weeks/<int:week_number>/days/<int:day_number>/quiz/",
        views.quiz_list,
        name="quiz-list",
    ),
    path(
        "courses/<uuid:course_id>/weeks/<int:week_number>/days/<int:day_number>/quiz/submit/",
        views.quiz_submit,
        name="quiz-submit",
    ),
    path(
        "courses/<uuid:course_id>/weeks/<int:week_number>/days/<int:day_number>/quiz/results/",
        views.quiz_results,
        name="quiz-results",
    ),
]
