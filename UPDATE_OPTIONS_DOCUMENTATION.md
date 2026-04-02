# Course Update Options

## Available Update Types

When updating a course, users can choose from **4 available options** + **1 coming soon**:

---

## 1. Update Current (50%)

**Description:** Replace the last 50% of the course with new content.

**Use Case:** You want to update recent content while keeping the foundation intact.

**Example:** 4-week course → Updates weeks 3-4, keeps weeks 1-2

**Duration:** Same as original

**Input Required:** No

---

## 2. Update Current (75%)

**Description:** Replace the last 75% of the course with new content.

**Use Case:** You want to keep only the basics and update most of the course.

**Example:** 4-week course → Updates weeks 2-4, keeps week 1

**Duration:** Same as original

**Input Required:** No

---

## 3. Compact Course ✅ NEW

**Description:** Compress and redesign the entire course into fewer weeks while keeping essential content.

**Use Case:** You want to complete the course faster by focusing on high-impact topics.

**Example:** 4-week Java course → 2 weeks
- Week 1: "Java Fundamentals & OOP Mastery" (combines original Weeks 1-2)
- Week 2: "Advanced Java & Real-World Applications" (combines original Weeks 3-4)

**Duration:** User-specified (must be less than current duration)

**Input Required:** Yes - Target weeks (1 to current_duration)

**How It Works:**
1. User selects "Compact Course" and enters target weeks (e.g., "2")
2. System regenerates ALL weeks with compressed content
3. AI combines multiple concepts efficiently
4. Old weeks beyond target are deleted
5. Progress is reset for the new compact course

**AI Prompt:**
```
COMPACT COURSE MODE:
- Original course: 4 weeks
- New compact course: 2 weeks

IMPORTANT: This is a COMPRESSED course. You must:
1. Combine multiple concepts into fewer weeks
2. Focus on ESSENTIAL and HIGH-IMPACT topics only
3. Remove redundant or nice-to-have content
4. Ensure each week covers more ground efficiently
5. Maintain logical progression
6. Prioritize practical, hands-on learning
```

---

## 4. Extend + Update (50%)

**Description:** Keep all current content and add 50% more weeks with new content.

**Use Case:** You want to expand the course without losing existing content.

**Example:** 4-week course → 6 weeks (adds weeks 5-6)

**Duration:** Original + 50%

**Input Required:** No

---

## 5. Custom Update 🔜 Coming Soon

**Description:** Select specific weeks to update and customize.

**Use Case:** You want to update only certain weeks (e.g., just week 2 and week 4).

**Status:** Not Available Yet

**Badge:** "Coming Soon" (disabled in UI)

---

## UI Implementation

### Update Options Card

```
┌─────────────────────────────────────────────────────────┐
│  Great! Let's update your 'Java' course. Choose how    │
│  you'd like to update it:                               │
├─────────────────────────────────────────────────────────┤
│  ○ Update Current (50%)                                 │
│    Replace the last 50% of the course with new content  │
│    Same duration                                        │
│                                                         │
│  ○ Update Current (75%)                                 │
│    Replace the last 75% of the course with new content  │
│    Same duration                                        │
│                                                         │
│  ○ Compact Course                                       │
│    Compress and redesign the entire course into fewer   │
│    weeks while keeping essential content                │
│    4 weeks → [your choice] weeks                        │
│    [Input: Target weeks] ___                            │
│                                                         │
│  ○ Extend + Update (50%)                                │
│    Keep all current content and add 50% more weeks      │
│    4 weeks → 6 weeks                                    │
│                                                         │
│  ⦸ Custom Update                        [Coming Soon]   │
│    Select specific weeks to update and customize        │
│    Not Available Yet                                    │
└─────────────────────────────────────────────────────────┘
```

---

## API Request Examples

### Compact Course Request

```json
POST /api/courses/{id}/update/
{
    "update_type": "compact",
    "user_query": "Include OOP concepts",
    "target_weeks": 2,
    "web_search_enabled": true
}
```

### Compact Course Response

```json
{
    "success": true,
    "data": {
        "course_id": "uuid",
        "status": "updating",
        "message": "Course update started...",
        "update_type": "compact",
        "weeks_to_update": [1, 2, 3, 4],
        "new_duration_weeks": 2,
        "total_days_being_updated": 20
    }
}
```

### Custom Update Request (Coming Soon)

```json
POST /api/courses/{id}/update/
{
    "update_type": "custom_update",
    "user_query": "Add advanced topics",
    "weeks_list": [2, 4],
    "web_search_enabled": true
}
```

**Response:**
```json
{
    "success": false,
    "error": "Custom Update is coming soon. Please use another update type."
}
```

---

## Backend Validation

### Compact Course Validation

```python
# In courses/views.py
if update_type == "compact":
    target_weeks = data.get("target_weeks")
    if target_weeks >= current_weeks:
        return _err("Target weeks must be less than current course duration")
    new_duration_weeks = target_weeks
    weeks_to_update = list(range(1, current_weeks + 1))  # ALL weeks
```

### Custom Update Validation (Coming Soon)

```python
# In courses/serializers.py
if data.get("update_type") == "custom_update":
    raise serializers.ValidationError({
        "update_type": "Custom Update is coming soon. Please use another update type."
    })
```

---

## Progress Calculation

### Compact Course (4 weeks → 2 weeks)

| Stage | Tasks Done | Total Tasks | Progress |
|-------|------------|-------------|----------|
| Week 1 days complete | 5 days | 14 tasks | 36% |
| Week 2 days complete | 10 days | 14 tasks | 71% |
| MCQ Week 1 | 11 tasks | 14 tasks | 79% |
| Coding Week 1 | 12 tasks | 14 tasks | 86% |
| MCQ Week 2 | 13 tasks | 14 tasks | 93% |
| Coding Week 2 | 14 tasks | 14 tasks | 100% |

**Formula:** `total_tasks = (new_duration_weeks × 5 days) + (new_duration_weeks × 2 tests)`

---

## Files Modified

| File | Changes |
|------|---------|
| `apps/chat/views.py` | Added 5 update options with availability flags |
| `apps/courses/serializers.py` | Added validation for compact and custom_update |
| `apps/courses/views.py` | Added compact logic |
| `apps/courses/tasks.py` | Added compact handling |
| `services/course/generator.py` | Added compact-specific AI prompts |

---

## Testing Checklist

- [x] Compact Course option shows in UI
- [x] Compact Course input field appears
- [x] Compact Course validates target_weeks
- [x] Compact Course regenerates all weeks
- [x] Compact Course deletes old weeks
- [x] Custom Update shows "Coming Soon" badge
- [x] Custom Update is disabled in UI
- [x] Custom Update API request is rejected

---

**Last Updated:** 2026-04-02  
**Status:** ✅ Production Ready (Compact Course) | 🔜 Coming Soon (Custom Update)
