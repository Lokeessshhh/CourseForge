# Course Generation Progress Bar - Implementation Guide

## Overview

A real-time progress bar popup that appears in the **top-right corner** immediately when course generation starts and stays visible until the course is fully generated.

## Features

### Visual Design
- **Brutalist/Neo-brutalist** aesthetic matching the app theme
- Hard shadows: `6px 6px 0px #000000`
- Thick borders: `3px solid var(--black)`
- Square corners (no border-radius)
- Animated progress bar with smooth transitions

### Functionality
- **Immediate appearance**: Shows as soon as generation starts
- **Real-time updates**: Polls every 2 seconds for progress
- **Persistent display**: Stays visible until generation completes
- **Auto-dismiss**: Disappears 3 seconds after completion
- **Expandable view**: Click '+' to see week-by-week breakdown
- **Error handling**: Shows error state if generation fails
- **Quick actions**: Dismiss button, expand/collapse, link to full progress view

### States
1. **Initializing**: Loading bar animation while fetching initial status
2. **Generating**: Progress bar with percentage, current stage, days completed
3. **Complete**: Green theme with checkmark, auto-dismiss after 3s
4. **Failed**: Red theme with error message

## Architecture

### Components Created

#### 1. GenerationProgressToast
**File:** `frontend/app/components/GenerationProgressToast/GenerationProgressToast.tsx`

Main toast component that:
- Polls `/api/courses/{courseId}/generation-progress/` every 2 seconds
- Displays progress with brutalist styling
- Handles expanding/collapsing week breakdown
- Auto-dismisses on completion

**Props:**
- `courseId: string` - Course being generated
- `onDismiss: () => void` - Dismiss callback
- `onGenerationComplete?: () => void` - Completion callback

#### 2. GenerationProgressProvider
**File:** `frontend/app/components/GenerationProgressProvider/GenerationProgressProvider.tsx`

Global state management for generation progress:
- Tracks currently generating course ID
- Provides start/complete/dismiss actions
- Accessible via `useGenerationProgress()` hook

**Context API:**
```typescript
{
  generatingCourseId: string | null;
  isGenerating: boolean;
  startGeneration: (courseId: string) => void;
  completeGeneration: () => void;
  dismissGeneration: () => void;
}
```

### Integration Points

#### Dashboard Layout
**File:** `frontend/app/dashboard/layout.tsx`

- Wraps dashboard with `GenerationProgressProvider`
- Renders `GenerationProgressToastWrapper` globally
- Uses `AnimatePresence` for smooth animations

```tsx
<GenerationProgressProvider>
  <DashboardContent>
    {children}
  </DashboardContent>
  <AnimatePresence>
    <GenerationProgressToastWrapper />
  </AnimatePresence>
</GenerationProgressProvider>
```

#### Generate Page
**File:** `frontend/app/dashboard/generate/page.tsx`

- Calls `startGeneration(courseId)` when generation starts
- Calls `completeGeneration()` when generation completes
- Auto-redirects to course page after completion

```tsx
const { startGeneration, completeGeneration } = useGenerationProgress();

// Start generation
if (result?.id) {
  setCourseId(result.id);
  startGeneration(result.id);
}

// Complete generation
useEffect(() => {
  if (isComplete && courseId) {
    completeGeneration();
    setTimeout(() => {
      router.push(`/dashboard/courses/${courseId}`);
    }, 2000);
  }
}, [isComplete, courseId]);
```

#### Dashboard Page
**File:** `frontend/app/dashboard/page.tsx`

- Detects generating courses on load
- Syncs with global provider state
- Removed old `GeneratingCourseWidget` usage

```tsx
const {
  generatingCourseId,
  isGenerating,
  startGeneration,
  completeGeneration,
  dismissGeneration,
} = useGenerationProgress();

// Detect generating course on load
const generatingCourse = courses.find(
  c => c.status === 'generating' || c.generation_status === 'generating'
);
if (generatingCourse) {
  startGeneration(generatingCourse.id);
}
```

## Backend API

### Endpoint
```
GET /api/courses/{course_id}/generation-progress/
```

