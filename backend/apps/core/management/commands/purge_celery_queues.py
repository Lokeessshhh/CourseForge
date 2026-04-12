"""
Management command to purge all Celery queues.
Usage: python manage.py purge_celery_queues
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Purge all Celery task queues to remove stale tasks"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show queue depths without purging",
        )
        parser.add_argument(
            "--queue",
            type=str,
            help="Purge specific queue (default: all queues)",
        )

    def handle(self, *args, **options):
        from config.celery import app
        
        queues = ['celery', 'course_generation', 'quiz_generation', 'certificates']
        
        if options["queue"]:
            queues = [options["queue"]]
        
        total_purged = 0
        
        self.stdout.write(self.style.SUCCESS("\n" + "="*60))
        self.stdout.write(self.style.SUCCESS(" CELERY QUEUE PURGE"))
        self.stdout.write(self.style.SUCCESS("="*60 + "\n"))
        
        for queue_name in queues:
            try:
                with app.connection() as conn:
                    queue = conn.SimpleQueue(queue_name)
                    depth = queue.qsize()
                    queue.close()
                    
                    if options["dry_run"]:
                        self.stdout.write(f" Queue '{queue_name}': {depth} task(s)")
                        continue
                    
                    if depth > 0:
                        purged = app.control.purge(queue=queue_name)
                        count = len(purged) if purged else 0
                        total_purged += count
                        self.stdout.write(
                            self.style.WARNING(
                                f"  Purged {count} task(s) from queue: {queue_name}"
                            )
                        )
                    else:
                        self.stdout.write(f" Queue '{queue_name}': empty")
                        
            except Exception as e:
                if "NOT_FOUND" in str(e) or "no queue" in str(e).lower():
                    self.stdout.write(f"  Queue '{queue_name}': does not exist (Celery worker not running)")
                else:
                    self.stderr.write(
                        self.style.ERROR(f" Error purging queue '{queue_name}': {e}")
                    )
        
        self.stdout.write("\n" + "="*60)
        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS(f" Total tasks in queues: {total_purged}"))
        else:
            self.stdout.write(self.style.SUCCESS(f" Purged {total_purged} stale task(s)"))
        self.stdout.write(self.style.SUCCESS("="*60 + "\n"))
