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
# GET /api/courses/{id}/weeks/{w}/coding-test/{test_number}/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_coding_test(request, course_id, week_number, test_number=1):
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
        return _err("Weekly test not unlocked yet. Complete all 5 days and pass the weekly MCQ test first.", status.HTTP_403_FORBIDDEN)

    # Check if specific coding test is unlocked
    if test_number == 1 and not week.coding_test_1_unlocked:
        return _err("Coding Test 1 not unlocked yet. Pass the weekly MCQ test first.", status.HTTP_403_FORBIDDEN)
    elif test_number == 2 and not week.coding_test_2_unlocked:
        return _err("Coding Test 2 not unlocked yet. Complete Coding Test 1 first.", status.HTTP_403_FORBIDDEN)

    try:
        test = CodingTest.objects.get(course=course, week_number=week_number, test_number=test_number)
    except CodingTest.DoesNotExist:
        logger.error(f"Coding test: Coding test {test_number} not found for course {course_id}, week {week_number}")
        return _err(f"Coding test {test_number} not generated yet. Please wait or contact support.", status.HTTP_400_BAD_REQUEST)

    logger.info(f"Coding test: Retrieved test {test_number} for course {course_id}, week {week_number}, {len(test.problems)} problems")
    logger.info(f"Coding test data: {test.problems}")

    return _ok({
        "week_number": week_number,
        "test_number": test_number,
        "total_problems": test.total_problems,
        "problems": test.problems,
    })


# ──────────────────────────────────────────────
# POST /api/courses/{id}/weeks/{w}/coding-test/{test_number}/start/
# ──────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_coding_test(request, course_id, week_number, test_number=1):
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

    # Check if specific coding test is unlocked
    if test_number == 1 and not week.coding_test_1_unlocked:
        return _err("Coding Test 1 not unlocked yet.", status.HTTP_403_FORBIDDEN)
    elif test_number == 2 and not week.coding_test_2_unlocked:
        return _err("Coding Test 2 not unlocked yet.", status.HTTP_403_FORBIDDEN)

    try:
        test = CodingTest.objects.get(course=course, week_number=week_number, test_number=test_number)
    except CodingTest.DoesNotExist:
        logger.error("Start coding test: Coding test not found")
        return _err("Coding test not generated yet.", status.HTTP_400_BAD_REQUEST)

    # Check if there's an existing incomplete attempt (score=0 means never submitted)
    existing_attempt = CodingTestAttempt.objects.filter(
        user=request.user,
        coding_test=test,
    ).order_by('-attempted_at').first()

    # If existing attempt was never submitted (score=0), allow resume
    if existing_attempt and existing_attempt.score == 0:
        logger.info(f"Start coding test: Found existing incomplete attempt {existing_attempt.id}")
        return _ok({
            "attempt_id": str(existing_attempt.id),
            "started_at": existing_attempt.attempted_at.isoformat(),
            "is_resume": True,
        })

    # If existing attempt was submitted (score > 0), create a new attempt for retake
    if existing_attempt and existing_attempt.score > 0:
        logger.info(f"Start coding test: Previous attempt {existing_attempt.id} was completed (score={existing_attempt.score}, passed={existing_attempt.passed}), creating new attempt for retake")

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
        "previous_score": existing_attempt.score if existing_attempt else None,
        "previous_passed": existing_attempt.passed if existing_attempt else None,
    })


