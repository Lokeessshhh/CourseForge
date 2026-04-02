# Weekly Test Generation Fix - Thread Pool

## Problem

With `--pool=solo` (single worker), weekly tests were not generating because:

1. `generate_weekly_tests_for_course` ran on the only worker
2. It queued child tasks (weekly test, coding test)
3. But those child tasks couldn't run because the worker was blocked
4. SSE connection closed before child tasks completed
5. Frontend showed 100% before weekly tests actually ran

## Solution

Changed Celery worker from **solo** to **threads** pool:

### Before (Broken)
```bash
celery -A config worker --pool=solo
```
- Single worker process
- Tasks run one at a time
- Child tasks wait forever if parent doesn't yield

### After (Fixed)
```bash
celery -A config worker --pool=threads --concurrency=4
```
- 4 worker threads
- Parent and child tasks run concurrently
- SSE stays open until all tasks complete

## Files Changed

### 1. `apps/core/management/commands/rundev.py`
```python
# Changed from:
"--pool=solo",

# To:
"--pool=threads",
"--concurrency=4",
```

### 2. `start_dev.py`
```python
# Changed from:
"--pool=solo",

# To:
"--pool=threads",
"--concurrency=4",
```

### 3. `apps/courses/tasks.py` - `generate_weekly_tests_for_course`
- Removed `task.get()` blocking calls
- Now just queues child tasks and exits
- Child tasks run in parallel on thread pool

### 4. `apps/courses/tasks.py` - `generate_coding_test_task`
- Added logic to detect if it's the LAST task
- If last task: sets `status='ready'` and broadcasts 100%
- If not last: broadcasts intermediate progress

## Progress Flow (2-week course)

```
Days 1-10:    7.14% → 71.43%  (10/14 tasks)
Week 1 MCQ:   78.57%          (11/14)
Week 1 Code:  85.71%          (12/14)
Week 2 MCQ:   92.86%          (13/14)
Week 2 Code:  100% + ready    (14/14) ← LAST task sets ready!
SSE closes → Toast dismisses
```

## Testing

1. **Run backend:**
   ```bash
   cd backend
   python manage.py rundev
   ```

2. **Generate course** (2 weeks for fast test)

3. **Watch logs:**
   ```
   ✅ Completed day 10 (progress: 10/14)
   📢 Broadcast: 71%
   📢 Broadcast: 78%  ← Week 1 MCQ
   📢 Broadcast: 85%  ← Week 1 Coding
   📢 Broadcast: 92%  ← Week 2 MCQ
   📢 Broadcast: 100% ← Week 2 Coding (LAST!)
   ✅ ALL tasks complete! Course is now ready
   ```

4. **Frontend shows:**
   - Progress bar smoothly increments to 100%
   - "Course generation complete!"
   - Auto-dismisses after 3 seconds

## Benefits

✅ All weekly tests generate (including last one)
✅ Progress bar accurate (doesn't jump around)
✅ SSE stays open until truly complete
✅ Toast dismisses at correct time
✅ Works with any number of weeks (2, 4, 8, etc.)

## Notes

- Thread pool is safe for development
- For production, consider using `--pool=gevent` or multiple processes
- 4 threads is good balance for local development
- Redis pub/sub still used for cross-process communication
