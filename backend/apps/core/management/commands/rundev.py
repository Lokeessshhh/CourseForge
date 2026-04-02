"""
Custom management command that starts Daphne (ASGI) + Celery worker + WebSocket support.
Usage: python manage.py rundev
"""
import os
import sys
import subprocess
import threading
import time
import signal
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = "Runs Daphne (ASGI) server with Celery worker and WebSocket support"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.processes = []
        self.shutting_down = False
        self.celery_started = threading.Event()

    def _handle_signal(self, signum, frame):
        """Handle shutdown signals gracefully."""
        if not self.shutting_down:
            self.shutting_down = True
            self.stdout.write(self.style.WARNING('\n\n🛑 Shutdown signal received...'))
            self.cleanup_processes()
        sys.exit(0)

    def add_arguments(self, parser):
        parser.add_argument(
            'addrport',
            nargs='?',
            default='8000',
            help='Optional port number, or addr:port'
        )
        parser.add_argument(
            '--no-celery',
            action='store_true',
            dest='no_celery',
            default=False,
            help='Run without Celery worker'
        )

    def handle(self, *args, **options):
        addrport = options['addrport']
        no_celery = options['no_celery']

        # Parse host and port
        if ':' in addrport:
            host, port = addrport.rsplit(':', 1)
        else:
            host, port = '127.0.0.1', addrport

        # Print startup banner
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('🚀 STARTING DEVELOPMENT SERVER'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('   Django + Daphne (ASGI) + Celery + WebSocket'))
        self.stdout.write(self.style.SUCCESS(f'   🌐 http://{host}:{port}'))
        self.stdout.write(self.style.SUCCESS('=' * 80 + '\n'))

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        # Start Celery worker if not disabled
        if not no_celery:
            self.stdout.write(self.style.SUCCESS('📦 Starting Celery worker...'))
            self.start_celery_worker()
            # Wait for Celery to initialize
            self.celery_started.wait(timeout=5)
        else:
            self.stdout.write(self.style.WARNING('⏭️  Celery worker disabled (--no-celery flag set)\n'))

        # Start Daphne ASGI server (blocks)
        self.stdout.write(self.style.SUCCESS('🌐 Starting Daphne ASGI server...'))
        self.start_daphne(f'{host}:{port}')

        # Cleanup on exit
        self.cleanup_processes()

    def cleanup_processes(self):
        """Clean up all spawned processes."""
        if self.shutting_down:
            return

        self.stdout.write(self.style.WARNING('\n🛑 Shutting down all services...\n'))

        for i, process in enumerate(reversed(self.processes), 1):
            if process and process.poll() is None:
                try:
                    service_name = "Celery" if i == len(self.processes) else "Daphne"
                    self.stdout.write(f'   Stopping {service_name}...')
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                        self.stdout.write(self.style.SUCCESS(f'   ✅ {service_name} stopped'))
                    except subprocess.TimeoutExpired:
                        process.kill()
                        self.stdout.write(self.style.WARNING(f'   ⚠️  {service_name} force killed'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'   Error stopping process: {e}'))

        self.stdout.write(self.style.SUCCESS('\n✅ All services stopped\n'))
        self.shutting_down = True

    def start_celery_worker(self):
        """Start Celery worker as a background process."""
        try:
            # Use the Celery app directly from config.celery
            # Listen to all queues: celery (default), course_generation, quiz_generation, certificates
            celery_cmd = [
                sys.executable, "-m", "celery",
                "-A", "config.celery",
                "worker",
                "--loglevel=info",  # INFO: Shows task start/complete, errors, progress (no debug spam)
                "--pool=threads",  # Use threads pool to allow concurrent task execution
                "--concurrency=4",  # 4 worker threads for parallel task processing
                "--without-gossip",
                "--without-mingle",
                "-Q", "celery,course_generation,quiz_generation,certificates",
            ]

            self.stdout.write(self.style.SUCCESS(f'   📦 Command: {" ".join(celery_cmd)}'))

            process = subprocess.Popen(
                celery_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout (Celery logs to stderr)
                universal_newlines=True,
                bufsize=1,
            )

            # Track the process
            self.processes.append(process)

            # Start thread to stream Celery logs (separate thread to avoid blocking)
            threading.Thread(
                target=self.stream_celery_logs,
                args=(process,),
                daemon=True,
                name="CeleryLogStreamer"
            ).start()

            self.stdout.write(self.style.SUCCESS('   ✅ Celery worker started\n'))

            return process

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Failed to start Celery: {e}'))
            return None

    def stream_celery_logs(self, process):
        """Stream Celery logs - shows all important logs with proper formatting."""
        try:
            # Signal that Celery has started
            self.celery_started.set()

            for line in process.stdout:
                if self.shutting_down:
                    break
                if not line.strip():
                    continue

                # ALWAYS SHOW - Errors and warnings (highest priority)
                if "ERROR" in line or "Traceback" in line or "Exception" in line:
                    self.stdout.write(self.style.ERROR(f'❌ [Celery] {line.rstrip()}'))
                    continue

                if "WARNING" in line or "WARN" in line or "retrying" in line.lower():
                    self.stdout.write(self.style.WARNING(f'⚠️ [Celery] {line.rstrip()}'))
                    continue

                # SKIP debug spam - Celery internal noise
                skip_patterns = [
                    "Timer wake-up",
                    "pidbox received",
                    "basic.qos",
                    "Celery beat:",
                    "DEBUG",
                ]
                if any(pattern in line for pattern in skip_patterns):
                    continue

                # Standard Celery task logs - ALWAYS SHOW these
                # Format: "Task <name>[<id>] received" or "Task <name>[<id>] succeeded"
                if "Task " in line and ("received" in line or "succeeded" in line or "failed" in line or "started" in line):
                    self.stdout.write(self.style.SUCCESS(f'🎯 [Celery] {line.rstrip()}'))
                    continue

                # Running task logs
                if "Running " in line and "task" in line.lower():
                    self.stdout.write(self.style.SUCCESS(f'🎯 [Celery] {line.rstrip()}'))
                    continue

                # Custom course generation logs
                if "CELERY TASK" in line:
                    self.stdout.write(self.style.SUCCESS(f'🎯 [Celery] {line.rstrip()}'))
                    continue

                if "Task ID:" in line or "Course ID:" in line or "Week:" in line or "Attempt:" in line:
                    self.stdout.write(self.style.SUCCESS(f'📋 [Celery] {line.rstrip()}'))
                    continue

                # Day generation logs
                if "[DAY GENERATION]" in line or "[DAY COMPLETE]" in line:
                    self.stdout.write(self.style.SUCCESS(f'📝 [Celery] {line.rstrip()}'))
                    continue

                # LLM call logs
                if "[LLM CALL]" in line:
                    self.stdout.write(self.style.SUCCESS(f'🤖 [Celery] {line.rstrip()}'))
                    continue

                # Web search logs
                if "[WEB SEARCH]" in line:
                    self.stdout.write(self.style.SUCCESS(f'📊 [Celery] {line.rstrip()}'))
                    continue

                # Week update logs
                if "STARTING WEEK" in line or "Generating week theme" in line:
                    self.stdout.write(self.style.SUCCESS(f'📝 [Celery] {line.rstrip()}'))
                    continue

                if "Generated" in line and ("test" in line.lower() or "quiz" in line.lower() or "questions" in line.lower() or "problems" in line.lower()):
                    self.stdout.write(self.style.SUCCESS(f'📝 [Celery] {line.rstrip()}'))
                    continue

                if "Questions:" in line or "Problems:" in line or "Test ID:" in line:
                    self.stdout.write(self.style.SUCCESS(f'📝 [Celery] {line.rstrip()}'))
                    continue

                if "Broadcast" in line or "progress" in line.lower():
                    self.stdout.write(self.style.WARNING(f'📡 [Celery] {line.rstrip()}'))
                    continue

                if "GENERATION COMPLETE" in line or "LAST TASK" in line or "marked as READY" in line:
                    self.stdout.write(self.style.SUCCESS(f'✅ [Celery] {line.rstrip()}'))
                    continue

                if "Starting" in line and ("weekly test" in line.lower() or "course" in line.lower()):
                    self.stdout.write(self.style.SUCCESS(f'📨 [Celery] {line.rstrip()}'))
                    continue

                if "Complete" in line or "generated" in line.lower():
                    self.stdout.write(self.style.SUCCESS(f'✅ [Celery] {line.rstrip()}'))
                    continue

                # Fallback: Show any remaining INFO lines from Celery
                # This ensures we don't miss valid logs that don't match specific patterns
                if "INFO" in line or "[celery]" in line.lower():
                    self.stdout.write(self.style.SUCCESS(f'📨 [Celery] {line.rstrip()}'))
                    continue

                # Default: Show any other non-empty line (prevents losing valid logs)
                # This is the key fix - don't silently drop lines
                self.stdout.write(f'[Celery] {line.rstrip()}\n')

        except Exception as e:
            if not self.shutting_down:
                self.stdout.write(self.style.ERROR(f'❌ [Celery Log Error] {e}'))

    def start_daphne(self, addrport):
        """Start Daphne ASGI server - runs in foreground with proper log streaming."""
        try:
            # Parse port from addrport
            port = addrport.split(':')[-1] if ':' in addrport else addrport

            # Build Daphne command
            daphne_cmd = [
                sys.executable, "-m", "daphne",
                "-b", "0.0.0.0",
                "-p", port,
                "config.asgi:application",
            ]

            self.stdout.write(self.style.SUCCESS(f'   🌐 Command: {" ".join(daphne_cmd)}'))
            self.stdout.write(self.style.SUCCESS('   ✅ Daphne started\n'))
            self.stdout.write(self.style.SUCCESS('=' * 80))
            self.stdout.write(self.style.SUCCESS('📋 Logs will show:'))
            self.stdout.write(self.style.SUCCESS('   🔌 WebSocket connections/disconnections'))
            self.stdout.write(self.style.SUCCESS('   🎯 Celery tasks (prefixed with [Celery])'))
            self.stdout.write(self.style.SUCCESS('   📡 API requests'))
            self.stdout.write(self.style.SUCCESS('   ⚠️  Errors and warnings'))
            self.stdout.write(self.style.SUCCESS('=' * 80 + '\n'))

            # Run Daphne with captured output for proper log streaming
            process = subprocess.Popen(
                daphne_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
            )

            # Stream Daphne logs
            self.stream_daphne_logs(process)

        except KeyboardInterrupt:
            pass
        except Exception as e:
            raise CommandError(f'Failed to start Daphne: {e}')

    def stream_daphne_logs(self, process):
        """Stream Daphne logs with proper formatting."""
        try:
            for line in process.stdout:
                if self.shutting_down:
                    break
                if not line.strip():
                    continue

                # ALWAYS SHOW - Errors and warnings
                if "ERROR" in line or "Traceback" in line or "Exception" in line:
                    self.stdout.write(self.style.ERROR(f'❌ [Daphne] {line.rstrip()}'))
                    continue

                if "WARNING" in line or "WARN" in line:
                    self.stdout.write(self.style.WARNING(f'⚠️ [Daphne] {line.rstrip()}'))
                    continue

                # WebSocket connection logs
                if "WebSocket" in line or "websocket" in line:
                    self.stdout.write(self.style.SUCCESS(f'🔌 [Daphne] {line.rstrip()}'))
                    continue

                # HTTP request logs
                if "HTTP" in line:
                    self.stdout.write(f'📡 [Daphne] {line.rstrip()}\n')
                    continue

                # ASGI logs
                if "[ASGI]" in line:
                    self.stdout.write(f'🌐 [Daphne] {line.rstrip()}\n')
                    continue

                # Default: Show any other Daphne log
                self.stdout.write(f'[Daphne] {line.rstrip()}\n')

        except Exception as e:
            if not self.shutting_down:
                self.stdout.write(self.style.ERROR(f'❌ [Daphne Log Error] {e}'))
