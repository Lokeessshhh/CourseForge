# AI Chat Course Management Feature

## Overview
The chat assistant can now intelligently manage courses through natural conversation. Users can create, delete, view, and get help with courses directly from the chat interface.

---

## Features Implemented

### 1. **Course Creation via Chat**
- **Intent Detection**: AI detects when user wants to create a course
- **Smart Form Display**: If required fields are missing, shows a form above chat input
- **Entity Extraction**: Automatically extracts course name, duration, level from message
- **Immediate Creation**: If all fields provided, creates course immediately

**Example Flows:**

**Incomplete Request:**
```
User: "Create a course on Python"
  ↓
AI: Shows form with:
    - Course Name: Python (pre-filled)
    - Duration: [empty]
    - Level: [empty]
    - Description: [empty]
  ↓
User fills form → Course created
```

**Complete Request:**
```
User: "Create a 4 week beginner Python course for data science"
  ↓
AI: Extracts all fields → Creates course immediately
  ↓
AI: "Creating your 4-week beginner Python course focused on data science!"
```

### 2. **Course Deletion via Chat**
- **Always Confirms**: Asks for confirmation before deleting
- **Multiple Matches**: If multiple courses match, shows list and asks which one
- **Clear Feedback**: Confirms deletion with course name

**Example:**
```
User: "Delete my Python course"
  ↓
AI: "Are you sure you want to delete 'Python'? This cannot be undone."
  ↓
User: "Yes"
  ↓
AI: "Course 'Python' has been deleted."
```

### 3. **View Course Content**
- **Day Content**: Shows theory, code, and quiz for specific week/day
- **Tabbed Interface**: Theory, Code, Quiz tabs
- **Markdown Rendering**: Full markdown support for content

**Example:**
```
User: "Show me Week 2 Day 3 of Python course"
  ↓
AI: Fetches and displays day content with tabs
```

### 4. **MCQ Help**
- **Concept Explanations**: Explains concepts, guides to answer
- **Not Direct Answers**: Teaches rather than just giving answer
- **Context Aware**: Fetches specific quiz from course/week/day

**Example:**
```
User: "Help me with quiz question 2 from Week 1 Day 5"
  ↓
AI: Explains the concept and guides user to correct answer
```

### 5. **List All Courses**
- **Progress Summary**: Shows all courses with completion percentage
- **Status Indicators**: Shows if generating, completed, or in progress

**Example:**
```
User: "Show my courses"
  ↓
AI: Lists all courses with progress:
    - Python (4 weeks, beginner) - 75% complete
    - JavaScript (2 weeks, intermediate) - Generating
```

---

## Technical Architecture

### Backend Components

#### 1. Intent Classifier (`services/chat/intent_classifier.py`)
- Pattern-based intent detection
- Entity extraction using regex
- Returns: intent, confidence, entities, missing_fields

**Intents:**
- `create_course` - User wants to create a course
- `delete_course` - User wants to delete a course
- `read_course` / `list_courses` - User wants to see courses
- `read_day` - User wants to see specific day content
- `answer_mcq` - User wants MCQ help
- `unknown` - Intent not recognized

#### 2. Handlers (`services/chat/handlers.py`)
- `CourseCreationHandler` - Manages course creation flow
- `CourseDeletionHandler` - Manages deletion with confirmation
- `CourseReaderHandler` - Fetches and displays course content
- `MCQHelperHandler` - Provides quiz assistance
- `ChatHandler` - Routes to appropriate handler

#### 3. API Endpoints (`apps/chat/views.py`)
- `POST /api/chat/` - Main chat endpoint for course management
- `POST /api/chat/create/` - Create course from chat
- `POST /api/chat/delete/` - Delete course from chat
- `GET /api/chat/course/<id>/week/<w>/day/<d>/` - Get day content
- `GET /api/chat/course/<id>/week/<w>/day/<d>/mcq/` - Get MCQ content

### Frontend Components

#### 1. API Hook (`hooks/api/useChatCourse.ts`)
- `sendChatMessage()` - Send message to chat API
- `createCourse()` - Create course
- `deleteCourse()` - Delete course
- `getDayContent()` - Fetch day content
- `getMCQContent()` - Fetch MCQ content

#### 2. Course Creation Form (`components/chat/CourseCreationForm.tsx`)
- Dynamic form based on missing fields
- Supports: text, number, select, textarea
- Validation with error display
- Pre-filled values from AI extraction

#### 3. Day Content Card (`components/chat/DayContentCard.tsx`)
- Tabbed interface (Theory, Code, Quiz)
- Markdown rendering
- Quiz with show/hide answers
- Tasks display

