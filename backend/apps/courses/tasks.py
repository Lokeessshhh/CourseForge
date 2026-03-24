"""
Courses app — Celery tasks.
- generate_course_content_task: Fill skeleton with AI content (parallel weeks)
- generate_day_content_task: Generate full content for a single day
- generate_all_quizzes: Generate quiz questions for all days
- generate_weekly_test_task: Generate weekly test (10 questions)
- generate_coding_test_task: Generate coding test (2 problems)
- generate_certificate_task: Generate PDF certificate
- update_knowledge_state_task: Update user knowledge state
- send_streak_reminder: Daily streak reminder
"""
import asyncio
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def generate_course_content_task(
    self,
    course_id: str,
    course_name: str,
    duration_weeks: int,
    level: str,
    goals: list,
):
    """
    Async task: Fill course skeleton with AI-generated content.
    All weeks run in PARALLEL using asyncio.gather().
    Each week saves to DB immediately upon completion.
    Updates generation_progress after each day.
    """
    from apps.courses.models import Course
    from services.course.generator import CourseGenerator
    import asyncio

    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        logger.error("Course %s not found", course_id)
        return

    try:
        course.generation_status = "generating"
        course.save(update_fields=["generation_status"])

        print(f"[TASK] Received generate_course_content_task for course_id={course_id}")
        print(f"[TASK] course_name={course_name} duration_weeks={duration_weeks} level={level}")

        # Detect topic from course_name using vLLM (avoid OpenAI-client retries/timeouts here)
        try:
            from services.llm.qwen_client import QwenClient

            print(f"[TASK] Detecting topic via vLLM for course_id={course_id}...")
            llm = QwenClient(max_tokens=50, temperature=0.1)
            topic = llm.generate(
                prompt=(
                    "Extract the main topic from this course name. "
                    "Return ONLY a short topic phrase (2-4 words).\n\n"
                    f"Course name: {course_name}"
                ),
                max_tokens=50,
            )
            topic = (topic or "").strip().strip('"').strip("'")
            if topic.startswith("[Error:"):
                raise ValueError(topic)
            if not topic:
                topic = course_name
            if len(topic) > 100:
                topic = topic[:100]
            print(f"[TASK] Detected topic: {topic}")
        except Exception as exc:
            print(f"[TASK] Topic detection failed, falling back to course_name. Error: {exc}")
            topic = course_name

        # Update course topic
        course.topic = topic
        course.save(update_fields=["topic"])

        # Create generator and run parallel generation
        generator = CourseGenerator()

        # Build skeleton for reference
        total_days = duration_weeks * 5

        print(f"[TASK] Starting async generation for course {course_id}")
        
        # Run async parallel generation with progress updates
        asyncio.run(
            _generate_with_progress(
                generator=generator,
                course_id=course_id,
                topic=topic,
                level=level,
                goals=goals,
                duration_weeks=duration_weeks,
            )
        )
        
        print(f"[TASK] Async generation completed for course {course_id}")

        # Mark course as ready
        course.refresh_from_db()
        course.generation_status = "ready"
        course.status = "active"
        course.generation_progress = total_days
        course.save(update_fields=["generation_status", "status", "generation_progress"])

        logger.info("Course %s content generation complete (parallel)", course_id)

        # Generate weekly tests (MCQ + Coding) for all weeks
        from apps.courses.tasks import generate_weekly_tests_for_course
        generate_weekly_tests_for_course.delay(course_id)

    except Exception as exc:
        logger.exception("Error generating course %s: %s", course_id, exc)
        try:
            course.refresh_from_db()
            course.generation_status = "failed"
            course.save(update_fields=["generation_status"])
        except Exception:
            pass
        raise self.retry(exc=exc)


