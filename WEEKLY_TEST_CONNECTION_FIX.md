# Weekly Test Connection Error Fix

## Problem

Weekly tests (MCQ and coding tests) were consistently failing with connection errors:
```
WARNING LLM generation attempt 1/5 failed: Connection error.
RuntimeError: Event loop is closed
```

But day generation worked perfectly.

## Root Cause

**Event loop lifecycle mismatch.**

### Day Generation (Working ✅)
```python
# Main task uses asyncio.run() - proper async management
asyncio.run(_generate_in_blocks_with_web_search(...))
```

### Weekly Tests (Broken ❌)
```python
# Manual event loop management
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    result = loop.run_until_complete(generator.generate_weekly_test(...))
finally:
    loop.close()  # ← Closes the event loop
```

### Why This Caused Connection Errors

The HTTP client in `services/llm/client.py` is a **module-level singleton**:

```python
http_client = httpx.AsyncClient(...)  # Created ONCE at module import
client = AsyncOpenAI(..., http_client=http_client)  # Shares the client
```

When a Celery task:
1. Creates a new event loop with `asyncio.new_event_loop()`
2. Runs async HTTP calls through the shared `client`
3. Closes the loop with `loop.close()`

The HTTP client's internal connection pool still holds references to the **CLOSED event loop**. On retry or the next task:
```
RuntimeError: Event loop is closed
  → httpx tries to use connections from old loop
  → Connection error
```

## Solution

Replace manual event loop management with `asyncio.run()` in both tasks:

### Before (Broken)
```python
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    result = loop.run_until_complete(generator.generate_weekly_test(...))
finally:
    loop.close()
```

### After (Fixed)
```python
result = asyncio.run(generator.generate_weekly_test(...))
```

## Files Changed

- `backend/apps/courses/tasks.py`
  - Line ~1013: `generate_weekly_test_task` - Use `asyncio.run()`
  - Line ~1176: `generate_coding_test_task` - Use `asyncio.run()`

## Why asyncio.run() Works

`asyncio.run()` properly:
1. Creates a new event loop
2. Runs the coroutine to completion
3. **Cleans up all async resources** (closes connections, cancels tasks)
4. Closes the loop safely

This ensures the HTTP client doesn't hold stale references to closed loops.

## Testing

After deploying:
1. Restart Celery workers
2. Generate a new course
3. Verify weekly tests complete without connection errors
4. Check logs for "Event loop is closed" errors

## Bonus Fix

Also fixed: `generate_coding_test()` was being called with 3 arguments but only accepts 2:
```python
# Before (wrong)
generator.generate_coding_test(course_id, week_number, test_number)

# After (correct)
generator.generate_coding_test(course_id, week_number)
```
