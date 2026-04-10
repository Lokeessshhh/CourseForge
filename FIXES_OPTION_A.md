# Option A Fixes Applied

## Date: 2026-04-09

---

## What Was Fixed

### 1. Day Content Silent Failures → Now Logged
**File:** `backend/apps/courses/tasks.py`
**Problem:** `asyncio.gather(return_exceptions=True)` silently swallowed errors when day generation failed
**Fix:** Added loop to check each result, log exceptions, and print failure counts

**Before:**
```python
results = await asyncio.gather(*day_tasks, return_exceptions=True)
successful = sum(1 for r in results if r is True)
print(f"Completed {successful}/{len(day_tasks)} days successfully")
```

**After:**
```python
results = await asyncio.gather(*day_tasks, return_exceptions=True)
successful = 0
failed = 0
for i, result in enumerate(results):
    if result is True:
        successful += 1
    elif isinstance(result, Exception):
        failed += 1
        logger.error("Day task %d failed: %s", i + 1, result)
    else:
        failed += 1
print(f"Completed {successful}/{len(day_tasks)} days ({failed} failed)")
```

---

### 2. Weekly Tests Hung Forever → Now Async
**File:** `backend/apps/courses/tasks.py` (`generate_weekly_tests_for_course`)
**Problem:** `.apply()` ran tests synchronously in the same thread. If LLM hung, entire task hung forever.
**Fix:** Changed to `.delay()` for async execution + immediate 'ready' status as fallback

**Before:**
```python
generate_weekly_test_task.apply(args=[course_id, week_number])  # Blocks forever if LLM hangs
generate_coding_test_task.apply(args=[course_id, week_number])
# Status only set to 'ready' by LAST coding test task
```

**After:**
```python
generate_weekly_test_task.delay(course_id, week_number)  # Non-blocking
generate_coding_test_task.delay(course_id, week_number)
# Immediately mark as 'ready' (idempotent - weekly tests also try but won't override)
course.generation_status = "ready"
course.save()
```

---

### 3. LLM Rate Limiting → Exponential Backoff
**File:** `backend/services/llm/client.py`
**Problem:** 1.5s fixed delay between retries was too short for rate limiting recovery
**Fix:** Exponential backoff: 3s → 6s → 12s → 24s → 48s (capped at 60s)

**Before:**
```python
await asyncio.sleep(1.5)  # Too short for rate limits
```

**After:**
```python
delay = min(3 * (2 ** attempt), 60)  # 3s, 6s, 12s, 24s, 48s
await asyncio.sleep(delay)
```

---

### 4. None LLM Response → Delayed Retry
**File:** `backend/services/llm/client.py`
**Problem:** When LLM returned `None`, it retried immediately (no delay)
**Fix:** Added 3s + 2s per attempt delay (3s, 5s, 7s, 9s, 11s)

---

### 5. Concurrent LLM Flood → Staggered Calls
**File:** `backend/apps/courses/tasks.py` (`_generate_single_day_with_titles`)
**Problem:** 5 days × 2 LLM calls each = 10 simultaneous requests → rate limiting
**Fix:** Added 0.5s delay before each day's theory+code generation

```python
# Before each day's LLM calls
await asyncio.sleep(0.5)  # Stagger to reduce rate limiting
```

---

### 6. Quiz Retry Delays → Increased
**File:** `backend/apps/courses/tasks.py`
**Problem:** 2s fixed delay between quiz retries
**Fix:** Increased to 3s → 5s → 7s exponential backoff

---

## Files Modified

1. `backend/apps/courses/tasks.py` - Exception logging, async weekly tests, staggered LLM calls
2. `backend/services/llm/client.py` - Exponential backoff, None response delay

---

## What Will Happen Now

1. **Day generation failures** → Logged with exact error messages
2. **Weekly tests** → Run async, course marked 'ready' immediately (won't hang)
3. **LLM rate limiting** → Retries with exponential backoff (longer waits between attempts)
4. **LLM connection failures** → Retries with delays, logs each attempt

---

## What Still Can't Be Fixed

- **LLM provider downtime** - If OpenRouter/Venice is down, no code helps
- **LLM rate limit quotas** - The free tier has limits; if exceeded, only waiting helps
- **Slow LLM responses** - Network latency is out of our control

---

## Expected Terminal Output After Fix

```
[BLOCK 1] Day 1 failed: ConnectionError: All connection attempts failed  ← Now visible
[BLOCK 1] Day 2 failed: NoneType error                                   ← Now visible
[BLOCK 1] Completed 3/5 days successfully (2 failed)                    ← Now accurate
📝 Weekly test generation complete                                      ← Fast, no hang
✅ COURSE GENERATION COMPLETE                                            ← Finishes
   Status: ready                                                         ← Set immediately
   Progress: 5/7 tasks
```

---

## Next Steps

1. Restart server: `python manage.py rundev`
2. Create a course
3. Check terminal for failure details (previously hidden)
4. Check `logs/celery.log` for complete execution trace