---

## API Request/Response Examples

### Create Course (Incomplete)
**Request:**
```json
POST /api/chat/
{
  "message": "Create a course on Python"
}
```

**Response:**
```json
{
  "intent": "create_course",
  "response": "Great! Let's create a course on Python. I just need a few more details:",
  "action": "show_form",
  "form_schema": {
    "fields": [
      {
        "name": "duration_weeks",
        "type": "number",
        "label": "Duration (weeks)",
        "min": 1,
        "max": 52,
        "required": true
      },
      {
        "name": "level",
        "type": "select",
        "label": "Skill Level",
        "options": [
          {"value": "beginner", "label": "Beginner"},
          {"value": "intermediate", "label": "Intermediate"},
          {"value": "advanced", "label": "Advanced"}
        ],
        "required": true
      }
    ],
    "prefilled": {
      "course_name": "Python"
    }
  }
}
```

### Create Course (Complete)
**Request:**
```json
POST /api/chat/
{
  "message": "Create a 4 week beginner Python course"
}
```

**Response:**
```json
{
  "intent": "create_course",
  "response": "Creating your 4-week beginner Python course!",
  "action": "create_course",
  "course_data": {
    "course_name": "Python",
    "duration_weeks": 4,
    "level": "beginner"
  }
}
```

### Delete Course
**Request:**
```json
POST /api/chat/
{
  "message": "Delete my Python course"
}
```

**Response:**
```json
{
  "intent": "delete_course",
  "response": "Are you sure you want to delete 'Python'? This cannot be undone.",
  "action": "confirm",
  "course_id": "uuid-here",
  "course_name": "Python"
}
```

### Show Day Content
**Request:**
```json
POST /api/chat/
{
  "message": "Show me Week 2 Day 3 of Python"
}
```

**Response:**
```json
{
  "intent": "read_day",
  "response": "Fetching Week 2 Day 3 from Python...",
  "action": "show_day",
  "course_id": "uuid-here",
  "week_number": 2,
  "day_number": 3
}
```

---

## Files Created/Modified

### Backend (New Files)
1. `backend/services/chat/intent_classifier.py` - Intent detection
2. `backend/services/chat/handlers.py` - Request handlers
3. `backend/apps/chat/views.py` - API endpoints
4. `backend/apps/chat/urls.py` - URL routing
5. `backend/apps/chat/__init__.py` - App initialization
6. `backend/apps/chat/apps.py` - App configuration

### Backend (Modified)
7. `backend/config/settings/base.py` - Added `apps.chat` to INSTALLED_APPS
8. `backend/config/urls.py` - Added `/api/chat/` routes

### Frontend (New Files)
9. `frontend/app/hooks/api/useChatCourse.ts` - API hooks
10. `frontend/app/components/chat/CourseCreationForm.tsx` - Form component
11. `frontend/app/components/chat/CourseCreationForm.module.css` - Form styles
12. `frontend/app/components/chat/DayContentCard.tsx` - Day content display
13. `frontend/app/components/chat/DayContentCard.module.css` - Card styles

---

## Integration Steps (Remaining)

To complete the integration, the chat page needs to:

1. Import `useChatCourse` hook
2. Add state for form display and day content
3. Intercept messages for course management
4. Show form when `action === 'show_form'`
5. Display day content cards when `action === 'show_day'`
6. Handle course creation/deletion confirmations

---

## Testing

### Backend Tests
```bash
cd backend
python manage.py test apps.chat
```

### Frontend Tests
```bash
cd frontend
npm run test
```

### Manual Testing Checklist
- [ ] Create course with incomplete info → Form appears
- [ ] Create course with complete info → Immediate creation
- [ ] Delete course → Confirmation required
- [ ] Delete non-existent course → Error message
- [ ] Delete with multiple matches → Shows options
- [ ] View day content → Displays theory, code, quiz
- [ ] List courses → Shows all with progress
- [ ] MCQ help → Explains concepts

---

## Future Enhancements

1. **Voice Input**: Allow voice commands for course management
2. **Bulk Operations**: Delete/archive multiple courses at once
3. **Course Updates**: Modify existing course details via chat
4. **Progress Tracking**: Ask "How am I doing in Python?"
5. **Recommendations**: "What should I learn next?"
6. **Export**: Export course content as PDF/Markdown
7. **Sharing**: Share course progress via chat

---

## Status
✅ **BACKEND COMPLETE**
✅ **FRONTEND COMPONENTS CREATED**
⏳ **INTEGRATION PENDING** - Chat page integration needed
