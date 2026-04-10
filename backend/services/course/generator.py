"""
Course generation service.
Uses LangGraph flows for multi-step generation with validation.
Integrates with vLLM server via services/llm/client.py.
"""
import asyncio
import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# Predefined structure rules
DAYS_PER_WEEK = 5
WEEKS_PER_MONTH = 4


def parse_duration(duration_input: str) -> int:
    """
    Parse duration input string to number of weeks.

    Examples:
        "1 month"   → 4
        "2 months"  → 8
        "3 months"  → 12
        "1 week"    → 1
        "6 weeks"   → 6
        "10 weeks"  → 10

    Args:
        duration_input: Duration string like "1 month", "2 weeks", etc.

    Returns:
        Number of weeks
    """
    if not duration_input:
        return 4  # Default to 1 month

    duration_input = duration_input.lower().strip()

    # Handle typos and variations
    duration_input = duration_input.replace("months", "month").replace("weeks", "week")
    duration_input = duration_input.replace("moths", "month").replace("wks", "week")
    duration_input = duration_input.replace("mth", "month").replace("wk", "week")

    # Extract number
    match = re.search(r"(\d+)", duration_input)
    number = int(match.group(1)) if match else 1

    # Determine unit
    if "month" in duration_input:
        return number * WEEKS_PER_MONTH
    elif "week" in duration_input:
        return number
    else:
        # Default interpretation
        return number if number > 12 else number * WEEKS_PER_MONTH


def build_skeleton(
    duration_weeks: int,
    topic: str,
    skill_level: str,
) -> Dict[str, Any]:
    """
    Build empty course skeleton with predefined structure.

    Args:
        duration_weeks: Number of weeks
        topic: Course topic
        skill_level: Skill level (beginner/intermediate/advanced)

    Returns:
        Empty skeleton dict with null values for AI to fill
    """
    total_days = duration_weeks * DAYS_PER_WEEK

    skeleton = {
        "topic": topic,
        "skill_level": skill_level,
        "total_weeks": duration_weeks,
        "total_days": total_days,
        "weeks": [],
    }

    for week_num in range(1, duration_weeks + 1):
        week = {
            "week_number": week_num,
            "theme": None,  # AI will fill
            "objectives": [],  # AI will fill
            "is_completed": False,
            "days": [],
        }

        for day_num in range(1, DAYS_PER_WEEK + 1):
            day = {
                "day_number": day_num,
                "title": None,  # AI will fill
                "tasks": None,  # AI will fill
                "content": None,  # AI will fill
                "is_completed": False,
                "is_locked": not (week_num == 1 and day_num == 1),  # Only day 1 week 1 unlocked
                "content_generated": False,
                "quiz_generated": False,
            }
            week["days"].append(day)

        skeleton["weeks"].append(week)

    return skeleton


