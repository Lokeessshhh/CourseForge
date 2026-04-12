"""
Auto-run Celery worker alongside Django development server.
This allows running both with a single `python manage.py runserver` command.
"""
import os
import sys
import subprocess
import threading
import time
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Run Django development server with Celery worker"

    def add_arguments(self, parser):
        parser.add_argument(
            "args",
            metavar="addrport",
            nargs="*",
            default=[],
            help="Optional port number, or addr:port",
        )
        parser.add_argument(
            "--noreload",
            action="store_false",
            dest="use_reloader",
            default=True,
            help="Tells Django to NOT use the auto-reloader",
        )

    def handle(self, *args, **options):
        # Get the address/port for runserver
        addrport = args[0] if args else "8000"
        
        self.stdout.write(self.style.SUCCESS(
            "Starting Django development server with Celery worker..."
        ))
        
        # Start Celery worker in a separate process
        celery_process = self.start_celery_worker()
        
        # Start Django runserver
        try:
            from django.core.management import call_command
            call_command("runserver", addrport, use_reloader=options["use_reloader"])
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nShutting down..."))
        finally:
            # Clean up Celery process
            if celery_process:
                self.stdout.write("Stopping Celery worker...")
                celery_process.terminate()
                try:
                    celery_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    celery_process.kill()
                self.stdout.write(self.style.SUCCESS("Celery worker stopped"))

    def start_celery_worker(self):
        """Start Celery worker as a background process."""
        try:
            # Get project name from settings
            project_name = os.path.basename(os.path.dirname(settings.__file__))
            
            # Build Celery command
            celery_cmd = [
                sys.executable, "-m", "celery",
                "-A", project_name,
                "worker",
                "--loglevel=info",
                "--pool=solo",  # Use solo pool for Windows compatibility
                "--without-gossip",
                "--without-mingle",
            ]
            
            self.stdout.write(self.style.SUCCESS("\n" + "=" * 80))
            self.stdout.write(self.style.SUCCESS(" STARTING CELERY WORKER"))
            self.stdout.write(self.style.SUCCESS(f"   Command: {' '.join(celery_cmd)}"))
            self.stdout.write(self.style.SUCCESS(f"   Project: {project_name}"))
            self.stdout.write(self.style.SUCCESS("=" * 80 + "\n"))
            
            # Start process
            process = subprocess.Popen(
                celery_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
            )
            
            # Start thread to print Celery logs
            threading.Thread(
                target=self.print_celery_logs,
                args=(process,),
                daemon=True
            ).start()
            
            # Wait for Celery to start
            time.sleep(3)
            
            self.stdout.write(self.style.SUCCESS(" Celery worker started successfully\n"))
            
            return process
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f" Failed to start Celery: {e}"))
            return None

    def print_celery_logs(self, process):
        """Print Celery logs to console with formatting."""
        try:
            for line in process.stdout:
                # Filter and format Celery logs
                if "[celery]" in line.lower() or "worker" in line.lower() or "task" in line.lower():
                    if "received" in line.lower() or "starting" in line.lower():
                        self.stdout.write(self.style.SUCCESS(f"[Celery]  {line.strip()}"))
                    elif "completed" in line.lower() or "ready" in line.lower():
                        self.stdout.write(self.style.SUCCESS(f"[Celery]  {line.strip()}"))
                    elif "error" in line.lower() or "failed" in line.lower():
                        self.stdout.write(self.style.ERROR(f"[Celery]  {line.strip()}"))
                    else:
                        self.stdout.write(f"[Celery] {line.strip()}\n")
        except Exception:
            pass
