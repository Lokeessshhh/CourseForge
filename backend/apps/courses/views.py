"""
Courses app — views.
All course CRUD + AI generation + progress.
"""
import logging
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Course, WeekPlan, DayPlan
from .serializers import (
    CourseSerializer,
    CourseListSerializer,
    CourseGenerateSerializer,
    WeekPlanSerializer,
    DayPlanSerializer,
)

logger = logging.getLogger(__name__)


def _ok(data, status_code=status.HTTP_200_OK):
    return Response({"success": True, "data": data, "error": None}, status=status_code)


def _err(msg, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"success": False, "data": None, "error": msg}, status=status_code)


# ──────────────────────────────────────────────
# GET /api/courses/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def course_list(request):
    courses = Course.objects.filter(user=request.user)
    return _ok(CourseListSerializer(courses, many=True).data)


# ──────────────────────────────────────────────
# POST /api/courses/generate/
# ──────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def course_generate(request):
    """
    Create a new course with 3 required fields: course_name, duration, level.
    Returns course_id immediately and fires Celery task in background.
    User can create multiple courses that generate in parallel.
    """
    serializer = CourseGenerateSerializer(data=request.data)
    if not serializer.is_valid():
        return _err(serializer.errors)

    data = serializer.validated_data
    user = request.user

    # Parse duration
    from services.course.generator import parse_duration
    duration_weeks = parse_duration(data.get("duration", "1 month"))

    # Create course row immediately with status="generating"
    course = Course.objects.create(
        user=user,
        course_name=data["course_name"],
        topic=data["course_name"],  # Will be updated by Celery task
        level=data.get("level", "beginner"),
        duration_weeks=duration_weeks,
        hours_per_day=data.get("hours_per_day", 2),
        goals=data.get("goals", []),
        status="generating",
        generation_status="pending",
        generation_progress=0,
    )

    # Create empty week/day skeleton in DB
    for week_num in range(1, duration_weeks + 1):
        week = WeekPlan.objects.create(
            course=course,
            week_number=week_num,
            theme=None,
            objectives=[],
        )
        for day_num in range(1, 6):
            DayPlan.objects.create(
                week_plan=week,
                day_number=day_num,
                title=None,
                tasks={},
                content="",
                is_locked=not (week_num == 1 and day_num == 1),
                content_generated=False,
                quiz_generated=False,
            )

    # Fire Celery task in background (returns immediately)
    from apps.courses.tasks import generate_course_content_task
    generate_course_content_task.delay(
        course_id=str(course.id),
        course_name=data["course_name"],
        duration_weeks=duration_weeks,
        level=data.get("level", "beginner"),
        goals=data.get("goals", []),
    )

    # Return course_id instantly - user can create another course immediately
    return _ok({
        "course_id": str(course.id),
        "course_name": course.course_name,
        "level": course.level,
        "duration_weeks": duration_weeks,
        "total_days": duration_weeks * 5,
        "status": "generating",
        "message": "Course creation started. Poll /api/courses/{id}/status/ for progress.",
    }, status.HTTP_202_ACCEPTED)


# ──────────────────────────────────────────────
# GET /api/courses/{id}/status/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def course_status(request, course_id):
    """
    Get course generation status for polling.
    Each course polls independently so multiple courses
    can show independent progress bars simultaneously.
    """
    try:
        course = Course.objects.get(id=course_id, user=request.user)
    except Course.DoesNotExist:
        return _err("Course not found.", status.HTTP_404_NOT_FOUND)

    # Use generation_progress field (updated by Celery task)
    progress = course.generation_progress or 0
    total_days = course.total_days

    # Calculate percentage
    percentage = int((progress / total_days) * 100) if total_days > 0 else 0

    data = {
        "course_id": str(course_id),
        "course_name": course.course_name,
        "status": course.status,
        "generation_status": course.generation_status,
        "progress": f"{progress}/{total_days} days ready",
        "progress_count": progress,
        "total_days": total_days,
        "percentage": percentage,
        "is_ready": course.generation_status == "ready",
        "is_failed": course.generation_status == "failed",
        "is_generating": course.generation_status == "generating",
    }

    return _ok(data)


# ──────────────────────────────────────────────
# GET /api/courses/{id}/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def course_detail(request, course_id):
    try:
        course = Course.objects.get(id=course_id, user=request.user)
    except Course.DoesNotExist:
        return _err("Course not found.", status.HTTP_404_NOT_FOUND)
    return _ok(CourseSerializer(course).data)


