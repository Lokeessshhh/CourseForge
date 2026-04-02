# Chat Session Navigation Fix

## Problem

When generating a course from chat and navigating away:
1. User generates course from **Chat A** → progress bar shows
2. User navigates to another page → progress bar shows toast (working)
3. User returns to chat → **wrong session** may be restored
4. User clicks on another chat → progress bar "jumps" to the wrong session
5. Original chat messages are lost
6. **Sessions not appearing in sidebar** after navigation

## Root Cause

1. **Session restoration was ambiguous** - didn't reliably restore the session that created the generating course
2. **Progress bar filtering had fallback logic** - allowed progress to show in sessions that didn't create the course
3. **No session save on navigation** - session wasn't persisted to DB when user navigated away
4. **Backend renameSession only updated placeholders** - didn't create/update system messages for sessions without placeholders

## Solution

### 1. Route Change Detection (Frontend)

**File:** `frontend/app/dashboard/chat/page.tsx`

Added `usePathname()` hook to detect route changes and save session to DB before navigation completes:

```typescript
// Keep refs updated for latest data during unmount
const messagesRef = useRef(messages);
const currentSessionRef = useRef(currentSession);

useEffect(() => {
  messagesRef.current = messages;
  currentSessionRef.current = currentSession;
}, [messages, currentSession]);

// Save function using refs
const saveCurrentSessionToDB = useCallback(async (force: boolean = false) => {
  const hasMessages = messagesRef.current.length > 0;
  const hasGeneratingCourses = Array.from(generatingCourses.values()).some(
    c => c.createdBySessionId === currentSessionId
  );
  
  if (!hasMessages && !hasGeneratingCourses && !force) return;
  
  // Generate title from first message if needed
  let sessionTitle = currentSessionRef.current?.title || 'New Chat';
  if (sessionTitle === '[Session created]' || sessionTitle === 'New Chat' || !sessionTitle) {
    const firstUserMessage = messagesRef.current.find(m => m.role === 'user');
    if (firstUserMessage) {
      sessionTitle = firstUserMessage.content.slice(0, 50) + '...';
    }
  }

  // ALWAYS update session title in DB
  await renameSession(currentSessionId, sessionTitle);
  
  // Save generating course IDs to Redis
  const generatingIds = Array.from(generatingCourses.values())
    .filter(c => c.createdBySessionId === currentSessionId)
    .map(c => c.courseId);
  
  if (generatingIds.length > 0) {
    await fetch(`/api/conversations/sessions/${currentSessionId}/generating-courses/`, {
      method: 'POST',
      body: JSON.stringify({ course_ids: generatingIds }),
    });
  }
}, [currentSessionId, generatingCourses, renameSession]);

// Save on unmount
useEffect(() => {
  return () => {
    if (currentSessionId) {
      saveCurrentSessionToDB(true); // Force save
    }
  };
}, [currentSessionId, saveCurrentSessionToDB]);

// Save on route change
useEffect(() => {
  const oldRoute = previousPathnameRef.current.split('?')[0];
  const newRoute = pathname.split('?')[0];
  
  if (oldRoute !== newRoute && currentSessionId) {
    saveCurrentSessionToDB();
  }
  previousPathnameRef.current = pathname;
}, [pathname, currentSessionId, saveCurrentSessionToDB]);
```

### 2. Backend: Always Update System Message

**File:** `backend/apps/conversations/views.py`

Updated `session_rename` to ALWAYS create or update the system message:

```python
@sync_to_async
def update_or_create_system_message():
    system_msg = Conversation.objects.filter(
        user=request.user,
        session_id=sid,
        role="system"
    ).first()
    
    if system_msg:
        # Update existing
        system_msg.content = title
        system_msg.save()
    else:
        # Create new
        Conversation.objects.create(
            user=request.user,
            session_id=sid,
            role="system",
            content=title,
            is_summarized=True,
        )

async_to_sync(update_or_create_system_message)()
```

### 3. Strict Progress Bar Filtering (Frontend)

**File:** `frontend/app/dashboard/chat/page.tsx`

Changed from loose matching to handle null/undefined cases properly:

```typescript
const generatingCourseInThisSession = Array.from(generatingCourses.values()).find(
  c => c.generation_status === 'generating' &&
  // Match if both are null/undefined OR both match exactly
  (c.createdBySessionId === currentSessionId || 
   (!c.createdBySessionId && !currentSessionId))
);
```

### 4. Ensure Session Exists Before Course Creation

**File:** `frontend/app/dashboard/chat/page.tsx`

Updated course creation handlers to create a session first:

```typescript
let sessionIdToUse = currentSessionId;
if (!sessionIdToUse) {
  sessionIdToUse = await createSession({ course_id: courseId });
  setCurrentSessionId(sessionIdToUse);
}

addGeneratingCourse({
  courseId: newCourseId,
  createdBySessionId: sessionIdToUse, // Now guaranteed
});
```

### 5. Enhanced Session Restoration (Frontend)

**File:** `frontend/app/dashboard/chat/page.tsx`

Updated restoration logic to prioritize sessions with generating courses:

