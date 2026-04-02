# Generating Courses Widget - Dashboard

## Feature Added

A new widget has been added to the dashboard that shows **live progress** of courses currently being generated.

## What It Does

When a course is being generated in the background, a card appears on the dashboard showing:
- 🔴 **Live indicator** (pulsing green dot)
- **Course topic** being generated
- **Current stage** (e.g., "Generating Week 2, Day 3...")
- **Progress bar** (0-100%)
- **Days completed** / Total days
- **Status badge** (GENERATING)
- **View Progress** button (links to `/dashboard/generate?id=xxx`)
- **Dismiss** button (hides card but generation continues)

## Features

### Real-time Updates
- Polls backend every **3 seconds** for progress updates
- Progress bar animates smoothly as generation progresses
- Current stage text updates in real-time

### Multiple Courses
- Shows all courses currently being generated
- Grid layout adapts to number of courses
- Each course updates independently

### User Experience
- Can dismiss individual cards (generation continues in background)
- Card automatically disappears when generation completes
- Clicking "VIEW PROGRESS" takes user to detailed generation page

## Files Created/Modified

### New Files
1. **`frontend/app/components/GeneratingCourseCard/GeneratingCourseCard.tsx`**
   - React component for the generating course card
   - Handles progress display and animations
   - Dismiss functionality

2. **`frontend/app/components/GeneratingCourseCard/GeneratingCourseCard.module.css`**
   - Styles for the card
   - Pulsing animation for live indicator
   - Progress bar styling

### Modified Files
1. **`frontend/app/dashboard/page.tsx`**
   - Added `generatingCourses` state
   - Added fetching logic for generating courses
   - Added polling mechanism (3 second interval)
   - Added dismiss handler
   - Added widget to UI

2. **`frontend/app/dashboard/page.module.css`**
   - Added `.generatingCoursesWidget` styles
   - Added `.generatingCoursesGrid` grid layout

## How It Works

### 1. Course Creation
```
User creates course → Backend sets status="generating" → 
Celery task starts → Dashboard polls every 3s
```

### 2. Progress Polling
```javascript
// Every 3 seconds:
GET /api/courses/{id}/generation-progress/
→ Returns: { progress, completed_days, total_days, current_stage, ... }
→ Updates progress bar and stage text
```

### 3. Auto-dismiss
When `generation_status === 'ready'` or `'failed'`, card is automatically removed.

### 4. Manual Dismiss
User can click × to hide card (generation continues in background).

## Backend Endpoint

Uses existing endpoint:
```
GET /api/courses/{id}/generation-progress/
```

Response format:
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "topic": "Python Programming",
    "progress": 45,
    "completed_days": 9,
    "total_days": 20,
    "current_stage": "Generating Week 2, Day 4...",
    "generation_status": "generating"
  }
}
```

## UI Flow

```
Dashboard Page
├── Hero Strip (Greeting + XP)
├── Stats Grid
├── 🔄 COURSES BEING GENERATED ← NEW WIDGET
│   ├── Generating Course Card 1
│   ├── Generating Course Card 2
│   └── ...
├── AI Personal Insights
├── Study Activity Chart
├── Course Progress Chart
└── Continue Where You Left Off
```

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
   - Go to Dashboard
   - Click "Create Course" button
   - Fill in topic, duration, skill level
   - Click "Create Course"

4. **Check Dashboard:**
   - New widget appears: "🔄 COURSES BEING GENERATED"
   - Card shows course being generated
   - Progress bar updates every 3 seconds
   - Current stage text updates
   - Click "VIEW PROGRESS" → goes to detailed progress page
   - Click "×" → dismisses card (generation continues)

5. **Wait for Completion:**
   - When generation completes, card automatically disappears
   - Course appears in "CONTINUE WHERE YOU LEFT OFF" section

## Component Structure

```
GeneratingCourseCard
├── Header
│   ├── Live Indicator (pulsing dot)
│   ├── Title: "GENERATING COURSE"
│   └── Dismiss Button (×)
├── Content
│   ├── Course Topic
│   ├── Current Stage Badge
│   ├── Progress Container
│   │   ├── Progress Label
│   │   ├── Progress Bar (animated)
│   │   └── Progress Details
│   └── Footer
│       └── View Progress Button
```

## Styling

- **Border:** 3px solid black with 8px shadow (retro style)
- **Live Indicator:** Pulsing green dot (CSS animation)
- **Progress Bar:** Black fill on gray background
- **Button:** Black background, white text
- **Grid:** Responsive (auto-fill, minmax 350px)

## Animations

- **Pulsing:** Live indicator pulses every 1.5s
- **Progress Bar:** Smooth transition (0.3s ease)
- **Card Entry:** Fade in + slide up (0.4s)
- **Card Exit:** Fade out + slide down (AnimatePresence)

## Accessibility

- Dismiss button has `aria-label`
- Progress percentage shown as text (not just visual bar)
- Semantic HTML structure

---

**Status:** ✅ Complete
**Date:** 2026-03-28
**Test Status:** Ready for testing
