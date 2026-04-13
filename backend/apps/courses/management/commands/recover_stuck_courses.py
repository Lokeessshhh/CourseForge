"""
Django management command to recover courses stuck in 'generating' status.
This can happen if the server restarts during background task execution.
Usage: python manage.py recover_stuck_courses [--hours 1] [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.courses.models import Course


class Command(BaseCommand):
    help = 'Recover courses stuck in "generating" status for more than N hours'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=1,
            help='Hours threshold to consider a course stuck (default: 1)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating',
        )

    def handle(self, *args, **options):
        hours = options['hours']
        dry_run = options['dry_run']

        cutoff = timezone.now() - timedelta(hours=hours)

        stuck_courses = Course.objects.filter(
            generation_status="generating",
            created_at__lt=cutoff,
        )

        count = stuck_courses.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS(
                f'No courses stuck in "generating" status for more than {hours} hour(s).'
            ))
            return

        self.stdout.write(self.style.WARNING(
            f'\nFound {count} course(s) stuck in "generating" status for more than {hours} hour(s):\n'
        ))

        for course in stuck_courses:
            self.stdout.write(f'  - {course.course_name} (ID: {course.id}, created: {course.created_at})')

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'\n[DRY RUN] Would mark {count} course(s) as "failed".'))
            return

        # Update stuck courses to failed status
        updated = stuck_courses.update(generation_status="failed")
        self.stdout.write(self.style.SUCCESS(
            f'\nMarked {updated} course(s) as "failed". Users can now regenerate.'
        ))
