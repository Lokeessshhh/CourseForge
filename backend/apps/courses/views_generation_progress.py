"""Course generation progress endpoint."""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def course_generation_progress(request, course_id):
    """
    Get real-time course generation progress.

    Returns:
    {
        "status": "generating" | "ready" | "failed",
        "progress": 0-100,
        "total_days": 20,
        "completed_days": 15,
        "current_stage": "Generating Week 3...",
        "weeks": [...]
    }
    """
    from apps.courses.models import Course, WeekPlan, DayPlan

    logger.info("Generation progress request: course_id=%s, user=%s", course_id, request.user)

    try:
        course = Course.objects.get(id=course_id, user=request.user)
        logger.info("Found course: %s, status=%s, progress=%d/%d", 
                   course.id, course.generation_status, course.generation_progress, course.total_days)

        # Count completed days
        # For updates, use generation_progress as the tracker (it tracks days updated)
        # Calculate total based on what's being updated
        if course.generation_status == "updating":
            # For updates, calculate total from weeks being updated
            # Use the course's generation_progress to determine the scale
            # generation_progress starts at 0 and increments by 5 for each week updated
            # So we can estimate total from the expected update size
            weeks_being_updated = 0
            if course.duration_weeks <= 4:
                # Small course, likely 2 weeks being updated (50% of 4 = 2)
                weeks_being_updated = 2
            elif course.duration_weeks <= 6:
                # Medium course, likely 2-3 weeks being updated
                weeks_being_updated = 3
            else:
                # Large course
                weeks_being_updated = 4
            total_days = weeks_being_updated * 5
        else:
            total_days = course.duration_weeks * 5 if course.duration_weeks else 0
        
        completed_days = course.generation_progress or 0

        # Calculate progress percentage
        progress = round((completed_days / total_days) * 100) if total_days > 0 else 0

        # Build weeks structure for UI
        weeks_data = []
        for week in course.weeks.prefetch_related('days').all():
            days_data = []
            for day in week.days.all():
                # Determine day status based on generation flags
                if day.theory_generated and day.code_generated:
                    day_status = "completed"
                elif day.title:  # Has content but not fully generated
                    day_status = "generating"
                else:
                    day_status = "pending"

                days_data.append({
                    "day": day.day_number,
                    "title": day.title or f"Day {day.day_number}",
                    "status": day_status,
                })

            # Determine week status
            completed_day_count = sum(1 for d in days_data if d["status"] == "completed")
            if completed_day_count == 5:
                week_status = "completed"
            elif completed_day_count > 0:
                week_status = "generating"
            else:
                week_status = "pending"

            weeks_data.append({
                "week": week.week_number,
                "status": week_status,
                "days": days_data,
            })

        # Determine current stage
        current_stage = "Initializing course structure..."
        if course.generation_status == "generating":
            if completed_days == 0:
                current_stage = "Generating Week 1, Day 1..."
            else:
                current_week = (completed_days // 5) + 1
                current_day = (completed_days % 5) + 1
                current_stage = f"Generating Week {current_week}, Day {current_day}..."
        elif course.generation_status == "ready":
            current_stage = "Course generation complete!"
        elif course.generation_status == "failed":
            current_stage = "Generation failed. Please try again."

        return Response({
            "success": True,
            "data": {
                "id": str(course.id),
                "topic": course.topic or course.course_name,
                "status": course.generation_status,
                "progress": progress,
                "completed_days": completed_days,
                "total_days": total_days,
                "current_stage": current_stage,
                "generation_status": course.generation_status,
                "weeks": weeks_data,
            },
        })

    except Course.DoesNotExist:
        logger.warning("Course not found: course_id=%s, user=%s", course_id, request.user)
        # Check if course exists but belongs to different user
        try:
            course = Course.objects.get(id=course_id)
            logger.warning("Course exists but belongs to different user: course.user=%s, request.user=%s", 
                          course.user, request.user)
        except Course.DoesNotExist:
            pass
        
        return Response({
            "success": False,
            "error": "Course not found",
        }, status=404)
    except Exception as e:
        logger.exception("Error getting course progress: %s", e)
        return Response({
            "success": False,
            "error": str(e),
        }, status=400)
