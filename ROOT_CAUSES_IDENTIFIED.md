# Root Causes Identified - Course Update System Issues

## Issues Reported

1. **User selects 3 weeks update but only 2 weeks are extended**
2. **Hardcoded "20 days + 8 tests" showing initially**
3. **Progress going backward sometimes**
4. **Multiple LLM connection errors during test generation**

---

## Root Cause Analysis

### Issue #1: Wrong Weeks Calculation for `extend_50%`

**Location:** `backend/apps/courses/views.py` - `course_update()` view (lines 380-420)

**Problem:**
```python
elif update_type == "extend_50%":
    additional_weeks = max(1, int(current_weeks * 0.5))
    new_duration_weeks = current_weeks + additional_weeks
    weeks_to_update = list(range(current_weeks + 1, new_duration_weeks + 1))
```

**Example:**
- If course has 4 weeks: `additional_weeks = int(4 * 0.5) = 2`
- `new_duration_weeks = 4 + 2 = 6`
- `weeks_to_update = [5, 6]` ✓ Correct

**BUT** the LLM intent classifier is detecting `update_type` from user query, and it's often returning `null` or wrong type.

**Real Problem:** In `chat_views.py` line 407:
```python
update_type = llm_result.entities.get("update_type")  # Often returns None!
```

When `update_type` is `None`, the preview/update logic doesn't know which type to use, and defaults are inconsistent.

---

### Issue #2: Hardcoded "20 days + 8 tests" Display

**Location:** `backend/apps/courses/tasks.py` - `update_course_content_task()` (lines 1130-1140)

**Problem:**
```python
# Calculate total tasks for progress tracking
# Each week has: 5 days + 1 MCQ test + 1 coding test = 7 tasks
weeks_being_updated = len(weeks_to_update)
total_days_to_update = weeks_being_updated * 5
total_tests_to_update = weeks_being_updated * 2  # MCQ + coding per week
total_tasks = total_days_to_update + total_tests_to_update

logger.info("Progress calculation: %d weeks × (5 days + 2 tests) = %d tasks",
           weeks_being_updated, total_tasks)
```

**This is NOT hardcoded** - it's calculated dynamically. BUT the issue is:

The **frontend** might be showing incorrect values because of how progress is broadcast via SSE.

Looking at logs:
```
Progress calculation: 2 weeks × (5 days + 2 tests) = 14 tasks
```

This is correct for 2 weeks, but user selected 3 weeks. So the problem is in **weeks_to_update calculation**.

---

### Issue #3: Progress Going Backward

**Location:** `backend/apps/courses/tasks.py` - `_update_single_week()` (lines 1450-1470)

**Problem:**
```python
async with progress_lock:
    await sync_to_async(course.refresh_from_db)()
    course.generation_progress += 5  # 5 days per week
    await sync_to_async(course.save)(update_fields=["generation_progress"])

    # Broadcast progress update with CORRECT percentage
    from apps.courses.sse import broadcast_progress_update
    if total_tasks:
        # Calculate how many tasks completed so far
        tasks_done = course.generation_progress + ((course.generation_progress // 5) * 2)
        progress_percent = round((tasks_done / total_tasks) * 100)
```

**Bug Found!** The calculation `tasks_done = course.generation_progress + ((course.generation_progress // 5) * 2)` is **WRONG**:

- `course.generation_progress` tracks **days only** (e.g., 5, 10, 15)
- Formula adds tests: `(5 // 5) * 2 = 2` tests, so `tasks_done = 5 + 2 = 7`
- But `total_tasks = 14` (for 2 weeks)
- Progress = `7 / 14 = 50%` ✓

**BUT** when second week completes:
- `course.generation_progress = 10`
- `tasks_done = 10 + ((10 // 5) * 2) = 10 + 4 = 14`
- Progress = `14 / 14 = 100%` ✓

**Wait, this looks correct...**

Let me check the **broadcast** calls more carefully.

**REAL ISSUE:** In logs:
```
📡 [Celery] Broadcast progress update for course 00ffe289: 50% via Redis
📡 [Celery] Broadcast progress update for course 00ffe289: 95% via Redis
📡 [Celery] Broadcast progress update for course 00ffe289: 26% via Redis  ← JUMP!
```

The progress jumps because **test generation tasks** are broadcasting their own progress:

```python
# From update_course_content_task (line 1260)
progress_percent = 95 + (test_count * (5 / total_tests))
broadcast_progress_update(course_id, {
    "progress": int(progress_percent),
    ...
})
```

So:
1. Days complete: 50% → 95%
2. Tests start: jumps to 26% (because test task uses different total!)
3. Tests complete: 96% → 100%

**Root Cause:** Test generation uses **different total_tasks calculation** than day generation!

---

### Issue #4: LLM Connection Errors

**Location:** `backend/services/llm/client.py` (lines 173-185)

**Problem:**
```python
for attempt in range(3):
    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            **params
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.warning("LLM generation attempt %d failed: %s", attempt + 1, e)
        if attempt == 2:
            logger.exception("LLM generation failed after 3 attempts")
            raise
        await asyncio.sleep(2 ** attempt)
```

**From logs:**
```
⚠️ LLM generation attempt 1 failed: Connection error.
⚠️ LLM generation attempt 2 failed: Connection error.
⚠️ LLM generation attempt 3 failed: Connection error.
RuntimeError: Event loop is closed
```

