"""
Test script to manually unlock weekly test for debugging.
Run this script to unlock a weekly test without completing all 5 days.
"""
import os
import sys
import django

# Setup Django - ensure we're in the backend directory
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Add parent directory to path for config import
parent_dir = os.path.dirname(backend_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.courses.models import Course, WeekPlan, WeeklyTest
from apps.users.models import User


def unlock_weekly_test(course_id, week_number, user_email):
    """
    Manually unlock weekly test for a specific course and week.
    
    Args:
        course_id: UUID of the course
        week_number: Week number (1-based)
        user_email: Email of the user who owns the course
    """
    try:
        # Get course and user
        course = Course.objects.get(id=course_id)
        user = User.objects.get(email=user_email)
        
        # Verify ownership
        if course.user != user:
            print(f" Error: User {user_email} does not own course {course_id}")
            return False
        
        # Get week
        week = WeekPlan.objects.get(course=course, week_number=week_number)
        
        # Check current state
        completed_days = week.days.filter(is_completed=True).count()
        total_days = week.days.count()
        
        print(f"\n Current State:")
        print(f"   Course: {course.course_name}")
        print(f"   Week: {week_number}")
        print(f"   Completed Days: {completed_days}/{total_days}")
        print(f"   Test Unlocked: {week.test_unlocked}")
        
        # Unlock the test
        week.test_unlocked = True
        week.save(update_fields=["test_unlocked"])
        
        print(f"\n Weekly test unlocked for week {week_number}!")
        
        # Generate weekly test if not exists
        test, created = WeeklyTest.objects.get_or_create(
            course=course,
            week_number=week_number,
            defaults={
                "questions": [],
                "total_questions": 10,
            }
        )
        
        if created:
            print(f" Created weekly test for week {week_number}")
            # Trigger test generation
            from apps.courses.tasks import generate_weekly_test_task
            generate_weekly_test_task.delay(str(course_id), week_number)
            print(f" Triggered weekly test generation (running in background)")
        else:
            print(f" Weekly test already exists for week {week_number}")
        
        print(f"\n You can now take the weekly test at:")
        print(f"   http://localhost:3000/dashboard/courses/{course_id}/week/{week_number}/test")
        
        return True
        
    except Course.DoesNotExist:
        print(f" Error: Course {course_id} not found")
        return False
    except User.DoesNotExist:
        print(f" Error: User {user_email} not found")
        return False
    except WeekPlan.DoesNotExist:
        print(f" Error: Week {week_number} not found for course {course_id}")
        return False
    except Exception as e:
        print(f" Error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Weekly Test Unlock Debug Tool")
    print("=" * 60)
    
    # Get user input
    course_id = input("\nEnter Course ID (UUID): ").strip()
    week_number = input("Enter Week Number (1, 2, 3, etc.): ").strip()
    user_email = input("Enter User Email: ").strip()
    
    if not course_id or not week_number or not user_email:
        print("\n Error: All fields are required")
        sys.exit(1)
    
    try:
        week_number = int(week_number)
    except ValueError:
        print("\n Error: Week number must be an integer")
        sys.exit(1)
    
    # Unlock the test
    success = unlock_weekly_test(course_id, week_number, user_email)
    
    if success:
        print("\n Done! Refresh your browser to see the weekly test.")
    else:
        print("\n Failed to unlock weekly test. Check the error above.")
    
    sys.exit(0 if success else 1)
