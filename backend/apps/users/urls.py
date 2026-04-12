"""Users app URL patterns — /api/users/"""
from django.urls import path
from . import views

urlpatterns = [
    path("me/",                            views.me,                   name="user-me"),
    path("me/progress/",                   views.UserProgressView.as_view(), name="user-progress"),
    path("me/knowledge-state/",            views.knowledge_state_list, name="knowledge-state-list"),
    path("me/knowledge-state/<str:concept>/", views.knowledge_state_detail, name="knowledge-state-detail"),
    path("me/quiz-history/",               views.quiz_history,         name="quiz-history"),
    path("me/quiz-history-aggregated/",    views.quiz_history_aggregated, name="quiz-history-aggregated"),
    path("me/daily-activity/",             views.daily_activity,       name="daily-activity"),
]
