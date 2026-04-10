"""
Monitor Celery task executions in real-time.
Run this script to watch what happens when you create a course.
"""
import os
import sys
import django
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django_celery_results.models import TaskResult
from apps.courses.models import Course

def monitor_tasks():
    """Monitor recent Celery tasks"""
    print("\n" + "="*80)
    print("📊 CELERY TASK MONITOR")
    print("="*80)
    
    # Get recent task results
    recent_tasks = TaskResult.objects.all().order_by('-date_created')[:10]
    
    print(f"\nRecent {len(recent_tasks)} Celery tasks:")
    print("-" * 80)
    
    for i, task in enumerate(recent_tasks, 1):
        print(f"\n{i}. Task ID: {task.task_id}")
        print(f"   Status: {task.status}")
        print(f"   Task Name: {task.task_name}")
        print(f"   Created: {task.date_created}")
        
        if task.status == 'FAILURE':
            print(f"   ❌ ERROR: {task.result[:200] if task.result else 'Unknown'}")
            if task.traceback:
                print(f"   Traceback: {task.traceback[:300]}")
        elif task.status == 'SUCCESS':
            print(f"   ✅ Completed successfully")
        elif task.status == 'STARTED':
            print(f"   🔄 Still running...")
        elif task.status == 'PENDING':
            print(f"   ⏳ Waiting to be processed")
    
    # Check recent courses
    print("\n" + "="*80)
    print("🎓 RECENT COURSES")
    print("="*80)
    
    courses = Course.objects.all().order_by('-created_at')[:5]
    for course in courses:
        print(f"\n📚 {course.course_name}")
        print(f"   ID: {course.id}")
        print(f"   Status: {course.status}")
        print(f"   Generation Status: {course.generation_status}")
        print(f"   Created: {course.created_at}")
        print(f"   Has error in generation_status? {'error' in str(course.generation_status).lower()}")

if __name__ == "__main__":
    monitor_tasks()
