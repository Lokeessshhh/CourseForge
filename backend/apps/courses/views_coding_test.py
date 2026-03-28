"""
Coding test views with Judge0 integration.
Production-grade views with comprehensive error handling and logging.
"""
import logging
from datetime import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import CodingTest, CodingTestAttempt

logger = logging.getLogger(__name__)


def _ok(data, status_code=status.HTTP_200_OK):
    """Standard success response."""
    return Response({"success": True, "data": data, "error": None}, status=status_code)


def _err(msg, status_code=status.HTTP_400_BAD_REQUEST):
    """Standard error response."""
    return Response({"success": False, "data": None, "error": msg}, status=status_code)


# ──────────────────────────────────────────────
# GET /api/courses/{id}/weeks/{w}/coding-test/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_coding_test(request, course_id, week_number):
    """Get coding test challenges for a week."""
    try:
        from apps.courses.models import Course, WeekPlan
        course = Course.objects.get(id=course_id, user=request.user)
        week = course.weeks.get(week_number=week_number)
    except (Course.DoesNotExist, WeekPlan.DoesNotExist):
        logger.error(f"Coding test: Course or week not found for course {course_id}, week {week_number}")
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    if not week.test_unlocked:
        logger.warning(f"Coding test: Week {week_number} test not unlocked for course {course_id}")
        return _err("Weekly test not unlocked yet.", status.HTTP_403_FORBIDDEN)

    try:
        test = CodingTest.objects.get(course=course, week_number=week_number)
    except CodingTest.DoesNotExist:
        logger.error(f"Coding test: Coding test not found for course {course_id}, week {week_number}")
        return _err("Coding test not generated yet.", status.HTTP_400_BAD_REQUEST)

    logger.info(f"Coding test: Retrieved test for course {course_id}, week {week_number}, {len(test.problems)} problems")
    logger.info(f"Coding test data: {test.problems}")

    return _ok({
        "week_number": week_number,
        "total_problems": test.total_problems,
        "problems": test.problems,
    })


# ──────────────────────────────────────────────
# POST /api/courses/{id}/weeks/{w}/coding-test/start/
# ──────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_coding_test(request, course_id, week_number):
    """Start a coding test attempt."""
    try:
        from apps.courses.models import Course, WeekPlan
        course = Course.objects.get(id=course_id, user=request.user)
        week = course.weeks.get(week_number=week_number)
    except (Course.DoesNotExist, WeekPlan.DoesNotExist):
        logger.error("Start coding test: Course or week not found")
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    if not week.test_unlocked:
        logger.warning(f"Start coding test: Week {week_number} test not unlocked")
        return _err("Weekly test not unlocked yet.", status.HTTP_403_FORBIDDEN)

    try:
        test = CodingTest.objects.get(course=course, week_number=week_number)
    except CodingTest.DoesNotExist:
        logger.error("Start coding test: Coding test not found")
        return _err("Coding test not generated yet.", status.HTTP_400_BAD_REQUEST)

    # Check if there's an existing incomplete attempt
    existing_attempt = CodingTestAttempt.objects.filter(
        user=request.user,
        coding_test=test,
        passed=False
    ).order_by('-attempted_at').first()

    if existing_attempt:
        logger.info(f"Start coding test: Found existing incomplete attempt {existing_attempt.id}")
        return _ok({
            "attempt_id": str(existing_attempt.id),
            "started_at": existing_attempt.attempted_at.isoformat(),
            "is_resume": True,
        })

    # Create new attempt
    attempt = CodingTestAttempt.objects.create(
        user=request.user,
        coding_test=test,
        total=test.total_problems,
        score=0,
        percentage=0.0,
    )

    logger.info(f"Start coding test: Created new attempt {attempt.id} for course {course_id}, week {week_number}")

    return _ok({
        "attempt_id": str(attempt.id),
        "started_at": attempt.attempted_at.isoformat(),
        "is_resume": False,
    })


