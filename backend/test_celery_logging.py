"""
Test script to verify Celery task execution and logging.
Run this while both Daphne and Celery are running.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from apps.courses.tasks import generate_course_content_task

def test_celery_task():
    """Send a simple test task to Celery worker"""
    print("\n" + "="*80)
    print("🧪 SENDING TEST CELERY TASK")
    print("="*80)
    
    # Send a minimal test task
    task = generate_course_content_task.delay(
        course_id="test-123",
        course_name="Test Course",
        duration_weeks=1,
        level="beginner",
        goals=["test"],
        description="Test course for verification"
    )
    
    print(f"✅ Task sent with ID: {task.id}")
    print("📝 Check your Celery worker terminal for logs")
    print("="*80 + "\n")

if __name__ == "__main__":
    test_celery_task()
