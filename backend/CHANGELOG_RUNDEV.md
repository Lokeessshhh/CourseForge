# Changelog - Development Server Update

## Latest Update: Custom `rundev` Command

### What Changed

The custom development server command has been renamed from `runserver` to **`rundev`** to avoid conflicts with Django's built-in `runserver` command.

### Why the Change

Django's built-in `runserver` command takes precedence over custom commands with the same name. To ensure our custom command (which starts Daphne + Celery + WebSocket) is used, we renamed it to `rundev`.

### How to Use

**Old command (no longer works):**
```bash
python manage.py runserver  # ❌ Uses Django's built-in server (no WebSocket support)
```

**New command:**
```bash
python manage.py rundev  # ✅ Starts Daphne + Celery + WebSocket
```

### What It Does

Running `python manage.py rundev` now starts:

1. **Daphne** - ASGI server for HTTP + WebSocket connections
2. **Celery Worker** - Background task processing
3. **Full WebSocket Support** - Real-time features enabled

### Command Options

```bash
# Default (port 8000)
python manage.py rundev

# Custom port
python manage.py rundev 8080

# Without Celery worker
python manage.py rundev --no-celery

# Without auto-reloader
python manage.py rundev --noreload
```

### Files Changed

- `apps/core/management/commands/runserver.py` → `rundev.py` (renamed)
- `start.bat` (updated to use `rundev`)
- `QUICK_START.md` (updated documentation)
- `DEV_SERVER_GUIDE.md` (updated documentation)
- `SERVER_STARTUP_GUIDE.md` (updated documentation)
- `config/settings/base.py` (added `apps.core` to INSTALLED_APPS)

### Migration Steps

1. Stop any running servers
2. Use `python manage.py rundev` going forward
3. Update any scripts or documentation that reference `runserver`

### Quick Start

```bash
cd backend
venv\Scripts\activate
python manage.py rundev
```

Or use the batch file:
```bash
cd backend
start.bat
```

---

**Date:** 2026-03-28
**Status:** ✅ Complete
