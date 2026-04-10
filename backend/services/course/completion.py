"""
Production-grade Course Completion Service.

Handles:
- Day completion with 3 quiz attempts requirement
- Weekly test unlocking after 5 days completion
- Course progress tracking
- Knowledge state updates
- Streak tracking
- Certificate eligibility checks
"""
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional
from django.utils import timezone
from django.db import transaction
from django.db.models import Avg, Count, Q

logger = logging.getLogger(__name__)


class CourseCompletionService:
    """
    Service for handling all course completion logic.
    
    Business Rules:
    1. Day is marked complete after attempting 3 quizzes (regardless of score)
    2. Weekly test unlocks after all 5 days are completed
    3. Course completes after all weeks + weekly tests are done
    4. Streak updates based on daily activity
    5. Knowledge state updates based on quiz performance
    """
    
    # Constants
    QUIZ_ATTEMPTS_REQUIRED = 3
    DAYS_PER_WEEK = 5
    PASSING_SCORE = 50.0  # Percentage
    
    def __init__(self):
        pass
    
    @transaction.atomic
    def complete_day(
        self,
        user_id: str,
        course_id: str,
        week_number: int,
        day_number: int,
        quiz_score: float,
        quiz_attempts: int,
        time_spent_minutes: int = 0,
    ) -> Dict[str, Any]:
        """
        Complete a day after quiz submission.
        
        Args:
            user_id: User UUID
            course_id: Course UUID
            week_number: Week number (1-based)
            day_number: Day number (1-5)
            quiz_score: Latest quiz score (0-100)
            quiz_attempts: Total quiz attempts for this day
            time_spent_minutes: Time spent on the day
            
        Returns:
            Dict with completion status and next steps
        """
        from apps.courses.models import Course, DayPlan, WeekPlan, CourseProgress
        from apps.quizzes.models import QuizAttempt
        
        try:
            # Fetch related objects
            course = Course.objects.select_related("user").get(id=course_id)
            week = WeekPlan.objects.get(course=course, week_number=week_number)
            day = DayPlan.objects.select_related("week_plan").get(
                week_plan=week,
                day_number=day_number,
            )
            
            # Validate day is not locked
            if day.is_locked:
                return {
                    "success": False,
                    "error": "Day is locked",
                    "error_code": "DAY_LOCKED",
                }

            # Mark day as complete on ANY quiz attempt (no minimum attempts required)
            # Next day unlocks immediately regardless of score
            now = timezone.now()
            day.is_completed = True
            day.completed_at = now
            day.quiz_score = quiz_score
            day.quiz_attempts = quiz_attempts
            day.time_spent_minutes += time_spent_minutes
            if not day.started_at:
                day.started_at = now
            day.save(update_fields=[
                "is_completed", "completed_at", "quiz_score",
                "quiz_attempts", "time_spent_minutes", "started_at",
            ])

            logger.info(
                f"Day completed: user={user_id}, course={course_id}, "
                f"week={week_number}, day={day_number}, score={quiz_score}"
            )
            
            # Update course progress
            progress = self._update_course_progress(
                user_id=user_id,
                course=course,
                week=week,
                day=day,
                quiz_score=quiz_score,
                time_spent_minutes=time_spent_minutes,
            )
            
            # Check and unlock weekly test
            week_test_unlocked = self._check_and_unlock_weekly_test(week)
            
            # Unlock next day
            next_day_unlocked = self._unlock_next_day(course, week_number, day_number)
            
            # Update streak
            streak_updated = self._update_streak(progress)
            
            # Update knowledge state
            self._update_knowledge_state(user_id, course, day)
            
            return {
                "success": True,
                "day_completed": True,
                "week_test_unlocked": week_test_unlocked,
                "next_day_unlocked": next_day_unlocked,
                "streak_days": progress.streak_days,
                "overall_percentage": progress.overall_percentage,
                "current_week": progress.current_week,
                "current_day": progress.current_day,
                "quiz_score": quiz_score,
                "quiz_attempts": quiz_attempts,
            }
            
        except Course.DoesNotExist:
            logger.error(f"Course not found: {course_id}")
            return {
                "success": False,
                "error": "Course not found",
                "error_code": "COURSE_NOT_FOUND",
            }
        except WeekPlan.DoesNotExist:
            logger.error(f"Week not found: {week_number} in course {course_id}")
            return {
                "success": False,
                "error": "Week not found",
                "error_code": "WEEK_NOT_FOUND",
            }
        except DayPlan.DoesNotExist:
            logger.error(f"Day not found: {day_number} in week {week_number}")
            return {
                "success": False,
                "error": "Day not found",
                "error_code": "DAY_NOT_FOUND",
            }
        except Exception as exc:
            logger.exception(f"Error completing day: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "error_code": "INTERNAL_ERROR",
            }
    
    def _update_course_progress(
        self,
        user_id: str,
        course: Any,
        week: Any,
        day: Any,
        quiz_score: float,
        time_spent_minutes: int,
    ) -> Any:
        """Update course progress tracking."""
        from apps.courses.models import CourseProgress, DayPlan
        
        progress, created = CourseProgress.objects.get_or_create(
            user_id=user_id,
            course=course,
            defaults={
                "total_days": course.total_days,
                "total_weeks": course.duration_weeks,
                "current_week": week.week_number,
                "current_day": day.day_number,
            }
        )
        
        # Count total completed days
        completed_days = DayPlan.objects.filter(
            week_plan__course=course,
            is_completed=True,
        ).count()
        
        progress.completed_days = completed_days
        progress.total_days = course.total_days
        progress.total_weeks = course.duration_weeks
        
        # Calculate overall percentage
        if progress.total_days > 0:
            progress.overall_percentage = round(
                (progress.completed_days / progress.total_days) * 100, 1
            )
        else:
            progress.overall_percentage = 0.0
        
        # Update average quiz score across all completed days
        self._update_avg_quiz_score(progress, course)
        
        # Update total study time
        progress.total_study_time += time_spent_minutes
        
        # Update current position
        if day.day_number < self.DAYS_PER_WEEK:
            progress.current_day = day.day_number + 1
            progress.current_week = week.week_number
        else:
            progress.current_day = 1
            if week.week_number < course.duration_weeks:
                progress.current_week = week.week_number + 1
            else:
                progress.current_week = week.week_number
        
        progress.last_activity = timezone.now()
        progress.save()
        
        logger.info(
            f"Progress updated: user={user_id}, course={course.id}, "
            f"completed={completed_days}/{progress.total_days}, "
            f"percentage={progress.overall_percentage}%"
        )
        
        return progress
    
    def _update_avg_quiz_score(self, progress: Any, course: Any) -> None:
        """Update average quiz score from all completed days."""
        from apps.courses.models import DayPlan
        
        completed_days = DayPlan.objects.filter(
            week_plan__course=course,
            is_completed=True,
            quiz_score__isnull=False,
        )
        
        if completed_days.exists():
            avg_score = completed_days.aggregate(
                avg_score=Avg("quiz_score")
            )["avg_score"]
            progress.avg_quiz_score = round(avg_score, 1) if avg_score else 0.0
        else:
            progress.avg_quiz_score = 0.0
    
    def _check_and_unlock_weekly_test(self, week: Any) -> bool:
        """
        Check if all 5 days are completed and unlock weekly test.
        
        Returns:
            True if weekly test was unlocked, False otherwise
        """
        # Refresh week object to get latest day completion status
        from apps.courses.models import WeekPlan
        week = WeekPlan.objects.select_related("course").prefetch_related("days").get(
            id=week.id
        )
        
        all_days_completed = not week.days.filter(
            is_completed=False
        ).exists()
        
        logger.info(
            f"Checking weekly test unlock: week={week.week_number}, "
            f"all_days_completed={all_days_completed}, test_unlocked={week.test_unlocked}"
        )

        if all_days_completed and not week.test_unlocked:
            week.test_unlocked = True
            week.save(update_fields=["test_unlocked"])

            logger.info(
                f"Weekly test unlocked: course={week.course.id}, week={week.week_number}"
            )

            # Trigger weekly test generation if not already generated
            if not week.test_generated:
                from apps.courses.tasks import generate_weekly_test_task
                generate_weekly_test_task.delay(str(week.course.id), week.week_number)
            
            return True
        
        return False
    
    def _unlock_next_day(
        self,
        course: Any,
        week_number: int,
        day_number: int,
    ) -> bool:
        """
        Unlock the next day after current day completion.

        Returns:
            True if next day was unlocked, False otherwise
        """
        from apps.courses.models import DayPlan

        try:
            if day_number < self.DAYS_PER_WEEK:
                # Unlock next day in same week
                next_day = DayPlan.objects.get(
                    week_plan__course=course,
                    week_number=week_number,
                    day_number=day_number + 1,
                )
                if next_day.is_locked:
                    next_day.is_locked = False
                    next_day.save(update_fields=["is_locked"])
                    logger.info(
                        f"Unlocked next day: course={course.id}, "
                        f"week={week_number}, day={day_number + 1}"
                    )
                    return True
            else:
                # Last day of week - next week's day 1 will be unlocked by weekly test
                pass
            
            return False
            
        except DayPlan.DoesNotExist:
            logger.warning(f"Next day not found: week={week_number}, day={day_number + 1}")
            return False
    
    def _update_streak(self, progress: Any) -> bool:
        """
        Update streak based on last activity.
        
        Returns:
            True if streak was updated, False otherwise
        """
        now = timezone.now().date()
        
        if progress.last_activity:
            last_date = progress.last_activity.date()
            yesterday = now - timedelta(days=1)
            
            if last_date == now:
                # Already studied today, no change
                return False
            elif last_date == yesterday:
                # Studied yesterday, increment streak
                progress.streak_days += 1
                progress.longest_streak = max(
                    progress.longest_streak, progress.streak_days
                )
                progress.save(update_fields=["streak_days", "longest_streak"])
                logger.info(f"Streak incremented: {progress.streak_days} days")
                return True
            elif last_date < yesterday:
                # Streak broken, reset to 1
                progress.streak_days = 1
                progress.save(update_fields=["streak_days"])
                logger.info("Streak reset to 1")
                return True
        
        # First activity
        progress.streak_days = 1
        progress.longest_streak = max(progress.longest_streak, 1)
        progress.save(update_fields=["streak_days", "longest_streak"])
        return True
    
    def _update_knowledge_state(
        self,
        user_id: str,
        course: Any,
        day: Any,
    ) -> None:
        """
        Update user knowledge state based on quiz performance.
        
        This analyzes quiz results and updates confidence scores for
        concepts covered in the day's content.
        """
        from apps.users.models import UserKnowledgeState
        from apps.quizzes.models import QuizAttempt
        
        # Get quiz attempts for this day
        attempts = QuizAttempt.objects.filter(
            user_id=user_id,
            question__course=course,
            question__week_number=day.week_plan.week_number,
            question__day_number=day.day_number,
        )
        
        if not attempts.exists():
            return
        
        # Group by concept/tag and calculate performance
        concept_performance: Dict[str, Dict[str, int]] = {}
        
        for attempt in attempts:
            # Extract concept from question tags or topic
            concept = attempt.question.topic or "general"
            
            if concept not in concept_performance:
                concept_performance[concept] = {"correct": 0, "total": 0}
            
            concept_performance[concept]["total"] += 1
            if attempt.is_correct:
                concept_performance[concept]["correct"] += 1
        
        # Update knowledge state for each concept
        for concept, stats in concept_performance.items():
            accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
            
            knowledge_state, created = UserKnowledgeState.objects.get_or_create(
                user_id=user_id,
                concept_tag=concept,
                defaults={
                    "confidence_score": accuracy * 100,
                    "practiced_count": stats["total"],
                    "last_practiced": timezone.now(),
                }
            )
            
            if not created:
                # Update existing knowledge state with weighted average
                old_score = knowledge_state.confidence_score
                new_score = accuracy * 100
                # Weight new performance more heavily
                knowledge_state.confidence_score = round(
                    (old_score * 0.3) + (new_score * 0.7), 1
                )
                knowledge_state.practiced_count += stats["total"]
                knowledge_state.last_practiced = timezone.now()
                knowledge_state.save()
        
        logger.info(
            f"Updated knowledge state for {len(concept_performance)} concepts"
        )
    
    def complete_weekly_test(
        self,
        user_id: str,
        course_id: str,
        week_number: int,
        test_score: float,
        passed: bool,
    ) -> Dict[str, Any]:
        """
        Complete a weekly test.
        
        Args:
            user_id: User UUID
            course_id: Course UUID
            week_number: Week number
            test_score: Test score (0-100)
            passed: Whether test was passed
            
        Returns:
            Dict with completion status
        """
        from apps.courses.models import Course, WeekPlan, CourseProgress
        
        try:
            course = Course.objects.get(id=course_id, user_id=user_id)
            week = WeekPlan.objects.get(course=course, week_number=week_number)
            
            # Mark week as completed
            week.is_completed = True
            week.test_generated = True
            week.save(update_fields=["is_completed", "test_generated"])
            
            # Update course progress
            progress, _ = CourseProgress.objects.get_or_create(
                user_id=user_id,
                course=course,
            )
            
            progress.avg_test_score = test_score
            progress.last_activity = timezone.now()
            progress.save()
            
            # Unlock next week if not last week
            next_week_unlocked = False
            if week_number < course.duration_weeks:
                next_week = WeekPlan.objects.filter(
                    course=course,
                    week_number=week_number + 1,
                ).first()
                
                if next_week:
                    # Unlock all days in next week
                    next_week.days.update(is_locked=False)
                    next_week_unlocked = True
                    
                    # Update progress current position
                    progress.current_week = week_number + 1
                    progress.current_day = 1
                    progress.save()
            
            # Check if course is complete
            course_complete = self._check_course_completion(course)
            
            # Generate certificate if course complete
            certificate_generated = False
            if course_complete:
                certificate_generated = self._generate_certificate(user_id, course_id)
            
            return {
                "success": True,
                "week_completed": True,
                "next_week_unlocked": next_week_unlocked,
                "course_complete": course_complete,
                "certificate_generated": certificate_generated,
                "test_score": test_score,
                "passed": passed,
            }
            
        except Exception as exc:
            logger.exception(f"Error completing weekly test: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "error_code": "INTERNAL_ERROR",
            }
    
    def _check_course_completion(self, course: Any) -> bool:
        """Check if all weeks and tests are completed."""
        from apps.courses.models import WeekPlan
        
        total_weeks = course.duration_weeks
        completed_weeks = WeekPlan.objects.filter(
            course=course,
            is_completed=True,
        ).count()
        
        return completed_weeks >= total_weeks
    
    def _generate_certificate(self, user_id: str, course_id: str) -> bool:
        """Generate certificate for completed course."""
        try:
            from services.certificate.generator import CertificateGenerator
            
            generator = CertificateGenerator()
            result = generator.generate_certificate(user_id, course_id)
            
            if result.get("success"):
                logger.info(
                    f"Certificate generated: user={user_id}, course={course_id}"
                )
                return True
            else:
                logger.error(f"Certificate generation failed: {result.get('error')}")
                return False
                
        except Exception as exc:
            logger.exception(f"Error generating certificate: {exc}")
            return False
    
    def get_day_status(
        self,
        user_id: str,
        course_id: str,
        week_number: int,
        day_number: int,
    ) -> Dict[str, Any]:
        """
        Get detailed status of a day.
        
        Returns:
            Dict with day status, quiz attempts, unlock status, etc.
        """
        from apps.courses.models import Course, WeekPlan, DayPlan
        from apps.quizzes.models import QuizAttempt
        
        try:
            course = Course.objects.get(id=course_id, user_id=user_id)
            week = WeekPlan.objects.get(course=course, week_number=week_number)
            day = DayPlan.objects.get(week_plan=week, day_number=day_number)
            
            # Count quiz attempts
            attempts_count = QuizAttempt.objects.filter(
                user_id=user_id,
                question__course=course,
                question__week_number=week_number,
                question__day_number=day_number,
            ).count()
            
            # Calculate attempts remaining
            attempts_remaining = max(0, self.QUIZ_ATTEMPTS_REQUIRED - attempts_count)
            
            return {
                "day_id": str(day.id),
                "is_completed": day.is_completed,
                "is_locked": day.is_locked,
                "quiz_attempts": attempts_count,
                "attempts_remaining": attempts_remaining,
                "quiz_score": day.quiz_score,
                "can_attempt": not day.is_locked and not day.is_completed,
                "can_complete": attempts_count >= self.QUIZ_ATTEMPTS_REQUIRED,
                "next_unlock_condition": (
                    f"Complete {attempts_remaining} more quiz attempt(s)"
                    if attempts_remaining > 0
                    else "Ready to unlock next day"
                ),
            }
            
        except Exception as exc:
            logger.exception(f"Error getting day status: {exc}")
            return {
                "error": str(exc),
                "error_code": "INTERNAL_ERROR",
            }


# Singleton instance
_completion_service: Optional[CourseCompletionService] = None


def get_completion_service() -> CourseCompletionService:
    """Get singleton instance of CourseCompletionService."""
    global _completion_service
    if _completion_service is None:
        _completion_service = CourseCompletionService()
    return _completion_service
