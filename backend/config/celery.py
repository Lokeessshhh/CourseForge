"""
Celery configuration for LearnAI.
- App name: learnai
- Broker: Redis
- Result backend: Redis
- Task routes for course, quiz, cert generation
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# Create Celery app
app = Celery("learnai")

# Load config from Django settings with CELERY_ prefix
app.config_from_object("django.conf:settings", namespace="CELERY")

# Autodiscover tasks from all installed apps
app.autodiscover_tasks()

# ──────────────────────────────────────────────
# Task Routes
# ──────────────────────────────────────────────
app.conf.task_routes = {
    "apps.courses.tasks.*": {"queue": "course_generation"},
    "apps.quizzes.tasks.*": {"queue": "quiz_generation"},
    "services.certificate.*": {"queue": "certificates"},
}

# ──────────────────────────────────────────────
# Celery Beat Schedule (periodic tasks)
# ──────────────────────────────────────────────
app.conf.beat_schedule = {
    "check-streaks-daily": {
        "task": "apps.courses.tasks.check_streak_task",
        "schedule": crontab(hour=0, minute=0),  # Every day at midnight UTC
    },
    "cleanup-expired-sessions": {
        "task": "apps.users.tasks.cleanup_sessions",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM UTC
    },
}

# ──────────────────────────────────────────────
# Default settings (overridden by Django settings)
# ──────────────────────────────────────────────
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max per task
    task_soft_time_limit=25 * 60,  # Soft limit at 25 minutes
    worker_prefetch_multiplier=1,  # One task per worker at a time
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks
)

# ──────────────────────────────────────────────
# Debug task
# ──────────────────────────────────────────────
@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