# ──────────────────────────────────────────────
# DELETE /api/courses/{id}/
# ──────────────────────────────────────────────
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def course_delete(request, course_id):
    try:
        course = Course.objects.get(id=course_id, user=request.user)
    except Course.DoesNotExist:
        return _err("Course not found.", status.HTTP_404_NOT_FOUND)
    course.delete()
    return _ok({"deleted": str(course_id)})


# ──────────────────────────────────────────────
# GET /api/courses/{id}/weeks/{week_number}/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def week_detail(request, course_id, week_number):
    try:
        course = Course.objects.get(id=course_id, user=request.user)
        week = course.weeks.prefetch_related("days").get(week_number=week_number)
    except (Course.DoesNotExist, WeekPlan.DoesNotExist):
        return _err("Not found.", status.HTTP_404_NOT_FOUND)
    return _ok(WeekPlanSerializer(week).data)


# ──────────────────────────────────────────────
# GET /api/courses/{id}/weeks/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def course_weeks(request, course_id):
    try:
        course = Course.objects.get(id=course_id, user=request.user)
    except Course.DoesNotExist:
        return _err("Course not found.", status.HTTP_404_NOT_FOUND)
    weeks = course.weeks.prefetch_related("days")
    return _ok(WeekPlanSerializer(weeks, many=True).data)


# ──────────────────────────────────────────────
# GET /api/courses/{id}/weeks/{week}/days/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def week_days(request, course_id, week_number):
    try:
        course = Course.objects.get(id=course_id, user=request.user)
        week = course.weeks.get(week_number=week_number)
    except (Course.DoesNotExist, WeekPlan.DoesNotExist):
        return _err("Not found.", status.HTTP_404_NOT_FOUND)
    return _ok(DayPlanSerializer(week.days.all(), many=True).data)


# ──────────────────────────────────────────────
# GET /api/courses/{id}/weeks/{week}/days/{day}/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def day_detail(request, course_id, week_number, day_number):
    try:
        course = Course.objects.get(id=course_id, user=request.user)
        week = course.weeks.get(week_number=week_number)
        day = week.days.get(day_number=day_number)
    except (Course.DoesNotExist, WeekPlan.DoesNotExist, DayPlan.DoesNotExist):
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    # Check if day is locked
    if day.is_locked:
        return _err("Day is locked. Complete previous day first.", status.HTTP_403_FORBIDDEN)

    return _ok(DayPlanSerializer(day).data)


# ──────────────────────────────────────────────
# POST /api/courses/{id}/weeks/{week}/days/{day}/complete/
# ──────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def day_complete(request, course_id, week_number, day_number):
    try:
        course = Course.objects.get(id=course_id, user=request.user)
        week = course.weeks.get(week_number=week_number)
        day = week.days.get(day_number=day_number)
    except (Course.DoesNotExist, WeekPlan.DoesNotExist, DayPlan.DoesNotExist):
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    if day.is_locked:
        return _err("Day is locked.", status.HTTP_403_FORBIDDEN)

    day.is_completed = True
    day.completed_at = timezone.now()
    day.save(update_fields=["is_completed", "completed_at"])

    # Check if entire week is done
    if not week.days.filter(is_completed=False).exists():
        week.is_completed = True
        week.save(update_fields=["is_completed"])

    # Unlock next day
    from .tasks import unlock_next_day
    unlock_next_day.delay(str(course.id), week_number, day_number)

    return _ok(DayPlanSerializer(day).data)


