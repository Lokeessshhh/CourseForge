# Progress Page Debug Guide

## Issue: Concept Mastery and Quiz History sections not visible

### What Was Fixed:

1. **Added Empty State Messages**
   - Concept Mastery now shows message when no concepts exist
   - Quiz History already had empty state message
   - Both messages guide users on how to get data

2. **Added Minimum Heights**
   - `.conceptList` now has `min-height: 100px`
   - `.quizTable` now has `min-height: 150px`
   - Ensures containers are visible even when empty

3. **Improved Empty State Styling**
   - Added `.emptyConceptMessage` class
   - All empty states now have consistent dashed border styling

---

## How to Test:

### 1. **Check Concept Mastery Section:**

**If you HAVE concept data:**
- Navigate to `/dashboard/progress`
- Scroll to "CONCEPT MASTERY" section
- You should see concept rows with:
  - Concept name
  - Progress bar (black fill)
  - Percentage
  - "PRACTICED Xx" count

**If you DON'T have concept data:**
- You should see a dashed box with message:
  > "No concept mastery data yet. Complete quizzes to track your progress!"

**To generate concept data:**
- Complete some lessons with quizzes
- The system auto-creates `UserKnowledgeState` records
- Or check backend: `UserKnowledgeState.objects.filter(user=request.user)`

---

### 2. **Check Quiz History Section:**

**If you HAVE quiz data:**
- Navigate to `/dashboard/progress`
- Scroll to "QUIZ HISTORY" section
- You should see 3 tabs:
  - DAILY MCQ
  - WEEKLY MCQ
  - WEEKLY TESTS
- Click each tab to see different views

**If you DON'T have quiz data:**
- You should see a dashed box with message:
  > "No quiz history available yet. Complete lessons to unlock quizzes!"

**To generate quiz data:**
- Complete lessons and take quizzes
- Or test the API directly: `GET /api/users/me/quiz-history-aggregated/`

---

## Debug Commands:

### Backend (Check if data exists):

```bash
cd backend
python manage.py shell

# Check concept mastery data
from apps.users.models import UserKnowledgeState
UserKnowledgeState.objects.count()  # Should be > 0
UserKnowledgeState.objects.all()[:5]  # Show first 5

# Check quiz history
from apps.quizzes.models import QuizAttempt
QuizAttempt.objects.count()  # Should be > 0

# Check weekly tests
from apps.courses.models import WeeklyTestAttempt
WeeklyTestAttempt.objects.count()  # May be 0 if no weekly tests taken
```

### Frontend (Check API responses):

Open browser console and run:

```javascript
// Check progress API
fetch('/api/users/me/progress/', { credentials: 'include' })
  .then(r => r.json())
  .then(d => console.log('Progress:', d))

// Check quiz history API
fetch('/api/users/me/quiz-history-aggregated/', { credentials: 'include' })
  .then(r => r.json())
  .then(d => console.log('Quiz History:', d))
```

---

## Common Issues:

### Issue 1: Sections Completely Missing
**Cause:** Component not rendering
**Fix:** Check browser console for errors

### Issue 2: Sections Show But Empty
**Cause:** No data in database
**Fix:** Complete quizzes to generate data, or check API is working

### Issue 3: Sections Collapsed/Hidden
**Cause:** CSS height issue
**Fix:** Already fixed with `min-height` properties

### Issue 4: Filters Hiding Concepts
**Cause:** Filter set to 'weak' or 'strong' but no matching concepts
**Fix:** Click "ALL" filter button

---

## Visual Checklist:

After refreshing `/dashboard/progress`, you should see:

- [ ] Section 1: OVERVIEW STATS (4 stat boxes)
- [ ] Section 2: STUDY STREAK (GitHub-style calendar)
- [ ] Section 3: COURSE PROGRESS (list of courses)
- [ ] Section 4: CONCEPT MASTERY (filters + concept list OR empty message)
- [ ] Section 5: QUIZ HISTORY (3 tabs + table OR empty message)

---

## If Still Not Visible:

1. **Check browser console for errors**
2. **Check network tab** - verify API calls succeed
3. **Hard refresh** - `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)
4. **Clear browser cache**
5. **Check if dev server is running** - `npm run dev` in frontend directory

---

**Last Updated:** April 12, 2026
**Status:** ✅ Fixed - Empty states added, min-heights set, styling improved
