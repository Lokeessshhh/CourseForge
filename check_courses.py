import os
import sys
import django

# Add backend directory to Python path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend'))
sys.path.insert(0, backend_path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

# Must call setup() before importing Django models
django.setup()

from django.db.models import Q, Prefetch
from apps.courses.models import Course, WeekPlan, DayPlan, WeeklyTest, CodingTest

# Query for ALL recent courses
courses = Course.objects.all().order_by('-created_at')[:5]

print(f"Found {courses.count()} recent course(s)\n")
print("=" * 80)

for course in courses:
    print(f"\n📚 Course: {course.course_name}")
    print(f"   ID: {course.id}")
    print(f"   Topic: {course.topic}")
    print(f"   Level: {course.level}")
    print(f"   Duration: {course.duration_weeks} weeks")
    print(f"   Status: {course.status}")
    print(f"   Generation Status: {course.generation_status}")
    print(f"   Progress: {course.generation_progress}%")
    print(f"   Created: {course.created_at}")
    
    # Check weeks
    weeks = course.weeks.all().order_by('week_number')
    print(f"\n   📅 Weeks Generated: {weeks.count()}/{course.duration_weeks}")
    
    all_days_complete = True
    total_theory = 0
    total_code = 0
    total_quiz = 0
    
    for week in weeks:
        days = week.days.all().order_by('day_number')
        print(f"\n   Week {week.week_number}: {week.theme}")
        print(f"      Days: {days.count()}/5")
        
        for day in days:
            theory_ok = day.theory_generated
            code_ok = day.code_generated
            quiz_ok = day.quiz_generated
            
            if theory_ok: total_theory += 1
            if code_ok: total_code += 1
            if quiz_ok: total_quiz += 1
            
            if not (theory_ok and code_ok and quiz_ok):
                all_days_complete = False
                
            status = "OK" if (theory_ok and code_ok and quiz_ok) else "FAIL"
            print(f"      [{status}] Day {day.day_number}: {day.title[:50] if day.title else 'N/A'} "
                  f"[T: {'OK' if theory_ok else 'FAIL'} C: {'OK' if code_ok else 'FAIL'} Q: {'OK' if quiz_ok else 'FAIL'}]")

    # Check weekly tests
    weekly_tests = course.weekly_tests.all().order_by('week_number')
    print(f"\n   Weekly Tests (MCQ): {weekly_tests.count()}/{course.duration_weeks}")
    for test in weekly_tests:
        print(f"      Week {test.week_number}: {test.total_questions} questions")

    # Check coding tests
    coding_tests = CodingTest.objects.filter(course=course).order_by('week_number')
    print(f"\n   Coding Tests: {coding_tests.count()}/{course.duration_weeks}")
    for ct in coding_tests:
        print(f"      Week {ct.week_number}: {ct.total_problems} problems")
    
    # Week flags
    print(f"\n   Week Flags:")
    for week in weeks:
        print(f"      Week {week.week_number}: "
              f"test_generated={week.test_generated} (MCQ), "
              f"coding_tests_generated={week.coding_tests_generated}")
    
    # Summary
    print("\n" + "=" * 80)
    print(f"   SUMMARY:")
    print(f"   Theory: {total_theory}/20 | Code: {total_code}/20 | Quiz: {total_quiz}/20")
    print(f"   MCQ Tests: {weekly_tests.count()}/{course.duration_weeks}")
    print(f"   Coding Tests: {coding_tests.count()}/{course.duration_weeks}")
    
    if course.generation_status == 'ready' and all_days_complete and weekly_tests.count() == course.duration_weeks and coding_tests.count() == course.duration_weeks:
        print("   FULLY COMPLETE")
    elif all_days_complete:
        print("   WARNING: Days complete, missing tests")
    else:
        print(f"   INCOMPLETE")
    print("=" * 80)
    print()