class CourseGenerator:
    """
    Course generator that fills skeleton with AI-generated content.
    Uses vLLM client from services/llm/client.py.
    """

    def __init__(self, llm_client=None):
        """
        Initialize generator.

        Args:
            llm_client: Optional LLM client (uses default vLLM client)
        """
        self._llm = llm_client

    @property
    def llm(self):
        """Lazy-load LLM client."""
        if self._llm is None:
            # Import here to avoid circular imports
            from services.llm.client import generate, safe_json_generate

            # Async version for use in async methods
            async def _generate_json_async(prompt: str, max_tokens: int = 2000, use_fresh_client: bool = False) -> dict:
                """Async wrapper for safe_json_generate with optional fresh client."""
                custom_client = None
                if use_fresh_client:
                    # Create a fresh HTTP client for each call to prevent connection pool corruption
                    from services.llm.client import create_fresh_client
                    fresh_openai_client, http_client = create_fresh_client()
                    custom_client = fresh_openai_client
                
                result = await safe_json_generate(prompt, "course_generator", "course", custom_client=custom_client)
                
                # Close the HTTP client if we created one
                if use_fresh_client and http_client:
                    try:
                        await http_client.aclose()
                    except Exception:
                        pass  # Ignore cleanup errors
                
                return result

            self._llm = type('LLMClient', (), {
                'generate': generate,
                'safe_json_generate': safe_json_generate,
                '_generate_json': _generate_json_async,
            })()
        return self._llm

    async def _generate_week_theme(
        self,
        week_number: int,
        total_weeks: int,
        topic: str,
        skill_level: str,
        goals: List[str],
        description: str = None,  # Optional user-provided description
        previous_themes: List[str] = None,
        is_compact: bool = False,  # Flag for compact course generation
        original_duration: int = None,  # Original course duration for compact
    ) -> Tuple[str, List[str]]:
        """
        Generate theme and objectives for a week.

        Args:
            week_number: Current week number
            total_weeks: Total weeks in course
            topic: Course topic
            skill_level: Skill level
            goals: Course goals
            previous_themes: Themes of previous weeks

        Returns:
            Tuple of (theme, objectives_list)
        """
        from services.llm.client import safe_json_generate

        goals_str = "\n".join(f"- {g}" for g in goals) if goals else "General mastery"
        previous_str = ", ".join(previous_themes) if previous_themes else "None"
        
        # Add user description if provided (ensure it's a string)
        description_str = ""
        if description and isinstance(description, str) and description.strip():
            description_str = f"\n\nUSER REQUIREMENTS:\n{description.strip()}\n\nIMPORTANT: Tailor the course content to meet these specific user requirements."

        # Special prompt for compact course generation
        if is_compact and original_duration:
            prompt = f"""You are a curriculum designer. Generate a COMPACTED week theme for a {skill_level} {topic} course.

COMPACT COURSE MODE:
- Original course: {original_duration} weeks
- New compact course: {total_weeks} weeks
- Week {week_number} of {total_weeks} total weeks

IMPORTANT: This is a COMPRESSED course. You must:
1. Combine multiple concepts into fewer weeks while maintaining learning quality
2. Focus on ESSENTIAL and HIGH-IMPACT topics only
3. Remove redundant or nice-to-have content
4. Ensure each week covers more ground efficiently
5. Maintain logical progression and build complexity appropriately
6. Prioritize practical, hands-on learning over theory

Course goals:
{goals_str}
Previous weeks covered: {previous_str}
{description_str}

Return ONLY valid JSON:
{{
  "theme": "<THEME NAME ONLY - NO WEEK PREFIX>",
  "objectives": ["objective 1", "objective 2", "objective 3", "objective 4"]
}}

Example for compact Java course (4 weeks → 2 weeks):
- Week 1: "Java Fundamentals & OOP Mastery" (combines basics, variables, control flow, classes, objects, inheritance)
- Week 2: "Advanced Java & Real-World Applications" (combines collections, streams, exceptions, file I/O, projects)"""
        else:
            prompt = f"""You are a curriculum designer. Generate a week theme and objectives for a {skill_level} {topic} course.

Week {week_number} of {total_weeks} total weeks.
Course goals:
{goals_str}
Previous weeks covered: {previous_str}
{description_str}

Return ONLY valid JSON:
{{
  "theme": "<THEME NAME ONLY - NO WEEK PREFIX>",
  "objectives": ["objective 1", "objective 2", "objective 3"]
}}"""

        result = await safe_json_generate(
            prompt,
            system_type="course_generator",
            param_type="course",
            expected_keys=["theme", "objectives"],
        )

        # LOG RAW AI OUTPUT for debugging
        logger.info("="*70)
        logger.info("🤖 RAW AI OUTPUT: Week %d Theme Generation", week_number)
        logger.info("="*70)
        logger.info("RAW RESULT: %s", result)
        logger.info("="*70)

        if "error" in result:
            logger.warning("Week theme generation failed: %s", result.get("error"))
            return f"{topic} - Part {week_number}", []

        theme = result.get("theme", f"{topic} - Part {week_number}")
        objectives = result.get("objectives", [])
        
        # Strip "Week N:" prefix if AI still adds it
        import re
        theme = re.sub(r'^Week\s+\d+:\s*', '', theme).strip()

        return theme, objectives

    async def _generate_week_day_titles(
        self,
        week_number: int,
        week_theme: str,
        topic: str,
        skill_level: str,
        description: str = None,
        previous_week_titles: Dict[int, List[str]] = None,
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Generate titles and tasks for ALL 5 days in a week with ONE LLM call.

        Args:
            week_number: Week number (1-N)
            week_theme: Theme of the current week
            topic: Course topic
            skill_level: Skill level
            previous_week_titles: Dict of week_num -> [day titles] from previous weeks

        Returns:
            List of 5 tuples: [(title, tasks), ...]
        """
        from services.llm.client import safe_json_generate

        # Build context from previous weeks
        prev_context = ""
        if previous_week_titles:
            for wn, titles in sorted(previous_week_titles.items()):
                prev_context += f"Week {wn}: {', '.join(titles)}\n"

        # Add user description if provided
        description_str = ""
        if description and isinstance(description, str) and description.strip():
            description_str = f"\n\nUSER REQUIREMENTS:\n{description.strip()}\n\nIMPORTANT: Tailor the daily content to meet these specific user requirements."

        prompt = f"""You are a curriculum designer for a {skill_level} {topic} course.

Week {week_number} theme: {week_theme}
{f"Previously covered:\n{prev_context}" if prev_context else ""}{description_str}

Generate titles and tasks for ALL 5 days of this week.
Each day should build progressively on the previous one.

CRITICAL: You MUST return EXACTLY 5 days in the "days" array. No more, no less.

Return ONLY valid JSON with this exact structure:
{{
  "days": [
    {{
      "title": "Day 1: <specific topic>",
      "tasks": {{
        "concepts": ["concept 1", "concept 2"],
        "key_points": ["point 1", "point 2"],
        "practice": "what to practice"
      }}
    }},
    {{
      "title": "Day 2: <specific topic>",
      "tasks": {{
        "concepts": ["concept 1"],
        "key_points": ["point 1"],
        "practice": "what to practice"
      }}
    }},
    {{
      "title": "Day 3: <specific topic>",
      "tasks": {{
        "concepts": ["concept 1"],
        "key_points": ["point 1"],
        "practice": "what to practice"
      }}
    }},
    {{
      "title": "Day 4: <specific topic>",
      "tasks": {{
        "concepts": ["concept 1"],
        "key_points": ["point 1"],
        "practice": "what to practice"
      }}
    }},
    {{
      "title": "Day 5: <specific topic>",
      "tasks": {{
        "concepts": ["concept 1"],
        "key_points": ["point 1"],
        "practice": "what to practice"
      }}
    }}
  ]
}}"""

        result = await safe_json_generate(
            prompt,
            system_type="course_generator",
            param_type="course",
            expected_keys=["days"],
        )

        # LOG RAW AI OUTPUT for debugging
        logger.info("="*70)
        logger.info("🤖 RAW AI OUTPUT: Week %d Day Titles Generation", week_number)
        logger.info("="*70)
        logger.info("RAW RESULT: %s", result)
        logger.info("="*70)

        if "error" in result:
            logger.warning("Week day titles generation failed (week %d): %s", week_number, result.get("error"))
            # Return fallback for all 5 days
            return [(f"Day {i}: {week_theme}", {}) for i in range(1, 6)]

        days_data = result.get("days", [])
        if not days_data or len(days_data) < 5:
            logger.warning("Week day titles returned incomplete data (week %d): got %d days", week_number, len(days_data))
            # Fill missing days with fallback
            while len(days_data) < 5:
                days_data.append({"title": f"Day {len(days_data) + 1}: {week_theme}", "tasks": {}})

        # Extract exactly 5 days
        result_list = []
        for i, day_data in enumerate(days_data[:5]):
            title = day_data.get("title", f"Day {i + 1}")
            tasks = day_data.get("tasks", {})
            result_list.append((title, tasks))

        return result_list

    async def _generate_day_title_tasks(
        self,
        day_number: int,
        week_theme: str,
        topic: str,
        skill_level: str,
        description: str = None,  # Optional user-provided description
        previous_titles: List[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        DEPRECATED: Use _generate_week_day_titles instead.
        Kept for backward compatibility.
        """
        from services.llm.client import safe_json_generate

        previous_str = ", ".join(previous_titles) if previous_titles else "None"

        # Add user description if provided (ensure it's a string)
        description_str = ""
        if description and isinstance(description, str) and description.strip():
            description_str = f"\n\nUSER REQUIREMENTS:\n{description.strip()}\n\nIMPORTANT: Tailor the daily content to meet these specific user requirements."

        prompt = f"""You are a curriculum designer for a {skill_level} {topic} course.

Week theme: {week_theme}
Day {day_number} of 5 in this week.
Previously covered days: {previous_str}
{description_str}

Generate the day title and tasks.
Return ONLY valid JSON:
{{
  "title": "Day {day_number}: <specific topic>",
  "tasks": {{
    "concepts": ["concept 1", "concept 2"],
    "key_points": ["point 1", "point 2"],
    "practice": "what to practice"
  }}
}}"""

        result = await safe_json_generate(
            prompt,
            system_type="course_generator",
            param_type="course",
            expected_keys=["title", "tasks"],
        )

        if "error" in result:
            logger.warning("Day title/tasks generation failed: %s", result.get("error"))
            return f"Day {day_number}: {week_theme}", {}

        title = result.get("title", f"Day {day_number}")
        tasks = result.get("tasks", {})

        return title, tasks

    async def _generate_theory_content(
        self,
        day_title: str,
        week_theme: str,
        topic: str,
        skill_level: str,
        description: str = None,  # Optional user-provided description
        web_search_results: str = "",
    ) -> str:
        """
        Generate theory content for a day (no code).

        Args:
            day_title: Title of the day's lesson
            week_theme: Theme for the current week
            topic: Course topic
            skill_level: Skill level (beginner/intermediate/advanced)
            web_search_results: Optional formatted web search results for enhancement

        Returns:
            Markdown theory content (comprehensive, 4000+ tokens)
        """
        from services.llm.client import generate

        # Build web search context if available
        web_context = ""
        if web_search_results:
            web_context = f"""

{web_search_results}

INTEGRATE WEB RESEARCH:
- Use the above research resources to enhance your explanation
- Include up-to-date information, best practices, and real-world examples
- Reference current industry standards where relevant
- If web resources mention specific tools/versions, incorporate them appropriately
"""

        # Add user description if provided (ensure it's a string)
        description_str = ""
        if description and isinstance(description, str) and description.strip():
            description_str = f"""

USER REQUIREMENTS:
{description.strip()}

IMPORTANT: Tailor your explanation to address these specific user requirements. Focus on the aspects mentioned by the user and provide relevant examples and use cases that match their needs.
"""

        prompt = f"""Generate a COMPREHENSIVE theory lesson for "{day_title}" in a {skill_level} {topic} course.

Week context: {week_theme}
{web_context}
{description_str}
Requirements:
1. Provide DETAILED explanations (aim for 2000+ words)
2. Explain concepts thoroughly with multiple analogies and real-world examples
3. Use simple language appropriate for {skill_level} learners
4. Break down complex topics into digestible sections
5. Include:
   - Introduction to the topic (what it is, why it matters)
   - Core concepts explained in detail
   - How it works (step-by-step breakdown)
   - Real-world applications and use cases
   - Common misconceptions and how to avoid them
   - Best practices and tips
   - Summary of key points
6. Use markdown formatting (headers, subheaders, lists, bold for key terms)
7. DO NOT include any code examples or code blocks
8. Focus on deep conceptual understanding

Structure your response like this:
## Introduction
[Comprehensive introduction - 300+ words]

## What is [Topic]?
[Detailed explanation - 400+ words]

## How It Works
[Step-by-step breakdown - 500+ words]

## Key Concepts
[Multiple sub-sections with detailed explanations - 600+ words]

## Real-World Applications
[Practical examples and use cases - 300+ words]

## Common Misconceptions
[Address common misunderstandings - 200+ words]

## Best Practices
[Tips and recommendations - 200+ words]

## Summary
[Recap of key points - 200+ words]

Return comprehensive markdown text. MINIMUM LENGTH: 3000 characters (approximately 500+ words)."""

        # Add validation and retry logic for minimum length
        max_retries = 3
        min_length = 3000  # Minimum 3000 characters
        
        for attempt in range(max_retries):
            content = await generate(
                prompt,
                system_type="tutor",
                param_type="course",  # Use 'course' param type for longer content (3000 tokens)
            )

            # Validate that content meets minimum length requirement
            if content and len(content.strip()) >= min_length:
                logger.info("Theory generation successful (%d chars, attempt %d/%d)", len(content), attempt + 1, max_retries)
                return content
            elif content and len(content.strip()) > 0:
                logger.warning("Theory generation too short (attempt %d/%d): %d chars (minimum: %d)", 
                             attempt + 1, max_retries, len(content), min_length)
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 + attempt * 2)  # 2s, 4s delay
                    # Add emphasis on length requirement for retry
                    prompt = prompt + f"\n\nIMPORTANT: Your previous attempt was only {len(content)} characters. Please provide a MUCH MORE DETAILED explanation with at least {min_length} characters."
            else:
                logger.warning("Theory generation returned empty content (attempt %d/%d)", attempt + 1, max_retries)
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 + attempt * 2)

        # If all retries failed, return what we have or a placeholder
        if content and len(content.strip()) > 0:
            logger.error("Theory generation failed after %d retries, returning partial content (%d chars)", max_retries, len(content))
            return content
        else:
            logger.error("Theory generation failed after %d retries, returning placeholder", max_retries)
            return f"## {day_title}\n\nTheory content could not be generated. Please refer to external resources for learning about this topic."

    async def _generate_code_content(
        self,
        day_title: str,
        week_theme: str,
        topic: str,
        skill_level: str,
    ) -> str:
        """
        Generate code examples and explanations for a day.

        Returns:
            Markdown code content with examples
        """
        from services.llm.client import generate

        prompt = f"""Generate code examples for "{day_title}" in a {skill_level} {topic} course.

Week context: {week_theme}

CRITICAL FORMATTING RULES:
1. ONLY put actual code inside ```python``` code blocks
2. All headings, explanations, examples, output, common mistakes, and practice exercises must be in NORMAL TEXT (outside code blocks)
3. Use markdown headings (##) for section titles
4. Use **bold** text for emphasis on key terms
5. Format like this example:

## Example 1: Basic Variable Assignment

Assign integer values to variables and print them.

```python
age = 25
height = 5.9
print("Age:", age)
print("Height:", height)
```

**Explanation:**
- `age = 25`: Assigns the integer value `25` to the variable `age`.
- `height = 5.9`: Assigns the floating-point value `5.9` to the variable `height`.

**Output:**
```
Age: 25
Height: 5.9
```

**Common Mistakes:**
- Forgetting to assign a value before using a variable.

Requirements:
1. Provide 2-3 complete, runnable code examples
2. Explain each example step by step in NORMAL TEXT
3. Show expected output in NORMAL TEXT
4. Point out common mistakes in NORMAL TEXT
5. Include a practice exercise at the end in NORMAL TEXT
6. ONLY code goes in ```python``` blocks, everything else is normal text

Return markdown with properly formatted code blocks."""

        # Add validation and retry logic for code generation
        max_retries = 3
        for attempt in range(max_retries):
            content = await generate(
                prompt,
                system_type="code_teacher",
                param_type="code",
            )

            # Validate that content was actually generated
            if content and content.strip() and len(content.strip()) > 50:
                logger.info("Code generation successful (%d chars, attempt %d/%d)", len(content), attempt + 1, max_retries)
                return content
            else:
                logger.warning("Code generation returned empty/short content (attempt %d/%d): %d chars", 
                             attempt + 1, max_retries, len(content) if content else 0)
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 + attempt * 2)  # 2s, 4s delay

        # If all retries failed, return a placeholder
        if content:
            logger.error("Code generation failed after %d retries, returning partial content", max_retries)
            return content
        else:
            logger.error("Code generation failed after %d retries, returning empty placeholder", max_retries)
            return f"## Code Examples for {day_title}\n\nCode examples could not be generated. Please refer to the theory content for conceptual understanding."

    async def _generate_quiz_questions(
        self,
        day_title: str,
        topic: str,
        skill_level: str,
    ) -> Dict[str, Any]:
        """
        Generate 3 MCQ quiz questions for a day.

        Returns:
            Dict with quizzes list
        """
        from services.llm.client import safe_json_generate

        prompt = f"""Generate 3 MCQ quizzes for "{day_title}" in a {skill_level} {topic} course.

IMPORTANT: Return ONLY valid JSON. No text before or after the JSON.
Escape all quotes inside strings with backslash (\\").
Do not include newlines inside string values.

Return ONLY this exact JSON structure:
{{
  "quizzes": [
    {{
      "question_number": 1,
      "question_text": "Question here?",
      "options": {{
        "a": "Option A",
        "b": "Option B",
        "c": "Option C",
        "d": "Option D"
      }},
      "correct_answer": "a",
      "explanation": "Explanation here..."
    }},
    {{
      "question_number": 2,
      "question_text": "Question here?",
      "options": {{
        "a": "Option A",
        "b": "Option B",
        "c": "Option C",
        "d": "Option D"
      }},
      "correct_answer": "b",
      "explanation": "Explanation here..."
    }},
    {{
      "question_number": 3,
      "question_text": "Question here?",
      "options": {{
        "a": "Option A",
        "b": "Option B",
        "c": "Option C",
        "d": "Option D"
      }},
      "correct_answer": "c",
      "explanation": "Explanation here..."
    }}
  ]
}}"""

        result = await safe_json_generate(
            prompt,
            system_type="quiz_generator",
            param_type="quiz",
            expected_keys=["quizzes"],
            max_retries=5,  # More retries for quiz generation
        )

        if "error" in result or "quizzes" not in result:
            logger.warning("Quiz generation failed for %s: %s", day_title, result.get("error", "No quizzes key"))
            return {"quizzes": [], "raw": "{}"}

        return result

    async def fill_week(
        self,
        week_data: Dict[str, Any],
        week_number: int,
        total_weeks: int,
        topic: str,
        skill_level: str,
        goals: List[str],
        description: str = None,  # Optional user-provided description
        course_id: str = None,
    ) -> Dict[str, Any]:
        """
        Async: Fill a single week with theme, objectives, and day content.
        All steps run sequentially within this week task.

        Steps:
        1. Generate week theme + objectives (1 LLM call)
        2. For each of 5 days, generate:
           - Day title + tasks (1 LLM call)
           - Theory content (1 LLM call)
           - Code content (1 LLM call)
           - Quiz questions (1 LLM call)
           = 4 LLM calls per day × 5 days = 20 LLM calls

        Args:
            week_data: Empty week skeleton
            week_number: Week number
            total_weeks: Total weeks
            topic: Course topic
            skill_level: Skill level
            goals: Course goals
            course_id: Course ID for DB updates

        Returns:
            Filled week data
        """
        # Step 1: Generate week theme and objectives
        theme, objectives = await self._generate_week_theme(
            week_number, total_weeks, topic, skill_level, goals, description, []
        )
        week_data["theme"] = theme
        week_data["objectives"] = objectives

        # Step 2: For each day, generate title + 3 content types
        previous_titles = []
        for day in week_data["days"]:
            day_num = day["day_number"]
            logger.info("Generating content for Week %d Day %d", week_number, day_num)

            # 2a: Generate day title and tasks
            title, tasks = await self._generate_day_title_tasks(
                day_num, theme, topic, skill_level, description, previous_titles
            )
            day["title"] = title
            day["tasks"] = tasks
            previous_titles.append(title)

            # 2b: Generate theory content (no code)
            theory = await self._generate_theory_content(title, theme, topic, skill_level, description)
            day["theory_content"] = theory
            day["theory_generated"] = True

            # 2c: Generate code content (examples + explanations)
            code = await self._generate_code_content(title, theme, topic, skill_level)
            day["code_content"] = code
            day["code_generated"] = True

            # 2d: Generate quiz questions (3 MCQs)
            quiz_result = await self._generate_quiz_questions(title, topic, skill_level)
            day["quiz_raw"] = quiz_result.get("raw", "{}") if "raw" in quiz_result else "{}"
            day["quizzes"] = quiz_result.get("quizzes", [])
            day["quiz_generated"] = len(quiz_result.get("quizzes", [])) > 0

        # Save to DB immediately if course_id provided
        if course_id:
            await self._save_week_to_db(course_id, week_data)

        return week_data

    async def _save_week_to_db(self, course_id: str, week_data: Dict[str, Any]):
        """
        Save filled week data to database immediately.
        Called as each parallel week task completes.
        Also saves quiz questions to quiz_questions table.
        """
        from apps.courses.models import Course
        from apps.quizzes.models import QuizQuestion

        try:
            course = Course.objects.get(id=course_id)
            week = course.weeks.get(week_number=week_data["week_number"])

            # Update week
            week.theme = week_data["theme"]
            week.objectives = week_data["objectives"]
            week.save(update_fields=["theme", "objectives"])

            # Update days
            for day_data in week_data["days"]:
                day = week.days.get(day_number=day_data["day_number"])
                day.title = day_data["title"]
                day.tasks = day_data["tasks"]
                # New content fields
                day.theory_content = day_data.get("theory_content", "")
                day.code_content = day_data.get("code_content", "")
                day.quiz_raw = day_data.get("quiz_raw", "{}")
                day.theory_generated = day_data.get("theory_generated", False)
                day.code_generated = day_data.get("code_generated", False)
                day.quiz_generated = day_data.get("quiz_generated", False)
                day.save(update_fields=[
                    "title", "tasks",
                    "theory_content", "code_content", "quiz_raw",
                    "theory_generated", "code_generated", "quiz_generated",
                ])

                # Save quiz questions to quiz_questions table
                quizzes = day_data.get("quizzes", [])
                if quizzes:
                    # Clear existing questions for this day
                    QuizQuestion.objects.filter(day_plan=day).delete()

                    for quiz in quizzes:
                        QuizQuestion.objects.create(
                            day_plan=day,
                            course=course,
                            question_number=quiz.get("question_number", 1),
                            question_text=quiz.get("question_text", ""),
                            options=quiz.get("options", {}),
                            correct_answer=quiz.get("correct_answer", "a"),
                            explanation=quiz.get("explanation", ""),
                        )

            logger.info("Saved week %d to DB for course %s", week_data["week_number"], course_id)

        except Exception as exc:
            logger.exception("Failed to save week %d to DB: %s", week_data["week_number"], exc)

    async def fill_skeleton_with_ai_async(
        self,
        skeleton: Dict[str, Any],
        skill_level: str,
        goals: List[str],
        course_id: str = None,
    ) -> Dict[str, Any]:
        """
        Async: Fill skeleton with AI-generated content.
        All weeks run in PARALLEL using asyncio.gather().

        Args:
            skeleton: Empty course skeleton
            skill_level: Skill level
            goals: Course goals
            course_id: Course ID for immediate DB saves

        Returns:
            Filled skeleton
        """
        topic = skeleton["topic"]
        total_weeks = skeleton["total_weeks"]

        # Create parallel tasks for all weeks
        tasks = [
            self.fill_week(
                week_data=week_data,
                week_number=week_data["week_number"],
                total_weeks=total_weeks,
                topic=topic,
                skill_level=skill_level,
                goals=goals,
                course_id=course_id,
            )
            for week_data in skeleton["weeks"]
        ]

        # Run all week tasks in parallel
        logger.info("Starting parallel generation for %d weeks", total_weeks)
        filled_weeks = await asyncio.gather(*tasks)

        # Update skeleton with filled weeks
        skeleton["weeks"] = list(filled_weeks)

        return skeleton

    def fill_skeleton_with_ai(
        self,
        skeleton: Dict[str, Any],
        skill_level: str,
        goals: List[str],
    ) -> Dict[str, Any]:
        """
        Fill skeleton with AI-generated content.
        Processes weeks sequentially to maintain context.

        Args:
            skeleton: Empty course skeleton
            skill_level: Skill level
            goals: Course goals

        Returns:
            Filled skeleton
        """
        topic = skeleton["topic"]
        total_weeks = skeleton["total_weeks"]
        previous_themes = []

        for week_data in skeleton["weeks"]:
            week_num = week_data["week_number"]
            logger.info("Filling week %d/%d for course: %s", week_num, total_weeks, topic)

            filled_week = self.fill_week_async(
                week_data, week_num, total_weeks, topic, skill_level, goals, previous_themes
            )

            skeleton["weeks"][week_num - 1] = filled_week
            previous_themes.append(filled_week["theme"])

        return skeleton

    def generate_day_content_for_day(
        self,
        day_data: Dict[str, Any],
        week_theme: str,
        topic: str,
        skill_level: str,
        goals: List[str],
    ) -> str:
        """
        Generate full content for a single day.

        Args:
            day_data: Day data with title
            week_theme: Week theme
            topic: Course topic
            skill_level: Skill level
            goals: Course goals

        Returns:
            Generated content string
        """
        return self._generate_day_content(
            day_data["title"], week_theme, topic, skill_level, goals
        )

    async def _generate_single_batch(
        self,
        course,
        week,
        week_number: int,
        batch_idx: int,
        batch_size: int,
        difficulties: list,
        day_focus: list,
        day_titles: list,
        existing_questions: list,
    ) -> dict:
        """
        Generate a single batch of questions independently (for parallel execution).
        
        Args:
            course: Course object
            week: WeekPlan object
            week_number: Week number
            batch_idx: Batch index (0, 1, 2)
            batch_size: Number of questions to generate
            difficulties: List of difficulty levels
            day_focus: List of day numbers to focus on
            day_titles: List of day titles
            existing_questions: List of previously generated questions (can be empty for parallel)
            
        Returns:
            Dict with batch_questions key
        """
        max_retries = 3  # Reduced from 5 for faster execution
        
        for retry in range(max_retries):
            try:
                # Build prompt - in parallel mode, existing_questions will be empty
                existing_questions_text = ""
                if existing_questions:
                    existing_questions_text = "\n\nPREVIOUSLY GENERATED QUESTIONS (DO NOT REPEAT THESE):\n"
                    for i, q in enumerate(existing_questions, 1):
                        existing_questions_text += f"{i}. {q.get('question_text', '')[:150]}\n"

                day_focus_text = ", ".join([f"Day {d}: {day_titles[d-1]}" for d in day_focus])

                prompt = f"""You are an expert {course.topic} instructor.

Week {week_number} theme: {week.theme or 'Course Content'}
This week covered these topics:
Day 1: {day_titles[0]}
Day 2: {day_titles[1]}
Day 3: {day_titles[2]}
Day 4: {day_titles[3]}
Day 5: {day_titles[4]}

CURRENT BATCH FOCUS: {day_focus_text}

Generate {batch_size} MCQ questions.
Difficulties for this batch: {', '.join(difficulties)}
{existing_questions_text}

IMPORTANT:
- Each question MUST be completely unique
- Do NOT repeat the same concept or question style
- Cover different topics from the focus days listed above
- Return ONLY valid JSON. No markdown. No extra text.
- Keep explanations brief (max 20 words)

JSON format:
{{"questions": [{{"question_number": 1, "question_text": "Question?", "difficulty": "{difficulties[0]}", "day_reference": {day_focus[0]}, "options": {{"a": "Option A", "b": "Option B", "c": "Option C", "d": "Option D"}}, "correct_answer": "a", "explanation": "Brief explanation"}}]}}"""

                # Use fresh client for each parallel call to avoid connection pool issues
                result = await self.llm._generate_json(prompt, max_tokens=3000, use_fresh_client=True)

                # LOG RAW AI OUTPUT
                logger.info("="*70)
                logger.info("🤖 RAW AI OUTPUT: Weekly Test Week %d Batch %d", week_number, batch_idx + 1)
                logger.info("="*70)
                logger.info("RAW RESULT: %s", result)
                logger.info("="*70)

                if "error" in result or "questions" not in result:
                    logger.warning("Batch %d generation failed (attempt %d/%d): %s",
                                 batch_idx + 1, retry + 1, max_retries, result.get("error"))
                    if retry < max_retries - 1:
                        await asyncio.sleep(1 + retry)  # Shorter delay: 1s, 2s
                        continue
                    return {"batch_questions": [], "error": result.get("error")}

                batch_questions = result.get("questions", [])

                # Validate batch questions
                if not batch_questions or len(batch_questions) == 0:
                    logger.warning("Batch %d returned empty questions (attempt %d/%d)",
                                 batch_idx + 1, retry + 1, max_retries)
                    if retry < max_retries - 1:
                        await asyncio.sleep(1 + retry)
                        continue
                    return {"batch_questions": [], "error": "Empty questions"}

                # LOG: Print batch questions
                logger.info("="*60)
                logger.info("🤖 BATCH %d: Generated %d unique questions for Week %d",
                           batch_idx + 1, len(batch_questions), week_number)
                logger.info("="*60)
                for i, q in enumerate(batch_questions, 1):
                    logger.info(f"  Q{i}: [{q.get('difficulty', '?')}] {q.get('question_text', 'N/A')[:100]}...")
                    logger.info(f"      Day ref: {q.get('day_reference', '?')}")
                logger.info("="*60)

                return {"batch_questions": batch_questions}

            except Exception as batch_exc:
                logger.warning("Batch %d generation error (attempt %d/%d): %s",
                             batch_idx + 1, retry + 1, max_retries, batch_exc)
                if retry < max_retries - 1:
                    await asyncio.sleep(1 + retry)
                continue
        
        return {"batch_questions": [], "error": "Max retries exceeded"}

    async def generate_weekly_test(
        self,
        course_id: str,
        week_number: int,
    ) -> Dict[str, Any]:
        """
        Generate a weekly test covering all 5 days of a week.
        Uses PARALLEL batch generation for speed (asyncio.gather).

        Args:
            course_id: Course ID
            week_number: Week number

        Returns:
            Dict with test data
        """
        from asgiref.sync import sync_to_async
        from apps.courses.models import Course, WeekPlan, WeeklyTest

        course = await sync_to_async(Course.objects.get)(id=course_id)
        week = await sync_to_async(WeekPlan.objects.get)(course=course, week_number=week_number)

        # Get all 5 days content
        days = await sync_to_async(list)(week.days.all().order_by("day_number"))
        if len(days) != 5:
            logger.warning("Week %d does not have 5 days", week_number)
            return {"error": "Week incomplete"}

        # Build context from all days
        day_titles = [d.title or f"Day {d.day_number}" for d in days]

        # Define batch configurations
        batch_configs = [
            {
                "batch_idx": 0,
                "batch_size": 4,
                "difficulties": ["easy", "easy", "medium", "medium"],
                "day_focus": [1, 2, 3],
                "existing_questions": [],  # Empty for parallel execution
            },
            {
                "batch_idx": 1,
                "batch_size": 4,
                "difficulties": ["easy", "medium", "medium", "hard"],
                "day_focus": [3, 4, 5],
                "existing_questions": [],  # Empty for parallel execution
            },
            {
                "batch_idx": 2,
                "batch_size": 2,
                "difficulties": ["hard", "medium"],
                "day_focus": [1, 2, 4, 5],
                "existing_questions": [],  # Empty for parallel execution
            },
        ]

        logger.info("🚀 Starting PARALLEL batch generation for Week %d (%d batches)", 
                   week_number, len(batch_configs))

        # Execute all batches CONCURRENTLY using asyncio.gather
        # Each batch gets its own fresh HTTP client to avoid connection pool issues
        batch_results = await asyncio.gather(
            *[
                self._generate_single_batch(
                    course=course,
                    week=week,
                    week_number=week_number,
                    batch_idx=config["batch_idx"],
                    batch_size=config["batch_size"],
                    difficulties=config["difficulties"],
                    day_focus=config["day_focus"],
                    day_titles=day_titles,
                    existing_questions=config["existing_questions"],
                )
                for config in batch_configs
            ],
            return_exceptions=True
        )

        # Collect all questions from successful batches
        all_questions = []
        successful_batches = 0
        failed_batches = 0

        for batch_idx, result in enumerate(batch_results):
            if isinstance(result, Exception):
                logger.warning("⚠️ Batch %d raised exception: %s", batch_idx + 1, result)
                failed_batches += 1
                continue
            
            if result.get("error"):
                logger.warning("⚠️ Batch %d failed: %s", batch_idx + 1, result.get("error"))
                failed_batches += 1
                continue
            
            batch_questions = result.get("batch_questions", [])
            if batch_questions:
                all_questions.extend(batch_questions)
                successful_batches += 1
                logger.info("✅ Batch %d complete: %d questions", batch_idx + 1, len(batch_questions))
            else:
                failed_batches += 1

        logger.info("📊 Parallel generation complete: %d/%d batches successful, %d total questions",
                   successful_batches, len(batch_configs), len(all_questions))

        # Assign question numbers sequentially
        question_number = 1
        for q in all_questions:
            q["question_number"] = question_number
            question_number += 1

        # Save whatever questions we managed to generate
        if len(all_questions) == 0:
            return {"error": "Failed to generate any questions", "questions": []}

        # Save to database
        @sync_to_async
        def save_test():
            test, created = WeeklyTest.objects.update_or_create(
                course=course,
                week_number=week_number,
                defaults={
                    "questions": all_questions,
                    "total_questions": len(all_questions),
                }
            )
            week.test_generated = True
            week.save(update_fields=["test_generated"])
            return test

        test = await save_test()

        logger.info("="*60)
        logger.info("✅ WEEKLY TEST COMPLETE: Week %d - %d unique MCQ questions",
                   week_number, len(all_questions))
        logger.info("="*60)

        return {
            "success": True,
            "test_id": str(test.id),
            "week_number": week_number,
            "total_questions": len(all_questions),
        }

    async def generate_coding_test(
        self,
        course_id: str,
        week_number: int,
    ) -> Dict[str, Any]:
        """
        Generate a weekly coding test with 2 coding problems.
        Problems are based on the week's content and difficulty matches course level.

        Args:
            course_id: Course ID
            week_number: Week number

        Returns:
            Dict with test data
        """
        from asgiref.sync import sync_to_async
        from apps.courses.models import Course, WeekPlan, CodingTest

        max_retries = 3
        
        for retry in range(max_retries):
            try:
                course = await sync_to_async(Course.objects.get)(id=course_id)
                week = await sync_to_async(WeekPlan.objects.get)(course=course, week_number=week_number)

                # Get all 5 days content
                days = await sync_to_async(list)(week.days.all().order_by("day_number"))
                day_titles = [d.title or f"Day {d.day_number}" for d in days]

                # Determine difficulty based on course level
                difficulty_map = {
                    "beginner": ["easy", "easy"],
                    "intermediate": ["easy", "medium"],
                    "advanced": ["medium", "hard"],
                }
                difficulties = difficulty_map.get(course.level, ["easy", "medium"])

                prompt = f"""You are an expert {course.topic} instructor creating coding challenges.

Week {week_number} theme: {week.theme or 'Course Content'}
Topics: {', '.join(day_titles)}
Level: {course.level}

Generate 2 coding problems. Difficulty: {difficulties[0]}, {difficulties[1]}.

IMPORTANT: Return ONLY valid JSON. No markdown. No extra text. Keep descriptions concise.

JSON format:
{{"coding_problems": [{{"problem_number": 1, "title": "Title", "description": "Brief description", "difficulty": "{difficulties[0]}", "starter_code": "def solve():", "test_cases": [{{"input": "input", "expected_output": "output", "is_hidden": false}}], "hints": ["Hint 1"], "solution": "def solve(): pass", "time_limit_seconds": 30, "memory_limit_mb": 256}}]}}"""

                result = await self.llm._generate_json(prompt, max_tokens=5000)

                if "error" in result or "coding_problems" not in result:
                    logger.warning("Coding test generation failed (attempt %d/%d): %s", 
                                  retry + 1, max_retries, result.get("error"))
                    if retry < max_retries - 1:
                        await asyncio.sleep(3)
                        continue
                    return {"error": "Generation failed", "problems": []}

                problems = result.get("coding_problems", [])

                # Accept 1-2 problems (don't retry if only 1 generated)
                if len(problems) < 1:
                    logger.warning("Coding test generated 0 problems - retrying")
                    if retry < max_retries - 1:
                        await asyncio.sleep(2)
                        continue
                    return {"error": "Generation failed - no problems generated", "problems": []}
                
                if len(problems) < 2:
                    logger.warning("Coding test only generated %d problem(s) instead of 2 - accepting partial result", len(problems))

                # Save to database
                @sync_to_async
                def save_test():
                    test, created = CodingTest.objects.update_or_create(
                        course=course,
                        week_number=week_number,
                        defaults={
                            "problems": problems,
                            "total_problems": len(problems),
                        }
                    )
                    return test

                test = await save_test()

                logger.info("Generated coding test for Week %d in course %s (%d problems)", 
                           week_number, course_id, len(problems))

                return {
                    "success": True,
                    "test_id": str(test.id),
                    "week_number": week_number,
                    "total_problems": len(problems),
                }

            except Exception as exc:
                logger.exception("Error generating coding test (attempt %d/%d): %s", 
                               retry + 1, max_retries, exc)
                if retry < max_retries - 1:
                    await asyncio.sleep(3)
                else:
                    return {"error": str(exc)}
        
        return {"error": "Max retries exceeded"}


