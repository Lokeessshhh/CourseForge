"""
Debug endpoint for course completion.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def debug_course_completion(request, course_id, week_number):
    """
    Debug endpoint to check course completion status.
    
    Returns detailed information about:
    - Day completion status
    - Weekly test unlock status
    - Course progress
    """
    from apps.courses.models import Course, WeekPlan, DayPlan, CourseProgress
    from apps.quizzes.models import QuizAttempt
    
    try:
        course = Course.objects.get(id=course_id, user=request.user)
        week = WeekPlan.objects.get(course=course, week_number=week_number)
        
        # Get all days
        days = DayPlan.objects.filter(week_plan=week).order_by("day_number")
        
        days_status = []
        for day in days:
            # Count quiz attempts for this day
            attempts = QuizAttempt.objects.filter(
                user=request.user,
                question__course=course,
                question__week_number=week_number,
                question__day_number=day.day_number,
            ).count()
            
            days_status.append({
                "day_number": day.day_number,
                "title": day.title,
                "is_completed": day.is_completed,
                "is_locked": day.is_locked,
                "quiz_attempts": attempts,
                "quiz_score": day.quiz_score,
                "completed_at": day.completed_at.isoformat() if day.completed_at else None,
            })
        
        # Check completion
        completed_days = days.filter(is_completed=True).count()
        total_days = days.count()
        
        # Get course progress
        progress = CourseProgress.objects.filter(
            user=request.user,
            course=course,
        ).first()
        
        return Response({
            "success": True,
            "data": {
                "course": {
                    "id": str(course.id),
                    "name": course.course_name,
                    "total_weeks": course.duration_weeks,
                },
                "week": {
                    "week_number": week.week_number,
                    "theme": week.theme,
                    "is_completed": week.is_completed,
                    "test_unlocked": week.test_unlocked,
                    "test_generated": week.test_generated,
                    "completed_days": completed_days,
                    "total_days": total_days,
                },
                "days": days_status,
                "progress": {
                    "completed_days": progress.completed_days if progress else 0,
                    "total_days": progress.total_days if progress else 0,
                    "overall_percentage": progress.overall_percentage if progress else 0,
                    "avg_quiz_score": progress.avg_quiz_score if progress else 0,
                    "current_week": progress.current_week if progress else 0,
                    "current_day": progress.current_day if progress else 0,
                } if progress else None,
            },
        })
        
    except Exception as exc:
        return Response({
            "success": False,
            "error": str(exc),
        }, status=400)
