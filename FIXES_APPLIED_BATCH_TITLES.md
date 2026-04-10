# Fixes Applied - Batch Title Generation & Course Generation Issues

## Date: 2026-04-09

---

## Issues Fixed

### 1. RAG SQL Parameter Mismatch (CRITICAL)
**Symptom**: `IndexError: list index out of range` in `retriever.py`
**Root Cause**: The SQL query had 7 placeholders (without course_id) or 9 (with course_id), but the params list only had 6/8 items. The first `%s` in `ROW_NUMBER() OVER (... <=> %s::vector)` was missing from params.

**Fix**: `backend/services/rag_pipeline/retriever.py`
- Rewrote params construction to explicitly match SQL placeholder order
- Without course_id: 7 params `[vec_str, vec_str, top_k, q_text, q_text, top_k, top_k]`
- With course_id: 9 params `[vec_str, course_id, vec_str, top_k, q_text, q_text, course_id, top_k, top_k]`

---

### 2. Incomplete JSON from LLM for Day Titles (MEDIUM)
**Symptom**: Only 3/5 day titles generated, Days 4-5 got generic fallback titles
**Root Cause**: LLM returned incomplete JSON array (only 3 items instead of 5)

**Fix**: `backend/services/course/generator.py`
- Improved prompt to show full 5-day JSON template explicitly
- Added "CRITICAL: You MUST return EXACTLY 5 days" instruction
- Shows complete structure for all 5 days in the prompt (not "... 4 more days")

---

### 3. Weekly Tests Never Ran (CRITICAL)
**Symptom**: Course stuck at "generating" status, no weekly test logs appeared
**Root Cause**: `.delay()` queued the task but Celery worker was busy with main task. The task was queued but never picked up because there was only 1 worker process.

**Fix**: `backend/apps/courses/tasks.py`
- Changed `generate_weekly_tests_for_course.delay(course_id)` → `.apply(args=[course_id])`
- `.apply()` runs synchronously in the current worker process
- Added try/except to catch weekly test failures without failing entire course
- Updated final log to show correct total tasks count (days + weekly tests)

---

### 4. NoneType Error in LLM Client (FIXED PREVIOUSLY)
**Symptom**: `'NoneType' object has no attribute 'strip'`
**Fix**: Added `None` check before `.strip()` call (already fixed in previous session)

---

## Files Modified

1. `backend/services/rag_pipeline/retriever.py` - SQL params fix
2. `backend/services/course/generator.py` - Improved day titles prompt
3. `backend/apps/courses/tasks.py` - Weekly tests sync execution + logging

---

## Testing Plan

1. Create a new 1-week course
2. Verify:
   - ✅ 5 day titles generated correctly (no generic fallbacks)
   - ✅ RAG retrieval succeeds (no SQL errors)
   - ✅ Weekly tests generate (MCQ + coding)
   - ✅ Course status set to "ready" after completion
   - ✅ Progress shows correct count (5 days + 2 tests = 7 tasks)

---

## Expected Log Output After Fix

```
[BLOCK 1] Generating themes and titles for weeks 1-1
[BLOCK 1] Week 1 theme saved: Week 1: <theme>
[BLOCK 1] Week 1 Day 1 title: <title>
[BLOCK 1] Week 1 Day 2 title: <title>
[BLOCK 1] Week 1 Day 3 title: <title>
[BLOCK 1] Week 1 Day 4 title: <title>
[BLOCK 1] Week 1 Day 5 title: <title>
[BLOCK 1] Running web search for weeks 1-1
[BLOCK 1] Running RAG retrieval
[BLOCK 1] Generating content for 5 days in parallel
[MCQ test generation logs...]
[Coding test generation logs...]
✅ LAST TASK (Week 1 Coding) - Course <id> marked as READY!
📝 Weekly test generation complete
✅ COURSE GENERATION COMPLETE
   Status: ready
   Progress: 7/7 tasks
   Total Days: 5
   Weekly Tests: 2
```