# ──────────────────────────────────────────────
# POST /api/courses/{id}/weeks/{w}/coding-test/execute/
# ──────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def execute_coding_challenge(request, course_id, week_number):
    """Execute code for a coding challenge using Judge0."""
    from services.judge0.client import get_judge0_client

    try:
        from apps.courses.models import Course, WeekPlan
        course = Course.objects.get(id=course_id, user=request.user)
        WeekPlan.objects.get(course=course, week_number=week_number)
    except (Course.DoesNotExist, WeekPlan.DoesNotExist):
        logger.error("Execute coding challenge: Course or week not found")
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    attempt_id = request.data.get("attempt_id")
    challenge_index = request.data.get("challenge_index")
    source_code = request.data.get("source_code")
    language = request.data.get("language", "python")

    if not attempt_id or challenge_index is None or not source_code:
        logger.error(f"Execute coding challenge: Missing required fields - attempt_id={attempt_id}, challenge_index={challenge_index}, source_code={bool(source_code)}")
        return _err("Missing required fields: attempt_id, challenge_index, source_code", status.HTTP_400_BAD_REQUEST)

    try:
        test = CodingTest.objects.get(course=course, week_number=week_number)
    except CodingTest.DoesNotExist:
        logger.error("Execute coding challenge: Coding test not found")
        return _err("Coding test not found.", status.HTTP_400_BAD_REQUEST)

    try:
        attempt = CodingTestAttempt.objects.get(id=attempt_id, user=request.user)
    except CodingTestAttempt.DoesNotExist:
        logger.error(f"Execute coding challenge: Attempt {attempt_id} not found for user {request.user.id}")
        return _err("Attempt not found.", status.HTTP_404_NOT_FOUND)

    if attempt.completed_at:
        logger.warning(f"Execute coding challenge: Attempt {attempt_id} already completed")
        return _err("Attempt already completed.", status.HTTP_400_BAD_REQUEST)

    # Get challenge details
    if challenge_index >= len(test.challenges):
        logger.error("Execute coding challenge: Invalid challenge_index")
        return _err("Invalid challenge index.", status.HTTP_400_BAD_REQUEST)

    challenge = test.challenges[challenge_index]
    expected_output = challenge.get("expected_output", "")
    stdin = challenge.get("stdin", "")

    logger.info(f"Execute coding challenge: Executing challenge {challenge_index} for attempt {attempt_id}, language={language}")

    # Execute code using Judge0
    judge0_client = get_judge0_client()
    result = judge0_client.execute_code(
        source_code=source_code,
        language=language,
        stdin=stdin,
        expected_output=expected_output if expected_output else None,
        timeout=30,
    )

    logger.info(f"Execute coding challenge: Execution completed - status={result.get('status')}, token={result.get('token')}")

    # Check if correct
    is_correct = result.get("status") == "accepted"

    return _ok({
        "execution_id": str(attempt.id),
        "status": result.get("status"),
        "stdout": result.get("stdout"),
        "stderr": result.get("stderr"),
        "compile_output": result.get("compile_output"),
        "execution_time": result.get("time"),
        "memory_used": result.get("memory"),
        "is_correct": is_correct,
    })


# ──────────────────────────────────────────────
# POST /api/courses/{id}/weeks/{w}/coding-test/submit/
# ──────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_coding_test(request, course_id, week_number):
    """Submit coding test results and calculate score."""
    try:
        from apps.courses.models import Course
        course = Course.objects.get(id=course_id, user=request.user)
        Course.objects.get(id=course_id, user=request.user).weeks.get(week_number=week_number)
    except Course.DoesNotExist:
        logger.error("Submit coding test: Course not found")
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    attempt_id = request.data.get("attempt_id")
    challenge_results = request.data.get("challenge_results", [])

    if not attempt_id:
        logger.error("Submit coding test: Missing attempt_id")
        return _err("Missing attempt_id.", status.HTTP_400_BAD_REQUEST)

    try:
        CodingTest.objects.get(course=course, week_number=week_number)
    except CodingTest.DoesNotExist:
        logger.error("Submit coding test: Coding test not found")
        return _err("Coding test not found.", status.HTTP_400_BAD_REQUEST)

    try:
        attempt = CodingTestAttempt.objects.get(id=attempt_id, user=request.user)
    except CodingTestAttempt.DoesNotExist:
        logger.error(f"Submit coding test: Attempt {attempt_id} not found for user {request.user.id}")
        return _err("Attempt not found.", status.HTTP_404_NOT_FOUND)

    if attempt.completed_at:
        logger.warning(f"Submit coding test: Attempt {attempt_id} already completed")
        return _err("Attempt already completed.", status.HTTP_400_BAD_REQUEST)

    # Calculate score
    total_challenges = len(challenge_results)
    correct_challenges = sum(1 for r in challenge_results if r.get("is_correct", False))
    percentage = round((correct_challenges / total_challenges * 100), 1) if total_challenges > 0 else 0
    passed = percentage >= 60

    logger.info(f"Submit coding test: Score={correct_challenges}/{total_challenges}, Percentage={percentage}%, Passed={passed}")

    # Update attempt
    attempt.score = correct_challenges
    attempt.total_challenges = total_challenges
    attempt.percentage = percentage
    attempt.passed = passed
    attempt.challenge_results = challenge_results
    attempt.completed_at = timezone.now()
    attempt.time_taken = (attempt.completed_at - attempt.started_at).total_seconds()
    attempt.save()

    # Complete week if passed
    next_week_unlocked = False
    if passed:
        from services.progress.tracker import get_tracker
        tracker = get_tracker()
        result = tracker.complete_week(
            user_id=str(request.user.id),
            course_id=course_id,
            week_number=week_number,
            test_score=percentage,
        )
        next_week_unlocked = result.get("next_week_unlocked", False)
        logger.info(f"Submit coding test: Week completed, next_week_unlocked={next_week_unlocked}")

    return _ok({
        "score": correct_challenges,
        "total_challenges": total_challenges,
        "percentage": percentage,
        "passed": passed,
        "next_week_unlocked": next_week_unlocked,
        "challenge_results": challenge_results,
        "time_taken": attempt.time_taken,
    })