def generate_full_course(
    course_name: str,
    duration_input: str,
    level: str,
    user_id: str,
    hours_per_day: int = 2,
    goals: List[str] = None,
) -> Dict[str, Any]:
    """
    Main orchestration function for course generation.
    Creates skeleton, saves to DB, triggers async content generation.

    Args:
        course_name: User-defined course name/title
        duration_input: Duration string ("1 month", "2 weeks", etc.)
        level: Course level (beginner/intermediate/advanced)
        user_id: User ID
        hours_per_day: Hours per day
        goals: Learning goals (optional)

    Returns:
        Dict with course_id and skeleton
    """
    from apps.courses.models import Course, WeekPlan, DayPlan

    if goals is None:
        goals = []

    # Parse duration
    duration_weeks = parse_duration(duration_input)

    # Detect topic from course_name using LLM (skip for obvious names)
    topic = _detect_topic_from_name(course_name, level)

    # Build skeleton
    skeleton = build_skeleton(duration_weeks, topic, level)

    # Create course record with new fields
    course = Course.objects.create(
        user_id=user_id,
        course_name=course_name,
        topic=topic,
        level=level,
        duration_weeks=duration_weeks,
        hours_per_day=hours_per_day,
        goals=goals,
        status="generating",
        generation_status="pending",
        generation_progress=0,
    )

    # Create week and day records from skeleton
    total_days = duration_weeks * DAYS_PER_WEEK
    for week_data in skeleton["weeks"]:
        week = WeekPlan.objects.create(
            course=course,
            week_number=week_data["week_number"],
            theme=None,  # Will be filled by AI
            objectives=[],
        )

        for day_data in week_data["days"]:
            DayPlan.objects.create(
                week_plan=week,
                day_number=day_data["day_number"],
                title=None,  # Will be filled by AI
                tasks={},
                is_locked=day_data["is_locked"],
                quiz_generated=False,
            )

    # Trigger async generation via Celery
    from apps.courses.tasks import generate_course_content_task
    generate_course_content_task.delay(
        str(course.id),
        course_name,
        duration_weeks,
        level,
        goals,
    )

    # Return skeleton with course_id
    skeleton["course_id"] = str(course.id)
    skeleton["status"] = "generating"

    return {
        "course_id": str(course.id),
        "course_name": course_name,
        "topic": topic,
        "level": level,
        "total_weeks": duration_weeks,
        "total_days": total_days,
        "status": "generating",
        "skeleton": skeleton,
    }


