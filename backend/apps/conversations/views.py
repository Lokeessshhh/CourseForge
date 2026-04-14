"""
Conversations app — views for chat history management.

Endpoints:
  POST   /api/conversations/sessions/           → Create new session
  GET    /api/conversations/                    → List all sessions
  GET    /api/conversations/sessions/           → List sessions with pagination
  GET    /api/conversations/sessions/{id}/      → Get session messages
  DELETE /api/conversations/sessions/{id}/      → Delete session
  PATCH  /api/conversations/sessions/{id}/      → Rename session
  POST   /api/conversations/sessions/{id}/title/ → Set session title
  GET    /api/conversations/course/{course_id}/ → Get course-specific history
  GET    /api/conversations/search/             → Search conversations
"""
import json
import logging
import uuid

from asgiref.sync import async_to_sync, sync_to_async
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Max, Min, Count
from django.utils import timezone

from .models import Conversation
from .serializers import ConversationSerializer

logger = logging.getLogger(__name__)


class ConversationPagination(PageNumberPagination):
    """Pagination for conversation lists."""
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _ok(data, status_code=status.HTTP_200_OK):
    return Response({"success": True, "data": data, "error": None}, status=status_code)


def _err(msg, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"success": False, "data": None, "error": msg}, status=status_code)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_session(request):
    """
    Create a new chat session.

    Body:
    {
        "course_id": "uuid" (optional),
        "title": "My Chat" (optional)
    }

    Returns:
    {
        "session_id": "uuid",
        "course_id": "uuid" (if provided),
        "title": "My Chat",
        "created_at": "timestamp"
    }
    """
    import uuid
    from django.utils import timezone
    from asgiref.sync import async_to_sync

    course_id = request.data.get("course_id")
    title = request.data.get("title", "New Chat")

    # Validate course_id if provided
    if course_id:
        try:
            course_id = uuid.UUID(str(course_id))
        except ValueError:
            return _err("Invalid course_id")
    else:
        course_id = None

    # Generate new session ID
    session_id = uuid.uuid4()

    # Store title in metadata
    from services.chat.session import ChatSession
    session = ChatSession(
        user_id=str(request.user.id),
        session_id=str(session_id),
        scope="global",
        course_id=str(course_id) if course_id else None,
        metadata={"title": title},
    )

    # Use async_to_sync to call async save_async from sync view
    async_to_sync(session.save_async)()

    # Save placeholder Conversation to database so session appears in list immediately
    from apps.conversations.models import Conversation

    # System message for metadata
    Conversation.objects.create(
        user=request.user,
        session_id=session_id,
        role="system",
        content="[Session created]",
        course=course_id,
        is_summarized=True,
    )

    # User-role placeholder so session appears in sidebar (conversation_list filters role="user")
    Conversation.objects.create(
        user=request.user,
        session_id=session_id,
        role="user",
        content="[New chat started]",
        course=course_id,
        is_summarized=True,
    )

    logger.info(
        "Created new session: user=%s session_id=%s course_id=%s title=%s",
        request.user.id, session_id, course_id, title
    )

    return _ok({
        "session_id": str(session_id),
        "course_id": str(course_id) if course_id else None,
        "title": title,
        "created_at": timezone.now().isoformat(),
    }, status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def conversation_list(request):
    """
    Return distinct sessions for the authenticated user.

    Query params:
    - limit: Max sessions to return (default 50)
    - offset: Pagination offset
    """
    limit = min(int(request.query_params.get("limit", 50)), 100)
    offset = int(request.query_params.get("offset", 0))

    # Get distinct sessions with metadata
    sessions = (
        Conversation.objects
        .filter(user=request.user, role="user")  # Count only user messages (1 user + 1 AI = 1 conversation)
        .values("session_id", "course", "course__topic", "course__course_name")
        .annotate(
            message_count=Count("id"),
            first_message=Min("created_at"),
            last_message=Max("created_at"),
        )
        .order_by("-last_message")
        [offset:offset + limit]
    )

    data = []
    for s in sessions:
        sid = str(s["session_id"])

        # Get AI-generated title from system conversation
        # System messages are created with role="system" for title storage
        system_msg = Conversation.objects.filter(
            user=request.user,
            session_id=s["session_id"],
            role="system"
        ).first()

        # If system message exists with generated title (not placeholder), use it
        if system_msg and system_msg.content and system_msg.content != "[Session created]":
            title = system_msg.content
        else:
            # Fallback: Get first user message as title
            first_msg = Conversation.objects.filter(
                user=request.user,
                session_id=s["session_id"],
                role="user"
            ).first()
            if first_msg:
                title = first_msg.content[:50] + "..." if len(first_msg.content) > 50 else first_msg.content
            else:
                title = "New Chat"

        # Get generating courses from Redis session metadata
        generating_course_ids = []
        try:
            from services.chat.session import ChatSession
            session = ChatSession(
                user_id=str(request.user.id),
                session_id=sid,
            )
            generating_courses = session.get_generating_courses()
            generating_course_ids = list(generating_courses.keys())
        except Exception as exc:
            logger.warning("Failed to get generating courses for session %s: %s", sid, exc)

        data.append({
            "id": sid,
            "title": title,
            "course_id": str(s["course"]) if s["course"] else None,
            "course_topic": s["course__topic"],
            "course_name": s["course__course_name"],
            "message_count": s["message_count"],
            "first_message": s["first_message"],
            "last_message": s["last_message"],
            "date": s["last_message"].strftime("%Y-%m-%d") if s["last_message"] else None,
            "generating_course_ids": generating_course_ids,  # NEW: Include generating courses
        })

    return _ok(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def session_list(request):
    """
    List all chat sessions with pagination and filtering.
    
    Query params:
    - page: Page number
    - page_size: Items per page (default 20)
    - course_id: Filter by course
    - scope: Filter by scope (global/course/day)
    """
    queryset = Conversation.objects.filter(user=request.user)
    
    # Filter by course
    course_id = request.query_params.get("course_id")
    if course_id:
        queryset = queryset.filter(course_id=course_id)
    
    # Get distinct sessions
    sessions = (
        queryset
        .values("session_id", "course", "course__topic", "course__course_name")
        .annotate(
            message_count=Count("id"),
            first_message=Min("created_at"),
            last_message=Max("created_at"),
        )
        .order_by("-last_message")
    )
    
    # Paginate
    paginator = ConversationPagination()
    page = paginator.paginate_queryset(list(sessions), request)
    
    data = [
        {
            "session_id": str(s["session_id"]),
            "course_id": str(s["course"]) if s["course"] else None,
            "course_topic": s["course__topic"],
            "course_name": s["course__course_name"],
            "message_count": s["message_count"],
            "first_message": s["first_message"],
            "last_message": s["last_message"],
            "date": s["last_message"].strftime("%Y-%m-%d") if s["last_message"] else None,
        }
        for s in page
    ]

    return Response({
        "success": True,
        "data": data,
        "pagination": {
            "page": paginator.page.number,
            "page_size": paginator.page_size,
            "total": paginator.page.paginator.count,
            "total_pages": paginator.page.paginator.num_pages,
        },
        "error": None,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def session_detail(request, session_id):
    """
    Return all messages in a session with metadata.
    
    Query params:
    - include_context: Include context info (default true)
    """
    try:
        sid = uuid.UUID(str(session_id))
    except ValueError:
        return _err("Invalid session_id")

    messages = Conversation.objects.filter(
        user=request.user, 
        session_id=sid
    ).order_by("created_at")
    
    if not messages.exists():
        return _err("Session not found.", status.HTTP_404_NOT_FOUND)
    
    # Get session metadata
    session_info = messages.values("session_id", "course", "course__topic").first()
    
    # Get first user message as title
    first_user_msg = messages.filter(role="user").first()
    title = first_user_msg.content[:50] + "..." if first_user_msg and len(first_user_msg.content) > 50 else (first_user_msg.content if first_user_msg else "New Chat")
    
    data = {
        "session": {
            "session_id": str(sid),
            "course_id": str(session_info["course"]) if session_info["course"] else None,
            "course_topic": session_info["course__topic"],
            "title": title,
            "message_count": messages.count(),
            "created_at": messages.first().created_at,
            "updated_at": messages.last().created_at,
            "date": messages.first().created_at.strftime("%Y-%m-%d") if messages.first().created_at else None,
        },
        "messages": ConversationSerializer(messages, many=True).data,
    }

    return _ok(data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def session_rename(request, session_id):
    """
    Rename a session by updating the title in Redis and database.

    Body:
    {
        "title": "New Title"
    }
    """
    try:
        sid = uuid.UUID(str(session_id))
    except ValueError:
        return _err("Invalid session_id")

    title = request.data.get("title", "").strip()
    if not title:
        return _err("Title is required")

    # Update Redis session metadata
    from services.chat.session import ChatSession
    session = ChatSession(
        user_id=str(request.user.id),
        session_id=str(sid),
        scope="global",
    )
    session.metadata["title"] = title
    async_to_sync(session.save_async)()

    # Update or create system message in database
    @sync_to_async
    def update_or_create_system_message():
        # Try to update existing system message
        system_msg = Conversation.objects.filter(
            user=request.user,
            session_id=sid,
            role="system"
        ).first()
        
        if system_msg:
            # Update existing system message
            system_msg.content = title
            system_msg.save()
            logger.info("Updated existing system message for session %s", session_id)
        else:
            # Create new system message
            Conversation.objects.create(
                user=request.user,
                session_id=sid,
                role="system",
                content=title,
                is_summarized=True,
            )
            logger.info("Created new system message for session %s", session_id)

    async_to_sync(update_or_create_system_message)()

    logger.info("Renamed session %s to: %s", session_id, title)

    return _ok({
        "session_id": str(sid),
        "title": title,
    })


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def session_archive(request, session_id):
    """
    Archive a session by adding an archived flag to metadata.
    
    Body:
    {
        "archived": true
    }
    """
    try:
        sid = uuid.UUID(str(session_id))
    except ValueError:
        return _err("Invalid session_id")

    archived = request.data.get("archived", True)

    # Update Redis session metadata
    from services.chat.session import ChatSession
    session = ChatSession(
        user_id=str(request.user.id),
        session_id=str(sid),
        scope="global",
    )
    session.metadata["archived"] = archived
    async_to_sync(session.save_async)()

    logger.info("Archived session %s: %s", session_id, archived)

    return _ok({
        "session_id": str(sid),
        "archived": archived,
    })


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def session_delete(request, session_id):
    """Delete all messages in a session."""
    try:
        sid = uuid.UUID(str(session_id))
    except ValueError:
        return _err("Invalid session_id")

    deleted, _ = Conversation.objects.filter(
        user=request.user, 
        session_id=sid
    ).delete()
    
    # Also clear Redis session
    from services.chat.session import ChatSession
    session = ChatSession(user_id=str(request.user.id), session_id=str(sid))
    session.clear()
    
    logger.info("Deleted session %s for user %s (%d messages)", sid, request.user.id, deleted)
    
    return _ok({"deleted_messages": deleted})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def course_history(request, course_id):
    """
    Get all conversations for a specific course.
    
    Query params:
    - limit: Max messages (default 100)
    - include_sessions: Group by session (default false)
    """
    limit = min(int(request.query_params.get("limit", 100)), 500)
    include_sessions = request.query_params.get("include_sessions", "false").lower() == "true"
    
    messages = Conversation.objects.filter(
        user=request.user,
        course_id=course_id,
    ).order_by("-created_at")[:limit]
    
    if include_sessions:
        # Group by session
        sessions = {}
        for msg in messages:
            sid = str(msg.session_id)
            if sid not in sessions:
                sessions[sid] = {
                    "session_id": sid,
                    "messages": [],
                    "created_at": msg.created_at,
                }
            sessions[sid]["messages"].append(ConversationSerializer(msg).data)
        
        return _ok(list(sessions.values()))
    
    return _ok(ConversationSerializer(messages, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_conversations(request):
    """
    Search conversations by content.
    
    Query params:
    - q: Search query (required)
    - course_id: Filter by course (optional)
    - limit: Max results (default 50)
    """
    query = request.query_params.get("q", "").strip()
    if not query:
        return _err("Search query required")
    
    limit = min(int(request.query_params.get("limit", 50)), 100)
    course_id = request.query_params.get("course_id")
    
    # Search in content
    queryset = Conversation.objects.filter(
        user=request.user,
        content__icontains=query,
    )
    
    if course_id:
        queryset = queryset.filter(course_id=course_id)
    
    messages = queryset.order_by("-created_at")[:limit]
    
    return _ok({
        "query": query,
        "total": queryset.count(),
        "results": ConversationSerializer(messages, many=True).data,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_session_title(request, session_id):
    """
    Set a custom title for a session.

    Body: {"title": "My Chat Title"}
    """
    try:
        sid = uuid.UUID(str(session_id))
    except ValueError:
        return _err("Invalid session_id")

    title = request.data.get("title", "").strip()
    if not title:
        return _err("Title required")

    if len(title) > 100:
        return _err("Title too long (max 100 chars)")

    # Store title in Redis session
    from services.chat.session import ChatSession
    session = ChatSession(user_id=str(request.user.id), session_id=str(sid))
    session.set_title(title)

    return _ok({"session_id": str(sid), "title": title})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def session_save_generating_courses(request, session_id):
    """
    Save generating course IDs to session metadata in Redis.

    This is called when user navigates away from chat to persist
    which courses are being generated in this session.

    Body:
    {
        "course_ids": ["uuid1", "uuid2", ...]
    }
    """
    try:
        sid = uuid.UUID(str(session_id))
    except ValueError:
        return _err("Invalid session_id")

    course_ids = request.data.get("course_ids", [])
    if not course_ids:
        return _err("course_ids required")

    # Get session from Redis
    from services.chat.session import ChatSession
    session = ChatSession(
        user_id=str(request.user.id),
        session_id=str(sid),
        scope="global",
    )

    # Load existing session to get metadata
    redis_client = session.get_redis()
    key = f"chat:session:{request.user.id}:{sid}"
    data = redis_client.get(key)

    if data:
        try:
            parsed = json.loads(data)
            session.metadata = parsed.get("metadata", {})
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to parse session data: %s", exc)

    # Update generating courses in metadata
    if "generating_courses" not in session.metadata:
        session.metadata["generating_courses"] = {}

    # Add course IDs (backend will fetch details from progress tracking)
    for course_id in course_ids:
        if course_id not in session.metadata["generating_courses"]:
            session.metadata["generating_courses"][course_id] = {
                "status": "generating",
                "saved_at": timezone.now().isoformat(),
            }

    # Save back to Redis
    session.save()

    logger.info("Saved generating courses to session %s: %s", session_id, course_ids)

    return _ok({
        "session_id": str(sid),
        "generating_courses": list(session.metadata["generating_courses"].keys()),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_session_title(request, session_id):
    """
    Get the current title for a session.
    
    This is useful for polling title updates after sending the first message.
    """
    try:
        sid = uuid.UUID(str(session_id))
    except ValueError:
        return _err("Invalid session_id")

    # Try to get title from Conversation
    from apps.conversations.models import Conversation
    
    # First check for a non-placeholder title
    conversation = Conversation.objects.filter(
        user=request.user,
        session_id=sid,
        role="system",
    ).exclude(content="[Session created]").first()
    
    if conversation:
        return _ok({"session_id": str(sid), "title": conversation.content})
    
    # Check placeholder
    placeholder = Conversation.objects.filter(
        user=request.user,
        session_id=sid,
        role="system",
        content="[Session created]"
    ).first()
    
    if placeholder:
        return _ok({"session_id": str(sid), "title": "[Session created]"})
    
    # Try Redis session
    from services.chat.session import ChatSession
    from asgiref.sync import async_to_sync
    
    session = async_to_sync(ChatSession.get_or_create)(
        user_id=str(request.user.id),
        session_id=str(sid),
        scope="global"
    )
    title = session.metadata.get("title")
    if title:
        return _ok({"session_id": str(sid), "title": title})
    
    return _ok({"session_id": str(sid), "title": "New Chat"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def conversation_stats(request):
    """
    Get conversation statistics for the user.
    
    Returns:
    - Total messages
    - Total sessions
    - Messages by role
    - Activity over time
    """
    from django.db.models.functions import TruncDate
    
    messages = Conversation.objects.filter(user=request.user)
    
    # Basic stats
    total_messages = messages.count()
    total_sessions = messages.values("session_id").distinct().count()
    
    # By role
    by_role = dict(
        messages.values_list("role")
        .annotate(count=Count("id"))
        .order_by("role")
    )
    
    # Activity over last 30 days
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    activity = (
        messages.filter(created_at__gte=thirty_days_ago)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    
    return _ok({
        "total_messages": total_messages,
        "total_sessions": total_sessions,
        "by_role": by_role,
        "activity_30_days": [
            {"date": str(a["date"]), "count": a["count"]}
            for a in activity
        ],
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def persist_conversation(request):
    """
    Persist a conversation (user message + AI response) to the database.
    
    This is used by the course management feature to save CRUD-generated
    messages to the database so they appear in chat history sidebar.
    
    Body:
    {
        "session_id": "uuid",
        "user_message": "List all courses",
        "ai_response": "Here are your courses...",
        "course_id": "uuid" (optional)
    }
    
    Returns:
    {
        "success": true,
        "session_id": "uuid"
    }
    """
    session_id = request.data.get("session_id")
    user_message = request.data.get("user_message", "").strip()
    ai_response = request.data.get("ai_response", "").strip()
    course_id = request.data.get("course_id")
    
    # Validate required fields
    if not session_id:
        return _err("session_id is required")
    
    if not user_message:
        return _err("user_message is required")
    
    if not ai_response:
        return _err("ai_response is required")
    
    try:
        sid = uuid.UUID(str(session_id))
    except ValueError:
        return _err("Invalid session_id")
    
    # Validate course_id if provided
    if course_id:
        try:
            course_id = uuid.UUID(str(course_id))
        except ValueError:
            return _err("Invalid course_id")
    else:
        course_id = None
    
    # Check if this is the first message in the session
    existing_messages = Conversation.objects.filter(
        user=request.user,
        session_id=sid
    )
    is_first_message = not existing_messages.exists()
    
    # Create placeholder system message if this is the first message
    if is_first_message:
        Conversation.objects.create(
            user=request.user,
            session_id=sid,
            role="system",
            content="[Session created]",
            course_id=course_id,
            is_summarized=True,
        )
        logger.info(
            "Created placeholder system message for session: user=%s session_id=%s",
            request.user.id, session_id
        )
    
    # Save user message
    Conversation.objects.create(
        user=request.user,
        session_id=sid,
        role="user",
        content=user_message,
        course_id=course_id,
    )
    
    # Save AI response
    Conversation.objects.create(
        user=request.user,
        session_id=sid,
        role="assistant",
        content=ai_response,
        course_id=course_id,
    )
    
    logger.info(
        "Persisted conversation: user=%s session_id=%s user_msg_len=%d ai_response_len=%d",
        request.user.id, session_id, len(user_message), len(ai_response)
    )
    
    return _ok({
        "success": True,
        "session_id": str(sid),
        "message_count": 2 if is_first_message else 2,  # Always 2 new messages
    })
