# Celery Queue Cleanup System

## Overview
The system now automatically clears stale Celery tasks when the Django backend restarts, preventing accumulation of old tasks from previous sessions.

## Automatic Cleanup on Startup

When you start the Django backend (`python manage.py runserver` or `rundev`), the system automatically:

1. **Checks all Celery queues** for stale tasks
2. **Purges any lingering tasks** from previous sessions
3. **Logs the cleanup** to the Django console

You'll see this in your Django startup logs:
```
[CLEANUP] Cleared X stale Celery task(s) on startup
```
or
```
[CLEANUP] No stale Celery tasks found on startup
```

## Manual Queue Management

### Purge all queues manually:
```bash
python manage.py purge_celery_queues
```

### Check queue depths without purging:
```bash
python manage.py purge_celery_queues --dry-run
```

### Purge a specific queue:
```bash
python manage.py purge_celery_queues --queue course_generation
```

## Task Expiration

Tasks are now configured to automatically expire:
- **Task expiration**: 1 hour (tasks not consumed within 1 hour are discarded)
- **Result expiration**: 24 hours (task results are cleaned up after 24 hours)

## Queue Names

The system manages these queues:
- `celery` - Default queue
- `course_generation` - Course content generation tasks
- `quiz_generation` - Quiz generation tasks
- `certificates` - Certificate generation tasks

## How It Works

1. **Django Startup Signal** (`apps/core/apps.py`):
   - Runs automatically when Django starts
   - Connects to Redis and checks each queue
   - Purges any tasks left from previous sessions
   - Handles errors gracefully (won't crash if Redis is down)

2. **Task Expiration**:
   - Tasks have a 1-hour expiration time
   - If you restart Django and Celery within an hour, old tasks might still be there
   - The startup purge ensures they're always cleared

3. **Management Command**:
   - Manual control for debugging
   - Can check queue depths without purging
   - Can target specific queues

## Best Practices

### Starting Your Development Environment:
1. Start Redis: `redis-server`
2. Start Celery: `python -m celery -A config.celery worker --loglevel=info --pool=threads --concurrency=4 --without-gossip --without-mingle -Q celery,course_generation,quiz_generation,certificates`
3. Start Django: `python manage.py runserver` (auto-purges queues)

### If Things Get Stuck:
```bash
# Stop Django and Celery, then:
python manage.py purge_celery_queues
# Then restart services
```

### Production Notes:
- In production, you might NOT want to purge queues on startup
- Use the management command for manual cleanup instead
- Consider increasing `task_expire_seconds` for long-running tasks

## Troubleshooting

**Tasks not being purged?**
- Check if Redis is running: `redis-cli ping` (should return PONG)
- Check Celery worker is connected: Look for "Connected to redis://localhost:6379/0"

**Still seeing old tasks?**
- Run manual purge: `python manage.py purge_celery_queues`
- Restart Celery worker (it will recreate the queues)

**Error on startup?**
- The purge is wrapped in try/except - won't crash Django
- Check Django logs for the warning message
