"""
Courses app — Background task functions (threading-based, no Celery).
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
import sys
import time
import threading
from asgiref.sync import sync_to_async, async_to_sync
from django.db import transaction

# Explicit logger name matching Django logging configuration
logger = logging.getLogger('apps.courses.tasks')


class WindowsSafeLogFilter(logging.Filter):
    """Filter that ensures log messages are safe for Windows console encoding."""
    def filter(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            try:
                record.msg.encode('ascii')
            except UnicodeEncodeError:
                record.msg = record.msg.encode('ascii', 'ignore').decode('ascii')
        if record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    try:
                        arg.encode('ascii')
                    except UnicodeEncodeError:
                        arg = arg.encode('ascii', 'ignore').decode('ascii')
                new_args.append(arg)
            record.args = tuple(new_args)
        return True


if sys.platform == 'win32':
    logger.addFilter(WindowsSafeLogFilter())


# ──────────────────────────────────────────────
# Background task launcher (replaces Celery .delay())
# ──────────────────────────────────────────────
def _start_background_task(target, args, task_name=None):
    """Launch a function in a background thread with error handling."""
    if task_name is None:
        task_name = target.__name__

    def _run():
        try:
            logger.info("[%s] Starting in background thread", task_name)
            target(*args)
            logger.info("[%s] Completed successfully", task_name)
        except Exception:
            logger.exception("[%s] FAILED in background thread", task_name)
            try:
                from apps.courses.models import Course
                course_id = args[0] if args else None
                if course_id:
                    Course.objects.filter(
                        pk=course_id, generation_status="generating"
                    ).update(generation_status="failed")
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()


def _start_background_task_kwargs(target, args, kwargs, task_name=None):
    """Launch a function with keyword arguments in a background thread with error handling."""
    if task_name is None:
        task_name = target.__name__
    all_args = args + (kwargs,) if kwargs else args

    def _run():
        try:
            logger.info("[%s] Starting in background thread", task_name)
            target(*args, **kwargs)
            logger.info("[%s] Completed successfully", task_name)
        except Exception:
            logger.exception("[%s] FAILED in background thread", task_name)
            try:
                from apps.courses.models import Course
                course_id = args[0] if args else None
                if course_id:
                    Course.objects.filter(
                        pk=course_id, generation_status="generating"
                    ).update(generation_status="failed")
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()


# ──────────────────────────────────────────────
# Concurrency limiter for course generation
# ──────────────────────────────────────────────
_course_generation_semaphore = threading.Semaphore(3)  # Max 3 concurrent generations


def generate_course_content_task(
    course_id: str,
    course_name: str,
    duration_weeks: int,
    level: str,
    goals: list,
    description: str = None,
):
    """
    Background task: Fill course skeleton with AI-generated content.
    All weeks run in PARALLEL using asyncio.gather().
    Each week saves to DB immediately upon completion.
    Updates generation_progress after each day.
    """
    MAX_RETRIES = 3
    RETRY_DELAY = 30  # seconds

    for attempt in range(MAX_RETRIES):
        try:
            return _generate_course_content_task_impl(
                course_id, course_name, duration_weeks, level, goals, description
            )
        except Exception as exc:
            if attempt == MAX_RETRIES - 1:
                logger.exception("generate_course_content_task FAILED after %d retries (course=%s)", MAX_RETRIES, course_id)
                # Mark course as failed
                try:
                    from apps.courses.models import Course
                    Course.objects.filter(pk=course_id, generation_status="generating").update(generation_status="failed")
                except Exception:
                    pass
                raise
            logger.warning("generate_course_content_task attempt %d failed, retrying in %ds: %s", attempt + 1, RETRY_DELAY, exc)
            time.sleep(RETRY_DELAY)


def _generate_course_content_task_impl(
    course_id: str,
    course_name: str,
    duration_weeks: int,
    level: str,
    goals: list,
    description: str = None,
):
    """
    Implementation of course content generation (called with retry loop).
    """
    import sys
    print(f"\n\n*** TASK STARTED: generate_course_content_task ***", flush=True)
    print(f"*** Course: {course_name} ***\n\n", flush=True)
    sys.stdout.flush()
    sys.stderr.flush()

    import logging
    task_logger = logging.getLogger('apps.courses.tasks')
    task_logger.info("TASK FUNCTION ENTERED - generate_course_content_task")

    try:
        from apps.courses.models import Course
        from services.course.generator import CourseGenerator
        import asyncio
    except Exception as import_exc:
        task_logger.exception(f"IMPORT ERROR: {import_exc}")
        print(f"IMPORT ERROR: {import_exc}", flush=True)
        raise

    logger.info("=" * 80)
    logger.info(" COURSE CONTENT GENERATION")
    logger.info(f"   Course ID: {course_id}")
    logger.info(f"   Course Name: {course_name}")
    logger.info(f"   Duration: {duration_weeks} weeks")
    logger.info(f"   Level: {level}")
    logger.info(f"   Description: {description}")
    logger.info("=" * 80)

    # Ensure description is a string (not a list or other type)
    if description is not None and not isinstance(description, str):
        logger.warning(f"Description received as {type(description)}, converting to string or None")
        description = str(description) if description else None

    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        logger.error(" Course %s not found", course_id)
        return

    try:
        course.generation_status = "generating"
        course.save(update_fields=["generation_status"])

        # Reset completion counter for this course
        from apps.courses.sse import get_redis_client
        redis_client = get_redis_client()
        completion_key = f"course_completion:{course_id}"
        redis_client.delete(completion_key)

        logger.info("=" * 80)
        logger.info(" Course status set to 'generating'")
        logger.info("=" * 80)

        print(f"\n{'='*80}")
        print(f" [TASK] RECEIVED: generate_course_content_task")
        print(f"   Course ID: {course_id}")
        print(f"   Course Name: {course_name}")
        print(f"   Duration: {duration_weeks} weeks")
        print(f"   Level: {level}")
        print(f"   Description: {description}")
        print(f"   Goals: {goals}")
        print(f"{'='*80}\n")

        # Use topic from course_name directly (no LLM detection for form submissions)
        # Chat-based generation will pass the topic explicitly
        topic = course_name.strip()
        
        if not topic:
            topic = course_name
        if len(topic) > 200:
            topic = topic[:200]
        
        print(f" [TASK] Topic: {topic}")

        # Update course topic
        course.topic = topic
        course.save(update_fields=["topic"])
        print(f" [TASK] Topic saved to database\n")

        # Create generator
        generator = CourseGenerator()

        # Build skeleton for reference
        total_days = duration_weeks * 5

        print(f" [TASK] Starting async generation for course {course_id}")
        print(f"   Total days to generate: {total_days}")
        print(f"   Weeks to generate: {duration_weeks}\n")

        # Process course in 4-week blocks with web search per block
        # Each block: generate titles → web search → generate content
        asyncio.run(
            _generate_in_blocks_with_web_search(
                generator=generator,
                course_id=course_id,
                topic=topic,
                level=level,
                goals=goals,
                description=description,
                duration_weeks=duration_weeks,
            )
        )

        print(f"\n [TASK] Async generation completed for course {course_id}\n")

        # Mark course days as complete (weekly tests will run next)
        course.refresh_from_db()
        course.generation_progress = total_days
        course.save(update_fields=["generation_progress"])

        # CRITICAL: Reset CourseProgress to Day 1 so users ALWAYS start from the beginning.
        # During generation, days are created with is_completed=False and is_locked=True (except Day 1).
        # We must ensure current_day=1 so the banner shows "Day 1" not the last generated day.
        from apps.courses.models import CourseProgress
        try:
            # Use get_or_create instead of select_for_update (which requires active transaction)
            cp, created = CourseProgress.objects.get_or_create(
                course=course,
                user=course.user,
                defaults={
                    "total_days": total_days,
                    "total_weeks": duration_weeks,
                    "current_week": 1,
                    "current_day": 1,
                    "completed_days": 0,
                    "overall_percentage": 0.0,
                }
            )
            if not created and (cp.current_week != 1 or cp.current_day != 1):
                cp.current_week = 1
                cp.current_day = 1
                cp.save(update_fields=["current_week", "current_day"])
                logger.info(" Reset CourseProgress to Week 1, Day 1 for course %s", course_id)
        except Exception as progress_exc:
            logger.error(" Failed to update CourseProgress for course %s: %s", course_id, progress_exc)

        # NOTE: Don't set generation_status to 'ready' yet!
        # Weekly tests are still generating. Status will be set to 'ready'
        # by the LAST weekly test task when all are complete.

        # Small delay to ensure DB is synced before queuing weekly tests
        time.sleep(0.5)

        # Generate weekly tests (MCQ + Coding) for all weeks
        # Run as background tasks so the main task can complete cleanly
        try:
            _start_background_task(generate_weekly_tests_for_course, (course_id,))
            logger.info(" Weekly test generation queued (async)")
        except Exception as test_exc:
            logger.error(" Weekly test generation failed: %s", test_exc)

        # Refresh course to get final status
        course.refresh_from_db()

        # Calculate total tasks including weekly tests
        total_weekly_tests = course.duration_weeks * 2  # MCQ + coding per week
        total_tasks = total_days + total_weekly_tests

        logger.info("=" * 80)
        logger.info(" COURSE GENERATION COMPLETE")
        logger.info(f"   Course ID: {course_id}")
        logger.info(f"   Status: {course.generation_status}")
        logger.info(f"   Progress: {course.generation_progress}/{total_tasks} tasks")
        logger.info(f"   Total Days: {total_days}")
        logger.info(f"   Weekly Tests: {total_weekly_tests}")
        logger.info("=" * 80)

    except Exception as exc:
        logger.exception("Error generating course %s: %s", course_id, exc)
        try:
            course.refresh_from_db()
            course.generation_status = "failed"
            course.save(update_fields=["generation_status"])
        except Exception:
            pass
        raise


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
    from apps.courses.sse import broadcast_progress_update

    print(f"[BLOCK GENERATION] Starting block-based generation for {duration_weeks} weeks")

    # Get course reference
    course = await sync_to_async(Course.objects.get)(id=course_id)

    # Total granular sub-steps: per week = theme(1) + titles(1) + 5days(5) + mcq(1) + coding(1) = 9
    # Plus per block: web(1) + rag(1) = 2
    # TOTAL: weeks * 9 + blocks * 2
    num_blocks = (duration_weeks + 3) // 4  # 4 weeks per block
    total_sub_steps = duration_weeks * 9 + num_blocks * 2

    def broadcast_sub_step(completed: int, stage: str):
        progress_percent = round((completed / total_sub_steps) * 100) if total_sub_steps > 0 else 0
        broadcast_progress_update(course_id, {
            "progress": progress_percent,
            "completed_days": completed,
            "total_days": total_sub_steps,
            "generation_status": "generating",
            "current_stage": stage,
        })
        logger.info(" Progress: %d/%d sub-steps (%d%%) - %s", completed, total_sub_steps, progress_percent, stage)

    step_counter = 0
    
    # Process in 4-week blocks
    block_start = 1
    block_num = 0
    
    while block_start <= duration_weeks:
        block_end = min(block_start + 3, duration_weeks)  # 4 weeks per block
        block_weeks = block_end - block_start + 1
        block_num += 1

        print(f"\n{'='*80}")
        print(f" [BLOCK {block_num}] Processing weeks {block_start}-{block_end} ({block_weeks} weeks)")
        print(f"{'='*80}")

        # ========== STEP 1: Generate week themes and day titles for this block ==========
        print(f"\n [BLOCK {block_num}] Step 1: Generating week themes and day titles...")
        logger.info("[BLOCK %d] Generating themes and titles for weeks %d-%d", 
                   block_num, block_start, block_end)
        
        block_day_titles = {}  # (week, day) -> title
        block_week_themes = {}  # week -> theme
        
        for week_num in range(block_start, block_end + 1):
            print(f"\n   [BLOCK {block_num}] Generating Week {week_num} theme and titles...")
            logger.info("[BLOCK %d] Week %d: Generating theme and day titles", block_num, week_num)
            
            # Get week plan
            week = await sync_to_async(WeekPlan.objects.get)(course=course, week_number=week_num)
            
            # Generate week theme
            theme, objectives = await generator._generate_week_theme(
                week_number=week_num,
                total_weeks=duration_weeks,
                topic=topic,
                skill_level=level,
                goals=goals,
                description=description,
                previous_themes=[],
            )
            week.theme = theme
            week.objectives = objectives
            await sync_to_async(week.save)(update_fields=["theme", "objectives"])

            step_counter += 1
            broadcast_sub_step(step_counter, f"Generated Week {week_num} theme: {theme[:60]}")

            block_week_themes[week_num] = theme
            print(f"   [BLOCK {block_num}] Week {week_num} theme: {theme}")
            logger.info("[BLOCK %d] Week %d theme saved: %s", block_num, week_num, theme)

            # Generate ALL day titles for this week in ONE LLM call
            days = await sync_to_async(list)(week.days.all().order_by("day_number"))

            # Build previous week titles context
            prev_week_titles = {
                wn: [block_day_titles[(wn, d)] for d in range(1, 6) if (wn, d) in block_day_titles]
                for wn in range(block_start, week_num)
            }

            week_day_titles = await generator._generate_week_day_titles(
                week_number=week_num,
                week_theme=theme,
                topic=topic,
                skill_level=level,
                description=description,
                previous_week_titles=prev_week_titles,
            )

            # Apply titles and tasks to days
            for day, (title, tasks) in zip(days, week_day_titles):
                day_num = day.day_number
                day.title = title
                day.tasks = tasks
                block_day_titles[(week_num, day_num)] = title
                print(f"      [BLOCK {block_num}] Week {week_num} Day {day_num}: {title}")
                logger.info("[BLOCK %d] Week %d Day %d title: %s", block_num, week_num, day_num, title)

            # Save all day titles for this week
            for day in days:
                await sync_to_async(day.save)(update_fields=["title", "tasks"])

            step_counter += 1
            broadcast_sub_step(step_counter, f"Generated Week {week_num} day titles")
        
        # ========== STEP 2: Run web search for this block ==========
        print(f"\n [BLOCK {block_num}] Step 2: Running web search for research data...")
        logger.info("[BLOCK %d] Running web search for weeks %d-%d", block_num, block_start, block_end)

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

            print(f"[BLOCK {block_num}]  Web search complete: {web_search_data.total_results} results, success={web_search_data.success}")

            if web_search_data.success:
                print(f"[BLOCK {block_num}] Results distributed to {len(web_search_data.day_results)} days")
        except Exception as search_exc:
            print(f"[BLOCK {block_num}]  Web search failed: {search_exc}")
            web_search_data = None
        finally:
            step_counter += 1
            broadcast_sub_step(step_counter, "Web search complete")

        # ========== STEP 2b: RAG retrieval from knowledge base ==========
        print(f"\n [BLOCK {block_num}] Step 2b: Retrieving from RAG knowledge base...")
        logger.info("[BLOCK %d] Running RAG retrieval", block_num)
        rag_context = None
        try:
            from services.rag_pipeline.retriever import hybrid_retrieve

            # Build search query from block themes and titles
            all_titles = " ".join(str(t) for t in block_day_titles.values())
            all_themes = " ".join(str(t) for t in block_week_themes.values())
            rag_query = f"{topic} {all_themes} {all_titles}"

            rag_context = await hybrid_retrieve(
                query=rag_query,
                top_k=30,
                course_id=str(course.id),
                use_hyde=True,
                use_decomposition=False,
            )

            if rag_context:
                from services.rag_pipeline.reranker import reranker
                rag_context = reranker.rerank(rag_query, rag_context, top_k=10)
                print(f"[BLOCK {block_num}] RAG retrieved {len(rag_context)} chunks from knowledge base")
            else:
                print(f"[BLOCK {block_num}] No RAG documents found for topic: {topic}")
        except Exception as rag_exc:
            print(f"[BLOCK {block_num}] RAG retrieval failed: {rag_exc}")
        finally:
            step_counter += 1
            broadcast_sub_step(step_counter, "RAG retrieval complete")

        # ========== STEP 3: Generate content for all days in this block ==========
        total_days_in_block = (block_end - block_start + 1) * 5
        print(f"\n [BLOCK {block_num}] Step 3: Generating content for {total_days_in_block} days...")
        print(f"   (Running {total_days_in_block} days in parallel with 1s staggering)")
        logger.info("[BLOCK %d] Generating content for %d days in parallel with staggering",
                   block_num, total_days_in_block)

        # Create progress lock for thread-safe updates
        progress_lock = asyncio.Lock()

        # Generate all days in parallel within this block with staggering
        day_tasks = []
        day_index = 0
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
                # Add staggering delay: 0s, 1s, 2s, 3s, 4s, etc. between day starts
                # This prevents all days from hitting OpenRouter simultaneously
                if day_index > 0:
                    await asyncio.sleep(1)  # 1 second delay between each day start
                
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
                    rag_context=rag_context,
                )
                day_tasks.append(task)
                day_index += 1
        
        # Run all days in parallel
        results = await asyncio.gather(*day_tasks, return_exceptions=True)
        successful = 0
        failed = 0

        for i, result in enumerate(results):
            if result is True:
                successful += 1
                # Note: Per-day progress broadcasts are now handled in _generate_single_day_with_progress
                # immediately after each day saves to DB. This prevents the race condition where
                # all day broadcasts fire at once after parallel completion.
                # We still increment step_counter for internal tracking.
                day_idx = i
                week_offset = 0
                for wn in range(block_start, block_end + 1):
                    days_in_week = 5
                    if day_idx < week_offset + days_in_week:
                        actual_day = day_idx - week_offset + 1
                        step_counter += 1
                        # REMOVED: broadcast_sub_step for day completion - now handled per-day
                        break
                    week_offset += days_in_week
            elif isinstance(result, Exception):
                failed += 1
                logger.error("[BLOCK %d] Day task %d failed: %s", block_num, i + 1, result)
                print(f"[BLOCK {block_num}]  Day task {i+1} failed: {result}")
            else:
                failed += 1
                logger.warning("[BLOCK %d] Day task %d returned unexpected result: %s", block_num, i + 1, result)

        print(f"[BLOCK {block_num}] Completed {successful}/{len(day_tasks)} days successfully ({failed} failed)")
        logger.info("[BLOCK %d] Day generation complete: %d/%d succeeded",
                   block_num, successful, len(day_tasks))
        
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
    rag_context=None,  # RAG retrieved chunks from knowledge base
):
    """
    Generate content for a single day (titles already generated).
    Uses web search results for theory generation if available.
    """
    from apps.quizzes.models import QuizQuestion
    import json

    week_number = week.week_number
    # Get title from day object first
    title = day.title or f"Week {week_number} Day {day_num}"
    
    print(f"\n   [Course {course.id}] Generating Week {week_number} Day {day_num}: {title}")
    logger.info("=" * 60)
    logger.info(" GENERATING: Course %s | Week %d | Day %d | %s",
               course.id, week_number, day_num, title)
    logger.info("=" * 60)

    try:
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

        # Combine web search + RAG context for theory generation
        combined_context = web_results_formatted
        if rag_context:
            rag_formatted = "\n\n--- Knowledge Base Context ---\n" + "\n\n".join(
                f"[Source {i+1}: {c.get('title', 'Document')}]\n{c['content']}"
                for i, c in enumerate(rag_context[:5])
            )
            combined_context = web_results_formatted + rag_formatted
            logger.info(
                "[RAG_USAGE] Week %d Day %d: Injecting %d RAG chunks into theory generation",
                week_number, day_num, len(rag_context[:5])
            )

        print(f"     [Week {week_number} Day {day_num}] Step 1: Generating THEORY content...")
        logger.info("[LLM REQUEST] Week %d Day %d: Generating theory content",
                   week_number, day_num)

        # Step 1: Generate theory (SEQUENTIAL)
        theory = await generator._generate_theory_content(
            title, theme, topic, level, description, combined_context
        )
        
        # LOG raw theory output (FULL, untruncated)
        logger.info("="*70)
        logger.info(" RAW AI OUTPUT: Week %d Day %d THEORY", week_number, day_num)
        logger.info("="*70)
        logger.info("THEORY (%d chars):\n%s", len(theory) if theory else 0, theory if theory else "EMPTY")
        logger.info("="*70)
        
        print(f"        [OK] Theory: {len(theory) if theory else 0} chars")

        # Step 2: Generate code (SEQUENTIAL, after theory)
        print(f"     [Week {week_number} Day {day_num}] Step 2: Generating CODE content...")
        logger.info("[LLM REQUEST] Week %d Day %d: Generating code content",
                   week_number, day_num)
        
        code = await generator._generate_code_content(title, theme, topic, level)
        
        # LOG raw code output (FULL, untruncated)
        logger.info("="*70)
        logger.info(" RAW AI OUTPUT: Week %d Day %d CODE", week_number, day_num)
        logger.info("="*70)
        logger.info("CODE (%d chars):\n%s", len(code) if code else 0, code if code else "EMPTY")
        logger.info("="*70)
        
        print(f"        [OK] Code: {len(code) if code else 0} chars")
        logger.info("[LLM RESPONSE] Week %d Day %d: Theory=%d chars, Code=%d chars",
                   week_number, day_num,
                   len(theory) if theory else 0,
                   len(code) if code else 0)

        # Step 3: Generate quiz questions with retry logic
        quizzes = []
        quiz_generated = False
        max_quiz_retries = 3

        print(f"     [Week {week_number} Day {day_num}] Step 3: Generating QUIZ ({max_quiz_retries} max retries)...")
        logger.info("[LLM REQUEST] Week %d Day %d: Generating quiz questions", week_number, day_num)
        
        for quiz_attempt in range(max_quiz_retries):
            try:
                quiz_result = await generator._generate_quiz_questions(title, topic, level)
                quizzes = quiz_result.get("quizzes", [])
                
                # LOG raw quiz output (FULL, untruncated)
                logger.info("="*70)
                logger.info(" RAW AI OUTPUT: Week %d Day %d QUIZ (attempt %d)", week_number, day_num, quiz_attempt+1)
                logger.info("="*70)
                logger.info("QUIZ (%d questions):\n%s", len(quizzes) if quizzes else 0, json.dumps(quizzes, indent=2) if quizzes else "EMPTY")
                logger.info("="*70)

                if quizzes and len(quizzes) > 0:
                    quiz_generated = True
                    logger.info("[OK] Quiz generated for Week %d Day %d (%d questions)",
                               week_number, day_num, len(quizzes))
                    break
                else:
                    logger.warning("Quiz generation returned empty result (attempt %d/%d)",
                                  quiz_attempt + 1, max_quiz_retries)
                    if quiz_attempt < max_quiz_retries - 1:
                        await asyncio.sleep(3 + quiz_attempt * 2)  # 3s, 5s, 7s
            except Exception as quiz_exc:
                logger.warning("Quiz generation error (attempt %d/%d): %s",
                              quiz_attempt + 1, max_quiz_retries, quiz_exc)
                if quiz_attempt < max_quiz_retries - 1:
                    await asyncio.sleep(3 + quiz_attempt * 2)  # 3s, 5s, 7s

        if not quiz_generated:
            logger.error("[ERROR] Quiz generation failed after %d attempts for Week %d Day %d",
                        max_quiz_retries, week_number, day_num)

        # Save to DB
        from services.course.generator import _sanitize_mermaid
        theory = _sanitize_mermaid(theory)
        day.theory_content = theory
        
        # Parse code content into structured format before saving
        structured_code = {}
        try:
            from services.course.code_parser import parse_code_content
            structured_code = parse_code_content(code)
            # Store structured JSON in code_content field
            day.code_content = json.dumps(structured_code, indent=2)
            logger.info("[CODE_PARSER] Week %d Day %d: Parsed %d examples",
                       week_number, day_num, len(structured_code.get("examples", [])))
        except Exception as parse_err:
            # Fallback: store raw content if parsing fails
            logger.warning("[CODE_PARSER] Week %d Day %d: Parsing failed, storing raw: %s",
                          week_number, day_num, parse_err)
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
            "is_completed", "is_locked",
        ])

        # DO NOT unlock the day here. Days should only be unlocked when:
        # 1. Week 1 Day 1 is unlocked by default during skeleton creation
        # 2. Subsequent days are unlocked ONLY when the user completes the previous day's quiz
        # This ensures proper course progression - users must complete quizzes to unlock next days.

        # REMOVED: broadcast_day_complete - was causing frontend to show 0% progress
        # Progress is now broadcast only via broadcast_progress_update with correct percentage
        # The day_unlock logic in quiz completion handles frontend unlocking

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

            # CRITICAL FIX: Broadcast progress update immediately after incrementing generation_progress
            # This prevents race condition where polling fetches stale data before SSE updates
            try:
                from apps.courses.sse import broadcast_progress_update
                # Calculate total days and match SSE progress formula exactly
                total_days_count = (course.duration_weeks or 1) * 5
                # Formula: 36% base + (completed_days / total_days) * 46%
                progress_pct = round(36 + (course.generation_progress / total_days_count) * 46) if total_days_count > 0 else 36
                broadcast_progress_update(str(course.id), {
                    "progress": min(82, progress_pct),  # Cap at 82% (tests complete remaining)
                    "completed_days": course.generation_progress,
                    "total_days": total_days_count,
                    "generation_status": "generating",
                    "current_stage": f"Week {week_number} Day {day_num} complete",
                })
            except Exception as progress_broadcast_err:
                logger.warning(" Failed to broadcast progress update (non-critical): %s", progress_broadcast_err)

        print(f"\n   [COMPLETE] Week {week_number} Day {day_num} saved to DB")
        logger.info(" [DAY COMPLETE] Course %s | Week %d Day %d saved to database",
                   course.id, week_number, day_num)
        return True

    except Exception as e:
        print(f"\n   [ERROR] Week {week_number} Day {day_num}: {e}")
        logger.exception(" [DAY ERROR] Course %s | Week %d Day %d: %s", course.id, week_number, day_num, e)
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

    # Run all 5 days in PARALLEL with staggering to avoid rate limiting
    print(f"[WEEK {week_number}] Starting {len(days)} days in parallel with 1s staggering...")
    day_tasks = []
    for idx, (day, day_num, title, tasks) in enumerate(day_titles):
        # Add staggering delay: 0s, 1s, 2s, 3s, 4s between day starts
        # This prevents all 5 days from hitting OpenRouter simultaneously
        if idx > 0:
            await asyncio.sleep(1)  # 1 second delay between each day start
        
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

    # Run all days in parallel (they're already staggered)
    results = await asyncio.gather(*day_tasks, return_exceptions=True)
    successful = sum(1 for r in results if r is True)
    print(f"[WEEK {week_number}] Completed {successful}/{len(days)} days successfully")
    logger.info("Completed week %d for course %s (%d/%d days successful)", week_number, course_id, successful, len(days))


def generate_day_content_task(
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

    MAX_RETRIES = 3
    RETRY_DELAY = 60  # seconds

    for attempt in range(MAX_RETRIES):
        try:
            try:
                day = DayPlan.objects.select_related("week_plan", "week_plan__course").get(id=day_id)
            except DayPlan.DoesNotExist:
                logger.error("Day %s not found", day_id)
                return

            if day.theory_generated and day.code_generated:
                logger.info("Day %s already has content, skipping", day_id)
                return

            generator = CourseGenerator()

            # Generate theory content
            logger.info("[LLM REQUEST] Generating theory content for day %s...", day_id)
            theory = generator._generate_theory_content(
                day_title=day.title or f"Day {day.day_number}",
                week_theme=day.week_plan.theme or "",
                topic=topic,
                skill_level=skill_level,
            )

            # LOG raw theory output
            logger.info("="*70)
            logger.info(" RAW AI OUTPUT: Day %s THEORY", day_id)
            logger.info("="*70)
            logger.info("THEORY (%d chars):\n%s", len(theory) if theory else 0, theory if theory else "EMPTY")
            logger.info("="*70)

            from services.course.generator import _sanitize_mermaid
            day.theory_content = _sanitize_mermaid(theory)
            day.theory_generated = True

            # Generate code content
            logger.info("[LLM REQUEST] Generating code content for day %s...", day_id)
            code = generator._generate_code_content(
                day_title=day.title or f"Day {day.day_number}",
                week_theme=day.week_plan.theme or "",
                topic=topic,
                skill_level=skill_level,
            )

            # LOG raw code output
            logger.info("="*70)
            logger.info(" RAW AI OUTPUT: Day %s CODE", day_id)
            logger.info("="*70)
            logger.info("CODE (%d chars):\n%s", len(code) if code else 0, code if code else "EMPTY")
            logger.info("="*70)

            day.code_content = code
            day.code_generated = True

            day.save(update_fields=["theory_content", "theory_generated", "code_content", "code_generated"])

            logger.info(" [DAY COMPLETE] Day %s: theory=%d chars, code=%d chars", day_id, len(theory) if theory else 0, len(code) if code else 0)
            break

        except Exception as exc:
            if attempt == MAX_RETRIES - 1:
                logger.exception("generate_day_content_task FAILED after %d retries (day=%s)", MAX_RETRIES, day_id)
                raise
            logger.warning("generate_day_content_task attempt %d failed, retrying in %ds: %s", attempt + 1, RETRY_DELAY, exc)
            time.sleep(RETRY_DELAY)


def generate_all_quizzes(course_id: str):
    """
    Generate quiz questions for all days in a course.
    """
    from apps.courses.models import Course, DayPlan
    from apps.quizzes.tasks import generate_quiz_for_day

    MAX_RETRIES = 2
    RETRY_DELAY = 30  # seconds

    for attempt in range(MAX_RETRIES):
        try:
            course = Course.objects.get(id=course_id)
            days = DayPlan.objects.filter(week_plan__course=course)

            for day in days:
                _start_background_task(generate_quiz_for_day, (str(day.id),))

            logger.info("Queued quiz generation for %d days in course %s", days.count(), course_id)
            break

        except Exception as exc:
            if attempt == MAX_RETRIES - 1:
                logger.exception("generate_all_quizzes FAILED after %d retries (course=%s)", MAX_RETRIES, course_id)
                raise
            logger.warning("generate_all_quizzes attempt %d failed, retrying in %ds: %s", attempt + 1, RETRY_DELAY, exc)
            time.sleep(RETRY_DELAY)


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


def generate_weekly_test_task(course_id: str, week_number: int, total_sub_steps: int = None, skip_broadcast: bool = False):
    """
    Generate a weekly test covering all 5 days of a week.
    10 MCQ questions covering entire week content.

    After completion, fires progress broadcast at fixed step number.
    If coding test step exceeds total, fires broadcast_generation_complete().

    Args:
        course_id: Course UUID
        week_number: Week number to generate test for
        total_sub_steps: Total granular sub-steps for the course
        skip_broadcast: If True, skip progress broadcast
    """
    from services.course.generator import CourseGenerator
    import asyncio

    MAX_RETRIES = 2
    RETRY_DELAY = 5  # seconds

    for attempt in range(MAX_RETRIES):
        try:
            logger.info("=" * 60)
            logger.info(" TASK: GENERATE WEEKLY TEST")
            logger.info("   Course ID: %s", course_id)
            logger.info("   Week: %d", week_number)
            logger.info("   Attempt: %d/%d", attempt + 1, MAX_RETRIES)
            logger.info("=" * 60)

            # Validate course exists before attempting generation
            from apps.courses.models import Course as CourseModel
            try:
                course_check = CourseModel.objects.get(id=course_id)
                logger.info(" Course validated: %s", course_check.course_name)
            except CourseModel.DoesNotExist:
                logger.error(" Course %s does not exist - aborting task", course_id)
                return {"error": "Course not found", "success": False}

            generator = CourseGenerator()
            result = asyncio.run(generator.generate_weekly_test(course_id, week_number))

            if result.get("success"):
                total_q = result.get("total_questions", 0)
                logger.info(" Weekly test generated successfully")
                logger.info("   Test ID: %s", result.get("test_id"))
                logger.info("   Questions: %d", total_q)
                if total_q < 10:
                    logger.warning(" Only %d/10 questions generated - partial test saved", total_q)

                # MCQ tests run AFTER coding tests
                # Coding steps: total_weeks*7 + num_blocks*2 + (1 to total_weeks)
                # MCQ steps: total_weeks*8 + num_blocks*2 + (1 to total_weeks) = total_sub_steps
                from apps.courses.models import Course
                from apps.courses.sse import broadcast_progress_update, broadcast_generation_complete

                course = Course.objects.get(id=course_id)
                total_weeks = course.duration_weeks or 0
                num_blocks = (total_weeks + 3) // 4
                total_sub_steps = total_weeks * 9 + num_blocks * 2

                # MCQ step = all days + web + rag + theme + titles + all coding tests + this week's MCQ
                mcq_step = total_weeks * 8 + num_blocks * 2 + week_number
                progress_percent = round((mcq_step / total_sub_steps) * 100)
                logger.info(" Weekly MCQ test complete: step %d/%d (%d%%)", mcq_step, total_sub_steps, progress_percent)

                # Atomic completion tracking: only fire COMPLETE when ALL weeks are done
                from apps.courses.sse import get_redis_client
                redis_client = get_redis_client()
                completion_key = f"course_completion:{course_id}"
                completed_count = redis_client.incr(completion_key)
                redis_client.expire(completion_key, 3600)  # Expire after 1 hour
                logger.info(" Completion counter: %d/%d weeks for course %s", completed_count, total_weeks, course_id)

                # Only mark as READY and broadcast when ALL weeks are complete
                if completed_count >= total_weeks:
                    course.generation_status = "ready"
                    course.status = "active"
                    course.save(update_fields=["generation_status", "status"])
                    logger.info(" ALL %d WEEKS COMPLETE - Course %s marked as READY!", total_weeks, course_id)
                    broadcast_generation_complete(course_id, {
                        "progress": 100,
                        "completed_days": total_sub_steps,
                        "total_days": total_sub_steps,
                        "generation_status": "ready",
                        "current_stage": "Course generation complete!",
                    })
                else:
                    logger.info("Waiting for remaining weeks to complete: %d/%d", completed_count, total_weeks)
            else:
                logger.warning(" Weekly test generation failed: %s", result.get("error"))
                raise Exception(result.get("error"))
            break

        except Exception as exc:
            if attempt == MAX_RETRIES - 1:
                logger.exception("generate_weekly_test_task FAILED after %d retries (course=%s, week=%d)", MAX_RETRIES, course_id, week_number)
                raise
            logger.warning("generate_weekly_test_task attempt %d failed, retrying in %ds: %s", attempt + 1, RETRY_DELAY, exc)
            time.sleep(RETRY_DELAY)


def generate_certificate_task(user_id: str, course_id: str):
    """
    Generate a PDF certificate for a completed course.
    """
    from services.certificate.generator import CertificateGenerator

    MAX_RETRIES = 3
    RETRY_DELAY = 60  # seconds

    for attempt in range(MAX_RETRIES):
        try:
            generator = CertificateGenerator()
            result = generator.generate_certificate(user_id, course_id)

            if result.get("success"):
                logger.info("Generated certificate for user %s course %s", user_id, course_id)
            else:
                logger.warning("Certificate generation failed: %s", result.get("error"))
                raise Exception(result.get("error"))
            break

        except Exception as exc:
            if attempt == MAX_RETRIES - 1:
                logger.exception("generate_certificate_task FAILED after %d retries (user=%s, course=%s)", MAX_RETRIES, user_id, course_id)
                raise
            logger.warning("generate_certificate_task attempt %d failed, retrying in %ds: %s", attempt + 1, RETRY_DELAY, exc)
            time.sleep(RETRY_DELAY)


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


def generate_coding_test_task(course_id: str, week_number: int, test_number: int = 1, total_sub_steps: int = None, skip_broadcast: bool = False):
    """
    Generate a weekly coding test with coding problems.

    After completion, fires broadcast_generation_complete().

    Args:
        course_id: Course UUID
        week_number: Week number to generate test for
        test_number: Which coding test (1 or 2)
        total_sub_steps: Total granular sub-steps for the course
        skip_broadcast: If True, skip progress broadcast
    """
    from services.course.generator import CourseGenerator
    import asyncio

    MAX_RETRIES = 2
    RETRY_DELAY = 5  # seconds

    for attempt in range(MAX_RETRIES):
        try:
            logger.info("=" * 60)
            logger.info(" TASK: GENERATE CODING TEST %d", test_number)
            logger.info("   Course ID: %s", course_id)
            logger.info("   Week: %d", week_number)
            logger.info("   Test Number: %d", test_number)
            logger.info("   Attempt: %d/%d", attempt + 1, MAX_RETRIES)
            logger.info("=" * 60)

            # Validate course exists before attempting generation
            from apps.courses.models import Course as CourseModel
            try:
                course_check = CourseModel.objects.get(id=course_id)
                logger.info(" Course validated: %s", course_check.course_name)
            except CourseModel.DoesNotExist:
                logger.error(" Course %s does not exist - aborting task", course_id)
                return {"error": "Course not found", "success": False}

            generator = CourseGenerator()
            result = asyncio.run(generator.generate_coding_test(course_id, week_number))

            if result.get("success"):
                logger.info(" Coding test %d generated successfully", test_number)
                logger.info("   Problems: %s", result.get("total_problems"))

                # Coding tests run FIRST (before MCQ)
                from apps.courses.models import Course
                from apps.courses.sse import broadcast_progress_update

                course = Course.objects.get(id=course_id)
                total_weeks = course.duration_weeks or 0
                num_blocks = (total_weeks + 3) // 4
                total_sub_steps = total_weeks * 9 + num_blocks * 2

                # Coding step = all days + web + rag + theme + titles + this week's coding
                coding_step = total_weeks * 7 + num_blocks * 2 + week_number
                progress_percent = round((coding_step / total_sub_steps) * 100)
                logger.info(" Weekly coding test complete: step %d/%d (%d%%)", coding_step, total_sub_steps, progress_percent)

                # Just broadcast progress (MCQ will fire complete)
                broadcast_progress_update(course_id, {
                    "progress": progress_percent,
                    "completed_days": coding_step,
                    "total_days": total_sub_steps,
                    "generation_status": "generating",
                    "current_stage": f"Generated coding test {test_number} for Week {week_number}...",
                    "coding_test_status": f"Week {week_number} coding test {test_number} complete",
                })
            else:
                logger.warning(" Coding test %d generation failed: %s", test_number, result.get("error"))
                raise Exception(result.get("error"))
            break

        except Exception as exc:
            if attempt == MAX_RETRIES - 1:
                logger.exception("generate_coding_test_task FAILED after %d retries (course=%s, week=%d)", MAX_RETRIES, course_id, week_number)
                raise
            logger.warning("generate_coding_test_task attempt %d failed, retrying in %ds: %s", attempt + 1, RETRY_DELAY, exc)
            time.sleep(RETRY_DELAY)


def generate_weekly_tests_for_course(course_id: str):
    """
    Generate both MCQ test and coding test for all weeks in a course.
    Called after all days are generated.

    Queues async weekly test tasks. Each test task increments a Redis completion counter.
    The LAST test to complete (atomic via Redis INCR) fires broadcast_generation_complete().
    """
    from apps.courses.models import Course
    from django.db import transaction
    from django.db.models import F

    MAX_RETRIES = 3
    RETRY_DELAY = 30  # seconds

    for attempt in range(MAX_RETRIES):
        try:
            course = Course.objects.get(id=course_id)
            total_weeks = course.duration_weeks

            logger.info("Starting sequential weekly test generation for %d weeks in course %s",
                       total_weeks, course_id)

            # Reset completion counter for this course
            from apps.courses.sse import get_redis_client
            redis_client = get_redis_client()
            completion_key = f"course_completion:{course_id}"
            redis_client.delete(completion_key)

            # Broadcast that weekly test generation is starting
            from apps.courses.sse import broadcast_progress_update

            # Calculate total granular sub-steps (must match _generate_in_blocks_with_web_search)
            num_blocks = (total_weeks + 3) // 4
            total_sub_steps = total_weeks * 9 + num_blocks * 2

            broadcast_progress_update(course_id, {
                "progress": round(((total_weeks * 7 + num_blocks * 2) / total_sub_steps) * 100),
                "completed_days": total_weeks * 7 + num_blocks * 2,
                "total_days": total_sub_steps,
                "generation_status": "generating",
                "current_stage": "Generating weekly tests...",
                "weekly_test_status": f"Starting weekly tests for {total_weeks} weeks",
            })

            # Queue coding tests FIRST for all weeks
            for week_number in range(1, total_weeks + 1):
                logger.info("Queuing coding test for Week %d...", week_number)
                _start_background_task(generate_coding_test_task, (course_id, week_number, total_sub_steps))

            # Then queue MCQ tests batch-wise (week by week)
            for week_number in range(1, total_weeks + 1):
                logger.info("Queuing MCQ test for Week %d...", week_number)
                _start_background_task(generate_weekly_test_task, (course_id, week_number, total_sub_steps))

            logger.info("Queued %d coding tests + %d MCQ tests for course %s",
                       total_weeks, total_weeks, course_id)
            break

        except Exception as exc:
            if attempt == MAX_RETRIES - 1:
                logger.exception("generate_weekly_tests_for_course FAILED after %d retries (course=%s)", MAX_RETRIES, course_id)
                raise
            logger.warning("generate_weekly_tests_for_course attempt %d failed, retrying in %ds: %s", attempt + 1, RETRY_DELAY, exc)
            time.sleep(RETRY_DELAY)


# ──────────────────────────────────────────────
# COURSE UPDATE TASK
# ──────────────────────────────────────────────
def update_course_content_task(
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

    MAX_RETRIES = 3
    RETRY_DELAY = 30  # seconds

    for attempt in range(MAX_RETRIES):
        try:
            logger.info("=" * 80)
            logger.info(" TASK: UPDATE COURSE CONTENT")
            logger.info("   Course ID: %s", course_id)
            logger.info("   Course Name: %s", course_name)
            logger.info("   Update Type: %s", update_type)
            logger.info("   Weeks to Update: %s", weeks_to_update)
            logger.info("   User Query: %s", user_query)
            logger.info("=" * 80)

            if weeks_to_update is None:
                weeks_to_update = []

            try:
                course = Course.objects.get(id=course_id)
            except Course.DoesNotExist:
                logger.error(" Course %s not found", course_id)
                return

            course.generation_status = "updating"
            course.save(update_fields=["generation_status"])

            logger.info(" Course status set to 'updating'")

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

 CRITICAL USER UPDATE REQUEST (PRIORITIZE THIS):
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
                logger.info(" COMPACT UPDATE: Compressing course from %d to %d weeks",
                           course.duration_weeks, new_duration_weeks or target_weeks)
                # For compact, skip web search and use special prompting
                web_search_enabled = False
            elif update_type == "extend":
                extend_weeks_count = len(weeks_to_update)
                logger.info(" EXTEND UPDATE: Adding %d new weeks (weeks %s)",
                           extend_weeks_count, weeks_to_update)
            elif update_type == "percentage":
                logger.info(" PERCENTAGE UPDATE: Replacing last %d%% of course (%d weeks)",
                           percentage, len(weeks_to_update))

            # Run async generation using async_to_sync for better event loop management
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
                logger.info(" [TEST PHASE] Starting test generation:")
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
                    logger.info(" [TEST] Regenerating weekly test for week %d", week_num)
                    generate_weekly_test_task(course_id, week_num, True)  # skip_broadcast=True
                    test_count += 1

                    # Update progress for MCQ test completion
                    # Start from days progress (~70%) and add test progress
                    tasks_done = days_completed + test_count
                    progress_percent = round((tasks_done / total_tasks) * 100)

                    logger.info(" [TEST PROGRESS] MCQ Test Week %d: days_completed=%d + test_count=%d = tasks_done=%d/%d = %d%%",
                               week_num, days_completed, test_count, tasks_done, total_tasks, progress_percent)

                    broadcast_progress_update(course_id, {
                        "progress": int(progress_percent),
                        "completed_days": days_completed,
                        "total_days": total_days_to_update,
                        "generation_status": "updating",
                        "current_stage": f"Generating tests for Week {week_num}...",
                    })

                    logger.info(" [TEST] Regenerating coding test for week %d", week_num)
                    generate_coding_test_task(course_id, week_num, True)  # skip_broadcast=True
                    test_count += 1

                    # Update progress for coding test completion
                    tasks_done = days_completed + test_count
                    progress_percent = round((tasks_done / total_tasks) * 100)

                    logger.info(" [TEST PROGRESS] Coding Test Week %d: days_completed=%d + test_count=%d = tasks_done=%d/%d = %d%%",
                               week_num, days_completed, test_count, tasks_done, total_tasks, progress_percent)

                    broadcast_progress_update(course_id, {
                        "progress": int(progress_percent),
                        "completed_days": days_completed,
                        "total_days": total_days_to_update,
                        "generation_status": "updating",
                        "current_stage": f"Generating coding test for Week {week_num}...",
                    })

            logger.info("=" * 80)
            logger.info(" COURSE UPDATE COMPLETE")
            logger.info("   Course ID: %s", course_id)
            logger.info("   Status: %s", course.generation_status)
            logger.info("   Weeks Updated: %s", weeks_to_update)
            logger.info("   Total Tasks: %s (100%%)", total_tasks)
            logger.info("=" * 80)

            # Broadcast final completion status to frontend
            from apps.courses.sse import broadcast_generation_complete
            broadcast_generation_complete(course_id, {
                "progress": 100,
                "completed_days": total_days_to_update,
                "total_days": total_days_to_update,
                "generation_status": "ready",
                "current_stage": "Update complete!",
            })
            break

        except Exception as exc:
            if attempt == MAX_RETRIES - 1:
                logger.exception("update_course_content_task FAILED after %d retries (course=%s)", MAX_RETRIES, course_id)
                try:
                    course.refresh_from_db()
                    course.generation_status = "failed"
                    course.save(update_fields=["generation_status"])
                except Exception:
                    pass
                raise
            logger.warning("update_course_content_task attempt %d failed, retrying in %ds: %s", attempt + 1, RETRY_DELAY, exc)
            time.sleep(RETRY_DELAY)


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
        logger.info(" Deleted %d weeks for compact update (now %d weeks total)", 
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

    logger.info(" STARTING WEEK %d UPDATE", week_number)
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

        logger.info(" Generating week theme for Week %d...", week_number)

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
        logger.info(" [PARALLEL DAY GENERATION] Starting parallel generation for all 5 days in Week %d...", week_number)
        
        async def generate_day_content(day, web_search_data, search_service):
            """Generate content for a single day."""
            day_num = day.day_number
            logger.info(" [DAY GENERATION] Week %d Day %d: %s", week_number, day_num, day.title)

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
                        logger.info(" [WEB SEARCH] Using %d results for Day %d", len(day_results), day_num)
                    except Exception as web_exc:
                        logger.warning("Failed to format web results: %s", web_exc)

            # Generate theory and code in parallel
            logger.info(" [LLM CALL] Generating theory content for Day %d...", day_num)
            theory_task = generator._generate_theory_content(
                day_title=day.title,
                week_theme=theme,
                topic=topic,
                skill_level=level,
                description=description,
                web_search_results=web_results_formatted,
            )
            logger.info(" [LLM CALL] Generating code content for Day %d...", day_num)
            code_task = generator._generate_code_content(
                day_title=day.title,
                week_theme=theme,
                topic=topic,
                skill_level=level,
            )
            theory, code = await asyncio.gather(theory_task, code_task)

            # LOG raw theory output (FULL, untruncated)
            logger.info("="*70)
            logger.info(" RAW AI OUTPUT: Week %d Day %d THEORY", week_number, day_num)
            logger.info("="*70)
            logger.info("THEORY (%d chars):\n%s", len(theory) if theory else 0, theory if theory else "EMPTY")
            logger.info("="*70)

            # LOG raw code output (FULL, untruncated)
            logger.info("="*70)
            logger.info(" RAW AI OUTPUT: Week %d Day %d CODE", week_number, day_num)
            logger.info("="*70)
            logger.info("CODE (%d chars):\n%s", len(code) if code else 0, code if code else "EMPTY")
            logger.info("="*70)

            # Generate quiz
            logger.info(" [LLM CALL] Generating quiz questions for Day %d...", day_num)
            quiz_result = await generator._generate_quiz_questions(
                day_title=day.title,
                topic=topic,
                skill_level=level,
            )
            quizzes = quiz_result.get("quizzes", [])
            quiz_generated = len(quizzes) > 0

            # LOG raw quiz output (FULL, untruncated)
            logger.info("="*70)
            logger.info(" RAW AI OUTPUT: Week %d Day %d QUIZ", week_number, day_num)
            logger.info("="*70)
            logger.info("QUIZ (%d questions):\n%s", len(quizzes) if quizzes else 0, json.dumps(quizzes, indent=2) if quizzes else "EMPTY")
            logger.info("="*70)

            logger.info(" [DAY COMPLETE] Day %d: theory=%d chars, code=%d chars, quiz=%d questions",
                       day_num, len(theory) if theory else 0, len(code) if code else 0, len(quizzes))

            return day, theory, code, quizzes, quiz_generated

        # Create tasks for all 5 days
        day_generation_tasks = [
            generate_day_content(day, web_search_data, search_service)
            for day in days
        ]

        # Run ALL 5 days in parallel!
        logger.info(" [PARALLEL] Launching %d parallel day generation tasks...", len(day_generation_tasks))
        day_results = await asyncio.gather(*day_generation_tasks, return_exceptions=True)

        # Process results and save to database
        for result in day_results:
            if isinstance(result, Exception):
                logger.error(" Day generation failed: %s", result)
                continue
            
            day, theory, code, quizzes, quiz_generated = result

            # Save day content
            from services.course.generator import _sanitize_mermaid
            day.theory_content = _sanitize_mermaid(theory)
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
            logger.info(" [DB SAVED] Week %d Day %d saved to database", week_number, day.day_number)

        logger.info(" [WEEK COMPLETE] All %d days in Week %d generated and saved!", len(days), week_number)

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
            
            logger.info(" [PROGRESS] Week %d complete: %d days total, progress %d%% (capped at 70%%)",
                       week_number, course.generation_progress, progress_percent)

            broadcast_progress_update(course.id, {
                "progress": progress_percent,
                "completed_days": course.generation_progress,
                "total_days": total_days_to_update,  # Only the days being updated, not full course
                "generation_status": "updating",
                "current_stage": f"Updating Week {week_number}...",
            })

        logger.info(" Week %d updated successfully", week_number)
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
    Preserves completed weeks' test status to avoid forcing users to retake tests.
    """
    from apps.courses.models import WeekPlan, DayPlan, CourseProgress
    from django.db import transaction

    @transaction.atomic
    def _reset():
        # Identify which weeks were already completed (test passed)
        completed_weeks = set(
            WeekPlan.objects.filter(
                course=course,
                week_number__in=weeks_to_update,
                is_completed=True
            ).values_list('week_number', flat=True)
        )

        # Reset days in updated weeks
        DayPlan.objects.filter(
            week_plan__course=course,
            week_plan__week_number__in=weeks_to_update
        ).update(
            is_completed=False,
            is_locked=True,
            completed_at=None,
        )

        # Reset weeks, but preserve completed status and test unlocks for already-completed weeks
        for week_num in weeks_to_update:
            week = WeekPlan.objects.filter(course=course, week_number=week_num).first()
            if not week:
                continue

            if week_num in completed_weeks:
                # Preserve completed week status and test unlocks
                # Only reset day completion, keep test status intact
                week.is_completed = True
                # Keep test_unlocked, coding_test_1_unlocked, etc. as they were
                week.save(update_fields=['is_completed'])
            else:
                # Fully reset incomplete weeks
                week.is_completed = False
                week.test_unlocked = False
                week.coding_test_1_unlocked = False
                week.coding_test_1_completed = False
                week.coding_test_2_unlocked = False
                week.coding_test_2_completed = False
                week.save(update_fields=[
                    'is_completed', 'test_unlocked',
                    'coding_test_1_unlocked', 'coding_test_1_completed',
                    'coding_test_2_unlocked', 'coding_test_2_completed'
                ])

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
                # Find the first non-completed week to set as current
                first_incomplete_week = None
                for week_num in sorted(weeks_to_update):
                    if week_num not in completed_weeks:
                        first_incomplete_week = week_num
                        break

                if first_incomplete_week is not None:
                    cp.current_week = first_incomplete_week
                    cp.current_day = 1
                elif completed_weeks:
                    # All updated weeks were completed, set to the week after the last completed one
                    last_completed = max(completed_weeks)
                    next_week = last_completed + 1
                    if next_week <= course.duration_weeks:
                        cp.current_week = next_week
                        cp.current_day = 1
                    else:
                        # Course is fully complete
                        cp.current_week = course.duration_weeks
                        cp.current_day = 5

            cp.save()
            logger.info("Reset user progress for course %s: %d days completed", course.id, completed)
        except CourseProgress.DoesNotExist:
            pass

    _reset()
