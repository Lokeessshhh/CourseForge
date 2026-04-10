# Course Generation Issues - Complete Analysis

## Database State Analysis (2026-04-10 06:14)

### SQL Course (ID: 1a356fe9-2239-433d-a4f1-33353b91c65b)
| Component | Expected | Actual | Status |
|-----------|----------|--------|--------|
| Weeks | 4 | 4 | ✅ |
| Days | 20 | 20 | ✅ |
| MCQ Tests | 4 | **3** | ❌ Week 2 missing |
| Coding Tests | 4 | **1** | ❌ Only Week 4 succeeded |
| Status | ready | **generating** | ❌ Stuck at 23% |

### Python Course (ID: 93525660-eb76-451a-8d11-fca7cce66c32)
| Component | Expected | Actual | Status |
|-----------|----------|--------|--------|
| Weeks | 5 | **9** | ❌ **4 extra weeks!** |
| MCQ Tests | 5 | 9 | ❌ Matches wrong week count |
| Coding Tests | 5 | 9 | ❌ Matches wrong week count |

### Java Course (ID: 838a37d2-2532-4d64-b83f-7964c45d4a33)
| Component | Expected | Actual | Status |
|-----------|----------|--------|--------|
| Weeks | 4 | 4 | ✅ |
| Days | 20 | 20 | ✅ |
| MCQ Tests | 4 | 4 | ✅ |
| Coding Tests | 4 | **0** | ❌ All failed |

---

## Root Causes Found

### 🔴 ISSUE 1: Stale Celery Tasks from Previous Courses

**Evidence from logs:**
```
[2026-04-10 06:08:42] Task started for coding test
INFO 2026-04-10 06:08:42 tasks    Course ID: a22d01f6-e26b-4a17-aa48-4f89d7e6f700  ← Java course
INFO 2026-04-10 06:08:42 tasks    Week: 2
ERROR: Course matching query does not exist  ← Java course was deleted/recreated?
```

But the SQL course being generated is: `1a356fe9-2239-433d-a4f1-33353b91c65b`

**What happened:**
1. Java course (`a22d01f6...`) was generated → queued 8 test tasks
2. Tests started generating but coding tests failed (event loop bug)
3. Coding test tasks went into **retry loop** (10s, 20s, 40s, 60s backoff)
4. You generated SQL course → queued 8 new test tasks
5. Celery worker started processing **BOTH** queues:
   - Java coding tests (stale, failing)
   - SQL coding tests (new, should work)
6. Java tasks consumed worker threads → SQL tasks delayed/failed

**Why Week 2 MCQ missing:**
- Week 2 MCQ task probably failed or got stuck behind retrying Java tasks
- It was never executed

**Why only Week 4 coding test succeeded:**
- Week 4 task (`e3038f73...`) started at 06:12:16 (AFTER Java retries exhausted)
- Previous Week 2/3 tasks (`8b9607a6...`, `46e2d39d...`) were still retrying Java course

---

### 🔴 ISSUE 2: Connection Errors on Task Start

**Evidence:**
```
[2026-04-10 06:12:16,717] Task received
WARNING 2026-04-10 06:12:16,735 LLM generation attempt 1/5 failed: Connection error.
WARNING 2026-04-10 06:12:18,744 LLM generation attempt 2/5 failed: Connection error.
WARNING 2026-04-10 06:12:22,757 LLM generation attempt 3/5 failed: Connection error.
[2026-04-10 06:12:32,194] HTTP Request: POST ... "HTTP/1.1 200 OK"  ← Success on attempt 4
```

**Root Cause:**
Even with `asyncio.run()` fix, the **httpx.AsyncClient** singleton at module level may have stale connections from previous tasks. When a new task starts, the connection pool is in a bad state.

**Why it doesn't happen for day generation:**
- Day generation runs in `asyncio.run()` which properly manages the event loop
- The HTTP client is created fresh within that loop
- Weekly tests run in **separate Celery tasks** that may reuse the module-level client across different event loops

---

### 🔴 ISSUE 3: Python Course Has 9 Weeks Instead of 5

**Evidence:**
```
Course: Python Programming
Duration: 5 weeks
Weeks in DB: 9 weeks
```

This is from course **update/extend** functionality. When you updated the course, it:
1. Kept existing 5 weeks
2. Added 4 more weeks (probably from extending or updating multiple times)
3. All tests generated for all 9 weeks

This is a **separate bug** in the course update logic.

---

## Solutions Required

### Fix 1: Purge Stale Celery Tasks Before Generating New Course ✅
**Action:** Add task queue cleanup when starting a new course generation.

**Implementation:**
```python
# In generate_course_content_task, before queuing tests:
from celery import Celery
app = Celery()
app.control.purge()  # Purge all pending tasks
```

**Or manually:**
```bash
celery -A config.celery purge
```

---

### Fix 2: Fix HTTP Client Connection Pool Issues

**Current code (client.py line 37-49):**
```python
http_client = httpx.AsyncClient(
    timeout=TIMEOUT_SECONDS,
    limits=httpx.Limits(
        max_connections=100,
        max_keepalive_connections=50,
        keepalive_expiry=60,
    ),
)
client = AsyncOpenAI(..., http_client=http_client)
```

**Problem:** This client is created ONCE at module import and reused across ALL Celery tasks. When tasks fail or retry, the connection pool can become corrupted.

**Solution:** Create a new HTTP client for each `asyncio.run()` call:

```python
# In generate_coding_test_task and generate_weekly_test_task:
async def generate_with_client(course_id, week_number):
    from services.llm.client import create_client  # New function
    generator = CourseGenerator()
    return await generator.generate_coding_test(course_id, week_number)

result = asyncio.run(generate_with_client(course_id, week_number))
```

**Better:** Add a `create_client()` function that creates a fresh client:

```python
# services/llm/client.py
def create_client():
    """Create a fresh HTTP client for each async context."""
    http_client = httpx.AsyncClient(
        timeout=TIMEOUT_SECONDS,
        limits=httpx.Limits(
            max_connections=100,
            max_keepalive_connections=50,
            keepalive_expiry=60,
        ),
        headers=headers,
    )
    return AsyncOpenAI(
        base_url=BASE_URL,
        api_key=API_KEY if API_KEY else "sk-or-placeholder",
        http_client=http_client,
        max_retries=SDK_MAX_RETRIES,
    )
```

Then use it in the generator methods.

---

### Fix 3: Add Task ID Validation

Before executing a coding/MCQ test task, verify the course still exists and the task belongs to the current generation:

```python
# In generate_coding_test_task:
try:
    course = Course.objects.get(id=course_id)
except Course.DoesNotExist:
    logger.warning("Course %s no longer exists - aborting task", course_id)
    return {"error": "Course not found", "success": False}
```

---

### Fix 4: Reduce Task Retries for Coding Tests

**Current:** `max_retries=5` with exponential backoff (10s, 20s, 40s, 60s, 60s)
**Problem:** Tasks retry for **~3 minutes** even when the course doesn't exist

**Better:** `max_retries=2` with shorter backoff (5s, 10s)

---

## Immediate Actions Required

1. **Purge stale tasks:**
   ```bash
   celery -A config.celery purge -f
   ```

2. **Regenerate Week 2 MCQ test and missing coding tests for SQL course**

3. **Fix Python course** - delete extra 4 weeks or recreate

4. **Apply the fixes above** to prevent recurrence
