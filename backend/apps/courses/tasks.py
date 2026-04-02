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
import time

from celery import shared_task
from asgiref.sync import sync_to_async, async_to_sync

# Explicit logger name matching Django logging configuration
logger = logging.getLogger('apps.courses.tasks')


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def generate_course_content_task(
    self,
    course_id: str,
    course_name: str,
    duration_weeks: int,
    level: str,
    goals: list,
    description: str = None,  # Optional user-provided description
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

    logger.info("=" * 80)
    logger.info("🎓 CELERY TASK: GENERATE COURSE CONTENT")
    logger.info(f"   Task ID: {self.request.id}")
    logger.info(f"   Course ID: {course_id}")
    logger.info(f"   Course Name: {course_name}")
    logger.info(f"   Duration: {duration_weeks} weeks")
    logger.info(f"   Level: {level}")
    logger.info(f"   Description: {description}")  # Log description
    logger.info("=" * 80)

    # Ensure description is a string (not a list or other type)
    if description is not None and not isinstance(description, str):
        logger.warning(f"Description received as {type(description)}, converting to string or None")
        description = str(description) if description else None

    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        logger.error("❌ Course %s not found", course_id)
        return

    try:
        course.generation_status = "generating"
        course.save(update_fields=["generation_status"])
        
        logger.info("✅ Course status set to 'generating'")

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

        # Create generator
        generator = CourseGenerator()

        # Build skeleton for reference
        total_days = duration_weeks * 5

        print(f"[TASK] Starting async generation for course {course_id}")

        # Process course in 4-week blocks with web search per block
        # Each block: generate titles → web search → generate content
        asyncio.run(
            _generate_in_blocks_with_web_search(
                generator=generator,
                course_id=course_id,
                topic=topic,
                level=level,
                goals=goals,
                description=description,  # Pass user description to generator
                duration_weeks=duration_weeks,
            )
        )
        
        print(f"[TASK] Async generation completed for course {course_id}")

        # Mark course days as complete (weekly tests will run next)
        course.refresh_from_db()
        course.generation_progress = total_days
        course.save(update_fields=["generation_progress"])
        # NOTE: Don't set generation_status to 'ready' yet!
        # Weekly tests are still generating. Status will be set to 'ready'
        # by the LAST weekly test task when all are complete.

        # Small delay to ensure DB is synced before queuing weekly tests
        time.sleep(0.5)

        # Generate weekly tests (MCQ + Coding) for all weeks
        # These run sequentially to avoid LLM connection conflicts
        from apps.courses.tasks import generate_weekly_tests_for_course
        generate_weekly_tests_for_course.delay(course_id)

        logger.info("📝 Queued weekly test generation task")

        logger.info("=" * 80)
        logger.info("✅ COURSE GENERATION COMPLETE")
        logger.info(f"   Course ID: {course_id}")
        logger.info(f"   Status: {course.generation_status}")
        logger.info(f"   Progress: {course.generation_progress}/{total_days} days")
        logger.info(f"   Total Days: {total_days}")
        logger.info("=" * 80)

    except Exception as exc:
        logger.exception("Error generating course %s: %s", course_id, exc)
        try:
            course.refresh_from_db()
            course.generation_status = "failed"
            course.save(update_fields=["generation_status"])
        except Exception:
            pass
        raise self.retry(exc=exc)


async def _generate_in_blocks_with_web_search(
    generator,
    course_id: str,
    topic: str,
    level: str,
    goals: list,
    description: str = None,  # Optional user-provided description
    duration_weeks: int = None,
):
    """
    Generate course content in 4-week blocks.
    Each block:
    1. Generate week themes and day titles for 4 weeks
    2. Run web search with unified query from all day titles
    3. Generate theory content with web results for all 4 weeks
    
    This ensures web search is relevant to actual generated content.
    
    Web Search Count:
    - 1-4 weeks: 1 search
    - 5-8 weeks: 2 searches
    - 9-12 weeks: 3 searches
    - etc.
    """
    from apps.courses.models import Course, WeekPlan
    
    print(f"[BLOCK GENERATION] Starting block-based generation for {duration_weeks} weeks")
    
    # Get course reference
    course = await sync_to_async(Course.objects.get)(id=course_id)
    
    # Process in 4-week blocks
    block_start = 1
    block_num = 0
    
    while block_start <= duration_weeks:
        block_end = min(block_start + 3, duration_weeks)  # 4 weeks per block
        block_weeks = block_end - block_start + 1
        block_num += 1
        
        print(f"\n{'='*60}")
        print(f"[BLOCK {block_num}] Processing weeks {block_start}-{block_end} ({block_weeks} weeks)")
        print(f"{'='*60}")
        
        # ========== STEP 1: Generate week themes and day titles for this block ==========
        print(f"[BLOCK {block_num}] Step 1: Generating week themes and day titles...")
        
        block_day_titles = {}  # (week, day) -> title
        block_week_themes = {}  # week -> theme
        previous_titles = []  # For sequential title generation
        
        for week_num in range(block_start, block_end + 1):
            print(f"[BLOCK {block_num}] Generating Week {week_num} theme and titles...")
            
            # Get week plan
            week = await sync_to_async(WeekPlan.objects.get)(course=course, week_number=week_num)
            
            # Generate week theme
            theme, objectives = await generator._generate_week_theme(
                week_number=week_num,
                total_weeks=duration_weeks,
                topic=topic,
                skill_level=level,
                goals=goals,
                description=description,  # Pass user description
                previous_themes=[],  # Could pass previous weeks' themes if needed
            )
            week.theme = theme
            week.objectives = objectives
            await sync_to_async(week.save)(update_fields=["theme", "objectives"])
            
            block_week_themes[week_num] = theme
            
            # Generate day titles for this week
            days = await sync_to_async(list)(week.days.all().order_by("day_number"))
            for day in days:
                day_num = day.day_number
                title, tasks = await generator._generate_day_title_tasks(
                    day_num, theme, topic, level, description, previous_titles
                )
                day.title = title
                day.tasks = tasks
                previous_titles.append(title)
                block_day_titles[(week_num, day_num)] = title
                print(f"  - Week {week_num} Day {day_num}: {title}")
            
            # Save all day titles for this week
            for day in days:
                await sync_to_async(day.save)(update_fields=["title", "tasks"])
        
        # ========== STEP 2: Run web search for this block ==========
        print(f"\n[BLOCK {block_num}] Step 2: Running web search...")
        
        web_search_data = None
        try:
            from services.course.web_search import get_web_search_service
            
            search_service = get_web_search_service()
            web_search_data = search_service.run_full_search(
                course_topic=topic,
                skill_level=level,
                duration_weeks=block_weeks,
                day_titles=block_day_titles,
                week_themes=block_week_themes,
                learning_goals=goals or [],
            )
            
            print(f"[BLOCK {block_num}] ✅ Web search complete: {web_search_data.total_results} results, success={web_search_data.success}")
            
            if web_search_data.success:
                print(f"[BLOCK {block_num}] Results distributed to {len(web_search_data.day_results)} days")
        except Exception as search_exc:
            print(f"[BLOCK {block_num}] ❌ Web search failed: {search_exc}")
            web_search_data = None
        
        # ========== STEP 3: Generate content for all days in this block ==========
        print(f"\n[BLOCK {block_num}] Step 3: Generating content with web results...")
        
        # Create progress lock for thread-safe updates
        progress_lock = asyncio.Lock()
        
        # Generate all days in parallel within this block
        day_tasks = []
        for week_num in range(block_start, block_end + 1):
            week = await sync_to_async(WeekPlan.objects.get)(course=course, week_number=week_num)
            days = await sync_to_async(list)(week.days.all().order_by("day_number"))
            
            # Get previous titles for this block
            block_previous_titles = [
                block_day_titles[(w, d)] 
                for w in range(block_start, week_num + 1)
                for d in range(1, 6)
                if (w, d) in block_day_titles and (w != week_num or d < 5)
            ]
            
            for day in days:
                task = _generate_single_day_with_titles(
                    generator=generator,
                    course=course,
                    week=week,
                    day=day,
                    day_num=day.day_number,
                    theme=block_week_themes[week_num],
                    topic=topic,
                    level=level,
                    description=description,  # Pass user description
                    previous_titles=[t for w in range(block_start, week_num) for t in [block_day_titles.get((w, day.day_number), None)] if t],
                    progress_lock=progress_lock,
                    web_search_data=web_search_data,
                )
                day_tasks.append(task)
        
        # Run all days in parallel
        results = await asyncio.gather(*day_tasks, return_exceptions=True)
        successful = sum(1 for r in results if r is True)
        print(f"[BLOCK {block_num}] Completed {successful}/{len(day_tasks)} days successfully")
        
        # Move to next block
        block_start = block_end + 1
    
    print(f"\n{'='*60}")
    print(f"[BLOCK GENERATION] All {block_num} blocks completed for {duration_weeks} weeks")
    print(f"{'='*60}")


async def _generate_single_day_with_titles(
    generator,
    course,
    week,
    day,
    day_num: int,
    theme: str,
    topic: str,
    level: str,
    description: str = None,  # Optional user-provided description
    previous_titles: list = None,
    progress_lock: asyncio.Lock = None,
    web_search_data=None,
):
    """
    Generate content for a single day (titles already generated).
    Uses web search results for theory generation if available.
    """
    from apps.quizzes.models import QuizQuestion
    import json

    week_number = week.week_number
    print(f"[Course {course.id}] Generating Week {week_number} Day {day_num}...")
    logger.info("Generating content for course %s Week %d Day %d", course.id, week_number, day_num)

    try:
        # Title already generated, use existing
        title = day.title or f"Week {week_number} Day {day_num}"
        tasks = day.tasks or {}

        # Generate theory and code in parallel
        # Get web search results for this day if available
        web_results_formatted = ""
        if web_search_data and web_search_data.day_results:
            day_key = (week_number, day_num)
            day_results = web_search_data.day_results.get(day_key, [])
            if day_results:
                try:
                    from services.course.web_search import DayTopic, get_web_search_service
                    day_topic = DayTopic(
                        week_number=week_number,
                        day_number=day_num,
                        title=title,
                        theme=theme,
                    )
                    web_results_formatted = get_web_search_service().format_results_for_day(
                        day_results, day_topic
                    )
                    logger.info(
                        "[WEB_USAGE] Week %d Day %d: Using %d web results for theory generation",
                        week_number, day_num, len(day_results)
                    )
                    # Log the sources being used
                    sources = [r.domain for r in day_results[:3]]
                    logger.info("[WEB_USAGE]   Sources: %s", ', '.join(sources))
                except Exception as web_exc:
                    logger.warning("[WEB_USAGE] Failed to format web results for day: %s", web_exc)
                    web_results_formatted = ""
            else:
                logger.debug("[WEB_USAGE] Week %d Day %d: No web results available", week_number, day_num)
        else:
            logger.debug("[WEB_USAGE] Week %d Day %d: No web search data", week_number, day_num)

        theory_task = generator._generate_theory_content(
            title, theme, topic, level, description, web_results_formatted
        )
        code_task = generator._generate_code_content(title, theme, topic, level)
        theory, code = await asyncio.gather(theory_task, code_task)

        # Step 3: Generate quiz questions with retry logic
        quizzes = []
        quiz_generated = False
        max_quiz_retries = 3

        for quiz_attempt in range(max_quiz_retries):
            try:
                quiz_result = await generator._generate_quiz_questions(title, topic, level)
                quizzes = quiz_result.get("quizzes", [])

                if quizzes and len(quizzes) > 0:
                    quiz_generated = True
                    logger.info("✓ Quiz generated for Week %d Day %d (%d questions)",
                               week_number, day_num, len(quizzes))
                    break
                else:
                    logger.warning("Quiz generation returned empty result (attempt %d/%d)",
                                  quiz_attempt + 1, max_quiz_retries)
                    if quiz_attempt < max_quiz_retries - 1:
                        await asyncio.sleep(2)  # Wait before retry
            except Exception as quiz_exc:
                logger.warning("Quiz generation error (attempt %d/%d): %s",
                              quiz_attempt + 1, max_quiz_retries, quiz_exc)
                if quiz_attempt < max_quiz_retries - 1:
                    await asyncio.sleep(2)  # Wait before retry

        if not quiz_generated:
            logger.error("❌ Quiz generation failed after %d attempts for Week %d Day %d",
                        max_quiz_retries, week_number, day_num)

        # Save to DB
        day.theory_content = theory
        day.code_content = code
        day.theory_generated = True
        day.code_generated = True
        day.quiz_generated = quiz_generated
        # Save raw quiz JSON for display
        if quizzes:
            day.quiz_raw = json.dumps(quizzes, indent=2)
        else:
            day.quiz_raw = ""
        await sync_to_async(day.save)(update_fields=[
            "title", "tasks", "theory_content", "code_content", "quiz_raw",
            "theory_generated", "code_generated", "quiz_generated",
        ])

        # Save quiz questions to quiz_questions table
        if quizzes and quiz_generated:
            # Delete existing questions for this day
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

        # Update course progress (thread-safe with lock)
        async with progress_lock:
            await sync_to_async(course.refresh_from_db)()
            course.generation_progress += 1
            await sync_to_async(course.save)(update_fields=["generation_progress"])

            # Calculate total tasks: days + weekly tests (2 per week: MCQ + coding)
            total_days = course.total_days
            total_weekly_tests = (course.duration_weeks or 0) * 2  # MCQ + coding per week
            total_tasks = total_days + total_weekly_tests
            
            # Calculate progress including weekly tests
            current_task = course.generation_progress
            progress_percent = round((current_task / total_tasks) * 100) if total_tasks > 0 else 0
            
            # Broadcast progress update via SSE
            from apps.courses.sse import broadcast_progress_update
            broadcast_progress_update(course.id, {
                "progress": progress_percent,
                "completed_days": current_task,
                "total_days": total_tasks,
                "generation_status": "generating",
                "current_stage": f"Generating Week {week_number}, Day {day_num}...",
            })

        print(f"[Course {course.id}] ✓ Completed Week {week_number} Day {day_num} (Progress: {current_task}/{total_tasks})")
        logger.info("Completed day %d for course %s (progress: %d/%d)",
                   day_num, course.id, current_task, total_tasks)
        return True

    except Exception as e:
        print(f"[Course {course.id}] ✗ Error generating Week {week_number} Day {day_num}: {e}")
        logger.exception("Error generating day %d for course %s: %s", day_num, course.id, e)
        return False


async def _fill_week_with_progress(
    generator,
    course_id: str,
    week_number: int,
    total_weeks: int,
    topic: str,
    level: str,
    goals: list,
    web_search_data=None,
):
    """
    Fill a single week with content.
    Runs all 5 days in PARALLEL using asyncio.gather().
    Each day has 3 sequential steps: title → theory+code (parallel) → quiz

    Args:
        web_search_data: CourseWebSearchData from Tavily search (optional)
    """
    from apps.courses.models import Course, WeekPlan

    print(f"[WEEK START] Week {week_number} for course {course_id}")

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

    # Generate week theme and objectives (sequential - must complete before days)
    theme, objectives = await generator._generate_week_theme(
        week_number, total_weeks, topic, level, goals, []
    )
    week.theme = theme
    week.objectives = objectives
    await sync_to_async(week.save)(update_fields=["theme", "objectives"])

    # Get all days for this week
    days = await sync_to_async(list)(week.days.all().order_by("day_number"))

    # Generate day titles sequentially first (since each depends on previous titles)
    previous_titles = []
    day_titles = []
    for day in days:
        day_num = day.day_number
        title, tasks = await generator._generate_day_title_tasks(
            day_num, theme, topic, level, previous_titles
        )
        day.title = title
        day.tasks = tasks
        previous_titles.append(title)
        day_titles.append((day, day_num, title, tasks))

    # Save all day titles to DB
    for day, day_num, title, tasks in day_titles:
        await sync_to_async(day.save)(update_fields=["title", "tasks"])

    # Create progress lock for thread-safe updates
    progress_lock = asyncio.Lock()

    # Run all 5 days in PARALLEL
    print(f"[WEEK {week_number}] Starting {len(days)} days in parallel...")
    day_tasks = []
    for day, day_num, title, tasks in day_titles:
        task = _generate_single_day(
            generator=generator,
            course=course,
            week=week,
            day=day,
            day_num=day_num,
            theme=theme,
            topic=topic,
            level=level,
            previous_titles=previous_titles[:day_num-1] if day_num > 1 else [],
            progress_lock=progress_lock,
            web_search_data=web_search_data,
        )
        day_tasks.append(task)

    # Run all days in parallel
    results = await asyncio.gather(*day_tasks, return_exceptions=True)
    successful = sum(1 for r in results if r is True)
    print(f"[WEEK {week_number}] Completed {successful}/{len(days)} days successfully")
    logger.info("Completed week %d for course %s (%d/%d days successful)", week_number, course_id, successful, len(days))


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


@shared_task(bind=True, max_retries=5, default_retry_delay=10, autoretry_for=(Exception,))
def generate_weekly_test_task(self, course_id: str, week_number: int, skip_broadcast: bool = False):
    """
    Generate a weekly test covering all 5 days of a week.
    10 MCQ questions covering entire week content.

    FIX: Uses atomic DB increment with F() expression for consistency
    with coding test task. Only the last week's CODING test sets status to 'ready'.
    
    Args:
        course_id: Course UUID
        week_number: Week number to generate test for
        skip_broadcast: If True, skip progress broadcast (used during course updates)
    """
    from services.course.generator import CourseGenerator
    from django.db import transaction
    from django.db.models import F
    import asyncio

    logger.info("=" * 60)
    logger.info("📝 CELERY TASK: GENERATE WEEKLY TEST")
    logger.info(f"   Task ID: {self.request.id}")
    logger.info(f"   Course ID: {course_id}")
    logger.info(f"   Week: {week_number}")
    logger.info(f"   Attempt: {self.request.retries + 1}/{self.max_retries}")
    logger.info("=" * 60)

    try:
        # Create a fresh event loop for this task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            generator = CourseGenerator()
            result = loop.run_until_complete(generator.generate_weekly_test(course_id, week_number))
        finally:
            loop.close()

        if result.get("success"):
            logger.info("✅ Weekly test generated successfully")
            logger.info(f"   Test ID: {result.get('test_id')}")
            logger.info(f"   Questions: {result.get('total_questions')}")

            # Increment progress and broadcast via SSE
            from apps.courses.models import Course
            from apps.courses.sse import broadcast_progress_update

            # Get course info for logging
            course = Course.objects.get(id=course_id)
            total_weeks = course.duration_weeks or 0
            total_days = course.total_days
            total_weekly_tests = total_weeks * 2  # MCQ + coding per week
            total_tasks = total_days + total_weekly_tests

            # FIX: Atomic increment using F() expression - prevents race conditions
            with transaction.atomic():
                Course.objects.filter(id=course_id).update(
                    generation_progress=F('generation_progress') + 1
                )
                course.refresh_from_db()
                current_progress = course.generation_progress
                
                # Check if this is the LAST task (week 4 MCQ or week 4 coding that reaches 100%)
                is_last_week = (week_number == total_weeks)
                should_mark_ready = (
                    is_last_week and
                    current_progress >= total_tasks and
                    course.generation_status != 'ready'  # Idempotency
                )

                # If this is the last task, mark course as ready
                if should_mark_ready:
                    course.generation_status = "ready"
                    course.status = "active"
                    course.save(update_fields=["generation_status", "status"])
                    logger.info("✅✅✅ LAST TASK (Week %d MCQ) - Course %s marked as READY!", week_number, course_id)

                    # CRITICAL FIX: Send final 'complete' SSE event to close frontend connection
                    from apps.courses.sse import broadcast_generation_complete
                    broadcast_generation_complete(course_id, {
                        "progress": 100,
                        "completed_days": current_progress,
                        "total_days": total_tasks,
                        "generation_status": "ready",
                        "current_stage": "Course generation complete!",
                    })
                elif not skip_broadcast:
                    # Regular progress update (skip during course updates)
                    progress_percent = round((current_progress / total_tasks) * 100) if total_tasks > 0 else 0
                    broadcast_progress_update(course_id, {
                        "progress": progress_percent,
                        "completed_days": current_progress,
                        "total_days": total_tasks,
                        "generation_status": "generating",
                        "current_stage": f"Generated weekly test for Week {week_number}...",
                        "weekly_test_status": f"Week {week_number} MCQ test complete",
                    })
        else:
            logger.warning("❌ Weekly test generation failed: %s", result.get("error"))
            raise Exception(result.get("error"))

    except Exception as exc:
        logger.exception("Error generating weekly test (attempt %d): %s", self.request.retries + 1, exc)
        # Use exponential backoff for retries
        raise self.retry(exc=exc, countdown=min(60, 10 * (2 ** self.request.retries)))


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


@shared_task(bind=True, max_retries=5, default_retry_delay=10, autoretry_for=(Exception,))
def generate_coding_test_task(self, course_id: str, week_number: int, skip_broadcast: bool = False):
    """
    Generate a weekly coding test with 2 coding problems.

    FIX: Uses atomic DB operations + last-week check to guarantee
    generation_status is set to 'ready' exactly once.
    
    Args:
        course_id: Course UUID
        week_number: Week number to generate test for
        skip_broadcast: If True, skip progress broadcast (used during course updates)
    """
    from services.course.generator import CourseGenerator
    from django.db import transaction
    from django.db.models import F
    import asyncio

    logger.info("=" * 60)
    logger.info("💻 CELERY TASK: GENERATE CODING TEST")
    logger.info(f"   Task ID: {self.request.id}")
    logger.info(f"   Course ID: {course_id}")
    logger.info(f"   Week: {week_number}")
    logger.info(f"   Attempt: {self.request.retries + 1}/{self.max_retries}")
    logger.info("=" * 60)

    try:
        # Create a fresh event loop for this task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            generator = CourseGenerator()
            result = loop.run_until_complete(generator.generate_coding_test(course_id, week_number))
        finally:
            loop.close()

        if result.get("success"):
            logger.info("✅ Coding test generated successfully")
            logger.info(f"   Problems: {result.get('total_problems')}")

            # Increment progress and broadcast via SSE
            from apps.courses.models import Course
            from apps.courses.sse import broadcast_progress_update

            # Get total weeks for last-week check
            course = Course.objects.get(id=course_id)
            total_weeks = course.duration_weeks or 0
            total_days = course.total_days
            total_weekly_tests = total_weeks * 2  # MCQ + coding per week
            total_tasks = total_days + total_weekly_tests

            # FIX: Atomic increment with last-task check
            with transaction.atomic():
                Course.objects.filter(id=course_id).update(
                    generation_progress=F('generation_progress') + 1
                )
                course.refresh_from_db()
                current_progress = course.generation_progress
                
                # Check if this is the LAST task (week 4 coding that reaches 100%)
                is_last_week = (week_number == total_weeks)
                should_mark_ready = (
                    is_last_week and
                    current_progress >= total_tasks and
                    course.generation_status != 'ready'  # Idempotency
                )

                # If this is the last task, mark course as ready
                if should_mark_ready:
                    course.generation_status = "ready"
                    course.status = "active"
                    course.save(update_fields=["generation_status", "status"])
                    logger.info("✅✅✅ LAST TASK (Week %d Coding) - Course %s marked as READY!", week_number, course_id)

                    # CRITICAL FIX: Send final 'complete' SSE event to close frontend connection
                    from apps.courses.sse import broadcast_generation_complete
                    broadcast_generation_complete(course_id, {
                        "progress": 100,
                        "completed_days": current_progress,
                        "total_days": total_tasks,
                        "generation_status": "ready",
                        "current_stage": "Course generation complete!",
                    })
                elif not skip_broadcast:
                    # Regular progress update (skip during course updates)
                    progress_percent = round((current_progress / total_tasks) * 100) if total_tasks > 0 else 0
                    broadcast_progress_update(course_id, {
                        "progress": progress_percent,
                        "completed_days": current_progress,
                        "total_days": total_tasks,
                        "generation_status": "generating",
                        "current_stage": f"Generated coding test for Week {week_number}...",
                        "coding_test_status": f"Week {week_number} coding test complete",
                    })
        else:
            logger.warning("❌ Coding test generation failed: %s", result.get("error"))
            raise Exception(result.get("error"))

    except Exception as exc:
        logger.exception("Error generating coding test (attempt %d): %s", self.request.retries + 1, exc)
        # Use exponential backoff for retries
        raise self.retry(exc=exc, countdown=min(60, 10 * (2 ** self.request.retries)))


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def generate_weekly_tests_for_course(self, course_id: str):
    """
    Generate both MCQ test and coding test for all weeks in a course.
    Called after all days are generated.

    This task generates weekly tests SEQUENTIALLY within the same task.
    The LAST coding test will set status to 'ready'.
    """
    from apps.courses.models import Course
    from django.db import transaction
    from django.db.models import F

    try:
        course = Course.objects.get(id=course_id)
        total_weeks = course.duration_weeks

        logger.info("Starting sequential weekly test generation for %d weeks in course %s",
                   total_weeks, course_id)

        # Broadcast that weekly test generation is starting
        from apps.courses.sse import broadcast_progress_update
        total_days = course.total_days
        total_weekly_tests = total_weeks * 2  # MCQ + coding per week
        total_tasks = total_days + total_weekly_tests

        broadcast_progress_update(course_id, {
            "progress": round((total_days / total_tasks) * 100),  # Days are done
            "completed_days": total_days,
            "total_days": total_tasks,
            "generation_status": "generating",
            "current_stage": "Generating weekly tests...",
            "weekly_test_status": f"Starting weekly tests for {total_weeks} weeks",
        })

        # Generate tests week by week SEQUENTIALLY
        for week_number in range(1, total_weeks + 1):
            logger.info("Generating tests for Week %d of %d...", week_number, total_weeks)

            # Generate MCQ test for this week (synchronous execution)
            logger.info("Generating MCQ test for Week %d...", week_number)
            generate_weekly_test_task.apply(args=[course_id, week_number])

            # Generate coding test for this week (synchronous execution)
            logger.info("Generating coding test for Week %d...", week_number)
            generate_coding_test_task.apply(args=[course_id, week_number])

            logger.info("Week %d tests complete!", week_number)

        # NOTE: The last coding test task sets status to 'ready'
        logger.info("Queued weekly test generation for %d weeks in course %s",
                   total_weeks, course_id)

    except Exception as exc:
        logger.exception("Error queueing weekly tests: %s", exc)
        raise


# ──────────────────────────────────────────────
# COURSE UPDATE TASK
# ──────────────────────────────────────────────
@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def update_course_content_task(
    self,
    course_id: str,
    course_name: str,
    topic: str,
    level: str,
    goals: list,
    description: str = None,
    update_type: str = "percentage",
    user_query: str = "",
    weeks_to_update: list = None,
    new_duration_weeks: int = None,
    web_search_enabled: bool = True,
    target_weeks: int = None,  # For compact update type
    percentage: int = 50,  # For percentage update type (50 or 75)
):
    """
    Async task: Update existing course with new content.
    Only regenerates specified weeks based on update_type.

    Update Types:
    - "percentage": Replace last 50% or 75% of weeks (based on percentage param)
    - "extend": Keep all weeks, add extend_weeks more weeks
    - "compact": Compress entire course into target_weeks

    Progress Calculation:
    - For percentage update (2 weeks): 10 days + 4 tests = 14 tasks
    - For extend (2 new weeks): 10 days + 4 tests = 14 tasks
    - For compact (4 weeks → 2 weeks): 10 days + 4 tests = 14 tasks
    """
    from apps.courses.models import Course, WeekPlan, DayPlan, CourseProgress
    from services.course.generator import CourseGenerator
    from services.course.web_search import get_web_search_service
    import asyncio

    logger.info("=" * 80)
    logger.info("🔄 CELERY TASK: UPDATE COURSE CONTENT")
    logger.info(f"   Task ID: {self.request.id}")
    logger.info(f"   Course ID: {course_id}")
    logger.info(f"   Course Name: {course_name}")
    logger.info(f"   Update Type: {update_type}")
    logger.info(f"   Weeks to Update: {weeks_to_update}")
    logger.info(f"   User Query: {user_query}")
    logger.info("=" * 80)

    if weeks_to_update is None:
        weeks_to_update = []

    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        logger.error("❌ Course %s not found", course_id)
        return

    try:
        course.generation_status = "updating"
        course.save(update_fields=["generation_status"])

        logger.info("✅ Course status set to 'updating'")

        # Create generator
        generator = CourseGenerator()

        # Get total weeks for reference
        total_weeks = new_duration_weeks or course.duration_weeks

        # Calculate total tasks for progress tracking
        # Each week has: 5 days + 1 MCQ test + 1 coding test = 7 tasks
        weeks_being_updated = len(weeks_to_update)
        total_days_to_update = weeks_being_updated * 5
        total_tests_to_update = weeks_being_updated * 2  # MCQ + coding per week
        total_tasks = total_days_to_update + total_tests_to_update
        
        logger.info("Progress calculation: %d weeks × (5 days + 2 tests) = %d tasks", 
                   weeks_being_updated, total_tasks)

        # Build combined context: existing content + user query
        existing_context = _build_existing_context(course, weeks_to_update)

        # Combined prompt for LLM: PRIORITIZE user query over existing content
        combined_context = f"""
EXISTING COURSE CONTEXT:
{existing_context}

⚠️⚠️⚠️ CRITICAL USER UPDATE REQUEST (PRIORITIZE THIS): ⚠️⚠️⚠️
{user_query}

IMPORTANT GENERATION RULES:
1. **HEAVILY PRIORITIZE** the user's update request above all else
2. Generate content that focuses on: **{user_query}**
3. Maintain consistency with preserved weeks ONLY for continuity
4. Ensure smooth progression from preserved to updated content
5. The user wants to learn about **{user_query}** - make this the CENTRAL FOCUS
6. Include practical examples, tutorials, and best practices for **{user_query}**
7. If extending, add NEW weeks that specifically cover **{user_query}**
8. If updating existing weeks, REPLACE content with **{user_query}** focused material

EXAMPLE OF WHAT TO GENERATE:
- If user says "data analytics", generate content about SQL for data analytics, Python for data analysis, data visualization, etc.
- If user says "machine learning", generate content about ML algorithms, model training, evaluation, etc.
- Make it PRACTICAL and HANDS-ON with real-world examples
"""

        logger.info("Starting update generation for %d weeks", len(weeks_to_update))

        # Track progress
        tasks_completed = 0

        # Log update type with clear message
        if update_type == "compact":
            logger.info("📦 COMPACT UPDATE: Compressing course from %d to %d weeks",
                       course.duration_weeks, new_duration_weeks or target_weeks)
            # For compact, skip web search and use special prompting
            web_search_enabled = False
        elif update_type == "extend":
            extend_weeks_count = len(weeks_to_update)
            logger.info("➕ EXTEND UPDATE: Adding %d new weeks (weeks %s)",
                       extend_weeks_count, weeks_to_update)
        elif update_type == "percentage":
            logger.info("🔄 PERCENTAGE UPDATE: Replacing last %d%% of course (%d weeks)",
                       percentage, len(weeks_to_update))

        # Run async generation using async_to_sync for better event loop management
        # This avoids issues with multiple event loops in Celery workers
        tasks_completed = async_to_sync(_update_course_async)(
            generator=generator,
            course=course,
            weeks_to_update=weeks_to_update,
            total_weeks=total_weeks,
            topic=topic,
            level=level,
            goals=goals,
            description=description,
            user_query=user_query,
            update_type=update_type,
            new_duration_weeks=new_duration_weeks,
            web_search_enabled=web_search_enabled,
            total_tasks=total_tasks,  # Pass total tasks for progress calculation
            target_weeks=target_weeks,  # Pass for compact update
        )

        # For extend_50% type, create new week/day skeleton for added weeks
        if update_type == "extend_50%" and new_duration_weeks and new_duration_weeks > course.duration_weeks:
            old_duration = course.duration_weeks
            for week_num in range(old_duration + 1, new_duration_weeks + 1):
                week = WeekPlan.objects.create(
                    course=course,
                    week_number=week_num,
                    theme=None,
                    objectives=[],
                )
                for day_num in range(1, 6):
                    DayPlan.objects.create(
                        week_plan=week,
                        day_number=day_num,
                        title=None,
                        tasks={},
                        theory_content="",
                        code_content="",
                        is_locked=True,
                        theory_generated=False,
                        code_generated=False,
                        quiz_generated=False,
                    )
            logger.info("Created skeleton for %d new weeks", new_duration_weeks - old_duration)

        # Update course progress - set to 100%
        course.refresh_from_db()
        course.generation_progress = total_days_to_update  # Only count days, not tests
        course.generation_status = "ready"
        course.duration_weeks = new_duration_weeks
        course.save(update_fields=["generation_progress", "generation_status", "duration_weeks"])

        # Reset progress for updated weeks if course was completed
        _reset_user_progress_for_updated_weeks(course, weeks_to_update)

        # Generate weekly tests for updated weeks (these run separately, don't count toward main progress)
        if weeks_to_update:
            from apps.courses.tasks import generate_weekly_test_task, generate_coding_test_task
            from apps.courses.sse import broadcast_progress_update

            test_count = 0
            total_tests = len(weeks_to_update) * 2  # MCQ + coding per week

            # CRITICAL: Refresh course to get ACTUAL generation_progress from database
            # This MUST be done here because weeks were updated in parallel above
            course.refresh_from_db()
            days_completed = course.generation_progress
            
            # Verify the calculation
            expected_days = len(weeks_to_update) * 5
            logger.info("📊 [TEST PHASE] Starting test generation:")
            logger.info("   - Weeks to update: %s", weeks_to_update)
            logger.info("   - Expected days completed: %d", expected_days)
            logger.info("   - Actual days_completed from DB: %d", days_completed)
            logger.info("   - Total tasks (days+tests): %d", total_tasks)
            logger.info("   - Expected progress after days: %d%%", round((days_completed / total_tasks) * 100))

            # Progress calculation for tests:
            # Days completed = days_completed (already done, ~70% of total_tasks)
            # Each test adds: (1 / total_tasks) * 100 percent
            # Final progress should reach 100% after all tests complete

            for week_num in weeks_to_update:
                logger.info("📝 [TEST] Regenerating weekly test for week %d", week_num)
                generate_weekly_test_task.apply(args=[course_id, week_num, True])  # skip_broadcast=True
                test_count += 1

                # Update progress for MCQ test completion
                # Start from days progress (~70%) and add test progress
                tasks_done = days_completed + test_count
                progress_percent = round((tasks_done / total_tasks) * 100)
                
                logger.info("📊 [TEST PROGRESS] MCQ Test Week %d: days_completed=%d + test_count=%d = tasks_done=%d/%d = %d%%",
                           week_num, days_completed, test_count, tasks_done, total_tasks, progress_percent)
                
                broadcast_progress_update(course_id, {
                    "progress": int(progress_percent),
                    "completed_days": days_completed,
                    "total_days": total_days_to_update,
                    "generation_status": "updating",
                    "current_stage": f"Generating tests for Week {week_num}...",
                })

                logger.info("📝 [TEST] Regenerating coding test for week %d", week_num)
                generate_coding_test_task.apply(args=[course_id, week_num, True])  # skip_broadcast=True
                test_count += 1

                # Update progress for coding test completion
                tasks_done = days_completed + test_count
                progress_percent = round((tasks_done / total_tasks) * 100)
                
                logger.info("📊 [TEST PROGRESS] Coding Test Week %d: days_completed=%d + test_count=%d = tasks_done=%d/%d = %d%%",
                           week_num, days_completed, test_count, tasks_done, total_tasks, progress_percent)
                
                broadcast_progress_update(course_id, {
                    "progress": int(progress_percent),
                    "completed_days": days_completed,
                    "total_days": total_days_to_update,
                    "generation_status": "updating",
                    "current_stage": f"Generating coding test for Week {week_num}...",
                })

        logger.info("=" * 80)
        logger.info("✅ COURSE UPDATE COMPLETE")
        logger.info(f"   Course ID: {course_id}")
        logger.info(f"   Status: {course.generation_status}")
        logger.info(f"   Weeks Updated: {weeks_to_update}")
        logger.info(f"   Total Tasks: {total_tasks} (100%)")
        logger.info("=" * 80)

    except Exception as exc:
        logger.exception("Error updating course %s: %s", course_id, exc)
        try:
            course.refresh_from_db()
            course.generation_status = "failed"
            course.save(update_fields=["generation_status"])
        except Exception:
            pass
        raise self.retry(exc=exc)


async def _update_course_async(
    generator,
    course,
    weeks_to_update: list,
    total_weeks: int,
    topic: str,
    level: str,
    goals: list,
    description: str,
    user_query: str,
    update_type: str,
    new_duration_weeks: int,
    web_search_enabled: bool = True,
    total_tasks: int = None,  # Total tasks for progress calculation
    target_weeks: int = None,  # For compact update type
):
    """
    Async function to update course content.
    Called from update_course_content_task via async_to_sync().

    Update Types:
    - "50%", "75%": Replace percentage of weeks
    - "extend_50%": Add 50% more weeks
    - "compact": Compress entire course into fewer weeks

    Progress is calculated based on total_tasks:
    - Each day completed = 1 task
    - Progress % = (days_updated / total_tasks) * 100
    """
    from apps.courses.models import WeekPlan, DayPlan

    logger.info("Starting async update for %d weeks", len(weeks_to_update))

    # Calculate total days being updated (for broadcast)
    total_days_to_update = len(weeks_to_update) * 5

    if total_tasks is None:
        # Fallback: calculate from weeks
        total_tasks = len(weeks_to_update) * 7  # 5 days + 2 tests per week

    # Track how many days we've updated (for progress)
    days_updated = 0

    # Create progress lock for thread-safe updates
    progress_lock = asyncio.Lock()

    # Process weeks to update in blocks of 4 (parallel within block)
    block_start = 0
    block_size = 4

    while block_start < len(weeks_to_update):
        block_end = min(block_start + block_size, len(weeks_to_update))
        block_weeks = weeks_to_update[block_start:block_end]

        logger.info("Processing update block: weeks %s", block_weeks)

        # Create async tasks for this block
        update_tasks = []
        for week_num in block_weeks:
            task = _update_single_week(
                generator=generator,
                course=course,
                week_number=week_num,
                total_weeks=total_weeks,
                topic=topic,
                level=level,
                goals=goals,
                description=description,
                user_query=user_query,
                progress_lock=progress_lock,
                web_search_enabled=web_search_enabled,
                total_tasks=total_tasks,  # Pass for progress calculation
                total_days_to_update=total_days_to_update,  # Pass for broadcast
                update_type=update_type,  # Pass update type for compact handling
            )
            update_tasks.append(task)

        # Run all updates in parallel
        results = await asyncio.gather(*update_tasks, return_exceptions=True)
        successful = sum(1 for r in results if r is True)
        
        # Update days count for successful weeks
        days_updated += successful * 5  # 5 days per week
        
        logger.info("Block complete: %d/%d weeks updated successfully", successful, len(block_weeks))

        block_start = block_end

    # For extend_50% type, create new week/day skeleton for added weeks
    if update_type == "extend_50%" and new_duration_weeks and new_duration_weeks > course.duration_weeks:
        old_duration = course.duration_weeks
        for week_num in range(old_duration + 1, new_duration_weeks + 1):
            week = await sync_to_async(WeekPlan.objects.create)(
                course=course,
                week_number=week_num,
                theme=None,
                objectives=[],
            )
            for day_num in range(1, 6):
                await sync_to_async(DayPlan.objects.create)(
                    week_plan=week,
                    day_number=day_num,
                    title=None,
                    tasks={},
                    theory_content="",
                    code_content="",
                    is_locked=True,
                    theory_generated=False,
                    code_generated=False,
                    quiz_generated=False,
                )
        logger.info("Created skeleton for %d new weeks", new_duration_weeks - old_duration)

    # For compact type, delete old weeks beyond the new duration after regeneration
    if update_type == "compact" and new_duration_weeks and new_duration_weeks < course.duration_weeks:
        # Delete weeks that are beyond the new duration
        weeks_to_delete = await sync_to_async(list)(
            WeekPlan.objects.filter(course=course, week_number__gt=new_duration_weeks)
        )
        for week_to_delete in weeks_to_delete:
            await sync_to_async(week_to_delete.delete)()
        logger.info("📦 Deleted %d weeks for compact update (now %d weeks total)", 
                   len(weeks_to_delete), new_duration_weeks)

    logger.info("Async update complete for %d weeks", len(weeks_to_update))
    
    # Return the total days updated for progress tracking
    return days_updated


async def _update_single_week(
    generator,
    course,
    week_number: int,
    total_weeks: int,  # This is the NEW total (after extension if applicable)
    topic: str,
    level: str,
    goals: list,
    description: str,
    user_query: str,
    progress_lock: asyncio.Lock,
    web_search_enabled: bool = True,
    total_tasks: int = None,  # Total tasks for progress calculation
    total_days_to_update: int = None,  # Total days being updated (for broadcast)
    update_type: str = "percentage",  # Update type: percentage, extend, compact
):
    """
    Update a single week with new content.
    """
    from apps.courses.models import WeekPlan, DayPlan
    from apps.quizzes.models import QuizQuestion
    import json

    logger.info("📝 STARTING WEEK %d UPDATE", week_number)
    logger.info("   Course: %s", course.course_name)
    logger.info("   Topic: %s", topic)
    logger.info("   User Query: %s", user_query)

    try:
        # Get or create week
        week, created = await sync_to_async(WeekPlan.objects.get_or_create)(
            course=course,
            week_number=week_number,
            defaults={"theme": None, "objectives": []}
        )

        logger.info("📝 Generating week theme for Week %d...", week_number)

        # Generate week theme with update context
        # For compact type, use special prompt for course compression
        if update_type == "compact":
            # For compact, we need to redesign the entire course structure
            theme, objectives = await generator._generate_week_theme(
                week_number=week_number,
                total_weeks=total_weeks,  # This is the NEW reduced total
                topic=topic,
                skill_level=level,
                goals=goals,
                description=description,
                previous_themes=[],
                is_compact=True,  # Flag for compact generation
                original_duration=course.duration_weeks,  # Original duration for context
            )
            theme = f"{theme} (Compacted)"
        else:
            theme, objectives = await generator._generate_week_theme(
                week_number=week_number,
                total_weeks=total_weeks,
                topic=topic,
                skill_level=level,
                goals=goals,
                description=description,
                previous_themes=[],  # Could fetch from existing course
            )
            # Modify theme based on user query
            theme = f"{theme} (Updated)"

        week.theme = theme
        week.objectives = objectives
        await sync_to_async(week.save)(update_fields=["theme", "objectives"])

        # Get or create days
        days = []
        for day_num in range(1, 6):
            day, _ = await sync_to_async(DayPlan.objects.get_or_create)(
                week_plan=week,
                day_number=day_num,
                defaults={
                    "title": None,
                    "tasks": {},
                    "theory_content": "",
                    "code_content": "",
                    "is_locked": True,
                }
            )
            days.append(day)

        # Generate day titles
        previous_titles = []
        for day in days:
            day_num = day.day_number
            title, tasks = await generator._generate_day_title_tasks(
                day_number=day_num,
                week_theme=theme,
                topic=topic,
                skill_level=level,
                description=description,
                previous_titles=previous_titles,
            )
            day.title = title
            day.tasks = tasks
            previous_titles.append(title)

        # Save day titles
        for day in days:
            await sync_to_async(day.save)(update_fields=["title", "tasks"])

        # Run web search if enabled (skip for compact updates)
        web_search_data = None
        search_service = None
        if web_search_enabled and update_type != "compact":
            try:
                from services.course.web_search import DayTopic, get_web_search_service

                day_titles = {(week_number, day.day_number): day.title for day in days}
                search_service = get_web_search_service()
                web_search_data = search_service.run_full_search(
                    course_topic=topic,
                    skill_level=level,
                    duration_weeks=1,  # Just this week
                    day_titles=day_titles,
                    week_themes={week_number: theme},
                    learning_goals=goals or [],
                )
                logger.info("Web search complete for week %d", week_number)
            except Exception as search_exc:
                logger.warning("Web search failed for week %d: %s", week_number, search_exc)

        # Generate content for ALL 5 days IN PARALLEL
        logger.info("🚀 [PARALLEL DAY GENERATION] Starting parallel generation for all 5 days in Week %d...", week_number)
        
        async def generate_day_content(day, web_search_data, search_service):
            """Generate content for a single day."""
            day_num = day.day_number
            logger.info("📝 [DAY GENERATION] Week %d Day %d: %s", week_number, day_num, day.title)

            # Get web results for this day if available
            web_results_formatted = ""
            if web_search_data and web_search_data.day_results and search_service:
                day_key = (week_number, day_num)
                day_results = web_search_data.day_results.get(day_key, [])
                if day_results:
                    try:
                        from services.course.web_search import DayTopic
                        day_topic = DayTopic(
                            week_number=week_number,
                            day_number=day_num,
                            title=day.title,
                            theme=theme,
                        )
                        web_results_formatted = search_service.format_results_for_day(
                            day_results, day_topic
                        )
                        logger.info("📊 [WEB SEARCH] Using %d results for Day %d", len(day_results), day_num)
                    except Exception as web_exc:
                        logger.warning("Failed to format web results: %s", web_exc)

            # Generate theory and code in parallel
            logger.info("🤖 [LLM CALL] Generating theory content for Day %d...", day_num)
            theory_task = generator._generate_theory_content(
                day_title=day.title,
                week_theme=theme,
                topic=topic,
                skill_level=level,
                description=description,
                web_search_results=web_results_formatted,
            )
            logger.info("🤖 [LLM CALL] Generating code content for Day %d...", day_num)
            code_task = generator._generate_code_content(
                day_title=day.title,
                week_theme=theme,
                topic=topic,
                skill_level=level,
            )
            theory, code = await asyncio.gather(theory_task, code_task)

            # Generate quiz
            logger.info("🤖 [LLM CALL] Generating quiz questions for Day %d...", day_num)
            quiz_result = await generator._generate_quiz_questions(
                day_title=day.title,
                topic=topic,
                skill_level=level,
            )
            quizzes = quiz_result.get("quizzes", [])
            quiz_generated = len(quizzes) > 0

            logger.info("✅ [DAY COMPLETE] Day %d: theory=%d chars, code=%d chars, quiz=%d questions",
                       day_num, len(theory) if theory else 0, len(code) if code else 0, len(quizzes))

            return day, theory, code, quizzes, quiz_generated

        # Create tasks for all 5 days
        day_generation_tasks = [
            generate_day_content(day, web_search_data, search_service)
            for day in days
        ]

        # Run ALL 5 days in parallel!
        logger.info("🚀 [PARALLEL] Launching %d parallel day generation tasks...", len(day_generation_tasks))
        day_results = await asyncio.gather(*day_generation_tasks, return_exceptions=True)

        # Process results and save to database
        for result in day_results:
            if isinstance(result, Exception):
                logger.error("❌ Day generation failed: %s", result)
                continue
            
            day, theory, code, quizzes, quiz_generated = result
            
            # Save day content
            day.theory_content = theory
            day.code_content = code
            day.theory_generated = True
            day.code_generated = True
            day.quiz_generated = quiz_generated
            if quizzes:
                day.quiz_raw = json.dumps(quizzes, indent=2)
            else:
                day.quiz_raw = ""

            # Delete old quiz questions and save new ones
            await sync_to_async(QuizQuestion.objects.filter(
                course=course, week_number=week_number, day_number=day.day_number
            ).delete)()

            if quizzes:
                for quiz in quizzes:
                    await sync_to_async(QuizQuestion.objects.create)(
                        course=course,
                        week_number=week_number,
                        day_number=day.day_number,
                        question_type="mcq",
                        question_text=quiz.get("question_text", ""),
                        options=quiz.get("options", {}),
                        correct_answer=quiz.get("correct_answer", "a"),
                        explanation=quiz.get("explanation", ""),
                    )

            await sync_to_async(day.save)(update_fields=[
                "title", "tasks", "theory_content", "code_content", "quiz_raw",
                "theory_generated", "code_generated", "quiz_generated",
            ])
            logger.info("💾 [DB SAVED] Week %d Day %d saved to database", week_number, day.day_number)

        logger.info("✅ [WEEK COMPLETE] All %d days in Week %d generated and saved!", len(days), week_number)

        # Update course progress and broadcast after ALL days in week are complete
        async with progress_lock:
            await sync_to_async(course.refresh_from_db)()
            course.generation_progress += 5  # 5 days per week
            await sync_to_async(course.save)(update_fields=["generation_progress"])

            # Broadcast progress update with CORRECT percentage
            from apps.courses.sse import broadcast_progress_update
            # Calculate progress based on total_tasks (days + tests)
            # total_tasks = total_days_to_update + total_tests
            # total_tests = number of weeks being updated * 2 (MCQ + coding)
            # Tests are generated AFTER all days are complete, so we only count days here
            if total_tasks and total_days_to_update:
                # Progress = days_completed / total_tasks * 100
                # This will cap at ~71% for days (35/49 = 71% for 7 weeks)
                # Tests will complete the remaining ~29%
                progress_percent = round((course.generation_progress / total_tasks) * 100)
            else:
                # Fallback to old calculation
                progress_percent = round((course.generation_progress / total_days_to_update) * 100)

            # Cap at 70% (tests will complete the remaining 30%)
            progress_percent = min(progress_percent, 70)
            
            logger.info("📊 [PROGRESS] Week %d complete: %d days total, progress %d%% (capped at 70%%)",
                       week_number, course.generation_progress, progress_percent)

            broadcast_progress_update(course.id, {
                "progress": progress_percent,
                "completed_days": course.generation_progress,
                "total_days": total_days_to_update,  # Only the days being updated, not full course
                "generation_status": "updating",
                "current_stage": f"Updating Week {week_number}...",
            })

        logger.info("✓ Week %d updated successfully", week_number)
        return True

    except Exception as e:
        logger.exception("Error updating week %d: %s", week_number, e)
        return False


def _build_existing_context(course, weeks_to_update: list) -> str:
    """
    Build context string from existing course content.
    Includes preserved weeks and their content.
    """
    from apps.courses.models import WeekPlan

    weeks_to_preserve = [w for w in range(1, course.duration_weeks + 1) if w not in weeks_to_update]

    context_parts = []
    context_parts.append(f"Course: {course.course_name}")
    context_parts.append(f"Topic: {course.topic or course.course_name}")
    context_parts.append(f"Level: {course.level}")
    context_parts.append(f"Total Weeks: {course.duration_weeks}")

    if weeks_to_preserve:
        context_parts.append("\nPRESERVED WEEKS (DO NOT MODIFY):")
        for week_num in weeks_to_preserve:
            try:
                week = WeekPlan.objects.get(course=course, week_number=week_num)
                week_info = f"Week {week_num}: {week.theme or 'No theme'}"
                if week.objectives:
                    week_info += f"\n  Objectives: {', '.join(week.objectives[:3])}"
                context_parts.append(week_info)
            except WeekPlan.DoesNotExist:
                pass

    return "\n".join(context_parts)


def _reset_user_progress_for_updated_weeks(course, weeks_to_update: list):
    """
    Reset user progress for updated weeks.
    Marks updated weeks as locked and incomplete.
    """
    from apps.courses.models import WeekPlan, DayPlan, CourseProgress
    from django.db import transaction

    @transaction.atomic
    def _reset():
        # Reset days in updated weeks
        DayPlan.objects.filter(
            week_plan__course=course,
            week_plan__week_number__in=weeks_to_update
        ).update(
            is_completed=False,
            is_locked=True,
            completed_at=None,
        )

        # Reset weeks
        WeekPlan.objects.filter(
            course=course,
            week_number__in=weeks_to_update
        ).update(
            is_completed=False,
        )

        # Update CourseProgress
        try:
            cp = CourseProgress.objects.get(course=course, user=course.user)
            # Recalculate completed days
            completed = DayPlan.objects.filter(
                week_plan__course=course,
                is_completed=True
            ).count()
            cp.completed_days = completed
            cp.overall_percentage = round((completed / course.total_days) * 100, 1) if course.total_days > 0 else 0

            # Set current position to first updated week
            if weeks_to_update:
                first_updated_week = min(weeks_to_update)
                cp.current_week = first_updated_week
                cp.current_day = 1

            cp.save()
            logger.info("Reset user progress for course %s: %d days completed", course.id, completed)
        except CourseProgress.DoesNotExist:
            pass

    _reset()
