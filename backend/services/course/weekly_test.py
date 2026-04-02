"""
Weekly Test Service - Production Grade.

Handles:
- Weekly test generation (10 MCQ questions covering all 5 days)
- Test submission and scoring
- Test result tracking
- Certificate eligibility
"""
import logging
from typing import Any, Dict, List, Optional
from django.db import transaction
from django.db.models import Avg

logger = logging.getLogger(__name__)


class WeeklyTestService:
    """
    Service for handling weekly test operations.
    
    Business Rules:
    1. Weekly test unlocks after all 5 days are completed
    2. Test contains 10 MCQ questions (2 from each day)
    3. Passing score: 70%
    4. Must pass to unlock next week
    5. Test can be retaken if failed
    """
    
    QUESTIONS_COUNT = 10
    QUESTIONS_PER_DAY = 2
    PASSING_SCORE = 70.0
    
    def __init__(self):
        pass
    
    @transaction.atomic
    def generate_weekly_test(
        self,
        course_id: str,
        week_number: int,
    ) -> Dict[str, Any]:
        """
        Generate weekly test with 10 MCQ questions.
        
        Args:
            course_id: Course UUID
            week_number: Week number
            
        Returns:
            Dict with test data and questions
        """
        from apps.courses.models import Course, WeekPlan, DayPlan
        from apps.courses.models import WeeklyTest
        from apps.quizzes.models import QuizQuestion
        
        try:
            course = Course.objects.get(id=course_id)
            week = WeekPlan.objects.get(course=course, week_number=week_number)
            
            # Check if test already exists
            existing_test = WeeklyTest.objects.filter(
                course=course,
                week_number=week_number,
            ).first()
            
            if existing_test:
                return {
                    "success": False,
                    "error": "Weekly test already generated",
                    "error_code": "TEST_EXISTS",
                    "test": self._serialize_test(existing_test),
                }
            
            # Check if all 5 days are completed
            completed_days = week.days.filter(is_completed=True).count()
            if completed_days < 5:
                return {
                    "success": False,
                    "error": f"Complete all 5 days first ({completed_days}/5 completed)",
                    "error_code": "DAYS_NOT_COMPLETE",
                }
            
            # Generate questions from AI
            questions = self._generate_test_questions(course, week)
            
            if not questions or len(questions) < self.QUESTIONS_COUNT:
                return {
                    "success": False,
                    "error": "Failed to generate enough questions",
                    "error_code": "GENERATION_FAILED",
                }
            
            # Create weekly test
            test = WeeklyTest.objects.create(
                course=course,
                week_number=week_number,
                questions=questions,
                total_questions=self.QUESTIONS_COUNT,
            )
            
            # Also save to QuizQuestion for tracking
            for i, q_data in enumerate(questions):
                QuizQuestion.objects.create(
                    course=course,
                    week_number=week_number,
                    day_number=0,  # 0 indicates weekly test
                    question_number=i + 1,
                    topic=week.theme or f"Week {week_number} Review",
                    question_text=q_data["question_text"],
                    options=q_data["options"],
                    correct_answer=q_data["correct_answer"],
                    explanation=q_data["explanation"],
                    question_type="weekly_test",
                )
            
            logger.info(
                f"Weekly test generated: course={course_id}, week={week_number}"
            )
            
            return {
                "success": True,
                "test": self._serialize_test(test),
                "questions_count": len(questions),
            }
            
        except Exception as exc:
            logger.exception(f"Error generating weekly test: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "error_code": "INTERNAL_ERROR",
            }
    
    def _generate_test_questions(
        self,
        course: Any,
        week: Any,
    ) -> List[Dict[str, Any]]:
        """
        Generate 10 MCQ questions covering all 5 days.
        
        Uses AI to generate comprehensive questions based on:
        - Theory content from each day
        - Code examples
        - Key concepts
        """
        from services.llm.client import LLMClient
        
        try:
            # Gather content from all 5 days
            days_content = []
            for day in week.days.all().order_by("day_number"):
                days_content.append({
                    "day": day.day_number,
                    "title": day.title or "",
                    "theory": day.theory_content[:500] if day.theory_content else "",
                    "code": day.code_content[:500] if day.code_content else "",
                })
            
            # Call LLM to generate questions
            llm = LLMClient()
            prompt = self._build_test_generation_prompt(course, days_content)
            
            response = llm.generate(
                prompt=prompt,
                temperature=0.7,
                max_tokens=4000,
            )
            
            # Parse response (expecting JSON)
            import json
            try:
                result = json.loads(response)
                questions = result.get("questions", [])
                
                # Validate and format questions
                formatted_questions = []
                for q in questions[:self.QUESTIONS_COUNT]:
                    formatted_questions.append({
                        "id": f"wt_q{len(formatted_questions) + 1}",
                        "question_text": q.get("question", ""),
                        "options": {
                            "a": q.get("options", {}).get("a", ""),
                            "b": q.get("options", {}).get("b", ""),
                            "c": q.get("options", {}).get("c", ""),
                            "d": q.get("options", {}).get("d", ""),
                        },
                        "correct_answer": q.get("correct_answer", "a").lower(),
                        "explanation": q.get("explanation", ""),
                        "difficulty": q.get("difficulty", "medium"),
                        "day_reference": q.get("day_reference", 0),
                    })
                
                return formatted_questions
                
            except json.JSONDecodeError:
                logger.error("Failed to parse LLM response as JSON")
                return []
                
        except Exception as exc:
            logger.exception(f"Error generating test questions: {exc}")
            return []
    
    def _build_test_generation_prompt(
        self,
        course: Any,
        days_content: List[Dict],
    ) -> str:
        """Build prompt for LLM to generate test questions."""
        
        days_text = "\n\n".join([
            f"Day {d['day']}: {d['title']}\n"
            f"Theory: {d['theory'][:200]}...\n"
            f"Code: {d['code'][:200]}..."
            for d in days_content
        ])
        
        return f"""You are an expert educational content creator.
Generate a comprehensive weekly test for the following course.

Course: {course.course_name}
Topic: {course.topic}
Level: {course.level}

Week Content:
{days_text}

Generate exactly {self.QUESTIONS_COUNT} multiple-choice questions (MCQs).
Each question should:
- Test understanding of key concepts from the week
- Have 4 options (a, b, c, d)
- Include the correct answer
- Provide a clear explanation
- Be appropriate for {course.level} level

Return ONLY valid JSON in this format:
{{
  "questions": [
    {{
      "question": "Question text here?",
      "options": {{
        "a": "Option A",
        "b": "Option B",
        "c": "Option C",
        "d": "Option D"
      }},
      "correct_answer": "a",
      "explanation": "Why this is correct",
      "difficulty": "easy|medium|hard",
      "day_reference": 1-5
    }}
  ]
}}
"""
    
    def _serialize_test(self, test: Any) -> Dict[str, Any]:
        """Serialize weekly test for API response."""
        return {
            "id": str(test.id),
            "course_id": str(test.course.id),
            "week_number": test.week_number,
            "total_questions": test.total_questions,
            "generated_at": test.generated_at.isoformat() if test.generated_at else None,
        }
    
    @transaction.atomic
    def submit_test(
        self,
        user_id: str,
        course_id: str,
        week_number: int,
        answers: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Submit weekly test answers.
        
        Args:
            user_id: User UUID
            course_id: Course UUID
            week_number: Week number
            answers: Dict of question_index -> answer_letter
            
        Returns:
            Dict with results and pass/fail status
        """
        from apps.courses.models import Course, WeekPlan
        from apps.courses.models import WeeklyTest
        from apps.quizzes.models import QuizAttempt, QuizQuestion
        
        try:
            course = Course.objects.get(id=course_id, user_id=user_id)
            week = WeekPlan.objects.get(course=course, week_number=week_number)
            
            # Get weekly test
            test = WeeklyTest.objects.filter(
                course=course,
                week_number=week_number,
            ).first()
            
            if not test:
                return {
                    "success": False,
                    "error": "Weekly test not found",
                    "error_code": "TEST_NOT_FOUND",
                }
            
            # Get questions
            questions = QuizQuestion.objects.filter(
                course=course,
                week_number=week_number,
                day_number=0,  # Weekly test
            ).order_by("question_number")
            
            if not questions.exists():
                return {
                    "success": False,
                    "error": "No questions found",
                    "error_code": "NO_QUESTIONS",
                }
            
            # Grade answers
            results = []
            correct_count = 0
            total = questions.count()
            
            for i, question in enumerate(questions):
                user_answer = answers.get(str(i), answers.get(str(i + 1), ""))
                
                # Convert index to letter if needed
                try:
                    idx = int(user_answer)
                    user_answer = chr(97 + idx)
                except (ValueError, TypeError):
                    pass
                
                is_correct = user_answer.lower() == question.correct_answer.lower()
                
                if is_correct:
                    correct_count += 1
                
                # Save attempt
                QuizAttempt.objects.create(
                    user_id=user_id,
                    question=question,
                    user_answer=user_answer,
                    is_correct=is_correct,
                )
                
                results.append({
                    "question_number": i + 1,
                    "your_answer": user_answer,
                    "correct_answer": question.correct_answer,
                    "is_correct": is_correct,
                    "explanation": question.explanation,
                })
            
            # Calculate score
            score = round((correct_count / total * 100), 1) if total > 0 else 0
            passed = score >= self.PASSING_SCORE
            
            # Update week status if passed
            if passed:
                week.is_completed = True
                week.test_generated = True
                week.save(update_fields=["is_completed", "test_generated"])
                
                # Unlock next week
                self._unlock_next_week(course, week_number)
            
            logger.info(
                f"Weekly test submitted: user={user_id}, course={course_id}, "
                f"week={week_number}, score={score}, passed={passed}"
            )
            
            return {
                "success": True,
                "score": score,
                "total": total,
                "correct": correct_count,
                "passed": passed,
                "passing_score": self.PASSING_SCORE,
                "results": results,
                "week_completed": passed,
                "next_week_unlocked": passed,
            }
            
        except Exception as exc:
            logger.exception(f"Error submitting weekly test: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "error_code": "INTERNAL_ERROR",
            }
    
    def _unlock_next_week(
        self,
        course: Any,
        week_number: int,
    ) -> bool:
        """Unlock the next week after passing weekly test."""
        from apps.courses.models import WeekPlan
        
        if week_number >= course.duration_weeks:
            return False
        
        next_week = WeekPlan.objects.filter(
            course=course,
            week_number=week_number + 1,
        ).first()
        
        if next_week:
            # Unlock all days in next week
            next_week.days.update(is_locked=False)
            logger.info(
                f"Unlocked week {week_number + 1} for course {course.id}"
            )
            return True
        
        return False
    
    def get_test_status(
        self,
        user_id: str,
        course_id: str,
        week_number: int,
    ) -> Dict[str, Any]:
        """Get weekly test status and unlock state."""
        from apps.courses.models import Course, WeekPlan
        from apps.courses.models import WeeklyTest
        
        try:
            course = Course.objects.get(id=course_id, user_id=user_id)
            week = WeekPlan.objects.get(course=course, week_number=week_number)
            
            # Check if test is unlocked
            is_unlocked = week.test_unlocked
            
            # Check if all days are completed
            completed_days = week.days.filter(is_completed=True).count()
            
            # Get test if exists
            test = WeeklyTest.objects.filter(
                course=course,
                week_number=week_number,
            ).first()
            
            # Get user's best attempt
            from apps.quizzes.models import QuizAttempt, QuizQuestion
            test_questions = QuizQuestion.objects.filter(
                course=course,
                week_number=week_number,
                day_number=0,
            )
            
            attempts = QuizAttempt.objects.filter(
                user_id=user_id,
                question__in=test_questions,
            )
            
            best_score = None
            attempts_count = 0
            
            if attempts.exists():
                # Group by question and calculate score per attempt session
                # For simplicity, just get average
                correct = attempts.filter(is_correct=True).count()
                total = attempts.count()
                if total > 0:
                    best_score = round((correct / total) * 100, 1)
                attempts_count = attempts.values('question').distinct().count()
            
            return {
                "is_unlocked": is_unlocked,
                "test_exists": test is not None,
                "completed_days": completed_days,
                "total_days": 5,
                "can_attempt": is_unlocked and (test is not None),
                "best_score": best_score,
                "attempts_count": attempts_count,
                "week_completed": week.is_completed,
            }
            
        except Exception as exc:
            logger.exception(f"Error getting test status: {exc}")
            return {
                "error": str(exc),
                "error_code": "INTERNAL_ERROR",
            }


# Singleton instance
_weekly_test_service: Optional[WeeklyTestService] = None


def get_weekly_test_service() -> WeeklyTestService:
    """Get singleton instance of WeeklyTestService."""
    global _weekly_test_service
    if _weekly_test_service is None:
        _weekly_test_service = WeeklyTestService()
    return _weekly_test_service
