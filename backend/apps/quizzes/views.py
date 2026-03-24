"""
Quizzes app — views.
Endpoints:
  GET  /api/courses/{id}/weeks/{w}/days/{d}/quiz/
  POST /api/courses/{id}/weeks/{w}/days/{d}/quiz/submit/
  GET  /api/courses/{id}/weeks/{w}/days/{d}/quiz/results/
  GET  /api/users/me/quiz-history/  (in users app)
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses.models import Course, WeekPlan, DayPlan
from .models import QuizQuestion, QuizAttempt
from .serializers import (
    QuizQuestionSerializer,
    QuizQuestionDetailSerializer,
    QuizAttemptSerializer,
    QuizSubmitSerializer,
)

logger = logging.getLogger(__name__)


def _ok(data, status_code=status.HTTP_200_OK):
    return Response({"success": True, "data": data, "error": None}, status=status_code)


def _err(msg, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"success": False, "data": None, "error": msg}, status=status_code)


def _get_day(user, course_id, week_number, day_number):
    try:
        course = Course.objects.get(id=course_id, user=user)
        week = course.weeks.get(week_number=week_number)
        day = week.days.get(day_number=day_number)
        return course, week, day
    except (Course.DoesNotExist, WeekPlan.DoesNotExist, DayPlan.DoesNotExist):
        return None, None, None


# ──────────────────────────────────────────────
# GET /api/courses/{id}/weeks/{w}/days/{d}/quiz/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def quiz_list(request, course_id, week_number, day_number):
    course, week, day = _get_day(request.user, course_id, week_number, day_number)
    if not day:
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    questions = QuizQuestion.objects.filter(
        course=course, week_number=week_number, day_number=day_number
    )
    return _ok(QuizQuestionSerializer(questions, many=True).data)


# ──────────────────────────────────────────────
# POST /api/courses/{id}/weeks/{w}/days/{d}/quiz/submit/
# ──────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def quiz_submit(request, course_id, week_number, day_number):
    course, week, day = _get_day(request.user, course_id, week_number, day_number)
    if not day:
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    serializer = QuizSubmitSerializer(data=request.data)
    if not serializer.is_valid():
        return _err(serializer.errors)

    answers = serializer.validated_data["answers"]
    results = []
    correct_count = 0

    for answer in answers:
        q_id = answer.get("question_id")
        user_answer = answer.get("answer", "")
        try:
            question = QuizQuestion.objects.get(id=q_id, course=course)
        except QuizQuestion.DoesNotExist:
            continue

        # Check correctness
        is_correct = _evaluate_answer(question, user_answer)
        if is_correct:
            correct_count += 1

        attempt, _ = QuizAttempt.objects.update_or_create(
            user=request.user,
            question=question,
            defaults={"user_answer": user_answer, "is_correct": is_correct},
        )
        results.append({
            "question_id": str(q_id),
            "is_correct": is_correct,
            "correct_answer": question.correct_answer,
            "explanation": question.explanation,
        })

    total = len(answers)
    score_pct = round((correct_count / total * 100) if total > 0 else 0, 1)

    # Unlock next day if score > 50%
    if score_pct > 50:
        _unlock_next_day(course, week, day)

    # Update user knowledge state
    _update_knowledge_state(request.user, course, answers, results)

    return _ok({
        "score": score_pct,
        "correct": correct_count,
        "total": total,
        "results": results,
    })


# ──────────────────────────────────────────────
# GET /api/courses/{id}/weeks/{w}/days/{d}/quiz/results/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def quiz_results(request, course_id, week_number, day_number):
    course, week, day = _get_day(request.user, course_id, week_number, day_number)
    if not day:
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    attempts = QuizAttempt.objects.filter(
        user=request.user,
        question__course=course,
        question__week_number=week_number,
        question__day_number=day_number,
    ).select_related("question")

    data = [
        {
            "question_id": str(a.question_id),
            "question_text": a.question.question_text,
            "user_answer": a.user_answer,
            "is_correct": a.is_correct,
            "correct_answer": a.question.correct_answer,
            "explanation": a.question.explanation,
        }
        for a in attempts
    ]
    return _ok(data)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _evaluate_answer(question: QuizQuestion, user_answer: str) -> bool:
    """
    Evaluate answer correctness.
    For 'code' questions, delegates to Judge0.
    """
    if question.question_type == "code":
        try:
            from services.external.judge0 import Judge0Client
            client = Judge0Client()
            result = client.execute(
                code=user_answer,
                expected_output=question.correct_answer or "",
            )
            return result.get("status", {}).get("id") == 3  # 3 = Accepted
        except Exception as exc:
            logger.warning("Judge0 evaluation failed: %s", exc)
            return False

    # MCQ / short_answer — case-insensitive exact match
    return (user_answer or "").strip().lower() == (question.correct_answer or "").strip().lower()


def _unlock_next_day(course, week, day):
    """Mark the next day as completable (is_completed flag unlocking logic)."""
    from apps.courses.models import DayPlan, WeekPlan
    from django.utils import timezone

    next_day = DayPlan.objects.filter(
        week_plan=week, day_number=day.day_number + 1
    ).first()

    if not next_day:
        # Try first day of next week
        try:
            next_week = course.weeks.get(week_number=week.week_number + 1)
            next_day = next_week.days.order_by("day_number").first()
        except WeekPlan.DoesNotExist:
            return  # Course complete

    if next_day:
        # "Unlock" == we allow content_completed=True on the current day
        day.content_completed = True
        day.completed_at = timezone.now()
        day.save(update_fields=["content_completed", "completed_at"])


def _update_knowledge_state(user, course, answers, results):
    """Update confidence scores for each concept tag in answered questions."""
    from apps.users.models import UserKnowledgeState

    for answer, result in zip(answers, results):
        q_id = answer.get("question_id")
        try:
            question = QuizQuestion.objects.get(id=q_id)
        except QuizQuestion.DoesNotExist:
            continue

        for concept in question.concept_tags or []:
            state, _ = UserKnowledgeState.objects.get_or_create(
                user=user,
                concept=concept,
                defaults={"confidence_score": 0.0, "times_practiced": 0},
            )
            state.times_practiced += 1
            if result["is_correct"]:
                state.confidence_score = min(1.0, state.confidence_score + 0.1)
            else:
                state.confidence_score = max(0.0, state.confidence_score - 0.05)
                state.last_error = answer.get("answer", "")
            state.save(update_fields=["confidence_score", "times_practiced", "last_error"])