# ──────────────────────────────────────────────
# GET /api/courses/{id}/progress/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def course_progress(request, course_id):
    try:
        course = Course.objects.get(id=course_id, user=request.user)
    except Course.DoesNotExist:
        return _err("Course not found.", status.HTTP_404_NOT_FOUND)

    # Count days
    all_days = DayPlan.objects.filter(week_plan__course=course)
    total = all_days.count()
    completed = all_days.filter(is_completed=True).count()
    percentage = round((completed / total * 100) if total > 0 else 0, 1)

    # Find current position
    current_week = 1
    current_day = 1
    for week in course.weeks.all():
        for day in week.days.all():
            if not day.is_completed:
                current_week = week.week_number
                current_day = day.day_number
                break
        else:
            continue
        break

    # Week progress
    weeks_progress = []
    for week in course.weeks.all():
        weeks_progress.append({
            "week_number": week.week_number,
            "is_completed": week.is_completed,
            "days_completed": week.days.filter(is_completed=True).count(),
        })

    # Average quiz score
    from apps.quizzes.models import QuizAttempt
    attempts = QuizAttempt.objects.filter(
        user=request.user,
        question__course=course,
    )
    correct = attempts.filter(is_correct=True).count()
    total_attempts = attempts.count()
    avg_score = round((correct / total_attempts * 100) if total_attempts > 0 else 0, 1)

    # Certificate eligibility
    cert_earned = (percentage == 100 and avg_score >= 50)

    data = {
        "course_id": str(course_id),
        "total_days": total,
        "completed_days": completed,
        "percentage": percentage,
        "current_week": current_week,
        "current_day": current_day,
        "weeks": weeks_progress,
        "average_quiz_score": avg_score,
        "certificate_earned": cert_earned,
    }
    return _ok(data)


# ──────────────────────────────────────────────
# GET /api/courses/{id}/weeks/{week}/days/{day}/quiz/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def day_quiz(request, course_id, week_number, day_number):
    """Get quiz questions for a day (without answers)."""
    try:
        course = Course.objects.get(id=course_id, user=request.user)
        week = course.weeks.get(week_number=week_number)
        day = week.days.get(day_number=day_number)
    except (Course.DoesNotExist, WeekPlan.DoesNotExist, DayPlan.DoesNotExist):
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    if day.is_locked:
        return _err("Day is locked.", status.HTTP_403_FORBIDDEN)

    if not day.quiz_generated:
        return _err("Quiz not generated yet.", status.HTTP_400_BAD_REQUEST)

    # Get quiz questions (without answers)
    from apps.quizzes.models import QuizQuestion
    questions = QuizQuestion.objects.filter(day_plan=day).order_by("question_number")

    quizzes = [
        {
            "id": str(q.id),
            "question_number": q.question_number,
            "question_text": q.question_text,
            "options": q.options,
        }
        for q in questions
    ]

    return _ok({"quizzes": quizzes})


# ──────────────────────────────────────────────
# POST /api/courses/{id}/weeks/{week}/days/{day}/quiz/submit/
# ──────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def day_quiz_submit(request, course_id, week_number, day_number):
    """Submit quiz answers and get results."""
    from apps.quizzes.models import QuizQuestion, QuizAttempt
    from .serializers import QuizSubmitSerializer

    serializer = QuizSubmitSerializer(data=request.data)
    if not serializer.is_valid():
        return _err(serializer.errors)

    try:
        course = Course.objects.get(id=course_id, user=request.user)
        week = course.weeks.get(week_number=week_number)
        day = week.days.get(day_number=day_number)
    except (Course.DoesNotExist, WeekPlan.DoesNotExist, DayPlan.DoesNotExist):
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    if day.is_locked:
        return _err("Day is locked.", status.HTTP_403_FORBIDDEN)

    answers = serializer.validated_data["answers"]
    questions = QuizQuestion.objects.filter(day_plan=day).order_by("question_number")

    if not questions.exists():
        return _err("No quiz questions found.", status.HTTP_400_BAD_REQUEST)

    # Process answers
    results = []
    correct_count = 0
    total = questions.count()

    for question in questions:
        q_num = str(question.question_number)
        user_answer = answers.get(q_num, "").lower()
        is_correct = user_answer == question.correct_answer.lower()

        if is_correct:
            correct_count += 1

        # Save attempt
        QuizAttempt.objects.create(
            user=request.user,
            question=question,
            selected_answer=user_answer,
            is_correct=is_correct,
        )

        results.append({
            "question_number": question.question_number,
            "your_answer": user_answer,
            "correct_answer": question.correct_answer,
            "is_correct": is_correct,
            "explanation": question.explanation,
        })

    # Calculate score
    percentage = round((correct_count / total * 100), 1) if total > 0 else 0
    passed = percentage >= 50

    # Unlock next day if passed
    next_day_unlocked = False
    if passed:
        from .tasks import unlock_next_day
        unlock_next_day.delay(str(course.id), week_number, day_number)
        next_day_unlocked = True

    return _ok({
        "score": correct_count,
        "total": total,
        "percentage": percentage,
        "passed": passed,
        "results": results,
        "day_unlocked": day.is_completed,
        "next_day_unlocked": next_day_unlocked,
    })


