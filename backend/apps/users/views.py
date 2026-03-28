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
from datetime import timedelta
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
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


class UserProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request):
        from django.utils import timezone
        from apps.courses.models import CourseProgress, WeeklyTestAttempt
        from apps.quizzes.models import QuizAttempt

        progress_qs = CourseProgress.objects.filter(user=request.user).select_related("course")

        if not progress_qs.exists():
            today = timezone.localdate()
            start = today - timedelta(days=27)
            calendar = []
            cursor = start
            for _ in range(4):
                week = []
                for _ in range(7):
                    week.append(False)
                    cursor += timedelta(days=1)
                calendar.append(week)

            payload = {
                "overall": {
                    "total_days_completed": 0,
                    "courses_active": 0,
                    "courses_completed": 0,
                    "longest_streak": 0,
                    "current_streak": 0,
                    "avg_quiz_score": 0.0,
                    "avg_test_score": 0.0,
                    "total_study_hours": 0.0,
                },
                "courses": [],
                "concepts": [],
                "quiz_history": [],
                "streak_calendar": {"weeks": calendar},
            }
            return _ok(payload)

        total_days_completed = 0
        courses_active = 0
        courses_completed = 0
        longest_streak = 0
        total_study_minutes = 0
        quiz_scores = []
        test_scores = []

        courses_payload = []
        for p in progress_qs:
            total_days_completed += p.completed_days
            total_study_minutes += p.total_study_time
            longest_streak = max(longest_streak, p.streak_days or 0)
            if p.completed_at:
                courses_completed += 1
            else:
                courses_active += 1

            if p.avg_quiz_score is not None:
                quiz_scores.append(p.avg_quiz_score)
            if p.avg_test_score is not None:
                test_scores.append(p.avg_test_score)

            weeks_payload = []
            for week in p.course.weeks.all().prefetch_related("days"):
                completed_days = week.days.filter(is_completed=True).count()
                test_attempt = WeeklyTestAttempt.objects.filter(
                    user=request.user,
                    course=p.course,
                    week_number=week.week_number,
                    passed=True,
                ).order_by("-attempted_at").first()

                weeks_payload.append(
                    {
                        "week": week.week_number,
                        "completed_days": completed_days,
                        "total_days": 5,
                        "test_score": test_attempt.percentage if test_attempt else None,
                    }
                )

            courses_payload.append(
                {
                    "course_id": str(p.course.id),
                    "course_name": p.course.course_name,
                    "topic": p.course.topic,
                    "progress": p.overall_percentage,
                    "weeks": weeks_payload,
                }
            )

        avg_quiz_score = round(sum(quiz_scores) / len(quiz_scores), 1) if quiz_scores else 0.0
        avg_test_score = round(sum(test_scores) / len(test_scores), 1) if test_scores else 0.0

        # Concept mastery
        concepts = UserKnowledgeState.objects.filter(user=request.user).order_by("-updated_at")
        concepts_payload = [
            {
                "concept": c.concept,
                "mastery": int(round((c.confidence_score or 0.0) * 100)),
                "practiced_count": c.times_practiced,
                "last_practiced": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in concepts
        ]

        # Quiz history (best-effort)
        attempts = (
            QuizAttempt.objects.filter(user=request.user)
            .select_related("question", "question__course")
            .order_by("-attempted_at")[:50]
        )
        quiz_history_payload = [
            {
                "date": a.attempted_at.date().isoformat(),
                "course": getattr(a.question.course, "course_name", ""),
                "day": f"W{a.question.week_number or 0}D{a.question.day_number or 0}",
                "score": 100 if a.is_correct else 0,
                "passed": bool(a.is_correct),
            }
            for a in attempts
        ]

        # Streak calendar (full 52 weeks)
        studied_dates = set()
        for p in progress_qs:
            if p.last_activity:
                studied_dates.add(p.last_activity.date())

        today = timezone.localdate()
        calendar = []
        
        # Generate 52 weeks of data
        for w in range(52):
            week_data = []
            for d in range(7):
                # Calculate date for this cell (GitHub style: columns are weeks, rows are days)
                # current date - (weeks remaining * 7) - (days remaining in current week)
                date_offset = (51 - w) * 7 + (6 - d)
                cell_date = today - timedelta(days=date_offset)
                week_data.append(cell_date in studied_dates)
            calendar.append(week_data)

        payload = {
            "overall": {
                "total_days_completed": total_days_completed,
                "courses_active": courses_active,
                "courses_completed": courses_completed,
                "longest_streak": longest_streak,
                "current_streak": longest_streak,
                "avg_quiz_score": avg_quiz_score,
                "avg_test_score": avg_test_score,
                "total_study_hours": round(total_study_minutes / 60, 1),
            },
            "courses": courses_payload,
            "concepts": concepts_payload,
            "quiz_history": quiz_history_payload,
            "streak_calendar": {"weeks": calendar},
        }

        return _ok(payload)


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
