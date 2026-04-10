# Log File Output for rundev

## Date: 2026-04-09

---

## What Changed

The `python manage.py rundev` command now writes **ALL** Celery and Daphne logs to separate files in addition to the terminal output.

## Log File Locations

```
backend/
├── logs/
│   ├── celery.log    ← ALL Celery worker logs (task execution, errors, progress)
│   └── daphne.log    ← ALL Daphne ASGI server logs (HTTP requests, WebSocket, errors)
```

## Key Features

### 1. **Complete Log Capture**
- **ALL** Celery output goes to `logs/celery.log` (no filtering)
- **ALL** Daphne output goes to `logs/daphne.log` (no filtering)
- Even logs that don't appear in the terminal are captured in the files

### 2. **Terminal Output (Unchanged)**
- Terminal still shows filtered, readable output
- Errors/warnings always shown
- Debug noise filtered out
- No changes to your current terminal experience

### 3. **Automatic Log Management**
- Logs directory created automatically on startup
- Files opened with line buffering (real-time writes)
- Proper cleanup on shutdown (Ctrl+C)
- Timestamp headers in each file

### 4. **Startup Banner**
```
================================================================================
🚀 STARTING DEVELOPMENT SERVER
================================================================================
   Django + Daphne (ASGI) + Celery + WebSocket
   🌐 http://127.0.0.1:8000
   📝 Logs: C:\...\backend\logs
================================================================================
```

## How to View Logs

### While Server is Running

**Option 1: Terminal (filtered)**
- Just watch the terminal output as before

**Option 2: Log Files (complete)**
```bash
# Tail Celery logs in real-time
tail -f backend/logs/celery.log

# Tail Daphne logs in real-time
tail -f backend/logs/daphne.log

# Search for specific task
grep "generate_course_content_task" backend/logs/celery.log

# Search for errors
grep -i "error\|exception" backend/logs/celery.log
```

**Option 3: Windows PowerShell**
```powershell
# Tail Celery logs
Get-Content backend\logs\celery.log -Wait -Tail 50

# Tail Daphne logs
Get-Content backend\logs\daphne.log -Wait -Tail 50

# Search for errors
Select-String -Path backend\logs\celery.log -Pattern "ERROR|Exception"
```

## What's in Each File

### `celery.log`
- Celery worker startup banner
- Task registration list
- Task execution logs (📦 CELERY TASK: GENERATE COURSE CONTENT)
- Progress logs (BLOCK 1, Week 1, Day 1, etc.)
- LLM call logs
- Error traces and exceptions
- Weekly test generation logs
- Course completion logs

### `daphne.log`
- Daphne server startup
- HTTP request logs (GET /api/courses/, POST /api/courses/generate/, etc.)
- WebSocket connection/disconnection events
- JWT authentication logs
- Serializer logs
- Error traces and exceptions

## Troubleshooting

### "Celery tasks not showing in terminal?"
→ Check `logs/celery.log` for complete output

### "Course generation failed but no error in terminal?"
→ Check `logs/celery.log` for full error trace

### "HTTP requests failing?"
→ Check `logs/daphne.log` for request/response details

### "Logs getting too large?"
→ Safe to delete while server is stopped. New files created on next start.

## Technical Details

### Implementation
- `subprocess.Popen` with `stdout=subprocess.PIPE`
- Dedicated threading.Thread for each process log stream
- `readline()` loop for real-time line reading
- Line-buffered file writes (`buffering=1`)
- Proper file cleanup on shutdown

### File Paths
- Determined dynamically from `rundev.py` location
- `backend_root = Path(__file__).resolve().parent.parent.parent.parent.parent`
- `logs_dir = backend_root / "logs"`

### Buffering
- Python `-u` flag forces unbuffered output
- `PYTHONUNBUFFERED=1` environment variable
- `bufsize=1` for line buffering
- File `flush()` after each write

## Changes Made

### File: `backend/apps/core/management/commands/rundev.py`

1. Added `logging` and `Path` imports
2. Added `celery_log_file`, `daphne_log_file`, `logs_dir` instance variables
3. Added `setup_log_files()` method - creates logs/ directory and opens files
4. Added `cleanup_log_files()` method - closes files on shutdown
5. Modified `stream_celery_logs()` - writes ALL output to `celery.log`
6. Modified `stream_daphne_logs()` - writes ALL output to `daphne.log`
7. Updated startup banner to show log directory path
8. Updated `cleanup_processes()` to close log files
