"""
UserContextLoader for LearnAI AI Tutor.

Loads comprehensive user context for personalized tutoring:
- User profile and skill level
- Knowledge state (weak/strong concepts)
- Course progress and current position
- Quiz scores and study patterns
- Recent conversations
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class UserContextLoader:
    """
    Loads complete user context for AI tutor personalization.
    
    All context loading runs in parallel for performance.
    
    Context includes:
    - Profile: name, skill level, total courses
    - Knowledge State: weak concepts, strong concepts
    - Course Context: progress, current week/day, quiz scores
    - Day Context: specific lesson content, quiz attempts
    - Conversations: recent chat history
    """
    
    SCOPE_GLOBAL = "global"
    SCOPE_COURSE = "course"
    SCOPE_DAY = "day"
    
    async def load_full_context(
        self,
        user_id: str,
        scope: str = "global",
        course_id: Optional[str] = None,
        week: Optional[int] = None,
        day: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Load everything about user in parallel.
        
        Args:
            user_id: User UUID
            scope: Context scope (global/course/day)
            course_id: Course UUID for course/day scope
            week: Week number for day scope
            day: Day number for day scope
            
        Returns:
            Complete context dictionary
        """
        # Base tasks always run
        tasks = [
            self._load_user_profile(user_id),
            self._load_knowledge_state(user_id),
            self._load_recent_conversations(user_id, course_id),
        ]
        
        # Scope-specific tasks
        if scope == self.SCOPE_GLOBAL:
            tasks.append(self._load_all_courses_summary(user_id))
        elif scope == self.SCOPE_COURSE and course_id:
            tasks.append(self._load_course_context(user_id, course_id))
        elif scope == self.SCOPE_DAY and course_id:
            tasks.append(self._load_day_context(user_id, course_id, week, day))
        
        # Run all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("Context task %d failed: %s", i, result)
                processed_results.append({})
            else:
                processed_results.append(result)
        
        return self._build_context_dict(processed_results, scope, course_id, week, day)
    
    async def _load_user_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Load user profile information.
        
        Args:
            user_id: User UUID
            
        Returns:
            Profile dict with name, skill_level, total_courses
        """
        from apps.users.models import User
        from apps.courses.models import CourseProgress
        
        @sync_to_async
        def _fetch():
            try:
                user = User.objects.get(id=user_id)
                total_courses = CourseProgress.objects.filter(user_id=user_id).count()
                
                return {
                    "name": user.name or "Student",
                    "email": user.email,
                    "skill_level": user.skill_level or "beginner",
                    "total_courses": total_courses,
                    "user_id": str(user.id),
                }
            except User.DoesNotExist:
                logger.warning("User not found: %s", user_id)
                return {
                    "name": "Student",
                    "skill_level": "beginner",
                    "total_courses": 0,
                }
        
        return await _fetch()
    
    async def _load_knowledge_state(self, user_id: str) -> Dict[str, Any]:
        """
        Load user's knowledge state (weak and strong concepts).
        
        Args:
            user_id: User UUID
            
        Returns:
            Dict with weak_concepts and strong_concepts lists
        """
        from apps.users.models import UserKnowledgeState
        
        @sync_to_async
        def _fetch():
            states = list(
                UserKnowledgeState.objects.filter(user_id=user_id)
                .order_by("confidence_score")
                .values("concept", "confidence_score", "times_practiced", "last_error")[:30]
            )
            
            weak = [
                {
                    "concept": s["concept"],
                    "confidence": round(s["confidence_score"], 2),
                    "times_practiced": s["times_practiced"],
                }
                for s in states
                if s["confidence_score"] < 0.5
            ][:10]
            
            strong = [
                {
                    "concept": s["concept"],
                    "confidence": round(s["confidence_score"], 2),
                }
                for s in states
                if s["confidence_score"] >= 0.8
            ][:10]
            
            improving = [
                s["concept"]
                for s in states
                if 0.5 <= s["confidence_score"] < 0.8
            ][:5]
            
            return {
                "weak_concepts": weak,
                "strong_concepts": strong,
                "improving_concepts": improving,
                "total_tracked": len(states),
            }
        
        return await _fetch()
    
    async def _load_course_context(self, user_id: str, course_id: str) -> Dict[str, Any]:
        """
        Load context for a specific course.
        
        Args:
            user_id: User UUID
            course_id: Course UUID
            
        Returns:
            Course context dict
        """
        from apps.courses.models import Course, CourseProgress, DayPlan
        
        @sync_to_async
        def _fetch():
            try:
                course = Course.objects.get(id=course_id, user_id=user_id)
                
                # Get progress
                try:
                    progress = CourseProgress.objects.get(user_id=user_id, course_id=course_id)
                except CourseProgress.DoesNotExist:
                    progress = None
                
                # Get current unlocked but not completed day
                current_day = (
                    DayPlan.objects.filter(
                        week_plan__course_id=course_id,
                        is_locked=False,
                        is_completed=False,
                    )
                    .select_related("week_plan")
                    .order_by("week_plan__week_number", "day_number")
                    .first()
                )
                
                # Get last completed day
                last_completed = (
                    DayPlan.objects.filter(
                        week_plan__course_id=course_id,
                        is_completed=True,
                    )
                    .select_related("week_plan")
                    .order_by("-week_plan__week_number", "-day_number")
                    .first()
                )
                
                # Calculate total completed days
                completed_days = DayPlan.objects.filter(
                    week_plan__course_id=course_id,
                    is_completed=True,
                ).count()
                
                total_days = course.duration_weeks * 5 if course.duration_weeks else 0
                
                return {
                    "course_id": str(course.id),
                    "topic": course.topic,
                    "course_name": course.course_name,
                    "level": course.level,
                    "total_weeks": course.duration_weeks or 0,
                    "current_week": progress.current_week if progress else 1,
                    "current_day": progress.current_day if progress else 1,
                    "overall_percentage": round(progress.overall_percentage, 1) if progress else 0,
                    "streak_days": progress.streak_days if progress else 0,
                    "avg_quiz_score": round(progress.avg_quiz_score, 1) if progress else 0,
                    "avg_test_score": round(progress.avg_test_score, 1) if progress else 0,
                    "total_study_hours": round(progress.total_study_time / 60, 1) if progress else 0,
                    "current_day_title": current_day.title if current_day else None,
                    "current_week_theme": current_day.week_plan.theme if current_day else None,
                    "last_completed_title": last_completed.title if last_completed else None,
                    "completed_days": completed_days,
                    "total_days": total_days,
                    "status": course.status,
                }
            except Course.DoesNotExist:
                logger.warning("Course not found: %s", course_id)
                return {}
        
        return await _fetch()
    
    async def _load_day_context(
        self,
        user_id: str,
        course_id: str,
        week: Optional[int],
        day: Optional[int],
    ) -> Dict[str, Any]:
        """
        Load context for a specific day within a course.
        
        Args:
            user_id: User UUID
            course_id: Course UUID
            week: Week number
            day: Day number
            
        Returns:
            Day context dict
        """
        from apps.courses.models import DayPlan
        from apps.quizzes.models import QuizAttempt
        
        # First get course context
        course_ctx = await self._load_course_context(user_id, course_id)
        
        if not week or not day:
            return course_ctx
        
        @sync_to_async
        def _fetch_day():
            try:
                day_plan = DayPlan.objects.select_related("week_plan").get(
                    week_plan__course_id=course_id,
                    week_plan__week_number=week,
                    day_number=day,
                )
                
                # Get quiz attempts for this day
                quiz_attempts = QuizAttempt.objects.filter(
                    user_id=user_id,
                    question__day_plan=day_plan,
                ).count()
                
                return {
                    "day_id": str(day_plan.id),
                    "day_title": day_plan.title,
                    "day_number": day_plan.day_number,
                    "week_number": day_plan.week_plan.week_number,
                    "week_theme": day_plan.week_plan.theme,
                    "is_completed": day_plan.is_completed,
                    "is_locked": day_plan.is_locked,
                    "theory_generated": day_plan.theory_generated,
                    "code_generated": day_plan.code_generated,
                    "quiz_generated": day_plan.quiz_generated,
                    "theory_content_preview": day_plan.theory_content[:500] if day_plan.theory_content else None,
                    "code_content_preview": day_plan.code_content[:300] if day_plan.code_content else None,
                    "quiz_attempts": quiz_attempts,
                    "quiz_score": day_plan.quiz_score,
                    "time_spent_minutes": day_plan.time_spent_minutes,
                    "started_at": day_plan.started_at.isoformat() if day_plan.started_at else None,
                    "completed_at": day_plan.completed_at.isoformat() if day_plan.completed_at else None,
                }
            except DayPlan.DoesNotExist:
                logger.warning("Day not found: week=%s day=%s", week, day)
                return {}
        
        day_ctx = await _fetch_day()
        
        # Merge course and day context
        return {**course_ctx, **day_ctx}
    
    async def _load_all_courses_summary(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Load summary of all user's courses for global scope.
        
        Args:
            user_id: User UUID
            
        Returns:
            List of course summaries
        """
        from apps.courses.models import Course, CourseProgress
        
        @sync_to_async
        def _fetch():
            courses = list(
                Course.objects.filter(
                    user_id=user_id,
                    generation_status="ready",
                )
                .prefetch_related("progress_records")
                .order_by("-created_at")[:10]
            )
            
            summaries = []
            for course in courses:
                progress = course.progress_records.first()
                summaries.append({
                    "course_id": str(course.id),
                    "topic": course.topic,
                    "course_name": course.course_name,
                    "level": course.level,
                    "duration_weeks": course.duration_weeks,
                    "progress_percentage": round(progress.overall_percentage, 1) if progress else 0,
                    "current_week": progress.current_week if progress else 1,
                    "status": course.status,
                    "created_at": course.created_at.isoformat() if course.created_at else None,
                })
            
            return summaries
        
        return await _fetch()
    
    async def _load_recent_conversations(
        self,
        user_id: str,
        course_id: Optional[str] = None,
        limit: int = 6,
    ) -> List[Dict[str, Any]]:
        """
        Load recent conversation history.
        
        Args:
            user_id: User UUID
            course_id: Optional course filter
            limit: Max conversations to load
            
        Returns:
            List of conversation messages
        """
        from apps.conversations.models import Conversation
        
        @sync_to_async
        def _fetch():
            qs = Conversation.objects.filter(user_id=user_id)
            if course_id:
                qs = qs.filter(course_id=course_id)
            
            conversations = list(
                qs.order_by("-created_at")[:limit]
                .values("role", "content", "created_at", "course_id")
            )
            
            return [
                {
                    "role": c["role"],
                    "content": c["content"][:300] if c["content"] else "",
                    "created_at": c["created_at"].isoformat() if c["created_at"] else None,
                }
                for c in conversations
            ]
        
        return await _fetch()
    
    def _build_context_dict(
        self,
        results: List[Any],
        scope: str,
        course_id: Optional[str],
        week: Optional[int],
        day: Optional[int],
    ) -> Dict[str, Any]:
        """
        Build the final context dictionary from parallel results.
        
        Args:
            results: List of results from parallel tasks
            scope: Context scope
            course_id: Course UUID if applicable
            week: Week number if applicable
            day: Day number if applicable
            
        Returns:
            Complete context dictionary
        """
        profile = results[0] if len(results) > 0 else {}
        knowledge = results[1] if len(results) > 1 else {}
        conversations = results[2] if len(results) > 2 else []
        
        context = {
            "scope": scope,
            "profile": profile,
            "knowledge_state": knowledge,
            "recent_conversations": conversations,
            "course_id": course_id,
            "week": week,
            "day": day,
        }
        
        # Add scope-specific data
        if scope == self.SCOPE_GLOBAL and len(results) > 3:
            context["all_courses"] = results[3]
        elif scope in [self.SCOPE_COURSE, self.SCOPE_DAY] and len(results) > 3:
            context["current_course"] = results[3]
        
        return context
    
    def build_context_string(self, context: Dict[str, Any]) -> str:
        """
        Build a formatted context string for the LLM prompt.
        
        Args:
            context: Context dictionary from load_full_context
            
        Returns:
            Formatted context string
        """
        profile = context.get("profile", {})
        knowledge = context.get("knowledge_state", {})
        conversations = context.get("recent_conversations", [])
        scope = context.get("scope", "global")
        
        # Build base context
        ctx_str = f"""STUDENT PROFILE:
Name: {profile.get('name', 'Student')}
Skill Level: {profile.get('skill_level', 'beginner')}
Total Courses Enrolled: {profile.get('total_courses', 0)}

KNOWLEDGE STATE:
"""
        
        # Add weak concepts
        weak = knowledge.get("weak_concepts", [])
        if weak:
            weak_str = ", ".join([
                f"{w['concept']} ({w['confidence']*100:.0f}% confidence)"
                for w in weak[:5]
            ])
            ctx_str += f"Weak concepts (needs help): {weak_str}\n"
        else:
            ctx_str += "Weak concepts: none identified yet\n"
        
        # Add strong concepts
        strong = knowledge.get("strong_concepts", [])
        if strong:
            strong_str = ", ".join([s["concept"] for s in strong[:5]])
            ctx_str += f"Strong concepts: {strong_str}\n"
        else:
            ctx_str += "Strong concepts: none yet\n"
        
        # Add improving concepts
        improving = knowledge.get("improving_concepts", [])
        if improving:
            ctx_str += f"Improving: {', '.join(improving[:3])}\n"
        
        # Add recent conversations
        if conversations:
            ctx_str += "\nRECENT CONVERSATION:\n"
            for conv in conversations[-4:]:
                role = conv.get("role", "user").upper()
                content = conv.get("content", "")[:150]
                ctx_str += f"{role}: {content}\n"
        
        # Add scope-specific context
        if scope == self.SCOPE_COURSE or scope == self.SCOPE_DAY:
            course = context.get("current_course", {})
            if course:
                ctx_str += f"""
CURRENT COURSE: {course.get('topic', 'Unknown')} ({course.get('level', 'beginner')})
Progress: Week {course.get('current_week', 1)}/{course.get('total_weeks', 1)} · Day {course.get('current_day', 1)} · {course.get('overall_percentage', 0):.0f}% complete
Current lesson: {course.get('current_day_title') or 'Not started'}
Quiz average: {course.get('avg_quiz_score', 0):.0f}%
Study streak: {course.get('streak_days', 0)} days
Total study time: {course.get('total_study_hours', 0):.1f} hours
"""
        
        if scope == self.SCOPE_DAY:
            day_info = context.get("current_course", {})
            if day_info.get("day_title"):
                ctx_str += f"""
CURRENT LESSON: {day_info.get('day_title')}
Week {day_info.get('week_number', 1)} · Day {day_info.get('day_number', 1)}
Quiz score this day: {day_info.get('quiz_score') or 'Not taken yet'}
Time spent: {day_info.get('time_spent_minutes', 0)} minutes
"""
        
        if scope == self.SCOPE_GLOBAL:
            all_courses = context.get("all_courses", [])
            if all_courses:
                ctx_str += "\nALL COURSES:\n"
                for c in all_courses[:5]:
                    ctx_str += f"- {c.get('topic', 'Unknown')} ({c.get('level', 'beginner')}): {c.get('progress_percentage', 0):.0f}% complete\n"
        
        return ctx_str
    
    async def get_context_summary(self, user_id: str, course_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a quick summary for welcome messages.
        
        Args:
            user_id: User UUID
            course_id: Optional course UUID
            
        Returns:
            Summary dict for connection message
        """
        profile = await self._load_user_profile(user_id)
        
        summary = {
            "user_name": profile.get("name", "Student"),
            "skill_level": profile.get("skill_level", "beginner"),
        }
        
        if course_id:
            course = await self._load_course_context(user_id, course_id)
            summary.update({
                "course_topic": course.get("topic"),
                "current_day": f"Week {course.get('current_week', 1)} Day {course.get('current_day', 1)}",
                "progress": f"{course.get('overall_percentage', 0):.0f}%",
            })
        
        return summary
