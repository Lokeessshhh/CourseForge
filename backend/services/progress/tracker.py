"""
Progress tracking service.
Handles day/week completion, streak tracking, knowledge state updates.
"""
import logging
from datetime import timedelta
from typing import Any, Dict

from django.utils import timezone

logger = logging.getLogger(__name__)


class ProgressTracker:
    """
    Tracks user progress through a course.
    Handles streaks, time tracking, and knowledge state updates.
    """

    def start_day(
        self,
        user_id: str,
        course_id: str,
        week_number: int,
        day_number: int,
    ) -> Dict[str, Any]:
        """
        Mark a day as started, begin time tracking.
        Update streak logic.

        Args:
            user_id: User ID
            course_id: Course ID
            week_number: Week number
            day_number: Day number

        Returns:
            Dict with status and streak info
        """
        from apps.courses.models import Course, DayPlan, CourseProgress

        try:
            course = Course.objects.get(id=course_id)
            day = DayPlan.objects.select_related("week_plan").get(
                week_plan__course=course,
                week_plan__week_number=week_number,
                day_number=day_number,
            )

            if day.is_locked:
                return {"success": False, "error": "Day is locked"}

            # Set started_at if not already set
            if not day.started_at:
                day.started_at = timezone.now()
                day.save(update_fields=["started_at"])

            # Update progress record
            progress, _ = CourseProgress.objects.get_or_create(
                user_id=user_id,
                course=course,
                defaults={
                    "total_days": course.total_days,
                    "total_weeks": course.duration_weeks,
                }
            )

            # Update streak
            self._update_streak(progress)

            progress.last_activity = timezone.now()
            progress.save(update_fields=["last_activity", "streak_days"])

            return {
                "success": True,
                "started_at": day.started_at.isoformat(),
                "streak_days": progress.streak_days,
            }

        except Exception as exc:
            logger.exception("Error starting day: %s", exc)
            return {"success": False, "error": str(exc)}

    def complete_day(
        self,
        user_id: str,
        course_id: str,
        week_number: int,
        day_number: int,
        quiz_score: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Mark a day as completed, update progress, unlock next day if quiz passed.

        Args:
            user_id: User ID
            course_id: Course ID
            week_number: Week number
            day_number: Day number
            quiz_score: Quiz score (0-100)

        Returns:
            Dict with completion status and next steps
        """
        from apps.courses.models import Course, DayPlan, WeekPlan, CourseProgress

        try:
            course = Course.objects.get(id=course_id)
            week = WeekPlan.objects.get(course=course, week_number=week_number)
            day = DayPlan.objects.select_related("week_plan").get(
                week_plan=week,
                day_number=day_number,
            )

            if day.is_locked:
                return {"success": False, "error": "Day is locked"}

            # Calculate time spent
            now = timezone.now()
            time_spent = 0
            if day.started_at:
                delta = now - day.started_at
                time_spent = int(delta.total_seconds() / 60)

            # Update day
            day.is_completed = True
            day.completed_at = now
            day.quiz_score = quiz_score
            day.quiz_attempts += 1
            day.time_spent_minutes = time_spent
            day.save(update_fields=[
                "is_completed", "completed_at", "quiz_score",
                "quiz_attempts", "time_spent_minutes",
            ])

            # Update progress
            progress, _ = CourseProgress.objects.get_or_create(
                user_id=user_id,
                course=course,
                defaults={
                    "total_days": course.total_days,
                    "total_weeks": course.duration_weeks,
                }
            )

            progress.completed_days += 1
            progress.overall_percentage = round(
                (progress.completed_days / progress.total_days) * 100, 1
            ) if progress.total_days > 0 else 0

            # Update avg quiz score
            completed_days = DayPlan.objects.filter(
                week_plan__course=course,
                is_completed=True,
                quiz_score__isnull=False,
            )
            scores = [d.quiz_score for d in completed_days if d.quiz_score]
            progress.avg_quiz_score = round(sum(scores) / len(scores), 1) if scores else 0

            progress.total_study_time += time_spent
            progress.last_activity = now

            # Update current position
            if day_number < 5:
                progress.current_day = day_number + 1
            else:
                progress.current_day = 1
                if week_number < course.duration_weeks:
                    progress.current_week = week_number + 1

            progress.save()

            # Update streak
            self._update_streak(progress)

            # Check if all 5 days of week done
            week_test_unlocked = False
            all_days_done = not week.days.filter(is_completed=False).exists()
            if all_days_done and not week.test_unlocked:
                week.test_unlocked = True
                week.save(update_fields=["test_unlocked"])
                week_test_unlocked = True
                # Trigger weekly test generation
                from apps.courses.tasks import generate_weekly_test_task
                generate_weekly_test_task.delay(course_id, week_number)

            # Unlock next day if quiz passed (>50%)
            next_day_unlocked = False
            if quiz_score >= 50:
                next_day_unlocked = self._unlock_next_day(course, week_number, day_number)

            # Update knowledge state
            self._update_knowledge_state(user_id, course_id, day)

            return {
                "success": True,
                "day_completed": True,
                "next_day_unlocked": next_day_unlocked,
                "week_test_unlocked": week_test_unlocked,
                "streak_days": progress.streak_days,
                "overall_percentage": progress.overall_percentage,
                "quiz_passed": quiz_score >= 50,
            }

        except Exception as exc:
            logger.exception("Error completing day: %s", exc)
            return {"success": False, "error": str(exc)}

    def complete_week(
        self,
        user_id: str,
        course_id: str,
        week_number: int,
        test_score: float,
    ) -> Dict[str, Any]:
        """
        Mark a week as completed after passing weekly test.
        Unlock next week, check for certificate.

        Args:
            user_id: User ID
            course_id: Course ID
            week_number: Week number
            test_score: Weekly test score (0-100)

        Returns:
            Dict with completion status
        """
        from apps.courses.models import Course, WeekPlan, CourseProgress

        try:
            course = Course.objects.get(id=course_id)
            week = WeekPlan.objects.get(course=course, week_number=week_number)

            # Mark week complete
            week.is_completed = True
            week.save(update_fields=["is_completed"])

            # Update progress
            progress = CourseProgress.objects.get(user_id=user_id, course=course)
            progress.completed_weeks += 1

            # Update avg test score
            attempts = course.weekly_test_attempts.filter(user_id=user_id, passed=True)
            test_scores = [a.percentage for a in attempts]
            progress.avg_test_score = round(
                sum(test_scores) / len(test_scores), 1
            ) if test_scores else 0

            # Update current position
            if week_number < course.duration_weeks:
                progress.current_week = week_number + 1
                progress.current_day = 1

            progress.last_activity = timezone.now()
            progress.save()

            # Unlock next week day 1
            next_week_unlocked = False
            if week_number < course.duration_weeks:
                next_week = WeekPlan.objects.get(course=course, week_number=week_number + 1)
                first_day = next_week.days.get(day_number=1)
                first_day.is_locked = False
                first_day.save(update_fields=["is_locked"])
                next_week_unlocked = True

            # Check if all weeks done - trigger certificate
            certificate_generated = False
            all_weeks_done = not course.weeks.filter(is_completed=False).exists()
            if all_weeks_done:
                progress.completed_at = timezone.now()
                progress.save(update_fields=["completed_at"])
                # Trigger certificate generation
                from apps.courses.tasks import generate_certificate_task
                generate_certificate_task.delay(user_id, course_id)
                certificate_generated = True

            return {
                "success": True,
                "week_completed": True,
                "next_week_unlocked": next_week_unlocked,
                "certificate_generated": certificate_generated,
                "overall_percentage": progress.overall_percentage,
            }

        except Exception as exc:
            logger.exception("Error completing week: %s", exc)
            return {"success": False, "error": str(exc)}

    def get_progress(
        self,
        user_id: str,
        course_id: str,
    ) -> Dict[str, Any]:
        """
        Get complete progress for a user in a course.

        Returns:
            Full progress object with weeks breakdown
        """
        from apps.courses.models import Course, CourseProgress, WeeklyTestAttempt

        try:
            course = Course.objects.get(id=course_id)
            progress = CourseProgress.objects.filter(
                user_id=user_id,
                course=course,
            ).first()

            if not progress:
                # Create initial progress
                progress = CourseProgress.objects.create(
                    user_id=user_id,
                    course=course,
                    total_days=course.total_days,
                    total_weeks=course.duration_weeks,
                )

            # Build weeks breakdown
            weeks_data = []
            for week in course.weeks.all():
                # Get test score if any
                test_attempt = WeeklyTestAttempt.objects.filter(
                    user_id=user_id,
                    course=course,
                    week_number=week.week_number,
                    passed=True,
                ).first()

                days_data = []
                for day in week.days.all():
                    days_data.append({
                        "day_number": day.day_number,
                        "title": day.title,
                        "is_completed": day.is_completed,
                        "is_locked": day.is_locked,
                        "quiz_score": day.quiz_score,
                        "time_spent_minutes": day.time_spent_minutes,
                    })

                weeks_data.append({
                    "week_number": week.week_number,
                    "theme": week.theme,
                    "is_completed": week.is_completed,
                    "test_unlocked": week.test_unlocked,
                    "test_score": test_attempt.percentage if test_attempt else None,
                    "test_passed": test_attempt.passed if test_attempt else False,
                    "days": days_data,
                })

            # Get knowledge state
            from apps.users.models import UserKnowledgeState
            knowledge_state = UserKnowledgeState.objects.filter(user_id=user_id)
            knowledge_data = [
                {"concept": ks.concept_tag, "confidence_score": ks.confidence_score}
                for ks in knowledge_state
            ]

            return {
                "overall_percentage": progress.overall_percentage,
                "completed_days": progress.completed_days,
                "total_days": progress.total_days,
                "completed_weeks": progress.completed_weeks,
                "total_weeks": progress.total_weeks,
                "current_week": progress.current_week,
                "current_day": progress.current_day,
                "avg_quiz_score": progress.avg_quiz_score,
                "avg_test_score": progress.avg_test_score,
                "streak_days": progress.streak_days,
                "total_study_time": progress.total_study_time,
                "last_activity": progress.last_activity.isoformat() if progress.last_activity else None,
                "weeks": weeks_data,
                "knowledge_state": knowledge_data,
            }

        except Exception as exc:
            logger.exception("Error getting progress: %s", exc)
            return {"error": str(exc)}

    def get_all_courses_progress(self, user_id: str) -> Dict[str, Any]:
        """
        Get progress across all courses for a user.

        Returns:
            Dict with all courses progress
        """
        from apps.courses.models import CourseProgress

        try:
            progress_records = CourseProgress.objects.filter(user_id=user_id).select_related("course")

            courses_data = []
            total_study_time = 0
            longest_streak = 0
            completed_courses = 0

            for progress in progress_records:
                courses_data.append({
                    "course_id": str(progress.course.id),
                    "topic": progress.course.topic,
                    "overall_percentage": progress.overall_percentage,
                    "streak_days": progress.streak_days,
                    "last_activity": progress.last_activity.isoformat() if progress.last_activity else None,
                })
                total_study_time += progress.total_study_time
                if progress.streak_days > longest_streak:
                    longest_streak = progress.streak_days
                if progress.completed_at:
                    completed_courses += 1

            return {
                "courses": courses_data,
                "total_study_time": total_study_time,
                "longest_streak": longest_streak,
                "total_courses": len(courses_data),
                "completed_courses": completed_courses,
            }

        except Exception as exc:
            logger.exception("Error getting all courses progress: %s", exc)
            return {"error": str(exc)}

    def calculate_streak(self, user_id: str) -> int:
        """
        Calculate current streak for a user.

        Returns:
            Current streak count
        """
        from apps.courses.models import CourseProgress

        try:
            progress_records = CourseProgress.objects.filter(user_id=user_id)
            max_streak = 0
            for progress in progress_records:
                if progress.streak_days > max_streak:
                    max_streak = progress.streak_days
            return max_streak
        except Exception:
            return 0

    def _update_streak(self, progress) -> None:
        """
        Update streak based on last activity.
        Internal method.
        """
        now = timezone.now()
        today = now.date()

        if progress.last_activity:
            last_date = progress.last_activity.date()
            yesterday = today - timedelta(days=1)

            if last_date == today:
                # Already studied today, no change
                pass
            elif last_date == yesterday:
                # Studied yesterday, increment streak
                progress.streak_days += 1
            else:
                # Gap in studying, reset streak
                progress.streak_days = 1
        else:
            # First activity
            progress.streak_days = 1

    def _unlock_next_day(self, course, week_number: int, day_number: int) -> bool:
        """
        Unlock the next day after quiz passed.

        Returns:
            True if unlocked, False otherwise
        """
        from apps.courses.models import DayPlan

        try:
            if day_number < 5:
                # Next day in same week
                next_week = week_number
                next_day = day_number + 1
            else:
                # First day of next week (but week stays locked until test passed)
                next_week = week_number + 1
                next_day = 1

            # Check if next week exists
            if next_week > course.duration_weeks:
                return False

            # For day 5, don't unlock next week day 1 yet
            # (weekly test must be passed first)
            if day_number == 5:
                return False

            # Unlock next day
            day = DayPlan.objects.get(
                week_plan__course=course,
                week_plan__week_number=next_week,
                day_number=next_day,
            )
            day.is_locked = False
            day.save(update_fields=["is_locked"])
            return True

        except Exception as exc:
            logger.exception("Error unlocking next day: %s", exc)
            return False

    def _update_knowledge_state(self, user_id: str, course_id: str, day) -> None:
        """
        Update user knowledge state based on quiz results.
        Internal method.
        """
        from apps.users.models import UserKnowledgeState
        from apps.quizzes.models import QuizAttempt

        try:
            # Get quiz attempts for this day
            attempts = QuizAttempt.objects.filter(
                user_id=user_id,
                question__day_plan=day,
            ).select_related("question")

            for attempt in attempts:
                # Get concept tags from question (if stored)
                # For now, use day title as concept
                concept = day.title or f"Week {day.week_plan.week_number} Day {day.day_number}"

                state, _ = UserKnowledgeState.objects.get_or_create(
                    user_id=user_id,
                    concept_tag=concept,
                    defaults={"confidence_score": 0.5}
                )

                if attempt.is_correct:
                    state.confidence_score = min(1.0, state.confidence_score + 0.1)
                else:
                    state.confidence_score = max(0.0, state.confidence_score - 0.05)

                state.save(update_fields=["confidence_score"])

        except Exception as exc:
            logger.exception("Error updating knowledge state: %s", exc)

    def is_accessible(
        self,
        user_id: str,
        course_id: str,
        week_number: int,
        day_number: int,
    ) -> bool:
        """
        Check if a day is accessible to the user.
        Based on previous day completion + quiz passed.

        Returns:
            True if accessible, False otherwise
        """
        from apps.courses.models import Course, DayPlan, WeekPlan

        try:
            course = Course.objects.get(id=course_id)
            day = DayPlan.objects.get(
                week_plan__course=course,
                week_plan__week_number=week_number,
                day_number=day_number,
            )

            # Day 1 Week 1 is always accessible (if unlocked)
            if week_number == 1 and day_number == 1:
                return not day.is_locked

            # Check if day is locked
            if day.is_locked:
                return False

            # Check previous day completed with passed quiz
            if day_number == 1:
                # First day of week - check previous week test passed
                prev_week = WeekPlan.objects.filter(
                    course=course,
                    week_number=week_number - 1,
                ).first()
                if prev_week and not prev_week.is_completed:
                    return False
            else:
                # Check previous day
                prev_day = DayPlan.objects.get(
                    week_plan__course=course,
                    week_plan__week_number=week_number,
                    day_number=day_number - 1,
                )
                if not prev_day.is_completed:
                    return False
                if prev_day.quiz_score is not None and prev_day.quiz_score < 50:
                    return False

            return True

        except Exception:
            return False


# Singleton instance
_tracker = None


def get_tracker() -> ProgressTracker:
    """Get the progress tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = ProgressTracker()
    return _tracker
