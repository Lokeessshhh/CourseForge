# Development Server Guide

## Quick Start

### Option 1: Using the Custom `rundev` Command (Recommended)

```bash
# Activate your virtual environment first
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac

# Run all services with one command
python manage.py rundev
```

This starts:
- **Daphne** - ASGI server handling HTTP + WebSocket connections
- **Celery Worker** - Async task queue for background jobs
- **Full WebSocket support** - Real-time features enabled

**Server URL:** http://localhost:8000

---

### Option 2: Using the Batch Script (Windows Only)

```bash
# Double-click start.bat or run from command line
start.bat
```

This script:
- ✅ Checks if virtual environment is activated
- ✅ Verifies Redis is running
- ✅ Checks database connection
- ✅ Starts all services automatically

---

### Option 3: Manual Startup (Individual Services)

If you prefer to run services separately:

```bash
# Terminal 1: Daphne (ASGI server)
python -m daphne -b 0.0.0.0 -p 8000 config.asgi:application

# Terminal 2: Celery Worker
python -m celery -A config.celery worker --loglevel=info --pool=solo

# Terminal 3: Celery Beat (Periodic Tasks - Optional)
python -m celery -A config.celery beat --loglevel=info
```

---

## Command Options

### Custom Rundev Command

```bash
# Default (port 8000)
python manage.py rundev

# Custom port
python manage.py rundev 8080

# Custom host and port
python manage.py rundev 0.0.0.0:8080

# Without Celery worker
python manage.py rundev --no-celery
```

---

## What's Running?

When you run `python manage.py rundev`, here's what starts:

| Service | Purpose | Port |
|---------|---------|------|
| **Daphne** | ASGI server for HTTP + WebSocket | 8000 |
| **Celery Worker** | Background task processing | - |
| **Redis** | Message broker (must be running separately) | 6379 |

### Features Enabled:
- ✅ HTTP requests (REST API)
- ✅ WebSocket connections (real-time features)
- ✅ Celery async tasks (course generation, quizzes, certificates)
- ✅ Celery beat periodic tasks (streak checks, session cleanup)
- ✅ Django admin interface
- ✅ Static files serving

---

## Prerequisites

Before running the server, ensure:

### 1. Redis is Running

```bash
# Windows (if installed as service)
redis-server

# Linux/Mac
redis-server
```

**Test Redis:**
```bash
redis-cli ping
# Should return: PONG
```

### 2. PostgreSQL is Running

```bash
# Windows (if installed as service)
# Check Services panel for PostgreSQL

# Linux/Mac
sudo systemctl status postgresql
```

### 3. Virtual Environment Activated

```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 4. Dependencies Installed

```bash
pip install -r requirements.txt
```

---

## Troubleshooting

### Redis Connection Error

```
Error: Connection to Redis failed
```

**Solution:** Start Redis server:
```bash
redis-server
```

### Database Connection Error

```
Error: could not connect to server: Connection refused
```

**Solution:** 
1. Start PostgreSQL service
2. Check `.env` file for correct database credentials
3. Run migrations: `python manage.py migrate`

### Port Already in Use

```
Error: Address already in use
```

**Solution:** Use a different port:
```bash
python manage.py rundev 8080
```

Or kill the process using port 8000:
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

### Celery Worker Not Starting

```
Error: Celery failed to start
```

**Solutions:**
1. Ensure Redis is running
2. Check Celery app config: `python -c "from config.celery import app; print(app)"`
3. Try running Celery separately to see errors:
   ```bash
   python -m celery -A config.celery worker --loglevel=debug
   ```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│                  Client (Browser)               │
└───────────────────┬─────────────────────────────┘
                    │
                    │ HTTP / WebSocket
                    ▼
┌─────────────────────────────────────────────────┐
│              Daphne (ASGI Server)               │
│              Port: 8000                         │
│  ┌─────────────────────────────────────────┐    │
│  │  Django Channels                        │    │
│  │  - HTTP Handlers                        │    │
│  │  - WebSocket Handlers                   │    │
│  │  - ProtocolTypeRouter                   │    │
│  └─────────────────────────────────────────┘    │
└───────────┬───────────────────┬─────────────────┘
            │                   │
            │                   │
            ▼                   ▼
┌───────────────────┐  ┌─────────────────────────┐
│  Django App       │  │  Celery Worker          │
│  - REST API       │  │  - Course Generation    │
│  - Admin Panel    │  │  - Quiz Creation        │
│  - Auth (Clerk)   │  │  - Certificate PDF      │
└───────────────────┘  └───────────┬─────────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │  Redis Broker   │
                          │  Port: 6379     │
                          └─────────────────┘
```

---

## Logs

All logs appear in a single console window:

- **Daphne logs**: HTTP requests, WebSocket connections
- **Celery logs**: Task execution, worker status
- **Django logs**: Application events, errors

### Log Format

```
🌐 [Daphne] Starting server...
📦 [Celery] Worker ready
📨 [Celery] Task received: courses.tasks.generate_course
✅ [Celery] Task completed: courses.tasks.generate_course
🔌 [WebSocket] Client connected
💬 [WebSocket] Message received
📡 [HTTP] GET /api/courses/ 200
```

---

## Production Deployment

For production, use:

```bash
# With Gunicorn (HTTP) + Uvicorn (WebSocket)
gunicorn config.asgi:application -k uvicorn.workers.UvicornWorker

# Or with Daphne in production mode
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

Plus separate Celery worker:
```bash
celery -A config.celery worker --loglevel=info --concurrency=4
```

And Celery beat for periodic tasks:
```bash
celery -A config.celery beat --loglevel=info
```

---

## Need Help?

1. Check the main README.md
2. Review `.env.example` for required environment variables
3. See `DEV_SERVER_GUIDE.md` for more details
4. Check Django logs for specific errors