# ──────────────────────────────────────────────
# POST /api/courses/{id}/weeks/{w}/days/{d}/start/
# ──────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def day_start(request, course_id, week_number, day_number):
    """Mark a day as started, begin time tracking."""
    from services.progress.tracker import get_tracker

    tracker = get_tracker()
    result = tracker.start_day(
        user_id=str(request.user.id),
        course_id=course_id,
        week_number=week_number,
        day_number=day_number,
    )

    if not result.get("success"):
        return _err(result.get("error", "Failed to start day"))

    return _ok(result)


# ──────────────────────────────────────────────
# GET /api/courses/{id}/weeks/{w}/test/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def week_test(request, course_id, week_number):
    """Get weekly test questions (without answers)."""
    from .models import WeeklyTest

    try:
        course = Course.objects.get(id=course_id, user=request.user)
        week = course.weeks.get(week_number=week_number)
    except (Course.DoesNotExist, WeekPlan.DoesNotExist):
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    if not week.test_unlocked:
        return _err("Weekly test not unlocked yet.", status.HTTP_403_FORBIDDEN)

    try:
        test = WeeklyTest.objects.get(course=course, week_number=week_number)
    except WeeklyTest.DoesNotExist:
        return _err("Weekly test not generated yet.", status.HTTP_400_BAD_REQUEST)

    # Return questions without answers
    questions = [
        {
            "question_number": q.get("question_number"),
            "question_text": q.get("question_text"),
            "difficulty": q.get("difficulty"),
            "options": q.get("options", {}),
        }
        for q in test.questions
    ]

    return _ok({
        "week_number": week_number,
        "total_questions": test.total_questions,
        "questions": questions,
    })


# ──────────────────────────────────────────────
# POST /api/courses/{id}/weeks/{w}/test/submit/
# ──────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def week_test_submit(request, course_id, week_number):
    """Submit weekly test answers and get results."""
    from .models import WeeklyTest, WeeklyTestAttempt
    from .serializers import QuizSubmitSerializer

    serializer = QuizSubmitSerializer(data=request.data)
    if not serializer.is_valid():
        return _err(serializer.errors)

    try:
        course = Course.objects.get(id=course_id, user=request.user)
        week = course.weeks.get(week_number=week_number)
    except (Course.DoesNotExist, WeekPlan.DoesNotExist):
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    if not week.test_unlocked:
        return _err("Weekly test not unlocked yet.", status.HTTP_403_FORBIDDEN)

    try:
        test = WeeklyTest.objects.get(course=course, week_number=week_number)
    except WeeklyTest.DoesNotExist:
        return _err("Weekly test not generated yet.", status.HTTP_400_BAD_REQUEST)

    answers = serializer.validated_data["answers"]
    questions = test.questions

    # Process answers
    results = []
    correct_count = 0
    total = len(questions)

    # Track performance by day
    day_performance = {}

    for question in questions:
        q_num = str(question.get("question_number"))
        user_answer = answers.get(q_num, "").lower()
        correct_answer = question.get("correct_answer", "a").lower()
        is_correct = user_answer == correct_answer

        if is_correct:
            correct_count += 1

        # Track day performance
        day_ref = question.get("day_reference", 0)
        if day_ref not in day_performance:
            day_performance[day_ref] = {"correct": 0, "total": 0}
        day_performance[day_ref]["total"] += 1
        if is_correct:
            day_performance[day_ref]["correct"] += 1

        results.append({
            "question_number": question.get("question_number"),
            "your_answer": user_answer,
            "correct_answer": correct_answer,
            "is_correct": is_correct,
            "difficulty": question.get("difficulty"),
            "explanation": question.get("explanation", ""),
        })

    # Calculate score
    percentage = round((correct_count / total * 100), 1) if total > 0 else 0
    passed = percentage >= 60  # 60% to pass weekly test

    # Save attempt
    WeeklyTestAttempt.objects.create(
        user=request.user,
        course=course,
        week_number=week_number,
        answers=answers,
        score=correct_count,
        total=total,
        percentage=percentage,
        passed=passed,
    )

    # Calculate strong/weak days
    strong_days = []
    weak_days = []
    for day_num, perf in day_performance.items():
        if day_num > 0:
            day_pct = (perf["correct"] / perf["total"] * 100) if perf["total"] > 0 else 0
            if day_pct >= 70:
                strong_days.append(day_num)
            elif day_pct < 50:
                weak_days.append(day_num)

    # Generate recommendation
    recommendation = ""
    if weak_days:
        recommendation = f"Review Day {weak_days[0]} content before moving on"
    elif passed:
        recommendation = "Great job! Ready for next week"

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

    return _ok({
        "score": correct_count,
        "total": total,
        "percentage": percentage,
        "passed": passed,
        "next_week_unlocked": next_week_unlocked,
        "results": results,
        "week_summary": {
            "strong_days": strong_days,
            "weak_days": weak_days,
            "recommendation": recommendation,
        },
    })


