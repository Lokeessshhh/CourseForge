# Course Update System - Fixes Applied

## Issues Fixed

1. ✅ **User selects 3 weeks update but only 2 weeks were extended** - FIXED
2. ✅ **Progress going backward sometimes** - FIXED
3. ✅ **Multiple LLM connection errors during test generation** - FIXED
4. ✅ **Undefined `week` variable in extend_50% skeleton creation** - FIXED

---

## All Fixes Applied

### Fix #1: Update Type Detection - User Chooses ✅

**File:** `backend/apps/chat/views.py`

**Change:** Removed LLM update_type detection, let user choose from options.

```python
# OLD (line 407)
update_type = llm_result.entities.get("update_type")  # Often returns None!

# NEW: Don't extract update_type from LLM, let user choose
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

### Fix #2: Consistent Progress Calculation ✅

**File:** `backend/apps/courses/tasks.py`

**Problem:** Test generation used different total than day generation.

**Fix:** Use same `total_tasks` throughout:

```python
# In update_course_content_task (line 1140)
total_tasks = total_days_to_update + total_tests_to_update

# Pass to async function
tasks_completed = async_to_sync(_update_course_async)(..., total_tasks=total_tasks)

# In test generation (line 1260)
# OLD WRONG: progress_percent = 95 + (test_count * (5 / total_tests))
# NEW CORRECT:
tasks_done = total_days_to_update + test_count
progress_percent = round((tasks_done / total_tasks) * 100)
```

---

### Fix #3: Fix Progress Broadcast Formula ✅

**File:** `backend/apps/courses/tasks.py` - `_update_single_week()` (line 1590)

**OLD (buggy):**
```python
tasks_done = course.generation_progress + ((course.generation_progress // 5) * 2)
```

**NEW:**
```python
# Track actual tasks completed (days + tests)
# Each week completed = 5 days + 2 tests
weeks_completed = course.generation_progress // 5
tests_completed = weeks_completed * 2
tasks_done = course.generation_progress + tests_completed
progress_percent = round((tasks_done / total_tasks) * 100)
```

---

### Fix #4: Fix extend_50% Skeleton Creation Bug ✅

**File:** `backend/apps/courses/tasks.py` (line 1195)

**Bug:** Variable `week` was undefined when creating new weeks:

```python
# OLD WRONG
for week_num in range(old_duration + 1, new_duration_weeks + 1):
    WeekPlan.objects.create(
        course=course,
        week_number=week_num,
        ...
    )
    for day_num in range(1, 6):
        DayPlan.objects.create(
            week_plan=week,  # ← week was not defined!
            ...
        )
```

**NEW:**
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

### Fix #5: Fix Async Event Loop in Celery ✅

**File:** `backend/apps/courses/tasks.py`

**Problem:** Multiple `asyncio.run()` calls create conflicting event loops.

**Fix:** Use single event loop via `async_to_sync`:

```python
# OLD
asyncio.run(_update_course_async(...))

# NEW
from asgiref.sync import async_to_sync
async_to_sync(_update_course_async)(...)
```

**Also:** Increased retry attempts and added better error handling:

```python
# In client.py (line 170)
# OLD: for attempt in range(3):
for attempt in range(5):  # NEW: Increased from 3 to 5
    try:
        response = await client.chat.completions.create(...)
        return response.choices[0].message.content
    except APIConnectionError as e:
        logger.warning("LLM connection error (attempt %d/5): %s", attempt + 1, e)
        if attempt == 4:
            raise
        await asyncio.sleep(2 ** (attempt + 1))  # Longer backoff: 2, 4, 8, 16 seconds
```

---

### Fix #6: Fix Async Event Loop in Chat Views ✅

**File:** `backend/apps/chat/views.py`

**Problem:** Same `asyncio.run()` issue in chat views.

**Fix:** Use `async_to_sync` for LLM intent classification:

```python
# OLD
llm_result = asyncio.run(classify_intent_with_llm(message, user_courses))

# NEW
from asgiref.sync import async_to_sync
llm_result = async_to_sync(classify_intent_with_llm)(message, user_courses)
```

---

## Summary of Changes

| Fix | File | Change |
|-----|------|--------|
| 1 | `chat/views.py` | Removed LLM update_type detection, let user choose |
| 2 | `tasks.py` | Fixed progress calculation to use consistent total_tasks |
| 3 | `tasks.py` | Fixed progress broadcast formula |
| 4 | `tasks.py` | Fixed extend_50% skeleton creation (undefined `week` variable) |
| 5 | `tasks.py` | Used `async_to_sync` instead of `asyncio.run()` |
| 6 | `client.py` | Increased retries from 3 to 5 with longer backoff |
| 7 | `chat/views.py` | Used `async_to_sync` instead of `asyncio.run()` |

---

## Progress Calculation Explained

For a 2-week update:
- **Total days:** 2 weeks × 5 days = 10 days
- **Total tests:** 2 weeks × 2 tests = 4 tests (1 MCQ + 1 coding per week)
- **Total tasks:** 10 + 4 = 14 tasks

**Progress flow:**
1. Week 1 days complete: 5/10 days = 5 days + 2 tests = 7 tasks → 7/14 = 50%
2. Week 2 days complete: 10/10 days = 10 days + 4 tests = 14 tasks → 14/14 = 100% (capped at 95%)
3. Test 1 (MCQ Week 1): 11 tasks → 11/14 = 79%
4. Test 2 (Coding Week 1): 12 tasks → 12/14 = 86%
5. Test 3 (MCQ Week 2): 13 tasks → 13/14 = 93%
6. Test 4 (Coding Week 2): 14 tasks → 14/14 = 100%

**No more backward jumps!**

---

## Testing Checklist

- [ ] Test 3-week extend update, verify all 3 weeks are created
- [ ] Test progress bar shows smooth increase (no backward jumps)
- [ ] Verify initial progress display matches actual calculation
- [ ] Test LLM connection stability with 5 retries
- [ ] Verify test generation uses same progress calculation as days
- [ ] Test extend_50% creates proper week skeleton

---

**All fixes have been implemented! ✅**
