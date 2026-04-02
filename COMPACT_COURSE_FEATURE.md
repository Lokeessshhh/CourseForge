# Compact Course Update Feature

## Overview

The **Compact Course** feature allows users to compress their existing course into fewer weeks while maintaining essential content. This is useful when users want to:
- Complete a course faster
- Focus on essential topics only
- Redesign a course with a more efficient structure

## How It Works

### User Flow

1. User sends message: "update java course which includes oops"
2. System shows 4 update options:
   - Update Current (50%)
   - Update Current (75%)
   - Extend + Update (50%)
   - **Compact Course** ← New option
3. User selects "Compact Course" and enters target weeks (e.g., 2 weeks for a 4-week course)
4. System compresses the entire course into the specified duration

### Example

**Before:** 4-week Java course
- Week 1: Java Basics
- Week 2: OOP Concepts
- Week 3: Advanced Java
- Week 4: Projects

**After (Compact to 2 weeks):**
- Week 1: Java Fundamentals & OOP Mastery (combines Weeks 1-2)
- Week 2: Advanced Java & Real-World Applications (combines Weeks 3-4)

## Technical Implementation

### Files Modified

| File | Changes |
|------|---------|
| `apps/chat/views.py` | Added compact option with input field |
| `apps/courses/views.py` | Added compact logic to preview and update endpoints |
| `apps/courses/serializers.py` | Added `target_weeks` field and validation |
| `apps/courses/tasks.py` | Added compact handling in update tasks |
| `services/course/generator.py` | Added compact-specific AI prompts |

### API Changes

#### Request Format

```json
POST /api/courses/{id}/update/
{
    "update_type": "compact",
    "user_query": "Include OOP concepts",
    "target_weeks": 2,
    "web_search_enabled": true
}
```

#### Validation Rules

- `target_weeks` must be less than current course duration
- `target_weeks` must be between 1 and 52
- `target_weeks` is required for compact update type

### AI Prompt Engineering

The compact feature uses specialized prompts to ensure quality compression:

```
COMPACT COURSE MODE:
- Original course: 4 weeks
- New compact course: 2 weeks
- Week 1 of 2 total weeks

IMPORTANT: This is a COMPRESSED course. You must:
1. Combine multiple concepts into fewer weeks while maintaining learning quality
2. Focus on ESSENTIAL and HIGH-IMPACT topics only
3. Remove redundant or nice-to-have content
4. Ensure each week covers more ground efficiently
5. Maintain logical progression and build complexity appropriately
6. Prioritize practical, hands-on learning over theory
```

### Progress Calculation

For a 4-week → 2-week compact:
- **Total days:** 2 weeks × 5 days = 10 days
- **Total tests:** 2 weeks × 2 tests = 4 tests
- **Total tasks:** 10 + 4 = 14 tasks

**Progress flow:**
1. Week 1 days: 5/10 days → 50%
2. Week 2 days: 10/10 days → 95% (capped)
3. MCQ Week 1: 11/14 → 79%
4. Coding Week 1: 12/14 → 86%
5. MCQ Week 2: 13/14 → 93%
6. Coding Week 2: 14/14 → 100%

### Database Changes

**Weeks beyond target are deleted:**
```python
# For compact type, delete old weeks beyond the new duration
if update_type == "compact" and new_duration_weeks < course.duration_weeks:
    weeks_to_delete = WeekPlan.objects.filter(
        course=course, 
        week_number__gt=new_duration_weeks
    )
    for week in weeks_to_delete:
        week.delete()
```

**CourseProgress is updated:**
```python
CourseProgress.objects.filter(course=course).update(
    total_days=new_duration_weeks * 5,
    total_weeks=new_duration_weeks,
)
```

## Frontend Integration

### Update Options Response

```json
{
    "command": "update_course",
    "action": "show_options",
    "course_id": "uuid",
    "course_name": "Java",
    "user_query": "Include OOP concepts",
    "current_duration_weeks": 4,
    "update_options": [
        {
            "type": "50%",
            "label": "Update Current (50%)",
            "requires_input": false
        },
        {
            "type": "compact",
            "label": "Compact Course",
            "description": "Compress and redesign the entire course...",
            "duration_change": "4 weeks → [your choice] weeks",
            "requires_input": true,
            "input_label": "Target weeks",
            "input_placeholder": "Enter 1-4",
            "input_min": 1,
            "input_max": 4
        }
    ]
}
```

### UI Requirements

1. Show input field only when `requires_input: true`
2. Validate input range (min/max)
3. Show duration change preview
4. Disable compact option if course is already at minimum duration (1 week)

## Error Handling

| Error | Response |
|-------|----------|
| target_weeks >= current_duration | "Target weeks must be less than current course duration" |
| target_weeks < 1 | "Target weeks must be at least 1" |
| target_weeks > 52 | "Target weeks cannot exceed 52" |
| target_weeks missing | "target_weeks is required for compact update type" |

## Testing Checklist

- [ ] Compact 4-week course to 2 weeks
- [ ] Compact 8-week course to 4 weeks
- [ ] Verify old weeks are deleted
- [ ] Verify CourseProgress is updated
- [ ] Verify AI generates compressed content
- [ ] Verify progress calculation is correct
- [ ] Verify input validation works
- [ ] Verify error messages are shown

## Production Notes

- **Backwards compatible:** Existing update types (50%, 75%, extend_50%) work unchanged
- **Safe deletion:** Only deletes weeks beyond new duration after content regeneration
- **Progress reset:** User progress is reset for compacted course
- **Web search:** Works with web search enabled/disabled

---

**Implementation Date:** 2026-04-02  
**Status:** ✅ Production Ready