# ──────────────────────────────────────────────
# GET /api/courses/{id}/weeks/{w}/test/results/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def week_test_results(request, course_id, week_number):
    """Get last weekly test attempt results."""
    from .models import WeeklyTestAttempt

    try:
        attempt = WeeklyTestAttempt.objects.filter(
            user=request.user,
            course_id=course_id,
            week_number=week_number,
        ).order_by("-attempted_at").first()

        if not attempt:
            return _err("No test attempts found.", status.HTTP_404_NOT_FOUND)

        return _ok({
            "score": attempt.score,
            "total": attempt.total,
            "percentage": attempt.percentage,
            "passed": attempt.passed,
            "attempted_at": attempt.attempted_at.isoformat(),
        })

    except Exception as exc:
        logger.exception("Error getting test results: %s", exc)
        return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# ──────────────────────────────────────────────
# GET /api/courses/{id}/weeks/{w}/coding-test/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def week_coding_test(request, course_id, week_number):
    """Get weekly coding test problems (without solutions)."""
    from .models import CodingTest

    try:
        course = Course.objects.get(id=course_id, user=request.user)
        week = course.weeks.get(week_number=week_number)
    except (Course.DoesNotExist, WeekPlan.DoesNotExist):
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    if not week.test_unlocked:
        return _err("Weekly test not unlocked yet.", status.HTTP_403_FORBIDDEN)

    try:
        test = CodingTest.objects.get(course=course, week_number=week_number)
    except CodingTest.DoesNotExist:
        return _err("Coding test not generated yet.", status.HTTP_400_BAD_REQUEST)

    # Return problems without solutions
    problems = []
    for p in test.problems:
        problems.append({
            "problem_number": p.get("problem_number"),
            "title": p.get("title"),
            "description": p.get("description"),
            "difficulty": p.get("difficulty"),
            "starter_code": p.get("starter_code"),
            "test_cases": [tc for tc in p.get("test_cases", []) if not tc.get("is_hidden", False)],
            "hints": p.get("hints", [])[:1],  # Only first hint
            "time_limit_seconds": p.get("time_limit_seconds", 30),
            "memory_limit_mb": p.get("memory_limit_mb", 256),
        })

    return _ok({
        "week_number": week_number,
        "total_problems": test.total_problems,
        "problems": problems,
    })


