"""
Celery configuration for LearnAI.
- App name: learnai
- Broker: Redis
- Result backend: Redis
- Task routes for course, quiz, cert generation
"""
import os
import logging
from celery import Celery
from celery.schedules import crontab

# Set default Django settings module
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings.production"),
)

# Configure logging for Celery workers
import sys
import io

# Fix Windows console encoding for emojis and Unicode
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass  # Fallback if stdout/stderr don't have buffer attribute

logging.basicConfig(
    level=logging.INFO,
    format='[Celery] %(levelname)s %(asctime)s %(module)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    force=True,  # Override existing configuration
)
logger = logging.getLogger(__name__)
logger.info("[Celery] Starting with settings: %s", os.environ.get("DJANGO_SETTINGS_MODULE"))

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
    task_expire_seconds=60 * 60,  # Tasks expire after 1 hour if not consumed
    result_expires=60 * 60 * 24,  # Results expire after 24 hours
    # Force immediate shutdown on Ctrl+C
    worker_shutdown_timeout=2,  # Only wait 2 seconds for tasks to finish
    worker_proc_alive_timeout=4,  # Force kill unresponsive child processes after 4s
)

# ──────────────────────────────────────────────
# Debug task
# ──────────────────────────────────────────────
@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")


# ──────────────────────────────────────────────
# Logging test task
# ──────────────────────────────────────────────
@app.task(bind=True, ignore_result=True)
def test_logging_task(self):
    """Test task to verify logging works in Celery worker"""
    import sys
    print("\n" + "="*80, flush=True)
    print("🧪🧪🧪 TEST LOGGING TASK - IF YOU SEE THIS, LOGGING WORKS! 🧪🧪🧪", flush=True)
    print("="*80 + "\n", flush=True)
    sys.stdout.flush()
    sys.stderr.flush()
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info("="*80)
    logger.info("🧪 TEST LOGGING - Celery worker logging is working!")
    logger.info("="*80)
    return "Logging test completed!"


# ──────────────────────────────────────────────
# Fix: Celery thread pool shutdown crash
# ──────────────────────────────────────────────
# Monkey-patch the thread pool to suppress the NotImplementedError during shutdown
def _patch_celery_thread_pool_kill_job():
    """Suppress the NotImplementedError when killing jobs in thread pool during shutdown."""
    try:
        from celery.concurrency.thread import TaskPool
        
        def _patched_terminate_job(self, worker_pid, signal=None):
            """Gracefully handle thread pool termination - threads can't be killed."""
            import logging
            logger = logging.getLogger(__name__)
            logger.debug("[THREAD_POOL] Ignoring terminate_job for PID %s (threads can't be terminated)", worker_pid)
            # Threads cannot be forcibly terminated in Python, so just log and continue
        
        TaskPool.terminate_job = _patched_terminate_job
    except (ImportError, AttributeError) as patch_error:
        pass  # Don't crash if Celery internals change

_patch_celery_thread_pool_kill_job()
del _patch_celery_thread_pool_kill_job
