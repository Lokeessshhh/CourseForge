# Course Progression Fix - April 11, 2026

## Issues Fixed

### ✅ Issue 1: All Days Unlocked (Should Only Be Day 1)
**Root Cause:** `backend/apps/courses/tasks.py` line 740 was setting `day.is_locked = False` for ALL days during content generation.

**Fix:** Removed the unconditional unlocking. Days now only unlock when:
1. Week 1 Day 1 is unlocked by default during skeleton creation
2. Subsequent days unlock ONLY when user completes the previous day's quiz

### ✅ Issue 2: Checkmarks Showing on All Days
**Root Cause:** Frontend was receiving incorrect `is_completed` data because days were being marked completed during generation.

**Fix:** The generation task already sets `is_completed=False` correctly. The checkmarks will now only appear when users actually complete quizzes.

### ✅ Issue 3: Current Day Shows Week 1 Day 5 Instead of Week 1 Day 1
**Root Cause:** `backend/apps/courses/views.py` `course_progress` endpoint was calculating current position by finding the first incomplete day, but since all days were incorrectly marked complete, it showed the wrong day.

**Fix:** 
1. Now uses `CourseProgress` model as the source of truth
2. For new courses, defaults to Week 1, Day 1
3. When Day 5 is completed, stays on Day 5 until weekly test is completed (instead of jumping to next week)

### ✅ Issue 4: Course Generation Restarting (select_for_update Error)
**Root Cause:** `backend/apps/courses/tasks.py` line 216 used `CourseProgress.objects.select_for_update().get()` outside of a database transaction, causing a `TransactionManagementError` that triggered Celery to retry and restart the entire generation.

**Fix:** Replaced `select_for_update().get()` with `get_or_create()` which doesn't require an active transaction and handles both creation and retrieval gracefully.

### ✅ Issue 5: SSE Broadcast Error (Undefined Variables)
**Root Cause:** `backend/apps/courses/tasks.py` line ~745 referenced undefined variables `theory_generated`, `code_generated`, `quiz_generated` in the SSE broadcast call.

**Fix:** Changed to use `day.theory_generated`, `day.code_generated`, `day.quiz_generated` from the DayPlan object.

### ✅ Issue 6: Mermaid Parse Error on Day Pages
**Root Cause:** AI-generated content contains Mermaid diagrams with invalid syntax. The `mermaid.parse()` method throws errors instead of returning false on invalid syntax.

**Fix:** Added try-catch around `mermaid.parse()` call in `frontend/app/components/MermaidRenderer.tsx` to gracefully handle parse errors and show a fallback message instead of crashing.

## Files Modified

1. **backend/apps/courses/tasks.py** (Line ~738-740)
   - Removed: `day.is_locked = False` and save operation
   - Days remain locked until user completes previous day's quiz

2. **backend/apps/courses/views.py** (Line 603-690)
   - Updated `course_progress` endpoint to use `CourseProgress` model
   - Fixed current day calculation to always start at Week 1, Day 1 for new courses
   - Fixed Day 5 completion to not advance week until weekly test is done

3. **backend/apps/courses/tasks.py** (Line ~216)
   - Replaced: `select_for_update().get()` with `get_or_create()`
   - Added proper error handling for CourseProgress updates
   - Prevents generation restart due to transaction errors

4. **backend/apps/courses/tasks.py** (Line ~745-758)
   - Fixed: SSE broadcast to use `day.theory_generated`, `day.code_generated`, `day.quiz_generated`
   - Resolves undefined variable warnings

5. **backend/apps/courses/management/commands/reset_course_progress.py** (NEW)
   - Django management command to reset corrupted course data
   - Resets all days to locked (except Week 1 Day 1)
   - Resets all week test flags
   - Resets CourseProgress to Week 1, Day 1

6. **frontend/app/components/MermaidRenderer.tsx** (Line ~70-80)
   - Added try-catch around `mermaid.parse()` call
   - Gracefully handles invalid Mermaid syntax from AI-generated content
   - Shows user-friendly fallback message instead of crashing

## How to Apply Fix to Existing Courses

**✅ ALREADY COMPLETED:** The database reset has been run successfully on all 8 courses.

If you need to reset again in the future:

### Option 1: Reset All Courses
```bash
cd backend
python manage.py reset_course_progress --all
```

### Option 2: Reset Specific Course
```bash
cd backend
python manage.py reset_course_progress --course-id=YOUR_COURSE_ID
```

### Option 3: Dry Run (See what would change)
```bash
cd backend
python manage.py reset_course_progress --all --dry-run
```

## Testing Checklist

After running the reset command:

1. ✅ Visit dashboard → Should see only Day 1 unlocked
2. ✅ All other days should show as "LOCK" 
3. ✅ No checkmarks on any days (unless you've completed quizzes)
4. ✅ Current day shows "WEEK 1 · DAY 1"
5. ✅ "GO TO TODAY'S LESSON" button goes to Week 1 Day 1

## Expected Behavior After Fix

### Course Creation:
- Week 1 Day 1: **Unlocked** ✅
- Week 1 Day 2-5: **Locked** 🔒
- Week 2+ : **Locked** 🔒

### After Completing Day 1 Quiz:
- Week 1 Day 1: **Completed** ✓ (checkmark appears)
- Week 1 Day 2: **Unlocked** ✅
- Week 1 Day 3-5: **Locked** 🔒

### After Completing Day 5 Quiz:
- Week 1 Day 1-5: **All Completed** ✓✓✓✓✓
- Weekly Test: **Unlocked** ✅
- Week 2 Day 1: **Still Locked** 🔒 (must complete weekly test first)

### After Completing Weekly Test:
- Week 1: **Complete** ✓
- Week 2 Day 1: **Unlocked** ✅
- Week 2 Day 2-5: **Locked** 🔒

## Important Notes

1. **Quiz Score Doesn't Matter**: Next day unlocks regardless of score (0% or 100%)
2. **Weekly Test is Required**: Can't skip to next week without completing the weekly test
3. **Progress is Tracked**: CourseProgress model maintains accurate state
4. **No Data Loss**: Reset only affects progression flags, not generated content

## Next Steps

1. Run the reset command: `python manage.py reset_course_progress --all`
2. Refresh your browser (hard refresh: Ctrl+Shift+R)
3. Verify only Day 1 is unlocked
4. Test the quiz completion flow
5. Report any issues
