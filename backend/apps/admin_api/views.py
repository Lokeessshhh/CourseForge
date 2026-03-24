"""
Admin API endpoints.
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def _ok(data, status_code=status.HTTP_200_OK):
    return Response({"success": True, "data": data, "error": None}, status=status_code)


def _err(msg, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"success": False, "data": None, "error": msg}, status=status_code)


# ──────────────────────────────────────────────
# GET /api/admin/stats/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_stats(request):
    """Get platform-wide statistics."""
    from apps.users.models import User
    from apps.courses.models import Course, CourseProgress
    from apps.certificates.models import Certificate
    from django.db.models import Count
    from collections import Counter

    try:
        # Total users
        total_users = User.objects.count()

        # Total courses
        total_courses = Course.objects.count()

        # Average completion rate
        progress_records = CourseProgress.objects.all()
        if progress_records.exists():
            avg_completion = sum(p.overall_percentage for p in progress_records) / progress_records.count()
        else:
            avg_completion = 0

        # Most popular topics
        courses = Course.objects.all()
        topics = [c.topic.lower() for c in courses]
        topic_counts = Counter(topics).most_common(5)
        popular_topics = [topic for topic, count in topic_counts]

        # Certificates issued
        total_certificates = Certificate.objects.filter(is_unlocked=True).count()

        # Active users (last 7 days)
        from django.utils import timezone
        from datetime import timedelta
        week_ago = timezone.now() - timedelta(days=7)
        active_users = User.objects.filter(last_login__gte=week_ago).count()

        # Courses by status
        courses_by_status = dict(
            Course.objects.values_list('status')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        return _ok({
            "total_users": total_users,
            "total_courses": total_courses,
            "avg_completion_rate": round(avg_completion, 1),
            "most_popular_topics": popular_topics,
            "total_certificates": total_certificates,
            "active_users_7d": active_users,
            "courses_by_status": courses_by_status,
        })

    except Exception as exc:
        logger.exception("Error getting admin stats: %s", exc)
        return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# ──────────────────────────────────────────────
# GET /api/admin/users/
# ──────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_users(request):
    """List all users with their progress."""
    from apps.users.models import User
    from apps.courses.models import CourseProgress

    try:
        users = User.objects.all().order_by("-created_at")

        users_data = []
        for user in users[:50]:  # Limit to 50
            progress = CourseProgress.objects.filter(user=user)
            courses_count = progress.count()
            avg_completion = (
                sum(p.overall_percentage for p in progress) / courses_count
                if courses_count > 0 else 0
            )

            users_data.append({
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "courses_count": courses_count,
                "avg_completion": round(avg_completion, 1),
                "created_at": user.created_at.isoformat(),
            })

        return _ok({"users": users_data})

    except Exception as exc:
        logger.exception("Error getting admin users: %s", exc)
        return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