def _detect_topic_from_name(course_name: str, level: str) -> str:
    """
    Use LLM to detect/extract the main topic from course name.
    Returns a clean topic string for course generation.
    Skips LLM call for obvious course names.
    """
    # Skip LLM for obvious course names - just clean them up
    obvious_keywords = [
        "python", "java", "javascript", "typescript", "sql", "html", "css", "react",
        "angular", "vue", "node", "django", "flask", "fastapi", "spring", "docker",
        "kubernetes", "aws", "azure", "gcp", "machine learning", "deep learning",
        "data science", "ai", "artificial intelligence", "cybersecurity", "security",
        "devops", "git", "linux", "mongodb", "postgresql", "mysql", "redis",
        "graphql", "rest api", "microservices", "agile", "scrum", "testing",
    ]
    
    course_lower = course_name.lower()
    for keyword in obvious_keywords:
        if keyword in course_lower:
            # Extract topic from course name directly
            # Capitalize first letter of each word
            return ' '.join(word.capitalize() for word in course_name.split()[:4])
    
    # Only use LLM for ambiguous course names
    from services.llm.qwen_client import QwenClient

    try:
        llm = QwenClient()
        prompt = f"""Analyze this course name and extract the main subject/topic.
Course name: "{course_name}"
Level: {level}

Return ONLY the main topic as a short phrase (2-4 words).
Examples:
- "Python for Data Science" → "Python Data Science"
- "Learn React from scratch" → "React Web Development"
- "Machine Learning basics" → "Machine Learning"
- "Advanced JavaScript patterns" → "JavaScript Design Patterns"

Topic:"""

        topic = llm.generate(prompt, max_tokens=50).strip()
        # Clean up the response
        topic = topic.replace('"', '').replace("'", '').strip()
        if topic.startswith("[Error:"):
            raise ValueError(topic)
        if len(topic) > 100:
            topic = topic[:100]
        return topic or course_name

    except Exception as exc:
        logger.warning("Could not detect topic from name: %s, using name as topic", exc)
        return course_name