```typescript
useEffect(() => {
  // 1. Check Redis metadata (generating_course_ids from backend)
  const sessionWithGeneratingCourse = sessions.find(s => 
    s.generating_course_ids && s.generating_course_ids.length > 0
  );
  
  if (sessionWithGeneratingCourse) {
    setCurrentSessionId(sessionWithGeneratingCourse.id);
    return;
  }
  
  // 2. Check localStorage for sessions with generating courses
  const allSessionIds = storage.getAllSessionIds();
  for (const sessionId of allSessionIds) {
    const session = storage.getSession(sessionId);
    if (session?.generatingCourseIds?.length > 0) {
      const sessionExists = sessions.some(s => s.id === sessionId);
      if (sessionExists) {
        setCurrentSessionId(sessionId);
        return;
      }
    }
  }
  
  // 3. Fallback: Restore last active session
}, [sessions]);
```

### 6. Backend API Endpoint (Backend)

**File:** `backend/apps/conversations/views.py`

Added new endpoint to save generating course IDs to Redis session metadata:

```python
@api_view(["POST"])
def session_save_generating_courses(request, session_id):
    """Save generating course IDs to session metadata in Redis."""
    course_ids = request.data.get("course_ids", [])
    
    session = ChatSession(user_id=str(request.user.id), session_id=str(session_id))
    
    if "generating_courses" not in session.metadata:
        session.metadata["generating_courses"] = {}
    
    for course_id in course_ids:
        session.metadata["generating_courses"][course_id] = {
            "status": "generating",
            "saved_at": timezone.now().isoformat(),
        }
    
    session.save()
```

**File:** `backend/apps/conversations/urls.py`

Added URL route:
```python
path("sessions/<uuid:session_id>/generating-courses/", views.session_save_generating_courses),
```

### 7. ChatSession Helper Method (Backend)

**File:** `backend/services/chat/session.py`

Added static method to get Redis client:

```python
@staticmethod
def get_redis() -> redis.Redis:
    """Get the Redis client."""
    return get_redis()
```

## How It Works Now

### Flow: Chat → Navigate → Return

1. **User sends message in Chat A**
   - Message saved to DB (user + assistant)
   - Session has placeholder title `[Session created]`

2. **User navigates to Dashboard**
   - Route change detected OR unmount triggered
   - `saveCurrentSessionToDB()` called
   - Session title updated in DB (from first message)
   - System message created/updated in database
   - Generating course IDs saved to Redis (if any)
   - Session also saved to localStorage as backup

3. **Session appears in sidebar**
   - Backend `conversation_list` reads system message from DB
   - Title displayed (not "New Chat")
   - `generating_course_ids` included from Redis

4. **User returns to chat page**
   - Restoration logic runs:
     - Finds session with `generating_course_ids` → restores Chat A
     - OR finds localStorage session with generating courses → restores Chat A
   - Chat A opens with all messages

5. **Progress bar visible** in Chat A (strict session matching)

6. **User clicks Chat B**
   - Progress bar does NOT appear (strict matching)
   - Chat A's progress stays with Chat A

7. **User clicks back to Chat A**
   - Progress bar reappears
   - All messages preserved

## Benefits

✅ **Predictable behavior** - Progress bar stays with the session that created it
✅ **Session persistence** - Sessions saved to DB on navigation
✅ **No data loss** - Messages persisted to DB and localStorage
✅ **Clear session boundaries** - Navigation = session end
✅ **User control** - User explicitly chooses which session to open from sidebar
✅ **Sessions appear in sidebar** - System message always created/updated in DB

## Testing Checklist

- [ ] Send a message in chat
- [ ] Navigate to dashboard
- [ ] Check console for `[SESSION SAVE] ✅ Session saved successfully`
- [ ] Verify session appears in sidebar with proper title (not "New Chat")
- [ ] Return to chat page
- [ ] Verify correct session is restored
- [ ] Generate course from chat
- [ ] Navigate to dashboard while generating
- [ ] Verify session appears in sidebar with generating course indicator
- [ ] Return to chat
- [ ] Verify progress bar is visible in restored session
- [ ] Click on different session
- [ ] Verify progress bar does NOT appear in other session
- [ ] Click back to original session
- [ ] Verify progress bar reappears
- [ ] Verify all messages are preserved

## Files Changed

### Frontend
- `frontend/app/dashboard/chat/page.tsx` - Route change detection, strict filtering, enhanced restoration, refs for latest data

### Backend
- `backend/apps/conversations/views.py` - Updated `session_rename` to always update system message, new endpoint `session_save_generating_courses`
- `backend/apps/conversations/urls.py` - New URL route
- `backend/services/chat/session.py` - Added `get_redis()` static method

## API Endpoints

### PATCH `/api/conversations/sessions/{session_id}/rename/`

Rename a session (updated to always create/update system message).

**Request:**
```json
{
  "title": "My Chat Title"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "session_id": "uuid",
    "title": "My Chat Title"
  }
}
```

### POST `/api/conversations/sessions/{session_id}/generating-courses/`

Save generating course IDs to session metadata in Redis.

**Request:**
```json
{
  "course_ids": ["uuid1", "uuid2", ...]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "session_id": "uuid",
    "generating_courses": ["uuid1", "uuid2", ...]
  }
}
```