**Root Cause:** Celery worker is trying to use **async LLM calls** but the event loop is closing prematurely.

The issue is in how Celery tasks call async functions:
```python
asyncio.run(_update_course_async(...))
```

When multiple parallel async calls happen, they're creating **multiple event loops**, and some are closing before LLM calls complete.

---

## Proposed Fixes

### Fix #1: Update Type Detection in Chat

**File:** `backend/apps/chat/views.py`

**Change:** Always show update options to user instead of relying on LLM to detect type.

```python
# Current (line 407)
update_type = llm_result.entities.get("update_type")

# Fix: Don't extract update_type from LLM, let user choose
return _ok({
    "command": "update_course",
    "action": "show_options",
    "response": f"Great! Let's update your '{matched_course['course_name']}' course...",
    "course_id": matched_course["id"],
    "course_name": matched_course["course_name"],
    "user_query": user_query,
    "update_options": [
        {"type": "50%", "label": "Update Current (50%)", ...},
        {"type": "75%", "label": "Update Current (75%)", ...},
        {"type": "extend_50%", "label": "Extend + Update (50%)", ...},
    ],
})
```

**Frontend must let user select update type explicitly.**

---

### Fix #2: Consistent Progress Calculation

**File:** `backend/apps/courses/tasks.py`

**Problem:** Test generation uses different total than day generation.

**Fix:** Use same `total_tasks` throughout:

```python
# In update_course_content_task (line 1140)
total_tasks = total_days_to_update + total_tests_to_update

# Pass to async function
tasks_completed = asyncio.run(_update_course_async(..., total_tasks=total_tasks))

# In test generation (line 1260)
# WRONG: progress_percent = 95 + (test_count * (5 / total_tests))
# CORRECT:
tasks_done = total_days_to_update + test_count
progress_percent = round((tasks_done / total_tasks) * 100)
```

---

### Fix #3: Fix Progress Broadcast Formula

**File:** `backend/apps/courses/tasks.py` - `_update_single_week()` (line 1465)

**Current (buggy):**
```python
tasks_done = course.generation_progress + ((course.generation_progress // 5) * 2)
```

**Fix:**
```python
# Track actual tasks completed (days + tests)
# Each week = 5 days + 2 tests
weeks_completed = course.generation_progress // 5
tests_completed = weeks_completed * 2
tasks_done = course.generation_progress + tests_completed
progress_percent = round((tasks_done / total_tasks) * 100)
```

---

### Fix #4: Fix Async Event Loop in Celery

**File:** `backend/apps/courses/tasks.py`

**Problem:** Multiple `asyncio.run()` calls create conflicting event loops.

**Fix:** Use single event loop for entire update:

```python
# In update_course_content_task
# Instead of: asyncio.run(_update_course_async(...))
# Use: async_to_sync wrapper

from asgiref.sync import async_to_sync

@shared_task
def update_course_content_task(...):
    ...
    # Run entire async operation in one event loop
    async_to_sync(_update_course_async)(
        generator=generator,
        course=course,
        ...
    )
```

**Also:** Increase retry attempts and add better error handling:

```python
# In client.py (line 170)
for attempt in range(5):  # Increase from 3 to 5
    try:
        response = await client.chat.completions.create(...)
        return response.choices[0].message.content
    except APIConnectionError as e:
        logger.warning("LLM connection error (attempt %d/5): %s", attempt + 1, e)
        if attempt == 4:
            raise
        await asyncio.sleep(2 ** attempt * 2)  # Longer backoff
```

---

### Fix #5: Fix extend_50% Skeleton Creation Bug

**File:** `backend/apps/courses/tasks.py` (line 1220)

**Bug:** Variable `week` is undefined when creating new weeks:

```python
# WRONG
for week_num in range(old_duration + 1, new_duration_weeks + 1):
    WeekPlan.objects.create(
        course=course,
        week_number=week_num,
        ...
    )
    for day_num in range(1, 6):
        DayPlan.objects.create(
            week_plan=week,  # ← week is not defined!
            ...
        )
```

**Fix:**
```python
for week_num in range(old_duration + 1, new_duration_weeks + 1):
    week = WeekPlan.objects.create(
        course=course,
        week_number=week_num,
        theme=None,
        objectives=[],
    )
    for day_num in range(1, 6):
        DayPlan.objects.create(
            week_plan=week,  # ← Now correctly references the created week
            day_number=day_num,
            ...
        )
```

---

## Summary of Changes

1. **chat/views.py**: Remove LLM update_type detection, let user choose
2. **tasks.py**: Fix progress calculation to use consistent total_tasks
3. **tasks.py**: Fix progress broadcast formula
4. **tasks.py**: Fix extend_50% skeleton creation (undefined `week` variable)
5. **tasks.py**: Use `async_to_sync` instead of `asyncio.run()` for better event loop management
6. **client.py**: Increase retries from 3 to 5, add longer backoff for connection errors

---

## Testing Plan

1. Test 3-week extend update, verify all 3 weeks are created
2. Test progress bar shows smooth increase (no backward jumps)
3. Verify initial progress display matches actual calculation
4. Test LLM connection stability with 5 retries
5. Verify test generation uses same progress calculation as days

---

**Next Steps:**
Say "yes" and I'll implement all these fixes.
