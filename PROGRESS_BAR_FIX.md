# Progress Bar Fix - Course Generation

## Issue
When a course was being generated, the progress bar and week/day grid were not showing on the generation page (`/dashboard/generate`).

## Root Causes

### 1. Backend Endpoint Format Mismatch
The frontend was calling `/api/courses/{id}/generation-progress/` but the endpoint wasn't returning the `weeks` array structure needed to render the visual grid.

### 2. Frontend Hook Not Using Weeks Data
The `useCourseStatus` hook in `useCourses.ts` was setting `weeks: []` instead of using the weeks data from the backend response.

## Fixes Applied

### Backend (`apps/courses/views_generation_progress.py`)

**Updated the endpoint to return:**
- ✅ `weeks` array with week-by-week structure
- ✅ Each week contains `days` array with status (`pending` | `generating` | `completed`)
- ✅ `current_stage` with human-readable progress message
- ✅ `progress` percentage (0-100)
- ✅ `completed_days` and `total_days` counts

**Response format:**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "topic": "Python Programming",
    "status": "generating",
    "progress": 25,
    "completed_days": 5,
    "total_days": 20,
    "current_stage": "Generating Week 2, Day 1...",
    "generation_status": "generating",
    "weeks": [
      {
        "week": 1,
        "status": "completed",
        "days": [
          { "day": 1, "title": "Introduction", "status": "completed" },
          { "day": 2, "title": "Variables", "status": "completed" },
          ...
        ]
      },
      {
        "week": 2,
        "status": "generating",
        "days": [
          { "day": 1, "title": "", "status": "generating" },
          { "day": 2, "title": "", "status": "pending" },
          ...
        ]
      }
    ]
  }
}
```

### Frontend (`app/hooks/api/useCourses.ts`)

**Fixed the `useCourseStatus` hook to:**
- ✅ Use `weeks: data.data?.weeks || []` instead of `weeks: []`
- ✅ Properly map all fields from backend response
- ✅ Updated both initial fetch and refetch functions

## Files Changed

| File | Change |
|------|--------|
| `backend/apps/courses/views_generation_progress.py` | Updated to return weeks array with day status |
| `frontend/app/hooks/api/useCourses.ts` | Fixed to use weeks data from backend |

## How It Works Now

### 1. Course Creation
- User creates a course via `/dashboard/generate`
- Backend creates course with `generation_status="pending"` and `generation_progress=0`
- Celery task starts in background

### 2. Progress Polling
- Frontend polls `/api/courses/{id}/generation-progress/` every 3 seconds
- Backend returns current progress with week/day structure
- Frontend updates progress bar and day cells in real-time

### 3. Visual Feedback
- **Progress Bar**: Shows percentage (0-100%)
- **Current Stage**: Shows "Generating Week X, Day Y..."
- **Week Grid**: Shows 4 columns (weeks) with 5 rows (days)
- **Day Cells**: 
  - ⬛ Black (completed) - `theory_generated` and `code_generated` are true
  - 🟡 Animated (generating) - Has title but not fully generated
  - ⬜ White (pending) - No content yet

### 4. Completion
- When all days are generated, status becomes "ready"
- Progress bar shows 100%
- "START LEARNING" button appears

## Testing

1. **Start Backend:**
   ```bash
   cd backend
   python manage.py rundev
   ```

2. **Start Frontend:**
   ```bash
   cd frontend
   npm run dev
   ```

3. **Create a Course:**
   - Go to `/dashboard`
   - Click "Create Course"
   - Enter topic, duration, skill level
   - Click "Create Course"

4. **Verify Progress Page:**
   - Should redirect to `/dashboard/generate?id=xxx`
   - Should show progress bar animating
   - Should show week grid with day cells
   - First day should show "generating" animation
   - Other days should show locked icon 🔒

5. **Watch Progress:**
   - Progress bar should update as days are generated
   - Day cells should turn black when completed
   - Current stage text should update
   - After all days complete, "COURSE READY" message appears

## Celery Task Updates

The Celery task `generate_course_content_task` already updates:
- `course.generation_progress` after each day is generated
- `course.generation_status` to "generating", "ready", or "failed"

No changes needed to the task itself.

## API Endpoint

**URL:** `GET /api/courses/{id}/generation-progress/`

**Authentication:** Required (Clerk JWT)

**Response Codes:**
- `200` - Success with progress data
- `404` - Course not found
- `401` - Unauthorized

## Example Response

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "topic": "Python Programming",
    "status": "generating",
    "progress": 45,
    "completed_days": 9,
    "total_days": 20,
    "current_stage": "Generating Week 2, Day 4...",
    "generation_status": "generating",
    "weeks": [
      {
        "week": 1,
        "status": "completed",
        "days": [
          {"day": 1, "title": "Introduction to Python", "status": "completed"},
          {"day": 2, "title": "Variables and Data Types", "status": "completed"},
          {"day": 3, "title": "Control Flow", "status": "completed"},
          {"day": 4, "title": "Functions", "status": "completed"},
          {"day": 5, "title": "Modules and Packages", "status": "completed"}
        ]
      },
      {
        "week": 2,
        "status": "generating",
        "days": [
          {"day": 1, "title": "Object-Oriented Programming", "status": "completed"},
          {"day": 2, "title": "Inheritance and Polymorphism", "status": "completed"},
          {"day": 3, "title": "Error Handling", "status": "completed"},
          {"day": 4, "title": "", "status": "generating"},
          {"day": 5, "title": "", "status": "pending"}
        ]
      },
      {
        "week": 3,
        "status": "pending",
        "days": [
          {"day": 1, "title": "", "status": "pending"},
          {"day": 2, "title": "", "status": "pending"},
          {"day": 3, "title": "", "status": "pending"},
          {"day": 4, "title": "", "status": "pending"},
          {"day": 5, "title": "", "status": "pending"}
        ]
      }
    ]
  }
}
```

---

**Status:** ✅ Fixed
**Date:** 2026-03-28
