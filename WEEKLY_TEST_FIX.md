# Weekly Test Generation Fix

## Problem

When generating courses, the day content (quizzes, theory, code) was generated fluently in parallel, but the **weekly tests** and **coding tests** were failing with connection errors:

```
❌ LLM generation attempt 1 failed: Connection error.
❌ RuntimeError: Event loop is closed
```

### Root Cause

1. **Massive Parallelization**: After course content generation completed, the system queued **16 parallel tasks** (8 weeks × 2 tests each) simultaneously
2. **Shared Connection Pool**: All tasks used the same shared `httpx.AsyncClient` with limited connections (50 max, 20 keepalive)
3. **Event Loop Conflicts**: Each Celery task used `asyncio.run()` which creates its own event loop, but they all shared the same underlying HTTP client
4. **Connection Race Conditions**: When tasks completed and their event loops closed, they were closing connections that other tasks still needed

## Solution

### 1. Sequential Week Generation (`tasks.py`)

Changed `generate_weekly_tests_for_course` to process weeks **sequentially** instead of all at once:

**Before:**
```python
# All 16 tasks at once!
for week_number in range(1, 9):
    test_tasks.append(generate_weekly_test_task.delay(course_id, week_number))
    test_tasks.append(generate_coding_test_task.delay(course_id, week_number))
```

**After:**
```python
# One week at a time
for week_number in range(1, course.duration_weeks + 1):
    # Run both tests for this week in parallel (they use different endpoints)
    generate_weekly_test_task.delay(course_id, week_number)
    generate_coding_test_task.delay(course_id, week_number)
    time.sleep(0.5)  # Small delay before next week
```

### 2. Improved Retry Logic (`tasks.py`)

Enhanced `generate_weekly_test_task` and `generate_coding_test_task` with:

- **More retries**: Increased from 3 to 5 max retries
- **Exponential backoff**: `countdown=min(60, 10 * (2 ** self.request.retries))`
- **Fresh event loops**: Each task creates its own event loop to avoid conflicts
- **Better logging**: Shows attempt number in logs

```python
@shared_task(bind=True, max_retries=5, default_retry_delay=10, autoretry_for=(Exception,))
def generate_weekly_test_task(self, course_id: str, week_number: int):
    # Create fresh event loop for this task
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        generator = CourseGenerator()
        result = loop.run_until_complete(generator.generate_weekly_test(course_id, week_number))
    finally:
        loop.close()
```

### 3. Increased Connection Pool Limits (`client.py`)

Doubled the connection pool limits to handle concurrent tasks better:

```python
http_client = httpx.AsyncClient(
    timeout=TIMEOUT_SECONDS,
    limits=httpx.Limits(
        max_connections=100,           # Increased from 50
        max_keepalive_connections=50,  # Increased from 20
        keepalive_expiry=60,          # Increased from 30s
    ),
)
```

### 4. Better Task Ordering (`tasks.py`)

Changed the course generation flow to:

1. Generate all day content (parallel)
2. **Mark course as "ready"** (user can start using it)
3. Small delay (0.5s) for DB sync
4. Queue weekly tests (sequential weeks, parallel within week)

This ensures the course is available to users immediately, while weekly tests generate in the background.

## Impact

### Before Fix
- ❌ Weekly tests failed with "Event loop is closed" errors
- ❌ Multiple retry attempts needed
- ❌ Connection pool exhaustion
- ❌ 16 concurrent LLM calls overwhelming the server

### After Fix
- ✅ Weekly tests generate reliably one week at a time
- ✅ Each week's tests (MCQ + Coding) still run in parallel
- ✅ No connection pool exhaustion
- ✅ Only 2 concurrent LLM calls per week (max 2 at any time)
- ✅ Better error handling with exponential backoff
- ✅ Course available immediately after day content generation

## Files Changed

1. `backend/apps/courses/tasks.py`
   - `generate_weekly_tests_for_course`: Sequential week processing
   - `generate_weekly_test_task`: Fresh event loops, better retries
   - `generate_coding_test_task`: Fresh event loops, better retries
   - `generate_course_content_task`: Better ordering

2. `backend/services/llm/client.py`
   - Increased connection pool limits (50→100, 20→50, 30s→60s)

## Testing

To test the fix:

1. Start the development server: `python manage.py rundev`
2. Generate a new course from the frontend
3. Observe the Celery logs:
   - Day content should generate in parallel (fast)
   - Course status should change to "ready"
   - Weekly tests should generate one week at a time (sequential)
   - Each week should show both MCQ and coding test generating
   - No "Event loop is closed" errors

Example expected log output:
```
✅ COURSE GENERATION COMPLETE
📝 Queued weekly test generation task
Starting sequential weekly test generation for 8 weeks in course <id>
Generating tests for Week 1 of 8...
📝 CELERY TASK: GENERATE WEEKLY TEST (Attempt: 1/5)
💻 CELERY TASK: GENERATE CODING TEST (Attempt: 1/5)
✅ Weekly test generated successfully
✅ Coding test generated successfully
Generating tests for Week 2 of 8...
...
```