async def _generate_with_progress(
    generator,
    course_id: str,
    topic: str,
    level: str,
    goals: list,
    duration_weeks: int,
):
    """
    Run parallel week generation with progress updates.
    Updates course.generation_progress after each day completes.
    """
    print(f"[ASYNC START] Starting parallel generation for course {course_id} ({duration_weeks} weeks)")
    
    # Create parallel tasks for all weeks
    tasks = []
    for week_num in range(1, duration_weeks + 1):
        task = _fill_week_with_progress(
            generator=generator,
            course_id=course_id,
            week_number=week_num,
            total_weeks=duration_weeks,
            topic=topic,
            level=level,
            goals=goals,
        )
        tasks.append(task)

    # Run all weeks in parallel
    print(f"[ASYNC] Running {len(tasks)} week tasks in parallel")
    await asyncio.gather(*tasks)
    print(f"[ASYNC COMPLETE] All weeks generated for course {course_id}")


async def _fill_week_with_progress(
    generator,
    course_id: str,
    week_number: int,
    total_weeks: int,
    topic: str,
    level: str,
    goals: list,
):
    """
    Fill a single week with content and update progress after each day.
    """
    print(f"[WEEK START] Week {week_number} for course {course_id}")
    from apps.courses.models import Course, WeekPlan
    from asgiref.sync import sync_to_async

    try:
        print(f"[WEEK {week_number}] Fetching course and week from DB...")
        course = await sync_to_async(Course.objects.get)(id=course_id)
        week = await sync_to_async(WeekPlan.objects.get)(course=course, week_number=week_number)
        print(f"[WEEK {week_number}] Got course: {course.topic}, week: {week.week_number}")
    except (Course.DoesNotExist, WeekPlan.DoesNotExist) as e:
        print(f"[WEEK {week_number}] ERROR: Course/Week not found - {e}")
        logger.error("Course/Week not found: %s week %s", course_id, week_number)
        return
    except Exception as e:
        print(f"[WEEK {week_number}] ERROR fetching DB: {e}")
        logger.exception("Error fetching course/week: %s", e)
        return

    # Generate week theme and objectives
    theme, objectives = await generator._generate_week_theme(
        week_number, total_weeks, topic, level, goals, []
    )
    week.theme = theme
    week.objectives = objectives
    await sync_to_async(week.save)(update_fields=["theme", "objectives"])

    # Generate content for each day
    previous_titles = []
    days = await sync_to_async(list)(week.days.all().order_by("day_number"))

    for day in days:
        day_num = day.day_number
        print(f"[Course {course_id}] Generating Week {week_number} Day {day_num}...")
        logger.info("Generating content for course %s Week %d Day %d", course_id, week_number, day_num)

        try:
            # Generate day title and tasks
            title, tasks = await generator._generate_day_title_tasks(
                day_num, theme, topic, level, previous_titles
            )
            day.title = title
            day.tasks = tasks
            previous_titles.append(title)

            # Generate theory content
            theory = await generator._generate_theory_content(title, theme, topic, level)

            # Generate code content
            code = await generator._generate_code_content(title, theme, topic, level)

            # Generate quiz questions
            quiz_result = await generator._generate_quiz_questions(title, topic, level)
            quizzes = quiz_result.get("quizzes", [])

            # Save to DB
            day.theory_content = theory
            day.code_content = code
            day.theory_generated = True
            day.code_generated = True
            day.quiz_generated = len(quizzes) > 0
            # Save raw quiz JSON for display
            if quizzes:
                import json
                day.quiz_raw = json.dumps(quizzes, indent=2)
            else:
                day.quiz_raw = ""
            await sync_to_async(day.save)(update_fields=[
                "title", "tasks", "theory_content", "code_content", "quiz_raw",
                "theory_generated", "code_generated", "quiz_generated",
            ])

            # Save quiz questions
            if quizzes:
                from apps.quizzes.models import QuizQuestion
                await sync_to_async(QuizQuestion.objects.filter(
                    course=course, week_number=week_number, day_number=day_num
                ).delete)()
                for quiz in quizzes:
                    await sync_to_async(QuizQuestion.objects.create)(
                        course=course,
                        week_number=week_number,
                        day_number=day_num,
                        question_type="mcq",
                        question_text=quiz.get("question_text", ""),
                        options=quiz.get("options", {}),
                        correct_answer=quiz.get("correct_answer", "a"),
                        explanation=quiz.get("explanation", ""),
                    )

            # Update course progress
            await sync_to_async(course.refresh_from_db)()
            course.generation_progress += 1
            await sync_to_async(course.save)(update_fields=["generation_progress"])

            print(f"[Course {course_id}] ✓ Completed Week {week_number} Day {day_num} (Progress: {course.generation_progress}/{course.total_days})")
            logger.info("Completed day %d for course %s (progress: %d/%d)",
                       day_num, course_id, course.generation_progress, course.total_days)

        except Exception as e:
            print(f"[Course {course_id}] ✗ Error generating Week {week_number} Day {day_num}: {e}")
            logger.exception("Error generating day %d for course %s: %s", day_num, course_id, e)

    logger.info("Completed week %d for course %s", week_number, course_id)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_day_content_task(
    self,
    day_id: str,
    topic: str,
    skill_level: str,
    goals: list,
):
    """
    Generate full lesson content for a single day.
    """
    from apps.courses.models import DayPlan
    from services.course.generator import CourseGenerator

    try:
        day = DayPlan.objects.select_related("week_plan", "week_plan__course").get(id=day_id)
    except DayPlan.DoesNotExist:
        logger.error("Day %s not found", day_id)
        return

    if day.theory_generated and day.code_generated:
        logger.info("Day %s already has content, skipping", day_id)
        return

    try:
        generator = CourseGenerator()

        # Generate theory content
        theory = generator._generate_theory_content(
            day_title=day.title or f"Day {day.day_number}",
            week_theme=day.week_plan.theme or "",
            topic=topic,
            skill_level=skill_level,
        )
        day.theory_content = theory
        day.theory_generated = True

        # Generate code content
        code = generator._generate_code_content(
            day_title=day.title or f"Day {day.day_number}",
            week_theme=day.week_plan.theme or "",
            topic=topic,
            skill_level=skill_level,
        )
        day.code_content = code
        day.code_generated = True

        day.save(update_fields=["theory_content", "theory_generated", "code_content", "code_generated"])

        logger.info("Generated content for day %s", day_id)

    except Exception as exc:
        logger.exception("Error generating content for day %s: %s", day_id, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_all_quizzes(self, course_id: str):
    """
    Generate quiz questions for all days in a course.
    """
    from apps.courses.models import Course, DayPlan
    from apps.quizzes.tasks import generate_quiz_for_day

    try:
        course = Course.objects.get(id=course_id)
        days = DayPlan.objects.filter(week_plan__course=course)

        for day in days:
            generate_quiz_for_day.delay(str(day.id))

        logger.info("Queued quiz generation for %d days in course %s", days.count(), course_id)

    except Exception as exc:
        logger.exception("Failed to queue quizzes for course %s: %s", course_id, exc)
        raise self.retry(exc=exc)


@shared_task
def unlock_next_day(course_id: str, week_number: int, day_number: int):
    """
    Unlock the next day after quiz completion.
    Day 1 of Week 1 is always unlocked by default.
    """
    from apps.courses.models import Course, DayPlan

    try:
        course = Course.objects.get(id=course_id)

        # Calculate next day
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
            logger.info("Course %s completed!", course_id)
            return

        # For day 5, don't unlock next week day 1 yet
        # (weekly test must be passed first)
        if day_number == 5:
            logger.info("Day 5 complete, weekly test required before next week")
            return

        # Unlock next day
        try:
            day = DayPlan.objects.get(
                week_plan__course=course,
                week_plan__week_number=next_week,
                day_number=next_day,
            )
            day.is_locked = False
            day.save(update_fields=["is_locked"])
            logger.info("Unlocked day %d week %d for course %s", next_day, next_week, course_id)
        except DayPlan.DoesNotExist:
            logger.warning("Day not found for unlocking")

    except Exception as exc:
        logger.exception("Error unlocking next day: %s", exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_weekly_test_task(self, course_id: str, week_number: int):
    """
    Generate a weekly test covering all 5 days of a week.
    10 MCQ questions covering entire week content.
    """
    from services.course.generator import CourseGenerator

    try:
        generator = CourseGenerator()
        result = asyncio.run(generator.generate_weekly_test(course_id, week_number))

        if result.get("success"):
            logger.info("Generated weekly test for week %d in course %s", week_number, course_id)
        else:
            logger.warning("Weekly test generation failed: %s", result.get("error"))
            raise Exception(result.get("error"))

    except Exception as exc:
        logger.exception("Error generating weekly test: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_certificate_task(self, user_id: str, course_id: str):
    """
    Generate a PDF certificate for a completed course.
    """
    from services.certificate.generator import CertificateGenerator

    try:
        generator = CertificateGenerator()
        result = asyncio.run(generator.generate_certificate(user_id, course_id))

        if result.get("success"):
            logger.info("Generated certificate for user %s course %s", user_id, course_id)
        else:
            logger.warning("Certificate generation failed: %s", result.get("error"))
            raise Exception(result.get("error"))

    except Exception as exc:
        logger.exception("Error generating certificate: %s", exc)
        raise self.retry(exc=exc)


@shared_task
def update_knowledge_state_task(user_id: str, quiz_results: list):
    """
    Update user knowledge state based on quiz results.
    quiz_results: [{"concept": "...", "is_correct": True/False}, ...]
    """
    from apps.users.models import UserKnowledgeState

    try:
        for result in quiz_results:
            concept = result.get("concept")
            is_correct = result.get("is_correct", False)

            if not concept:
                continue

            state, _ = UserKnowledgeState.objects.get_or_create(
                user_id=user_id,
                concept_tag=concept,
                defaults={"confidence_score": 0.5}
            )

            if is_correct:
                state.confidence_score = min(1.0, state.confidence_score + 0.1)
            else:
                state.confidence_score = max(0.0, state.confidence_score - 0.05)

            state.save(update_fields=["confidence_score"])

        logger.info("Updated knowledge state for user %s", user_id)

    except Exception as exc:
        logger.exception("Error updating knowledge state: %s", exc)


@shared_task
def send_streak_reminder(user_id: str):
    """
    Send streak reminder to user if they haven't studied today.
    Called daily by celery beat.
    """
    from django.utils import timezone
    from apps.courses.models import CourseProgress

    try:
        progress_records = CourseProgress.objects.filter(user_id=user_id)
        now = timezone.now()
        today = now.date()

        for progress in progress_records:
            if progress.last_activity:
                last_date = progress.last_activity.date()
                if last_date < today:
                    # User hasn't studied today
                    # TODO: Send notification (email/push)
                    logger.info(
                        "Streak reminder: user %s hasn't studied today, current streak: %d",
                        user_id, progress.streak_days
                    )

    except Exception as exc:
        logger.exception("Error sending streak reminder: %s", exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_coding_test_task(self, course_id: str, week_number: int):
    """
    Generate a weekly coding test with 2 coding problems.
    """
    from services.course.generator import CourseGenerator

    try:
        generator = CourseGenerator()
        result = asyncio.run(generator.generate_coding_test(course_id, week_number))

        if result.get("success"):
            logger.info("Generated coding test for week %d in course %s", week_number, course_id)
        else:
            logger.warning("Coding test generation failed: %s", result.get("error"))
            raise Exception(result.get("error"))

    except Exception as exc:
        logger.exception("Error generating coding test: %s", exc)
        raise self.retry(exc=exc)


@shared_task
def generate_weekly_tests_for_course(course_id: str):
    """
    Generate both MCQ test and coding test for all weeks in a course.
    Called after all days are generated.
    """
    from apps.courses.models import Course

    try:
        course = Course.objects.get(id=course_id)

        for week_number in range(1, course.duration_weeks + 1):
            # Generate MCQ test
            generate_weekly_test_task.delay(course_id, week_number)
            # Generate coding test
            generate_coding_test_task.delay(course_id, week_number)

        logger.info("Queued weekly tests for %d weeks in course %s", course.duration_weeks, course_id)

    except Exception as exc:
        logger.exception("Error queueing weekly tests: %s", exc)
