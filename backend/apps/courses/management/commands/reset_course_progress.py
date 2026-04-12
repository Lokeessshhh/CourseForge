"""
Django management command to reset course progression.
Fixes corrupted data where all days are unlocked/completed incorrectly.

Usage:
    python manage.py reset_course_progress --course-id=<uuid>
    python manage.py reset_course_progress --all
"""
from django.core.management.base import BaseCommand, CommandError
from django.core.management.base import CommandParser
from apps.courses.models import Course, DayPlan, WeekPlan, CourseProgress
from django.db import transaction


class Command(BaseCommand):
    help = 'Reset course progression to fix corrupted data'

    def add_arguments(self, parser: CommandParser):
        parser.add_argument(
            '--course-id',
            type=str,
            help='Reset a specific course by UUID',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Reset all courses',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        course_id = options.get('course_id')
        reset_all = options.get('all')
        dry_run = options.get('dry_run')

        if not course_id and not reset_all:
            # Auto-detect: if only one course exists, use it
            course_count = Course.objects.count()
            if course_count == 1:
                course = Course.objects.first()
                course_id = str(course.id)
                self.stdout.write(self.style.WARNING(
                    f'Auto-selecting only course: {course.course_name} ({course_id})'
                ))
            else:
                raise CommandError('You must specify --course-id=<uuid> or --all')

        if course_id:
            courses = Course.objects.filter(id=course_id)
            if not courses.exists():
                raise CommandError(f'Course with ID {course_id} not found')
        else:
            courses = Course.objects.all()

        self.stdout.write(self.style.WARNING(
            f'Found {courses.count()} course(s) to process'
        ))

        total_days_reset = 0
        total_weeks_reset = 0
        total_progress_reset = 0

        for course in courses:
            self.stdout.write(f'\nProcessing course: {course.course_name} ({course.id})')

            # Reset all days
            days = DayPlan.objects.filter(week_plan__course=course)
            days_count = days.count()
            total_days_reset += days_count

            if not dry_run:
                # Lock all days first
                days.update(is_locked=True, is_completed=False, completed_at=None)

                # Unlock only Week 1 Day 1
                week1 = WeekPlan.objects.filter(course=course, week_number=1).first()
                if week1:
                    day1 = DayPlan.objects.filter(week_plan=week1, day_number=1).first()
                    if day1:
                        day1.is_locked = False
                        day1.save(update_fields=['is_locked'])
                        self.stdout.write(self.style.SUCCESS(
                            f'   Unlocked Week 1 Day 1: {day1.title or "No title"}'
                        ))

            self.stdout.write(f'  Reset {days_count} days (all locked except Week 1 Day 1)')

            # Reset all weeks
            weeks = WeekPlan.objects.filter(course=course)
            weeks_count = weeks.count()
            total_weeks_reset += weeks_count

            if not dry_run:
                weeks.update(
                    is_completed=False,
                    test_unlocked=False,
                    coding_test_1_unlocked=False,
                    coding_test_2_unlocked=False,
                    coding_test_1_completed=False,
                    coding_test_2_completed=False,
                )

            self.stdout.write(f'  Reset {weeks_count} weeks (all tests re-locked)')

            # Reset course progress
            progress_records = CourseProgress.objects.filter(course=course)
            for progress in progress_records:
                total_progress_reset += 1

                if not dry_run:
                    progress.current_week = 1
                    progress.current_day = 1
                    progress.completed_days = 0
                    progress.overall_percentage = 0.0
                    progress.avg_quiz_score = 0.0
                    progress.save(update_fields=[
                        'current_week', 'current_day', 'completed_days',
                        'overall_percentage', 'avg_quiz_score'
                    ])

                self.stdout.write(self.style.SUCCESS(
                    f'   Reset progress for user: {progress.user_id} '
                    f'(Week 1, Day 1, 0% complete)'
                ))

        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('SUMMARY:'))
        self.stdout.write(f'  Courses processed: {courses.count()}')
        self.stdout.write(f'  Days reset: {total_days_reset}')
        self.stdout.write(f'  Weeks reset: {total_weeks_reset}')
        self.stdout.write(f'  Progress records reset: {total_progress_reset}')

        if dry_run:
            self.stdout.write(self.style.WARNING(
                '\n*** DRY RUN - No changes were made ***'
            ))
            self.stdout.write(self.style.WARNING(
                'Remove --dry-run to apply changes'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                '\n All changes applied successfully!'
            ))
