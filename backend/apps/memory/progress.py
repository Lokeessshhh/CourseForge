"""
Progress tracking helpers.
Marks days/weeks complete, calculates course progress.
Works with the existing course progress models.
"""
import logging

from django.db import connection

logger = logging.getLogger(__name__)


async def mark_day_complete(week_plan_id: str, day_number: int) -> dict:
    """Mark a specific day as completed."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE day_plans
            SET is_completed = TRUE,
                completed_at = NOW()
            WHERE week_plan_id = %s AND day_number = %s
            RETURNING id
            """,
            [week_plan_id, day_number],
        )
        row = cursor.fetchone()

    if row:
        return {"success": True, "day_plan_id": str(row[0])}
    return {"success": False, "error": "Day not found"}


async def mark_week_complete(week_plan_id: str) -> dict:
    """Mark all days in a week as completed."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE day_plans
            SET is_completed = TRUE,
                completed_at = NOW()
            WHERE week_plan_id = %s
            """,
            [week_plan_id],
        )
        return {"success": True, "updated": cursor.rowcount}


async def get_user_progress(
    course_id: str,
    user_id: str,
) -> dict:
    """Get full progress report for a user on a course."""
    with connection.cursor() as cursor:
        # Total days
        cursor.execute(
            """
            SELECT COUNT(*) FROM day_plans dp
            JOIN week_plans wp ON dp.week_plan_id = wp.id
            WHERE wp.course_id = %s
            """,
            [course_id],
        )
        total_days = cursor.fetchone()[0]

        # Completed days
        cursor.execute(
            """
            SELECT COUNT(*) FROM day_plans dp
            JOIN week_plans wp ON dp.week_plan_id = wp.id
            WHERE wp.course_id = %s AND dp.is_completed = TRUE
            """,
            [course_id],
        )
        completed_days = cursor.fetchone()[0]

        # Quiz attempts
        cursor.execute(
            """
            SELECT COUNT(*),
                   AVG(CASE WHEN is_correct THEN 1 ELSE 0 END) * 100
            FROM quiz_attempts
            WHERE user_id = %s
              AND question_id IN (
                  SELECT id FROM quiz_questions WHERE course_id = %s
              )
            """,
            [user_id, course_id],
        )
        quiz_row = cursor.fetchone()
        total_attempts = quiz_row[0] or 0
        avg_score = float(quiz_row[1]) if quiz_row[1] else 0.0

    percentage = round((completed_days / total_days * 100)) if total_days > 0 else 0

    return {
        "course_id": course_id,
        "user_id": user_id,
        "completed_days": completed_days,
        "total_days": total_days,
        "percentage": percentage,
        "total_quiz_attempts": total_attempts,
        "average_quiz_score": round(avg_score, 1),
        "certificate_eligible": percentage == 100 and avg_score >= 50,
    }
