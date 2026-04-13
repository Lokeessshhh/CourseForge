"""
Debug endpoint to manually unlock weekly tests for testing purposes.
This should only be used in development/testing environments.
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def _ok(data, status_code=status.HTTP_200_OK):
    """Standard success response."""
    return Response({"success": True, "data": data, "error": None}, status=status_code)


def _err(msg, status_code=status.HTTP_400_BAD_REQUEST):
    """Standard error response."""
    return Response({"success": False, "data": None, "error": msg}, status=status_code)


# ──────────────────────────────────────────────
# POST /api/courses/{id}/weeks/{w}/test/unlock/
# ──────────────────────────────────────────────
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unlock_weekly_test(request, course_id, week_number):
    """
    DEBUG: Manually unlock weekly test for testing.
    This endpoint should only be used in development/testing.
    """
    try:
        from apps.courses.models import Course, WeekPlan
        course = Course.objects.get(id=course_id, user=request.user)
        week = course.weeks.get(week_number=week_number)
    except (Course.DoesNotExist, WeekPlan.DoesNotExist):
        return _err("Not found.", status.HTTP_404_NOT_FOUND)

    # Check current state
    completed_days = week.days.filter(is_completed=True).count()
    total_days = week.days.count()
    
    logger.info(f"DEBUG: Unlock weekly test - course={course_id}, week={week_number}, completed_days={completed_days}/{total_days}, test_unlocked={week.test_unlocked}")

    # Unlock the test
    week.test_unlocked = True
    week.save(update_fields=["test_unlocked"])

    # Generate weekly test if not already generated
    try:
        from apps.courses.models import WeeklyTest
        test, created = WeeklyTest.objects.get_or_create(
            course=course,
            week_number=week_number,
            defaults={
                "questions": [],
                "total_questions": 10,
            }
        )
        if created:
            logger.info(f"DEBUG: Created weekly test for week {week_number}")
            # Trigger test generation
            from apps.courses.tasks import generate_weekly_test_task, _start_background_task
            _start_background_task(
                generate_weekly_test_task,
                (course_id, week_number),
                task_name="generate_weekly_test",
            )
    except Exception as e:
        logger.error(f"DEBUG: Error creating weekly test: {e}")

    return _ok({
        "week_number": week_number,
        "test_unlocked": True,
        "completed_days": completed_days,
        "total_days": total_days,
        "message": f"Weekly test unlocked for week {week_number}. You can now take the test.",
    })
