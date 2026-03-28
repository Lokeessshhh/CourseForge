"""
Django management command to generate coding test problems.
Usage: python manage.py generate_coding_test <course_id> <week_number>
"""
from django.core.management.base import BaseCommand
from apps.courses.tasks import generate_coding_test_task


class Command(BaseCommand):
    help = 'Generate coding test problems for a specific course and week'

    def add_arguments(self, parser):
        parser.add_argument('course_id', type=str, help='Course UUID')
        parser.add_argument('week_number', type=int, help='Week number (1-based)')

    def handle(self, *args, **options):
        course_id = options['course_id']
        week_number = options['week_number']

        try:
            self.stdout.write(self.style.WARNING(f"\n🔄 Generating coding test for course {course_id}, week {week_number}..."))
            
            # Trigger the task synchronously
            result = generate_coding_test_task(course_id, week_number)
            
            self.stdout.write(self.style.SUCCESS(f"\n✅ Coding test generated successfully for week {week_number}!"))
            self.stdout.write(self.style.SUCCESS(f"\n🎉 You can now take the coding test at:"))
            self.stdout.write(f"   http://localhost:3000/dashboard/courses/{course_id}/week/{week_number}/coding-test")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