# ──────────────────────────────────────────────
# POST /api/courses/{id}/weeks/{w}/coding-test/execute/
# ──────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def execute_coding_challenge(request, course_id, week_number):
    """Execute code for a coding challenge using local executor."""
    try:
        from apps.courses.models import Course, WeekPlan
        course = Course.objects.get(id=course_id, user=request.user)
        WeekPlan.objects.get(course=course, week_number=week_number)
    except (Course.DoesNotExist, WeekPlan.DoesNotExist):
        logger.error("Execute coding challenge: Course or week not found")
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    attempt_id = request.data.get("attempt_id")
    challenge_index = request.data.get("challenge_index") or request.data.get("problem_index")
    source_code = request.data.get("source_code")
    language = request.data.get("language", "python3")

    if not attempt_id or challenge_index is None or not source_code:
        logger.error(f"Execute coding challenge: Missing required fields - attempt_id={attempt_id}, challenge_index={challenge_index}, source_code={bool(source_code)}")
        return _err("Missing required fields: attempt_id, challenge_index (or problem_index), source_code", status.HTTP_400_BAD_REQUEST)

    try:
        attempt = CodingTestAttempt.objects.get(id=attempt_id, user=request.user)
    except CodingTestAttempt.DoesNotExist:
        logger.error(f"Execute coding challenge: Attempt {attempt_id} not found for user {request.user.id}")
        return _err("Attempt not found.", status.HTTP_404_NOT_FOUND)

    # Check if attempt is already completed (has a score)
    if attempt.score is not None and attempt.score > 0:
        logger.warning(f"Execute coding challenge: Attempt {attempt_id} already completed")
        return _err("Attempt already completed.", status.HTTP_400_BAD_REQUEST)

    # Get the coding test from the attempt (avoids ambiguity with multiple tests)
    test = attempt.coding_test

    # Get challenge details (support both 'problems' and 'challenges' field names)
    challenges = test.problems if hasattr(test, 'problems') and test.problems else test.challenges
    if challenge_index >= len(challenges):
        logger.error("Execute coding challenge: Invalid challenge_index")
        return _err("Invalid challenge index.", status.HTTP_400_BAD_REQUEST)

    challenge = challenges[challenge_index]
    expected_output = challenge.get("expected_output", "")
    stdin = challenge.get("stdin", "")

    logger.info(f"Execute coding challenge: Executing challenge {challenge_index} for attempt {attempt_id}, language={language}, test_number={test.test_number}")

    # Execute code using local executor
    from services.code_executor import get_code_executor
    executor = get_code_executor()
    result = executor.execute_code(
        source_code=source_code,
        language=language,
        stdin=stdin,
        expected_output=expected_output,
        timeout=30,
    )

    logger.info(f"Execute coding challenge: Execution completed - status={result.get('status')}")

    # Check if correct
    is_correct = result.get("status") == "accepted"

    # Save execution result to attempt's submissions
    if not attempt.submissions:
        attempt.submissions = {}
    
    # Store result for this challenge index
    attempt.submissions[str(challenge_index)] = {
        "problem_index": challenge_index,
        "is_correct": is_correct,
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "compile_output": result.get("compile_output", ""),
        "status": result.get("status"),
        "execution_time": result.get("time"),
        "memory_used": result.get("memory"),
    }
    attempt.save(update_fields=["submissions"])
    logger.info(f"Execute coding challenge: Saved result for challenge {challenge_index}, is_correct={is_correct}")

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
# POST /api/courses/{id}/weeks/{w}/coding-test/{test_number}/submit/
# ──────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_coding_test(request, course_id, week_number, test_number=1):
    """Submit coding test results and calculate score."""
    try:
        from apps.courses.models import Course, WeekPlan
        course = Course.objects.get(id=course_id, user=request.user)
        week = course.weeks.get(week_number=week_number)
    except Course.DoesNotExist:
        logger.error("Submit coding test: Course not found")
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    attempt_id = request.data.get("attempt_id")
    challenge_results = request.data.get("challenge_results", [])

    if not attempt_id:
        logger.error("Submit coding test: Missing attempt_id")
        return _err("Missing attempt_id.", status.HTTP_400_BAD_REQUEST)

    try:
        test = CodingTest.objects.get(course=course, week_number=week_number, test_number=test_number)
    except CodingTest.DoesNotExist:
        logger.error("Submit coding test: Coding test not found")
        return _err("Coding test not found.", status.HTTP_400_BAD_REQUEST)

    try:
        attempt = CodingTestAttempt.objects.get(id=attempt_id, user=request.user)
    except CodingTestAttempt.DoesNotExist:
        logger.error(f"Submit coding test: Attempt {attempt_id} not found for user {request.user.id}")
        return _err("Attempt not found.", status.HTTP_404_NOT_FOUND)

    # If challenge_results is empty or incomplete, use the saved submissions from attempt
    if not challenge_results and attempt.submissions:
        # Convert dict back to list format
        challenge_results = []
        for key in sorted(attempt.submissions.keys(), key=lambda x: int(x)):
            challenge_results.append(attempt.submissions[key])
        logger.info(f"Submit coding test: Using saved submissions from attempt, count={len(challenge_results)}")
    elif challenge_results and attempt.submissions:
        # Validate: ensure we're using the backend-stored results (which are authoritative)
        logger.info(f"Submit coding test: Received {len(challenge_results)} results from frontend, using backend-stored results")
        # Use backend submissions as source of truth
        challenge_results = []
        for key in sorted(attempt.submissions.keys(), key=lambda x: int(x)):
            challenge_results.append(attempt.submissions[key])

    # Check if attempt is already completed (has a score)
    if attempt.score is not None and attempt.score > 0:
        logger.warning(f"Submit coding test: Attempt {attempt_id} already completed")
        return _err("Attempt already completed.", status.HTTP_400_BAD_REQUEST)

    # Calculate score
    total_challenges = len(challenge_results)
    correct_challenges = sum(1 for r in challenge_results if r.get("is_correct", False))
    percentage = round((correct_challenges / total_challenges * 100), 1) if total_challenges > 0 else 0
    passed = percentage >= 60

    logger.info(f"Submit coding test {test_number}: Score={correct_challenges}/{total_challenges}, Percentage={percentage}%, Passed={passed}")

    # Update attempt
    attempt.score = correct_challenges
    attempt.total = total_challenges
    attempt.percentage = percentage
    attempt.passed = passed
    attempt.submissions = challenge_results
    attempt.save(update_fields=["score", "total", "percentage", "passed", "submissions"])

    # Mark coding test as completed in WeekPlan
    next_coding_test_unlocked = False
    if passed:
        if test_number == 1:
            week.coding_test_1_completed = True
            week.save(update_fields=["coding_test_1_completed"])

            # Unlock next week's day 1 immediately after Coding Test 1 is passed
            # (This treats Coding Test 1 as the primary gate for the weekly test)
            try:
                next_week = course.weeks.get(week_number=week_number + 1)
                next_week_day1 = next_week.days.filter(day_number=1).first()
                if next_week_day1 and next_week_day1.is_locked:
                    next_week_day1.is_locked = False
                    next_week_day1.save(update_fields=["is_locked"])
                    logger.info(f"Coding test 1 passed, next week unlocked: course={course_id}, week={week_number}")
            except WeekPlan.DoesNotExist:
                pass  # Last week of course

            # Also unlock coding test 2 if it exists, but don't block next week
            if not week.coding_test_2_unlocked:
                week.coding_test_2_unlocked = True
                week.save(update_fields=["coding_test_2_unlocked"])
                next_coding_test_unlocked = True

        elif test_number == 2:
            week.coding_test_2_completed = True
            week.save(update_fields=["coding_test_2_completed"])
            logger.info(f"Coding test 2 completed: course={course_id}, week={week_number}")

        # After any coding test is passed, check if week should be marked complete
        # A week is complete when: MCQ test passed OR coding test 1 passed (whichever is the primary gate)
        if not week.is_completed:
            week.is_completed = True
            week.save(update_fields=["is_completed"])
            logger.info(f"Week {week_number} marked as completed after coding test {test_number}: course={course_id}")

            # Check if ALL weeks are done - trigger certificate if so
            all_weeks_done = not course.weeks.filter(is_completed=False).exists()
            if all_weeks_done:
                from apps.courses.models import CourseProgress
                try:
                    progress = CourseProgress.objects.get(user_id=request.user.id, course=course)
                    progress.completed_at = timezone.now()
                    progress.save(update_fields=["completed_at"])
                    logger.info(f"Course completed! Triggering certificate generation: user={request.user.id}, course={course_id}")

                    from apps.courses.tasks import generate_certificate_task
                    generate_certificate_task.delay(str(request.user.id), str(course_id))
                except CourseProgress.DoesNotExist:
                    logger.warning(f"CourseProgress not found for user={request.user.id}, course={course_id}")

    return _ok({
        "score": correct_challenges,
        "total_challenges": total_challenges,
        "percentage": percentage,
        "passed": passed,
        "next_coding_test_unlocked": next_coding_test_unlocked,
        "challenge_results": challenge_results,
    })
