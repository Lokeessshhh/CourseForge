# Development Server Setup - Complete Guide

## Quick Start

### Option 1: Custom rundev Command (Recommended)

```bash
cd backend
python manage.py rundev
```

This single command starts:
- ✅ **Daphne** ASGI server (HTTP + WebSocket) - http://localhost:8000
- ✅ **Celery worker** (background tasks)
- ✅ **WebSocket support** (real-time features)
- ✅ **Comprehensive logging** (all logs visible in one console)

### Option 2: Windows Batch Script

```bash
cd backend
start.bat
```

This script checks prerequisites and starts everything automatically.

### Start Frontend (Separate Terminal)
```bash
cd frontend
npm run dev
```

## What You'll See

### Startup Logs
```
================================================================================
🚀 STARTING DEVELOPMENT SERVER
================================================================================
   Django + Daphne (ASGI) + Celery + WebSocket
   🌐 http://127.0.0.1:8000
================================================================================

📦 Starting Celery worker...
   📦 Command: python -m celery -A config.celery worker --loglevel=info --pool=solo --without-gossip --without-mingle
   ✅ Celery worker started

📨 [Celery] starting celeryd...
✅ [Celery] worker ready

🌐 Starting Daphne ASGI server...
   🌐 Command: python -m daphne -b 0.0.0.0 -p 8000 config.asgi:application
   ✅ Daphne started

================================================================================
📋 Logs will show:
   🔌 WebSocket connections/disconnections
   💬 Chat messages
   🎯 Celery tasks
   📡 API requests
================================================================================
```

### WebSocket Connection Logs
```
================================================================================
🔌 WEBSOCKET CONNECTION ATTEMPT
   Scope: {'type': 'websocket', 'path': '/ws/chat/'}
   Query: token=eyJhbG...&session_id=abc123
================================================================================
[WS] ✅ User authenticated: user@example.com (user_id)
```

### Message Logs
```
============================================================
💬 MESSAGE RECEIVED
   User: user@example.com
   Session: abc-123-def
   Message: {"message": "Explain recursion", ...}
============================================================
[WS] 📩 Processing message: 'Explain recursion' (ID: msg-uuid)
```

### Celery Task Logs
```
================================================================================
🎓 CELERY TASK: GENERATE COURSE CONTENT
   Task ID: abc-123-def
   Course ID: course-uuid
   Course Name: Python Programming
   Duration: 4 weeks
   Level: beginner
================================================================================
```

### Disconnection Logs
```
================================================================================
🔌 WEBSOCKET DISCONNECTED
   User: user@example.com
   Session: abc-123-def
   Close Code: 1000
================================================================================
[WS] 🧹 Cleanup completed for session abc-123-def
```

## Log Levels & Icons

| Icon | Meaning | Example |
|------|---------|---------|
| 🔌 | WebSocket Connect/Disconnect | Connection events |
| 💬 | Message Received | User sent message |
| 📨 | Task Received | Celery received task |
| ✅ | Success | Task completed |
| ❌ | Error | Task failed |
| 🎓 | Course Generation | Creating course |
| 📝 | Weekly Test | Generating test |
| 🚀 | Server Start | Starting services |
| 🛑 | Shutdown | Stopping services |
| 📦 | Celery Start | Starting worker |
| 🌐 | Django Start | Starting server |
| 🧹 | Cleanup | Session cleanup |

## Alternative: Manual Service Startup

If you prefer to run services separately in different terminals:

### Terminal 1 - Daphne (ASGI Server)
```bash
cd backend
python -m daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

### Terminal 2 - Celery Worker
```bash
cd backend
celery -A config.celery worker --loglevel=info --pool=solo
```

### Terminal 3 - Celery Beat (Periodic Tasks - Optional)
```bash
cd backend
celery -A config.celery beat --loglevel=info
```

## Troubleshooting

### No Logs Showing
1. Check you're using `python manage.py rundev` (not standard Django runserver)
2. Verify virtual environment is activated
3. Check console isn't filtering output

### Celery Not Starting
1. Check Redis is running: `redis-cli ping`
2. Verify Redis service is started
3. Check `.env` file for correct `REDIS_URL`

### WebSocket Not Connecting
1. Check Daphne is installed: `pip install channels[daphne]`
2. Verify ASGI config in `config/asgi.py`
3. Check WebSocket URL in frontend

### Port Already in Use
```
Error: Address already in use
```
Solution: Use different port:
```bash
python manage.py rundev 8080
```

### Redis Connection Error
```
Error: Connection to Redis failed
```
Solution: Start Redis server:
```bash
redis-server
```

## Configuration Files

### `apps/core/management/commands/rundev.py`
- Custom management command starting Daphne + Celery
- Starts Celery worker as background process
- Starts Daphne ASGI server
- Streams Celery logs to console with formatting
- Handles graceful shutdown of all services
- Signal handling for Ctrl+C

### `config/asgi.py`
- ProtocolTypeRouter for HTTP + WebSocket
- Clerk WebSocket middleware
- Static files handler
- WebSocket URL routing

### `config/celery.py`
- Celery app configuration
- Task routes for different queues
- Beat schedule for periodic tasks
- Worker configuration

### `config/settings/development.py`
- Root logger set to INFO level
- Specific loggers for:
  - `websockets`
  - `channels`
  - `apps.courses`
  - `apps.websockets`
  - `celery`

## Command Options

```bash
# Default (port 8000)
python manage.py rundev

# Custom port
python manage.py rundev 8080

# Custom host:port
python manage.py rundev 0.0.0.0:8080

# Without Celery worker
python manage.py rundev --no-celery
```

### `apps/websockets/consumers.py`
- Connection attempt logging
- Authentication logging
- Message receive logging
- Disconnection logging
- All with visual indicators

### `apps/courses/tasks.py`
- Task start logging with details
- Progress updates
- Completion logging
- Error handling with tracebacks

## Production Deployment

For production, use:
```bash
# Use gunicorn with uvicorn workers
gunicorn config.asgi:application -k uvicorn.workers.UvicornWorker

# Separate Celery worker
celery -A config worker --loglevel=WARNING --pool=prefork
```

## Monitoring

### Watch Specific Logs
All logs are shown in the same console window:
- Daphne logs: HTTP requests, WebSocket events
- Celery logs: Task execution (prefixed with `[Celery]`)
- Django logs: Application events

### Filter Logs (Windows)
```powershell
# Run and filter output
python manage.py rundev 2>&1 | Select-String "WebSocket"
python manage.py rundev 2>&1 | Select-String "Celery"
```

### Log to File
Add to your rundev command:
```bash
python manage.py rundev > dev.log 2>&1
```

---

**Status**: ✅ Complete development server with Daphne + Celery + WebSocket support
**Usage**: `python manage.py rundev` for full development environment
**Documentation**: See `SERVER_STARTUP_GUIDE.md` for more details
