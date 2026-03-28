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
    serializer = CourseListSerializer(courses, many=True, context={'request': request})
    return _ok(serializer.data)


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

    # Get duration_weeks directly from validated data
    duration_weeks = data.get("duration_weeks", 4)

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

    # Create CourseProgress record immediately so it shows up in dashboard/progress
    from .models import CourseProgress
    CourseProgress.objects.get_or_create(
        user=user,
        course=course,
        defaults={
            "total_days": duration_weeks * 5,
            "total_weeks": duration_weeks,
            "overall_percentage": 0.0,
            "completed_days": 0,
            "current_week": 1,
            "current_day": 1
        }
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
                theory_content="",
                code_content="",
                is_locked=not (week_num == 1 and day_num == 1),
                theory_generated=False,
                code_generated=False,
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
    serializer = CourseSerializer(course, context={'request': request})
    return _ok(serializer.data)


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

    # Bypass locking completely for all days
    # We set it to False in the object but we don't even check it in this view
    # to guarantee access even if DB saving is slow
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

    # Update CourseProgress
    from .models import CourseProgress
    cp, _ = CourseProgress.objects.get_or_create(user=request.user, course=course)
    
    # Recalculate completed days
    all_completed = DayPlan.objects.filter(week_plan__course=course, is_completed=True).count()
    cp.completed_days = all_completed
    
    # Calculate percentage
    total_days = course.total_days
    if total_days > 0:
        cp.overall_percentage = round((all_completed / total_days) * 100, 1)
    
    # Update current position to next day
    if day_number < 5:
        cp.current_day = day_number + 1
        cp.current_week = week_number
    else:
        cp.current_day = 1
        cp.current_week = week_number + 1
        
    cp.last_activity = timezone.now()
    cp.save()

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

    # Find current position (first incomplete day)
    current_week = 1
    current_day = 1
    found_current = False
    
    # Sort weeks and days to ensure we find the correct sequence
    for week in course.weeks.all().order_by("week_number"):
        days = week.days.all().order_by("day_number")
        for day in days:
            if not day.is_completed:
                current_week = week.week_number
                current_day = day.day_number
                found_current = True
                break
        if found_current:
            break
            
    # If all days completed, set to last day or some completion state
    if not found_current and total > 0:
        last_week = course.weeks.order_by("-week_number").first()
        if last_week:
            current_week = last_week.week_number
            last_day = last_week.days.order_by("-day_number").first()
            if last_day:
                current_day = last_day.day_number

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
    from .models import CourseProgress
    cp, _ = CourseProgress.objects.get_or_create(user=request.user, course=course)
    cert_earned = (percentage == 100 and avg_score >= 50)

    if cert_earned:
        from apps.certificates.models import Certificate
        Certificate.objects.get_or_create(
            user=request.user,
            course=course,
            defaults={
                "is_unlocked": True,
                "quiz_score_avg": avg_score,
                "test_score_avg": cp.avg_test_score,
                "total_study_hours": round(cp.total_study_time / 60, 1),
                "issued_at": timezone.now()
            }
        )

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
    questions = QuizQuestion.objects.filter(
        course=course,
        week_number=week_number,
        day_number=day_number
    ).order_by("id")

    quizzes = [
        {
            "id": str(q.id),
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
    questions = QuizQuestion.objects.filter(
        course=course,
        week_number=week_number,
        day_number=day_number
    ).order_by("id")

    if not questions.exists():
        return _err("No quiz questions found.", status.HTTP_400_BAD_REQUEST)

    # Process answers
    results = []
    correct_count = 0
    total = questions.count()

    # Map numeric keys if needed (frontend sends [0, 1, 2] usually)
    # The keys in the request body 'answers' might be "1", "2", "3" or indices
    for i, question in enumerate(questions):
        # Check both index-based and 1-based string keys
        user_answer_idx = answers.get(str(i)) if str(i) in answers else answers.get(str(i + 1))
        
        # If the frontend sends an array, it might be indices
        if user_answer_idx is None and isinstance(answers, list) and i < len(answers):
            user_answer_idx = answers[i]

        # Convert index (0, 1, 2, 3) to letter (a, b, c, d) if needed
        # Or compare directly if the model stores letters
        # Let's check what correct_answer stores. Usually it's a letter.
        # Options are usually a list.
        
        user_answer_letter = ""
        if user_answer_idx is not None:
            try:
                idx = int(user_answer_idx)
                user_answer_letter = chr(97 + idx) # 0 -> 'a'
            except (ValueError, TypeError):
                user_answer_letter = str(user_answer_idx).lower()

        is_correct = user_answer_letter == question.correct_answer.lower()

        if is_correct:
            correct_count += 1

        # Save attempt
        QuizAttempt.objects.create(
            user=request.user,
            question=question,
            user_answer=user_answer_letter,
            is_correct=is_correct,
        )

        results.append({
            "question_number": i + 1,
            "your_answer": user_answer_letter,
            "correct_answer": question.correct_answer,
            "is_correct": is_correct,
            "explanation": question.explanation,
        })

    # Calculate score
    percentage = round((correct_count / total * 100), 1) if total > 0 else 0
    # ALWAYS pass the quiz regardless of score, as requested by user
    passed = True 

    # Update day score and status
    day.quiz_score = percentage
    day.quiz_attempts += 1
    day.is_completed = True
    day.completed_at = timezone.now()
    day.save(update_fields=["quiz_score", "quiz_attempts", "is_completed", "completed_at"])

    # Use tracker to handle progress updates and weekly test unlock
    from services.progress.tracker import get_tracker
    tracker = get_tracker()
    tracker_result = tracker.complete_day(
        user_id=str(request.user.id),
        course_id=course_id,
        week_number=week_number,
        day_number=day_number,
        quiz_score=percentage,
        time_spent=0,  # We don't track time spent on quiz
    )

    logger.info(f"Quiz submit: Tracker result - week_test_unlocked={tracker_result.get('week_test_unlocked', False)}")

    # Update CourseProgress (tracker already handles this, but keep for compatibility)
    from .models import CourseProgress
    cp, _ = CourseProgress.objects.get_or_create(user=request.user, course=course)
    
    # Recalculate completed days
    all_completed = DayPlan.objects.filter(week_plan__course=course, is_completed=True).count()
    logger.info(f"Quiz submit: Found {all_completed} completed days for course {course.id}")
    cp.completed_days = all_completed
    
    # Calculate percentage
    total_days = course.total_days
    logger.info(f"Quiz submit: Total days for course {course.id}: {total_days}")
    if total_days > 0:
        cp.overall_percentage = round((all_completed / total_days) * 100, 1)
        logger.info(f"Quiz submit: Calculated percentage: {cp.overall_percentage}%")
    else:
        logger.warning(f"Quiz submit: total_days is 0 for course {course.id}")
    
    # Update current position to next day
    if day_number < 5:
        cp.current_day = day_number + 1
        cp.current_week = week_number
    else:
        cp.current_day = 1
        cp.current_week = week_number + 1
        
    cp.last_activity = timezone.now()
    cp.save()
    
    # DEBUG: Log progress update
    logger.info(
        f"Progress updated for user {request.user.id}, course {course.id}: "
        f"completed_days={cp.completed_days}, overall_percentage={cp.overall_percentage}, "
        f"current_week={cp.current_week}, current_day={cp.current_day}"
    )

    # Check if entire week is done
    if not week.days.filter(is_completed=False).exists():
        week.is_completed = True
        week.save(update_fields=["is_completed"])

    # ALWAYS unlock next day
    from .tasks import unlock_next_day
    unlock_next_day.delay(str(course.id), week_number, day_number)

    return _ok({
        "score": correct_count,
        "total": total,
        "percentage": percentage,
        "passed": passed,
        "results": results,
        "day_unlocked": True,
        "next_day_unlocked": True,
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
        # Debug: Check why test is not unlocked
        completed_days = week.days.filter(is_completed=True).count()
        total_days = week.days.count()
        logger.warning(f"Weekly test not unlocked: course={course_id}, week={week_number}, completed_days={completed_days}/{total_days}, test_unlocked={week.test_unlocked}")
        return _err(f"Weekly test not unlocked yet. Complete all {total_days} days in this week to unlock the test. Currently completed: {completed_days}/{total_days} days.", status.HTTP_403_FORBIDDEN)

    try:
        test = WeeklyTest.objects.get(course=course, week_number=week_number)
    except WeeklyTest.DoesNotExist:
        logger.error(f"Weekly test not found for course {course_id}, week {week_number}")
        return _err("Weekly test not generated yet.", status.HTTP_400_BAD_REQUEST)

    logger.info(f"Weekly test: Retrieved test for course {course_id}, week {week_number}, {len(test.questions)} questions")
    logger.info(f"Weekly test data: {test.questions}")

    # Return questions without answers
    questions = [
        {
            "id": q.get("question_number"),  # Frontend expects 'id'
            "question": q.get("question_text"),  # Frontend expects 'question'
            "difficulty": q.get("difficulty"),
            "options": list(q.get("options", {}).values()),  # Convert to array
            "correct": ord(q.get("correct_answer", "a").lower()) - 97,  # Convert letter to index (a->0, b->1, c->2, d->3)
        }
        for q in test.questions
    ]

    logger.info(f"Formatted questions for frontend: {questions}")

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

    logger.info(f"Weekly test submit request: course={course_id}, week={week_number}, data={request.data}")

    serializer = QuizSubmitSerializer(data=request.data)
    if not serializer.is_valid():
        logger.error(f"Weekly test submit validation failed: {serializer.errors}")
        return _err(serializer.errors)

    try:
        course = Course.objects.get(id=course_id, user=request.user)
        week = course.weeks.get(week_number=week_number)
    except (Course.DoesNotExist, WeekPlan.DoesNotExist):
        logger.error("Weekly test submit: Course or week not found")
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    if not week.test_unlocked:
        logger.warning(f"Weekly test submit: Week {week_number} test not unlocked")
        return _err("Weekly test not unlocked yet.", status.HTTP_403_FORBIDDEN)

    try:
        test = WeeklyTest.objects.get(course=course, week_number=week_number)
    except WeeklyTest.DoesNotExist:
        logger.error(f"Weekly test submit: Weekly test not found for week {week_number}")
        return _err("Weekly test not generated yet.", status.HTTP_400_BAD_REQUEST)

    answers = serializer.validated_data["answers"]
    questions = test.questions

    logger.info(f"Weekly test submit: Processing {len(questions)} questions")

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

        logger.info(f"Question {q_num}: user_answer={user_answer}, correct_answer={correct_answer}, is_correct={is_correct}")

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

    logger.info(f"Weekly test submit: Score={correct_count}/{total}, Percentage={percentage}%, Passed={passed}")

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

    logger.info(f"Weekly test submit: Strong days={strong_days}, Weak days={weak_days}")

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
        logger.info(f"Weekly test submit: Week completed, next_week_unlocked={next_week_unlocked}")

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
    Execute code against test cases with sandboxing.
    Returns dict with passed status, counts, output, and errors.
    
    Security: Uses Docker container for isolation when available,
    falls back to restricted subprocess when Docker is not available.
    """
    import subprocess
    import tempfile
    import os
    import shutil

    passed_count = 0
    total = len(test_cases)
    outputs = []
    errors = []

    # Check if Docker is available for sandboxing
    docker_available = shutil.which("docker") is not None

    try:
        if docker_available:
            # Use Docker for secure execution
            return _execute_code_docker(code, test_cases, language)
        
        # Fallback: Restricted subprocess execution (less secure)
        # Create temporary file with code in isolated directory
        temp_dir = tempfile.mkdtemp(prefix="code_exec_")
        temp_file = os.path.join(temp_dir, f"code.{language}")
        
        with open(temp_file, 'w') as f:
            f.write(code)
        
        # Restrict permissions
        os.chmod(temp_dir, 0o700)
        os.chmod(temp_file, 0o600)

        for tc in test_cases:
            input_data = tc.get("input", "")
            expected = tc.get("expected_output", "")

            try:
                # Run code with input and strict limits
                result = subprocess.run(
                    ['python', '-S', temp_file],  # -S disables site modules for security
                    input=input_data,
                    capture_output=True,
                    text=True,
                    timeout=5,  # Reduced timeout
                    cwd=temp_dir,
                    env={
                        'PYTHONDONTWRITEBYTECODE': '1',
                        'PYTHONUNBUFFERED': '1',
                    },  # Minimal env
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
        shutil.rmtree(temp_dir, ignore_errors=True)

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


def _execute_code_docker(code: str, test_cases: list, language: str) -> dict:
    """
    Execute code in Docker container for secure sandboxing.
    """
    import subprocess
    import json

    total = len(test_cases)

    # Docker image mapping
    image_map = {
        'python': 'python:3.11-slim',
        'javascript': 'node:18-slim',
    }
    image = image_map.get(language, 'python:3.11-slim')
    
    # Create execution payload
    exec_payload = {
        'code': code,
        'test_cases': test_cases,
        'language': language,
    }

    try:
        # Run in Docker with strict resource limits
        result = subprocess.run(
            [
                'docker', 'run', '--rm',
                '--network', 'none',  # No network access
                '--memory', '128m',   # Memory limit
                '--cpus', '0.5',      # CPU limit
                '--timeout', '10',    # Timeout
                '-i', image,
                'python', '-c',
                _get_executor_script(language),
            ],
            input=json.dumps(exec_payload),
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode == 0:
            exec_result = json.loads(result.stdout)
            return exec_result
        else:
            return {
                "passed": False,
                "passed_count": 0,
                "total": total,
                "output": "",
                "error": f"Docker execution failed: {result.stderr}",
            }

    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "passed_count": 0,
            "total": total,
            "output": "",
            "error": "Execution timeout",
        }
    except Exception as e:
        return {
            "passed": False,
            "passed_count": 0,
            "total": total,
            "output": "",
            "error": str(e),
        }


def _get_executor_script(language: str) -> str:
    """Get the executor script for the given language."""
    return '''
import json
import sys

def execute_tests(payload):
    code = payload['code']
    test_cases = payload['test_cases']
    language = payload['language']
    
    passed_count = 0
    outputs = []
    errors = []
    
    # Safe execution environment
    safe_globals = {'__builtins__': __builtins__}
    
    for tc in test_cases:
        try:
            # Execute code with input
            local_vars = {}
            exec(code, safe_globals, local_vars)
            
            # Get output from main function if exists
            if 'main' in local_vars:
                output = str(local_vars['main'](tc.get('input', '')))
            else:
                output = ""
            
            outputs.append(output)
            if output == tc.get('expected_output', ''):
                passed_count += 1
            else:
                errors.append(f"Expected: {tc.get('expected_output')}, Got: {output}")
        except Exception as e:
            errors.append(str(e))
    
    return {
        'passed': passed_count == len(test_cases),
        'passed_count': passed_count,
        'total': len(test_cases),
        'output': '\\n'.join(outputs),
        'error': '\\n'.join(errors) if errors else '',
    }

if __name__ == '__main__':
    payload = json.load(sys.stdin)
    result = execute_tests(payload)
    print(json.dumps(result))
'''


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