# ──────────────────────────────────────────────
# POST /api/courses/{id}/weeks/{w}/coding-test/submit/
# ──────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def week_coding_test_submit(request, course_id, week_number):
    """Submit coding test solutions and get results."""
    from .models import CodingTest, CodingTestAttempt
    from .serializers import CodingSubmissionSerializer

    serializer = CodingSubmissionSerializer(data=request.data)
    if not serializer.is_valid():
        return _err(serializer.errors)

    try:
        course = Course.objects.get(id=course_id, user=request.user)
        week = course.weeks.get(week_number=week_number)
    except (Course.DoesNotExist, WeekPlan.DoesNotExist):
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    if not week.test_unlocked:
        return _err("Weekly test not unlocked yet.", status.HTTP_403_FORBIDDEN)

    try:
        test = CodingTest.objects.get(course=course, week_number=week_number)
    except CodingTest.DoesNotExist:
        return _err("Coding test not generated yet.", status.HTTP_400_BAD_REQUEST)

    submissions = serializer.validated_data["submissions"]
    problems = test.problems

    # Execute code and evaluate
    results = []
    passed_count = 0
    total = len(problems)

    for problem in problems:
        p_num = str(problem.get("problem_number"))
        submission = submissions.get(p_num, {})
        code = submission.get("code", "")
        language = submission.get("language", "python")

        # Run code against test cases
        test_results = _execute_code_tests(code, problem.get("test_cases", []), language)
        problem_passed = test_results["passed"]
        problem_score = test_results["passed_count"]
        problem_total = test_results["total"]

        if problem_passed:
            passed_count += 1

        results.append({
            "problem_number": problem.get("problem_number"),
            "title": problem.get("title"),
            "passed": problem_passed,
            "passed_test_cases": problem_score,
            "total_test_cases": problem_total,
            "output": test_results.get("output", ""),
            "error": test_results.get("error", ""),
        })

    # Calculate score
    percentage = round((passed_count / total * 100), 1) if total > 0 else 0
    passed = passed_count == total  # Must pass all problems

    # Save attempt
    CodingTestAttempt.objects.create(
        user=request.user,
        coding_test=test,
        submissions=submissions,
        score=passed_count,
        total=total,
        percentage=percentage,
        passed=passed,
    )

    return _ok({
        "score": passed_count,
        "total": total,
        "percentage": percentage,
        "passed": passed,
        "results": results,
    })


def _execute_code_tests(code: str, test_cases: list, language: str) -> dict:
    """
    Execute code against test cases.
    Returns dict with passed status, counts, output, and errors.
    """
    import subprocess
    import tempfile
    import os

    passed_count = 0
    total = len(test_cases)
    outputs = []
    errors = []

    try:
        # Create temporary file with code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name

        for tc in test_cases:
            input_data = tc.get("input", "")
            expected = tc.get("expected_output", "")

            try:
                # Run code with input
                result = subprocess.run(
                    ['python', temp_file],
                    input=input_data,
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                output = result.stdout.strip()
                outputs.append(output)

                if output == expected:
                    passed_count += 1
                else:
                    errors.append(f"Expected: {expected}, Got: {output}")

            except subprocess.TimeoutExpired:
                errors.append("Time limit exceeded")
            except Exception as e:
                errors.append(str(e))

        # Cleanup
        os.unlink(temp_file)

    except Exception as e:
        return {
            "passed": False,
            "passed_count": 0,
            "total": total,
            "output": "",
            "error": str(e),
        }

    return {
        "passed": passed_count == total,
        "passed_count": passed_count,
        "total": total,
        "output": "\n".join(outputs),
        "error": "\n".join(errors) if errors else "",
    }


# ──────────────────────────────────────────────
# GET /api/courses/{id}/weeks/{w}/coding-test/results/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def week_coding_test_results(request, course_id, week_number):
    """Get last coding test attempt results."""
    from .models import CodingTestAttempt, CodingTest

    try:
        test = CodingTest.objects.get(course_id=course_id, week_number=week_number)
        attempt = CodingTestAttempt.objects.filter(
            user=request.user,
            coding_test=test,
        ).order_by("-attempted_at").first()

        if not attempt:
            return _err("No coding test attempts found.", status.HTTP_404_NOT_FOUND)

        return _ok({
            "score": attempt.score,
            "total": attempt.total,
            "percentage": attempt.percentage,
            "passed": attempt.passed,
            "attempted_at": attempt.attempted_at.isoformat(),
        })

    except CodingTest.DoesNotExist:
        return _err("Coding test not found.", status.HTTP_404_NOT_FOUND)


# ──────────────────────────────────────────────
# GET /api/users/me/progress/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_all_progress(request):
    """Get progress across all courses for the user."""
    from services.progress.tracker import get_tracker

    tracker = get_tracker()
    result = tracker.get_all_courses_progress(str(request.user.id))
    return _ok(result)


# ──────────────────────────────────────────────
# GET /api/courses/{id}/certificate/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def course_certificate(request, course_id):
    """Get certificate info for a course."""
    from services.certificate.generator import CertificateGenerator

    try:
        generator = CertificateGenerator()
        cert_data = generator.get_certificate(str(request.user.id), course_id)

        if not cert_data:
            return _ok({
                "is_unlocked": False,
                "issued_at": None,
                "download_url": None,
                "stats": None,
            })

        return _ok(cert_data)

    except Exception as exc:
        logger.exception("Error getting certificate: %s", exc)
        return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
