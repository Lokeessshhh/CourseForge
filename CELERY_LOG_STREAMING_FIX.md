# Celery Log Streaming Fix

## Date: 2026-04-09

---

## Problem

Celery task execution logs were not appearing in the terminal when running `python manage.py rundev`. The Celery worker banner showed, but no task execution logs (like "📦 [Celery] 🎓 CELERY TASK: GENERATE COURSE CONTENT") appeared.

## Root Cause

1. **Python output buffering**: When Python runs as a subprocess with `stdout=subprocess.PIPE`, output can be buffered even with `bufsize=1` (line buffering), because Python's internal buffering overrides this.

2. **Iterator-based reading**: The `for line in process.stdout:` pattern blocks until EOF and may not yield lines in real-time when the subprocess buffers its output.

## Fixes Applied

### File: `backend/apps/core/management/commands/rundev.py`

#### 1. Added `-u` flag to force unbuffered output
- Celery: `sys.executable, "-u", "-m", "celery", ...`
- Daphne: `sys.executable, "-u", "-m", "daphne", ...`

#### 2. Set `PYTHONUNBUFFERED` environment variable
- Both Celery and Daphne subprocesses now have `env["PYTHONUNBUFFERED"] = "1"`

#### 3. Changed from iterator to `readline()` loop
**Before:**
```python
for line in process.stdout:
    if self.shutting_down:
        break
    ...
```

**After:**
```python
while True:
    if self.shutting_down:
        break
    line = process.stdout.readline()
    if not line:
        if process.poll() is not None:
            break
        continue
    ...
```

#### 4. Added process exit code detection
- When Celery/Daphne exits unexpectedly, shows error message with return code

## How It Works Now

```
┌─────────────────────────────────────────────────────────────┐
│  python manage.py rundev                                     │
│                                                              │
│  ┌──────────────────────┐    ┌────────────────────────────┐ │
│  │  Celery Worker       │    │  Daphne (ASGI Server)      │ │
│  │  (subprocess -u)     │    │  (subprocess -u)           │ │
│  │  PYTHONUNBUFFERED=1  │    │  PYTHONUNBUFFERED=1        │ │
│  │                      │    │                            │ │
│  │  stdout ─────────────┼───▶│  stdout ───────────────────┼─┤
│  └──────────────────────┘    └────────────────────────────┘ │
│         │                                  │                │
│         ▼                                  ▼                │
│  stream_celery_logs()           stream_daphne_logs()       │
│  (while True + readline())      (while True + readline())   │
│         │                                  │                │
│         ▼                                  ▼                │
│  📦 [Celery] ...                  [Daphne] ...              │
│  ❌ [Celery] ERROR...             ❌ [Daphne] ERROR...      │
│  ⚠️ [Celery] WARNING...           ⚠️ [Daphne] WARNING...    │
└─────────────────────────────────────────────────────────────┘
```

## Testing

1. Run `python manage.py rundev`
2. Create a course via the UI
3. Expected: Celery task logs appear in real-time:
   ```
   📦 [Celery] 🎓 CELERY TASK: GENERATE COURSE CONTENT
   📦 [Celery] [BLOCK 1] Generating themes and titles for weeks 1-1
   📦 [Celery] [BLOCK 1] Week 1 theme saved: Week 1: ...
   📦 [Celery] [BLOCK 1] Week 1 Day 1 title: ...
   ...
   📦 [Celery] ✅ COURSE GENERATION COMPLETE
   ```

## Benefits

- ✅ Real-time Celery task logs
- ✅ Real-time Daphne server logs
- ✅ Errors/warnings always visible
- ✅ Graceful process exit detection
- ✅ No lost or delayed log messages
