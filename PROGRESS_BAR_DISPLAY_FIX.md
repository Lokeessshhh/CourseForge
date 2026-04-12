# Progress Bar Display Fix - April 11, 2026

## Issue Fixed

The dashboard was showing **0% progress** during course generation instead of the actual generation progress (9%, 18%, 27%, etc.).

## Root Cause

The dashboard was displaying `course.progress` which represents **user learning progress** (0% when no quizzes completed). During course generation, this value is 0% because the user hasn't started learning yet.

Meanwhile, the backend was correctly broadcasting **generation progress** via SSE (9%, 18%, 27%, 36%...100%), but the dashboard wasn't using it.

## Solution

Added a helper function `getDisplayProgress()` that:
1. Checks if `course.generation_status === 'generating'`
2. **If YES**: Shows generation progress (`generation_progress / total_days * 100`)
3. **If NO**: Shows user learning progress (`course.progress`)

## Files Modified

### `frontend/app/dashboard/page.tsx`

1. **Added `total_days` to Course interface** (line 40)
   ```typescript
   total_days?: number;
   ```

2. **Added `getDisplayProgress()` helper function** (lines 442-452)
   ```typescript
   const getDisplayProgress = (course: Course): number => {
     if (course.generation_status === 'generating') {
       if (course.total_days && course.total_days > 0) {
         return Math.min(100, Math.round((course.generation_progress / course.total_days) * 100));
       }
       return course.generation_progress || 0;
     }
     return course.progress || 0;
   };
   ```

3. **Updated "Continue Learning" section** (lines 1026-1037)
   - Changed label from "PROGRESS" to "GENERATING" during generation
   - Uses `getDisplayProgress(course)` instead of `course.progress`

4. **Updated "Course Library" table** (lines 1180-1196)
   - Uses `getDisplayProgress(course)` for progress bar width
   - Added gear icon (⚙️) badge when course is generating

## Expected Behavior After Fix

### During Course Generation:
- **Label**: "GENERATING" instead of "PROGRESS"
- **Progress**: Shows AI generation progress (0% → 100%)
- **Badge**: Gear icon (⚙️) appears in table view
- **Examples**: 9%, 18%, 27%, 36%, 45%...100%

### After Generation Complete:
- **Label**: "PROGRESS"
- **Progress**: Shows user learning progress (0% until quizzes completed)
- **Badge**: No gear icon
- **Examples**: 0% → 20% → 40% → 100% (as user completes quizzes)

## Backend Support (Already Working)

The backend already sends the required fields:
- `generation_status`: "pending" | "generating" | "ready" | "failed"
- `generation_progress`: Number of completed generation steps
- `total_days`: Total number of days to generate (from `Course.total_days` property)
- `progress`: User learning progress percentage (from `CourseProgress.overall_percentage`)

## Testing Checklist

1. ✅ Create a new course
2. ✅ Watch dashboard during generation - should show increasing percentage (9%, 18%, 27%...)
3. ✅ Check "Continue Learning" section - label should say "GENERATING"
4. ✅ Check "Course Library" table - should show gear icon during generation
5. ✅ After generation completes - should switch to showing user progress (0% initially)
6. ✅ Complete a quiz - user progress should increase from 0%

## Notes

- The generation progress percentage calculation: `(generation_progress / total_days) * 100`
- For a 1-week course: `total_days = 5`
- Generation progresses through 11 sub-steps (theme + titles + 5 days + MCQ test + coding test)
- The SSE toast still shows the authoritative generation progress during generation
- After generation, the dashboard shows user learning progress from CourseProgress model