### Response
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "topic": "Course Topic",
    "status": "generating",
    "progress": 45,
    "completed_days": 18,
    "total_days": 40,
    "current_stage": "Generating Week 4, Day 3...",
    "generation_status": "generating",
    "weeks": [
      {
        "week": 1,
        "status": "completed",
        "days": [
          {"day": 1, "title": "Intro", "status": "completed"},
          ...
        ]
      },
      ...
    ]
  }
}
```

### Status Values
- `"pending"` - Just created, not started
- `"generating"` - Currently generating
- `"ready"` - Generation complete
- `"failed"` - Generation failed

## CSS Styling

### Key Styles
**File:** `frontend/app/components/GenerationProgressToast/GenerationProgressToast.module.css`

```css
.toast {
  position: fixed;
  top: 20px;
  right: 20px;
  width: 380px;
  border: 3px solid var(--black);
  box-shadow: 6px 6px 0px var(--black);
  background: var(--white);
  z-index: 10000;
}

.toast.complete {
  border-color: #00aa00;
  box-shadow: 6px 6px 0px #00aa00;
}

.toast.failed {
  border-color: #ff4444;
  box-shadow: 6px 6px 0px #ff4444;
}

.progressFill {
  height: 100%;
  background: var(--black);
  transition: width 0.3s ease;
}
```

### Responsive
- Desktop: Fixed top-right (380px width)
- Mobile: Fixed bottom (full width minus margins)

## User Flow

1. **User clicks "Generate Course"**
   - API call to `/api/courses/generate/`
   - Returns course ID immediately
   - `startGeneration(courseId)` called
   - Toast appears in top-right

2. **Generation in Progress**
   - Toast polls every 2 seconds
   - Progress bar updates smoothly
   - Current stage displayed
   - Week breakdown available via '+' button
   - User can continue browsing dashboard

3. **Generation Complete**
   - Toast turns green with checkmark
   - "COURSE READY" displayed
   - Auto-redirect to course page (2s delay)
   - Toast auto-dismisses (3s delay)
   - `completeGeneration()` called

4. **Generation Failed**
   - Toast turns red
   - Error message displayed
   - User can dismiss manually
   - `dismissGeneration()` called

## Testing Checklist

- [ ] Toast appears immediately when generation starts
- [ ] Progress updates every 2 seconds
- [ ] Progress bar animates smoothly
- [ ] Expand/collapse week breakdown works
- [ ] Completion state shows correctly
- [ ] Auto-redirect works after completion
- [ ] Auto-dismiss works after 3 seconds
- [ ] Error state displays correctly
- [ ] Dismiss button works
- [ ] Multiple course generation handled correctly
- [ ] Responsive design works on mobile
- [ ] Animations are smooth (60fps)
- [ ] No console errors

## Files Modified/Created

### Created
1. `frontend/app/components/GenerationProgressToast/GenerationProgressToast.tsx`
2. `frontend/app/components/GenerationProgressToast/GenerationProgressToast.module.css`
3. `frontend/app/components/GenerationProgressProvider/GenerationProgressProvider.tsx`

### Modified
1. `frontend/app/dashboard/layout.tsx` - Added provider and toast wrapper
2. `frontend/app/dashboard/generate/page.tsx` - Integrated with provider
3. `frontend/app/dashboard/page.tsx` - Integrated with provider, removed old widget

## Future Enhancements

1. **WebSocket Support**: Replace polling with real-time WebSocket updates
2. **Notifications**: Browser push notifications on completion
3. **Email Notifications**: Send email when generation completes
4. **Retry Mechanism**: Allow retry if generation fails
5. **Estimated Time**: Show estimated time remaining
6. **Batch Generation**: Track multiple concurrent generations

## Troubleshooting

### Toast not appearing
- Check `GenerationProgressProvider` is in dashboard layout
- Verify `startGeneration()` is being called
- Check browser console for errors

### Progress not updating
- Verify API endpoint `/api/courses/{id}/generation-progress/` is working
- Check polling interval (should be 2000ms)
- Verify course has `generation_status = 'generating'`

### Auto-dismiss not working
- Check `onGenerationComplete` callback is wired up
- Verify `generation_status` changes to `'ready'`
- Check 3-second timeout is executing

### Styling issues
- Verify CSS variables are defined in `globals.css`
- Check z-index (should be 10000)
- Ensure brutalist theme is applied correctly
