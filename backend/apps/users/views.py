"""
Users app — views.
Endpoints:
  GET  /api/users/me/
  PUT  /api/users/me/
  GET  /api/users/me/knowledge-state/
  GET  /api/users/me/knowledge-state/{concept}/
  PUT  /api/users/me/knowledge-state/{concept}/
  GET  /api/users/me/quiz-history/
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from .models import UserKnowledgeState
from .serializers import (
    UserSerializer,
    UserUpdateSerializer,
    UserKnowledgeStateSerializer,
    UserKnowledgeStateUpdateSerializer,
)

logger = logging.getLogger(__name__)


def _ok(data, status_code=status.HTTP_200_OK):
    return Response({"success": True, "data": data, "error": None}, status=status_code)


def _err(msg, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"success": False, "data": None, "error": msg}, status=status_code)


# ──────────────────────────────────────────────
# /api/users/me/
# ──────────────────────────────────────────────
@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def me(request: Request):
    user = request.user
    if request.method == "GET":
        return _ok(UserSerializer(user).data)

    # PUT
    serializer = UserUpdateSerializer(user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return _ok(UserSerializer(user).data)
    return _err(serializer.errors)


# ──────────────────────────────────────────────
# /api/users/me/knowledge-state/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def knowledge_state_list(request: Request):
    states = UserKnowledgeState.objects.filter(user=request.user)
    return _ok(UserKnowledgeStateSerializer(states, many=True).data)


# ──────────────────────────────────────────────
# /api/users/me/knowledge-state/{concept}/
# ──────────────────────────────────────────────
@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def knowledge_state_detail(request: Request, concept: str):
    try:
        state = UserKnowledgeState.objects.get(user=request.user, concept=concept)
    except UserKnowledgeState.DoesNotExist:
        if request.method == "GET":
            return _err("Concept not found.", status.HTTP_404_NOT_FOUND)
        # PUT — create it
        state = UserKnowledgeState(user=request.user, concept=concept)

    if request.method == "GET":
        return _ok(UserKnowledgeStateSerializer(state).data)

    # PUT
    serializer = UserKnowledgeStateUpdateSerializer(state, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return _ok(UserKnowledgeStateSerializer(state).data)
    return _err(serializer.errors)


# ──────────────────────────────────────────────
# /api/users/me/quiz-history/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def quiz_history(request: Request):
    """Return all quiz attempts for the authenticated user."""
    from apps.quizzes.models import QuizAttempt
    from apps.quizzes.serializers import QuizAttemptSerializer

    attempts = QuizAttempt.objects.filter(user=request.user).select_related("question")
    return _ok(QuizAttemptSerializer(attempts, many=True).data)
