"""
Django management command to unlock coding test for debugging.
Usage: python manage.py unlock_coding_test <course_id> <week_number> <user_email>
"""
from django.core.management.base import BaseCommand
from apps.courses.models import Course, WeekPlan, CodingTest
from apps.users.models import User


class Command(BaseCommand):
    help = 'Unlock coding test for a specific course and week'

    def add_arguments(self, parser):
        parser.add_argument('course_id', type=str, help='Course UUID')
        parser.add_argument('week_number', type=int, help='Week number (1-based)')
        parser.add_argument('user_email', type=str, help='User email')

    def handle(self, *args, **options):
        course_id = options['course_id']
        week_number = options['week_number']
        user_email = options['user_email']

        try:
            # Get course and user
            course = Course.objects.get(id=course_id)
            user = User.objects.get(email=user_email)
            
            # Verify ownership
            if course.user != user:
                self.stdout.write(self.style.ERROR(f"User {user_email} does not own course {course_id}"))
                return
            
            # Get week
            week = WeekPlan.objects.get(course=course, week_number=week_number)
            
            # Check current state
            completed_days = week.days.filter(is_completed=True).count()
            total_days = week.days.count()
            
            self.stdout.write(self.style.WARNING(f"\n Current State:"))
            self.stdout.write(f"   Course: {course.course_name}")
            self.stdout.write(f"   Week: {week_number}")
            self.stdout.write(f"   Completed Days: {completed_days}/{total_days}")
            self.stdout.write(f"   Test Unlocked: {week.test_unlocked}")
            
            # Unlock the test
            week.test_unlocked = True
            week.save(update_fields=["test_unlocked"])
            
            self.stdout.write(self.style.SUCCESS(f"\n Coding test unlocked for week {week_number}!"))
            
            # Generate coding test if not exists
            test, created = CodingTest.objects.get_or_create(
                course=course,
                week_number=week_number,
                defaults={
                    "problems": [],
                    "total_problems": 2,
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f" Created coding test for week {week_number}"))
                # Trigger test generation
                from apps.courses.tasks import generate_coding_test_task
                generate_coding_test_task.delay(str(course_id), week_number)
                self.stdout.write(self.style.SUCCESS(f" Triggered coding test generation (running in background)"))
            else:
                self.stdout.write(self.style.SUCCESS(f" Coding test already exists for week {week_number}"))
            
            self.stdout.write(self.style.SUCCESS(f"\n You can now take the coding test at:"))
            self.stdout.write(f"   http://localhost:3000/dashboard/courses/{course_id}/week/{week_number}/coding-test")
            
        except Course.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Course {course_id} not found"))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User {user_email} not found"))
        except WeekPlan.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Week {week_number} not found for course {course_id}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
