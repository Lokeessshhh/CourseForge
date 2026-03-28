"""
LearnAI Django project configuration.
This ensures Celery app is loaded when Django starts.
"""
try:
    from .celery import app as celery_app
except Exception:  # pragma: no cover
    celery_app = None

__all__ = ("celery_app",)
