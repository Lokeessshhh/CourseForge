# Quick Reference: Running the Development Server

## 🚀 One Command to Start Everything

```bash
cd backend
python manage.py rundev
```

**That's it!** This starts:
- ✅ **Daphne** (ASGI server for HTTP + WebSocket)
- ✅ **Celery Worker** (background task processing)
- ✅ **Full WebSocket support**

**Access your app at:** http://localhost:8000

---

## 📋 Common Commands

### Start Server
```bash
python manage.py rundev
```

### Start on Different Port
```bash
python manage.py rundev 8080
```

### Start Without Celery
```bash
python manage.py rundev --no-celery
```

### Windows Batch Script
```bash
start.bat
```

---

## 🔧 Prerequisites

### 1. Activate Virtual Environment
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. Start Redis (Required for Celery)
```bash
# Windows (if installed)
redis-server

# Linux/Mac
redis-server
```

### 3. Ensure PostgreSQL is Running
Check your PostgreSQL service is running.

---

## 🛑 Stop Server

Press **Ctrl+C** in the terminal.

This gracefully shuts down:
- Daphne server
- Celery worker
- All background processes

---

## 📊 What You'll See

```
================================================================================
🚀 STARTING DEVELOPMENT SERVER
================================================================================
   Django + Daphne (ASGI) + Celery + WebSocket
   🌐 http://127.0.0.1:8000
================================================================================

📦 Starting Celery worker...
   📦 Command: python -m celery -A config.celery worker --loglevel=info ...
   ✅ Celery worker started

📨 [Celery] starting celeryd...
✅ [Celery] worker ready

🌐 Starting Daphne ASGI server...
   ✅ Daphne started

================================================================================
📋 Logs will show:
   🔌 WebSocket connections/disconnections
   💬 Chat messages
   🎯 Celery tasks
   📡 API requests
================================================================================
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| Redis not running | Start with `redis-server` |
| Port 8000 in use | Use different port: `python manage.py runserver 8080` |
| Celery won't start | Check Redis is running |
| Database error | Check PostgreSQL is running and `.env` is configured |

---

## 📚 More Documentation

- **Complete Guide:** `SERVER_STARTUP_GUIDE.md`
- **Detailed Setup:** `DEV_SERVER_GUIDE.md`
- **Environment Variables:** `.env.example`

---

**Quick Start:**
```bash
cd backend
venv\Scripts\activate
python manage.py runserver
```
