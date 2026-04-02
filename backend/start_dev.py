"""
Start Django development server with Celery worker.
This script starts both Django and Celery in the same terminal.
Usage: python start_dev.py
"""
import os
import sys
import subprocess
import threading
import time

# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

def print_banner():
    """Print startup banner."""
    print("\n" + "=" * 80)
    print("🚀 STARTING DEVELOPMENT SERVER")
    print("=" * 80)
    print("   Django + Celery + WebSocket")
    print("   http://localhost:8000")
    print("=" * 80 + "\n")

def start_celery():
    """Start Celery worker and stream logs."""
    print("📦 Starting Celery worker...\n")
    
    project_name = "config"
    celery_cmd = [
        sys.executable, "-m", "celery",
        "-A", project_name,
        "worker",
        "--loglevel=info",
        "--pool=threads",  # Use threads pool for concurrent task execution
        "--concurrency=4",  # 4 worker threads
        "--without-gossip",
        "--without-mingle",
    ]
    
    process = subprocess.Popen(
        celery_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1,
    )
    
    # Stream Celery logs
    for line in process.stdout:
        if line.strip():
            # Format Celery logs
            if "received" in line.lower() or "starting" in line.lower():
                print(f"📨 [Celery] {line.strip()}")
            elif "completed" in line.lower() or "ready" in line.lower():
                print(f"✅ [Celery] {line.strip()}")
            elif "error" in line.lower() or "failed" in line.lower():
                print(f"❌ [Celery] {line.strip()}")
            else:
                print(f"   [Celery] {line.strip()}")
    
    return process

def start_django():
    """Start Django development server."""
    from django.core.management import execute_from_command_line
    
    print("🌐 Starting Django development server...\n")
    
    sys.argv = ["manage.py", "runserver", "--noreload"]
    execute_from_command_line(sys.argv)

if __name__ == "__main__":
    print_banner()
    
    # Start Celery in background thread
    celery_thread = threading.Thread(target=start_celery, daemon=True)
    celery_thread.start()
    
    # Wait for Celery to initialize
    time.sleep(3)
    
    # Start Django (blocks main thread)
    try:
        start_django()
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
        sys.exit(0)
