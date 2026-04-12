import os
import sys
import django

# Add backend directory to Python path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend'))
sys.path.insert(0, backend_path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()

from apps.courses.models import Course

# Get all courses
courses = Course.objects.all().order_by('-created_at')[:10]

print(f"\nFound {courses.count()} course(s):\n")
print("=" * 100)
for course in courses:
    print(f"ID: {course.id}")
    print(f"Name: {course.course_name}")
    print(f"Topic: {course.topic}")
    print(f"Duration: {course.duration_weeks} weeks")
    print(f"Created: {course.created_at}")
    print("-" * 100)
