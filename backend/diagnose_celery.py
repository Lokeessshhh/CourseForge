"""
Comprehensive Celery diagnostic script.
Run this to verify the entire pipeline works.
"""
import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from apps.courses.tasks import generate_course_content_task
from config.celery import app

def check_celery_connection():
    """Check if Celery can connect to the broker"""
    print("\n" + "="*80)
    print("🔍 CELERY DIAGNOSTIC CHECKS")
    print("="*80)
    
    print("\n1. Checking broker connection...")
    try:
        conn = app.connection()
        conn.ensure_connection(max_retries=3)
        print("   ✅ Connected to broker")
        conn.release()
    except Exception as e:
        print(f"   ❌ Failed to connect: {e}")
        return False
    
    return True

def check_task_registration():
    """Check if tasks are registered"""
    print("\n2. Checking registered tasks...")
    registered = app.tasks.keys()
    course_tasks = [t for t in registered if 'courses.tasks' in t]
    
    if course_tasks:
        print(f"   ✅ Found {len(course_tasks)} course tasks:")
        for t in course_tasks[:5]:
            print(f"      - {t}")
    else:
        print("   ❌ No course tasks found!")
        return False
    
    return True

def test_task_dispatch():
    """Send a test task and check if it gets processed"""
    print("\n3. Sending test task to Celery worker...")
    
    try:
        task = generate_course_content_task.delay(
            course_id="test-diagnostic-001",
            course_name="Diagnostic Test Course",
            duration_weeks=1,
            level="beginner",
            goals=["test"],
            description="This is a diagnostic test course"
        )
        
        print(f"   ✅ Task sent successfully!")
        print(f"   Task ID: {task.id}")
        print(f"   Queue: course_generation")
        print("\n   👉 CHECK YOUR CELERY WORKER TERMINAL NOW!")
        print("   You should see:")
        print("      - A task being received")
        print("      - Logs starting with '🎓 CELERY TASK: GENERATE COURSE CONTENT'")
        print("      - Or an error message if the task fails")
        
        # Check task status after a brief delay
        import time
        time.sleep(2)
        
        result = task.result
        state = task.state
        
        print(f"\n   Task state: {state}")
        if state == 'SUCCESS':
            print("   ✅ Task completed successfully")
        elif state == 'FAILURE':
            print(f"   ❌ Task failed: {result}")
        elif state == 'PENDING':
            print("   ⚠️  Task is still pending (worker might be busy)")
        elif state == 'STARTED':
            print("   🔄 Task has started processing")
        
    except Exception as e:
        print(f"   ❌ Failed to send task: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    print("\n" + "="*80)
    print("🔧 CELERY PIPELINE DIAGNOSTIC TOOL")
    print("="*80)
    
    checks_passed = True
    
    if not check_celery_connection():
        checks_passed = False
        print("\n❌ Broker connection failed. Check if Redis is running!")
    
    if not check_task_registration():
        checks_passed = False
        print("\n❌ Tasks not registered. Check task discovery!")
    
    if checks_passed:
        test_task_dispatch()
    
    print("\n" + "="*80)
    print("✅ DIAGNOSTIC COMPLETE")
    print("="*80)
    
    if checks_passed:
        print("\n💡 If you saw 'Task sent successfully' but NO logs in Celery worker:")
        print("   1. Check that the worker is listening to 'course_generation' queue")
        print("   2. Check if there are any errors in the worker terminal")
        print("   3. The task might be failing before the logging statements")
        print("\n💡 If logs appear in Celery worker:")
        print("   ✅ Your system is working correctly!")
        print("   The issue was that course creation via API wasn't calling the task")
    
    print()
