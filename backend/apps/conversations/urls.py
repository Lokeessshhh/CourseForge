"""
Conversations app URL patterns — /api/conversations/

Endpoints:
  POST   /sessions/                     → Create new session
  GET    /                              → List all sessions (simple)
  GET    /sessions/                     → List sessions with pagination
  GET    /sessions/{id}/                → Get session messages
  DELETE /sessions/{id}/                → Delete session
  POST   /sessions/{id}/title/          → Set session title
  GET    /sessions/{id}/title/          → Get session title
  GET    /course/{course_id}/           → Get course-specific history
  GET    /search/                       → Search conversations
  GET    /stats/                        → Get conversation statistics
"""
from django.urls import path
from . import views

urlpatterns = [
    # Create session
    path("sessions/new/", views.create_session, name="create-session"),

    # Simple session list
    path("", views.conversation_list, name="conversation-list"),

    # Paginated sessions (GET only)
    path("sessions/", views.session_list, name="session-list"),
    path("sessions/<uuid:session_id>/", views.session_detail, name="session-detail"),
    path("sessions/<uuid:session_id>/delete/", views.session_delete, name="session-delete"),
    path("sessions/<uuid:session_id>/title/", views.set_session_title, name="session-title"),
    path("sessions/<uuid:session_id>/title/get/", views.get_session_title, name="session-title-get"),
    path("sessions/<uuid:session_id>/rename/", views.session_rename, name="session-rename"),
    path("sessions/<uuid:session_id>/archive/", views.session_archive, name="session-archive"),
    path("sessions/<uuid:session_id>/generating-courses/", views.session_save_generating_courses, name="session-save-generating-courses"),

    # Course-specific history
    path("course/<uuid:course_id>/", views.course_history, name="course-history"),

    # Search and stats
    path("search/", views.search_conversations, name="conversation-search"),
    path("stats/", views.conversation_stats, name="conversation-stats"),

    # Persist conversation (for course management)
    path("persist/", views.persist_conversation, name="conversation-persist"),
]
