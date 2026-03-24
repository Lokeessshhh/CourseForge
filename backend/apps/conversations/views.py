"""
Conversations app — views.
Endpoints:
  GET    /api/conversations/
  GET    /api/conversations/{session_id}/
  DELETE /api/conversations/{session_id}/
"""
import logging
import uuid
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Conversation
from .serializers import ConversationSerializer

logger = logging.getLogger(__name__)


def _ok(data, status_code=status.HTTP_200_OK):
    return Response({"success": True, "data": data, "error": None}, status=status_code)


def _err(msg, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"success": False, "data": None, "error": msg}, status=status_code)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def conversation_list(request):
    """Return distinct sessions for the authenticated user."""
    sessions = (
        Conversation.objects
        .filter(user=request.user)
        .values("session_id", "course", "created_at")
        .order_by("session_id", "-created_at")
        .distinct("session_id")
    )
    data = [
        {"session_id": str(s["session_id"]), "course_id": str(s["course"]) if s["course"] else None}
        for s in sessions
    ]
    return _ok(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def conversation_detail(request, session_id):
    """Return all messages in a session."""
    try:
        sid = uuid.UUID(str(session_id))
    except ValueError:
        return _err("Invalid session_id")

    messages = Conversation.objects.filter(user=request.user, session_id=sid).order_by("created_at")
    if not messages.exists():
        return _err("Session not found.", status.HTTP_404_NOT_FOUND)
    return _ok(ConversationSerializer(messages, many=True).data)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def conversation_delete(request, session_id):
    """Delete all messages in a session."""
    try:
        sid = uuid.UUID(str(session_id))
    except ValueError:
        return _err("Invalid session_id")

    deleted, _ = Conversation.objects.filter(user=request.user, session_id=sid).delete()
    return _ok({"deleted_messages": deleted})
