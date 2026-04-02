"""
Chat API endpoints for course management.
Simple keyword-based command handling without LLM intent classification.
"""
import logging
import re as regex_module
import json as json_module
from asgiref.sync import async_to_sync
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses.models import Course, WeekPlan, DayPlan
from apps.courses.serializers import CourseListSerializer

logger = logging.getLogger(__name__)


def _ok(data, status_code=status.HTTP_200_OK):
    return Response({"success": True, "data": data, "error": None}, status=status_code)


def _err(msg, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"success": False, "data": None, "error": msg}, status=status_code)


def _extract_course_name(message: str) -> str:
    """
    Extract course name from message.
    
    Smart extraction that stops at duration keywords (4 weeks, 2 days, etc.)
    and level keywords (beginner, intermediate, advanced).
    
    Examples:
    - "create java course 4 weeks intermediate" → "java"
    - "create a Python course for beginners 12 weeks" → "Python"
    - "create machine learning with Python 8 weeks advanced" → "machine learning with Python"
    - "create react native mobile app development course" → "react native mobile app development"
    """
    message_lower = message.lower()
    
    # Duration patterns to stop at (e.g., "4 weeks", "12 week", "2 wk")
    duration_patterns = [
        r'\d+\s*weeks?',
        r'\d+\s*days?',
        r'\d+\s*months?',
        r'\d+\s*hours?',
        r'for\s+\d+',
    ]
    
    # Level keywords to stop at
    level_keywords = [
        'beginner', 'intermediate', 'advanced', 'basic', 'starter',
        'mid-level', 'senior', 'junior', 'expert',
        'level', 'for beginners', 'for intermediate', 'for advanced'
    ]
    
    # Other keywords that indicate end of course name
    stop_keywords = [
        'with duration', 'duration', 'starting from', 'start from',
        'focused on', 'focus on', 'about', 'for learning'
    ]
    
    # Combine all stop patterns
    all_stop_patterns = duration_patterns.copy()
    all_stop_patterns.extend([regex_module.escape(kw) for kw in level_keywords])
    all_stop_patterns.extend([regex_module.escape(kw) for kw in stop_keywords])
    
    # Create a combined pattern to find the earliest stop point
    combined_stop_pattern = r'(' + '|'.join(all_stop_patterns) + r')'
    
    # First, find where the course name should end
    stop_match = regex_module.search(combined_stop_pattern, message_lower)
    end_position = len(message_lower)

    if stop_match:
        end_position = stop_match.start()

    # Now extract the course name based on command type
    command_patterns = [
        # Delete patterns
        r'(?:delete|remove|drop)\s+(?:the\s+)?(?:course\s+(?:on|about|in)?\s*)?',
        # Create patterns
        r'(?:create|make|start|begin)\s+(?:a\s+)?(?:course\s+(?:on|about|in)?\s*)?',
        # Show/view patterns
        r'(?:show|view|display)\s+(?:the\s+)?(?:course\s+(?:on|about|in)?\s*)?',
    ]

    start_position = 0
    for pattern in command_patterns:
        match = regex_module.search(pattern, message_lower)
        if match:
            start_position = match.end()
            break
    
    # If start is after our end position, something went wrong
    if start_position >= end_position:
        return ""
    
    # Extract the course name between start and end positions
    course_name = message[start_position:end_position].strip()
    
    # Remove trailing "course" if present
    course_name = regex_module.sub(r'\s+course\s*$', '', course_name, flags=regex_module.IGNORECASE)
    
    # Clean up extra whitespace
    course_name = ' '.join(course_name.split())
    
    # Capitalize appropriately (title case for most words)
    if course_name:
        # Keep small words lowercase unless they're first
        small_words = {'a', 'an', 'the', 'in', 'on', 'at', 'to', 'for', 'with', 'or', 'and'}
        words = course_name.split()
        capitalized = []
        for i, word in enumerate(words):
            if i == 0 or word.lower() not in small_words:
                capitalized.append(word.capitalize())
            else:
                capitalized.append(word.lower())
        course_name = ' '.join(capitalized)
    
    return course_name


def _extract_duration(message: str) -> int | None:
    """Extract duration in weeks from message."""
    patterns = [
        r'(\d+)\s*(?:week|wk)',
        r'for\s+(\d+)\s*(?:week|wk)',
        r'(\d+)\s*weeks?',
    ]
    for pattern in patterns:
        match = regex_module.search(pattern, message, regex_module.IGNORECASE)
        if match:
            return int(match.group(1))
    return None  # Return None if not found


def _extract_level(message: str) -> str | None:
    """Extract skill level from message."""
    message_lower = message.lower()
    if 'advanced' in message_lower:
        return 'advanced'
    elif 'intermediate' in message_lower or 'mid' in message_lower:
        return 'intermediate'
    elif 'beginner' in message_lower or 'basic' in message_lower or 'starter' in message_lower:
        return 'beginner'
    return None  # Return None if not found


def _extract_description(message: str) -> str | None:
    """Extract description/goals from message."""
    # Look for "for X", "to learn X", "about X" patterns
    patterns = [
        r'for\s+(.+?)(?:\s*$|\s+with|\s+\d+)',
        r'to\s+learn\s+(.+?)(?:\s*$)',
        r'about\s+(.+?)(?:\s*$)',
        r'focused?\s+on\s+(.+?)(?:\s*$)',
        r'covering\s+(.+?)(?:\s*$)',
        r'that\s+covers\s+(.+?)(?:\s*$)',
        r'including\s+(.+?)(?:\s*$)',
    ]
    for pattern in patterns:
        match = regex_module.search(pattern, message, regex_module.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            # Clean up trailing duration/level keywords
            extracted = regex_module.sub(r'\s+\d+\s*weeks?$', '', extracted, flags=regex_module.IGNORECASE)
            extracted = regex_module.sub(r'\s+(beginner|intermediate|advanced)$', '', extracted, flags=regex_module.IGNORECASE)
            return extracted if extracted else None
    return None  # Return None if not found


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat_course_management(request):
    """
    Process chat message for course management using hybrid approach.
    - Keywords for simple commands (fast)
    - LLM for complex queries (accurate)

    Commands supported:
    - "list all courses", "show my courses" → List courses
    - "create a Python course" → Create course (asks for missing details)
    - "delete the Python course" → Delete course (with confirmation)
    - "show Python course" → Show course details
    - "I want to learn Java to become a software engineer" → LLM extraction
    
    Request:
    {
        "message": "Delete the Java course",
        "crud_enabled": true
    }

    Response:
    {
        "command": "delete_course",
        "course_name": "Java",
        "course_id": "uuid",  // If matched
        "action": "confirm",  // confirm, execute, show_form, list
        "response": "Are you sure you want to delete the Java course?",
        "missing_fields": ["duration_weeks", "level"],  // If creating
    }
    """
    user = request.user
    data = request.data

    message = data.get("message", "").strip()
    crud_enabled = data.get("crud_enabled", False)
    form_data = data.get("form_data")  # Optional: form data for course creation

    logger.info("=" * 60)
    logger.info("CHAT COURSE MANAGEMENT REQUEST")
    logger.info("User: %s (%s)", user.email, user.id)
    logger.info("Message: %s", message)
    logger.info("CRUD enabled: %s", crud_enabled)
    logger.info("=" * 60)

    if not message:
        return _err("Message is required")

    # If CRUD not enabled, just return a simple response
    if not crud_enabled:
        return _ok({
            "command": "chat",
            "action": "respond",
            "response": "Course management is disabled.",
        })

    # Get user's courses for context
    user_courses = []
    try:
        courses = Course.objects.filter(user=user).order_by("-created_at")
        user_courses = CourseListSerializer(courses, many=True, context={'request': request}).data
        logger.info("Found %d courses for user", len(user_courses))
    except Exception as e:
        logger.exception("Error fetching user courses: %s", e)
        user_courses = []

    message_lower = message.lower()

    # ============ LIST COURSES ============
    list_keywords = [
        "list all", "show all", "my courses", "all courses", "enrolled courses",
        "what courses", "courses do i have", "list courses", "show courses",
        "view courses", "display courses", "course list"
    ]
    
    if any(keyword in message_lower for keyword in list_keywords):
        logger.info("Command: LIST_COURSES")
        
        if not user_courses:
            return _ok({
                "command": "list_courses",
                "action": "respond",
                "response": "You don't have any courses yet. Would you like to create one?",
                "courses": [],
            })
        
        return _ok({
            "command": "list_courses",
            "action": "list",
            "response": f"Here are your {len(user_courses)} course(s):",
            "courses": user_courses,
        })

    # ============ DELETE COURSE ============
    delete_keywords = ["delete", "remove", "drop"]
    if any(keyword in message_lower for keyword in delete_keywords):
        logger.info("Command: DELETE_COURSE")

        # First check if this is a confirmation with course_id in form_data
        if form_data and form_data.get("confirm_delete") and form_data.get("course_id"):
            course_id = form_data.get("course_id")
            try:
                course = Course.objects.get(id=course_id, user=user)
                course_name_full = course.course_name
                course.delete()
                logger.info("Deleted course: %s (ID: %s)", course_name_full, course_id)
                return _ok({
                    "command": "delete_course",
                    "action": "deleted",
                    "response": f"✅ Course '{course_name_full}' has been deleted.",
                })
            except Course.DoesNotExist:
                return _err("Course not found")

        # Extract course name from message
        course_name = _extract_course_name(message)

        if not course_name:
            return _ok({
                "command": "delete_course",
                "action": "respond",
                "response": "Which course would you like to delete? Please specify the course name.",
            })

        # Find matching course
        matched_course = None
        for course in user_courses:
            if course_name.lower() in course.get("course_name", "").lower():
                matched_course = course
                break

        if not matched_course:
            return _ok({
                "command": "delete_course",
                "action": "respond",
                "response": f"Could not find a course matching '{course_name}'. Here are your courses:",
                "courses": user_courses,
            })

        # If form_data has confirm_delete (but no course_id), proceed with deletion using matched course
        if form_data and form_data.get("confirm_delete"):
            try:
                course = Course.objects.get(id=matched_course["id"], user=user)
                course_name_full = course.course_name
                course.delete()
                logger.info("Deleted course: %s", course_name_full)
                return _ok({
                    "command": "delete_course",
                    "action": "deleted",
                    "response": f"✅ Course '{course_name_full}' has been deleted.",
                    "course_id": matched_course["id"],
                })
            except Course.DoesNotExist:
                return _err("Course not found")

        # Otherwise, ask for confirmation
        return _ok({
            "command": "delete_course",
            "action": "confirm",
            "response": f"Are you sure you want to delete the course '{matched_course['course_name']}'? This action cannot be undone.",
            "course_id": matched_course["id"],
            "course_name": matched_course["course_name"],
        })

    # ============ UPDATE COURSE ============
    # ALWAYS use LLM for update commands to properly extract intent, course, and requirements
    update_keywords = ["update", "modify", "change", "add to", "add this", "extend", "include", "cover"]

    if any(keyword in message_lower for keyword in update_keywords):
        logger.info("Command: UPDATE_COURSE")

        # Use LLM to extract course name and user query, but NOT update_type
        # User will choose update_type from options (50%, 75%, extend_50%)
        logger.info("Using LLM extraction for course name and query...")
        from services.chat.llm_intent_classifier import classify_intent_with_llm

        llm_result = async_to_sync(classify_intent_with_llm)(message, user_courses)

        logger.info("LLM extraction result: intent=%s, confidence=%s, entities=%s",
                   llm_result.intent, llm_result.confidence, llm_result.entities)

        # Extract course name and query from LLM (but NOT update_type - user chooses)
        if llm_result.confidence > 0.5:
            course_name = llm_result.entities.get("course_name")
            user_query = llm_result.entities.get("description") or llm_result.entities.get("update_query") or message
        else:
            # LLM couldn't extract, use fallback
            logger.info("LLM confidence low, using fallback extraction")
            course_name = _extract_course_name(message)
            user_query = _extract_description(message) or message

        # Find matching course
        if not course_name:
            return _ok({
                "command": "update_course",
                "action": "respond",
                "response": "Which course would you like to update? Please specify the course name.",
                "courses": user_courses,
            })

        # Find matching course
        matched_course = None
        for course in user_courses:
            if course_name.lower() in course.get("course_name", "").lower():
                matched_course = course
                break

        if not matched_course:
            return _ok({
                "command": "update_course",
                "action": "respond",
                "response": f"Could not find a course matching '{course_name}'. Here are your courses:",
                "courses": user_courses,
            })

        # Show update options - USER MUST CHOOSE update_type
        current_duration = matched_course.get('duration_weeks', 4)
        return _ok({
            "command": "update_course",
            "action": "show_options",
            "response": f"Great! Let's update your '{matched_course['course_name']}' course. Choose how you'd like to update it:",
            "course_id": matched_course["id"],
            "course_name": matched_course["course_name"],
            "user_query": user_query,
            "current_duration_weeks": current_duration,
            "update_options": [
                {
                    "type": "50%",
                    "label": "Update Current (50%)",
                    "description": f"Replace the last 50% of the course with new content about: {user_query[:100]}...",
                    "duration_change": "Same duration",
                    "requires_input": False,
                    "available": True,
                },
                {
                    "type": "75%",
                    "label": "Update Current (75%)",
                    "description": f"Replace the last 75% of the course with new content about: {user_query[:100]}...",
                    "duration_change": "Same duration",
                    "requires_input": False,
                    "available": True,
                },
                {
                    "type": "compact",
                    "label": "Compact Course",
                    "description": f"Compress and redesign the entire course into fewer weeks while keeping essential content about: {user_query[:100]}...",
                    "duration_change": f"{current_duration} weeks → [your choice] weeks",
                    "requires_input": True,
                    "input_label": "Target weeks",
                    "input_placeholder": f"Enter 1-{current_duration}",
                    "input_min": 1,
                    "input_max": current_duration,
                    "available": True,
                },
                {
                    "type": "extend_50%",
                    "label": "Extend + Update (50%)",
                    "description": f"Keep all current content and add 50% more weeks with: {user_query[:100]}...",
                    "duration_change": f"{current_duration} weeks → {int(current_duration * 1.5)} weeks",
                    "requires_input": False,
                    "available": True,
                },
                {
                    "type": "custom_update",
                    "label": "Custom Update",
                    "description": "Select specific weeks to update and customize",
                    "duration_change": "Same duration",
                    "requires_input": False,
                    "available": False,
                    "coming_soon": True,
                    "badge": "Coming Soon",
                },
            ],
        })

    # ============ CREATE COURSE ============
    create_keywords = ["create", "make", "start", "begin", "i want to learn", "new course", "generate", "build"]
    if any(keyword in message_lower for keyword in create_keywords):
        logger.info("Command: CREATE_COURSE")

        # Check if we have form data (user filled the form)
        if form_data:
            course_name = form_data.get("course_name", "").strip()
            duration_weeks = form_data.get("duration_weeks", 4)
            level = form_data.get("level", "beginner")
            description = form_data.get("description", "")
            
            # Validate
            if not course_name:
                return _err("Course name is required")
            
            try:
                duration_weeks = int(duration_weeks)
                if duration_weeks < 1 or duration_weeks > 52:
                    return _err("Duration must be between 1 and 52 weeks")
            except (ValueError, TypeError):
                return _err("Invalid duration value")
            
            if level not in ["beginner", "intermediate", "advanced"]:
                return _err("Level must be beginner, intermediate, or advanced")
            
            # Return data for frontend to call create endpoint
            return _ok({
                "command": "create_course",
                "action": "create",
                "response": f"Creating your {duration_weeks}-week {level} course on '{course_name}'!",
                "course_data": {
                    "course_name": course_name,
                    "duration_weeks": duration_weeks,
                    "level": level,
                    "description": description,
                },
            })
        
        # Extract details from message
        course_name = _extract_course_name(message)
        duration = _extract_duration(message)
        level = _extract_level(message)
        description = _extract_description(message)
        
        # Check if we have all required fields
        missing_fields = []
        if not course_name:
            missing_fields.append("course_name")
        if duration is None:
            missing_fields.append("duration_weeks")
        if level is None:
            missing_fields.append("level")
        
        if missing_fields:
            # Need to show form
            return _ok({
                "command": "create_course",
                "action": "show_form",
                "response": "Let's create a new course! I need a few details:",
                "missing_fields": missing_fields,
                "prefilled": {
                    "course_name": course_name if course_name else "",
                    "description": description if description else "",
                },
            })

        # Have all fields, proceed with creation
        return _ok({
            "command": "create_course",
            "action": "create",
            "response": f"Creating your {duration}-week {level} course on '{course_name}'!",
            "course_data": {
                "course_name": course_name,
                "duration_weeks": duration,
                "level": level,
                "description": description if description else "",
            },
        })

    # ============ SHOW COURSE DETAILS ============
    show_keywords = ["show", "view", "display", "details"]
    if any(keyword in message_lower for keyword in show_keywords):
        logger.info("Command: SHOW_COURSE")
        
        course_name = _extract_course_name(message)
        
        if not course_name:
            return _ok({
                "command": "show_course",
                "action": "list",
                "response": "Which course would you like to see? Here are your courses:",
                "courses": user_courses,
            })
        
        # Find matching course
        matched_course = None
        for course in user_courses:
            if course_name.lower() in course.get("course_name", "").lower():
                matched_course = course
                break
        
        if not matched_course:
            return _ok({
                "command": "show_course",
                "action": "respond",
                "response": f"Could not find a course matching '{course_name}'.",
                "courses": user_courses,
            })
        
        return _ok({
            "command": "show_course",
            "action": "show",
            "response": f"Here are the details for '{matched_course['course_name']}':",
            "course": matched_course,
        })

    # ============ WEEK/DAY SUMMARY (LLM-Powered) ============
    # Use LLM to analyze natural language queries about course content
    # ONLY trigger if BOTH summary keywords AND week/day references are present
    summary_keywords = ["summary", "explain", "summarize", "overview", "what did i learn",
                       "how is", "how's", "tell me about", "what's in", "whats in",
                       "walk me through"]
    
    # Quick check if query might be about summaries - require BOTH conditions
    might_be_summary = any(keyword in message_lower for keyword in summary_keywords)
    has_week_day_ref = bool(regex_module.search(r'(?:week|wk|w)\s*\d+|(?:day|dy|d)\s*\d+', message_lower))
    
    # Only process as summary if BOTH summary keyword AND week/day reference exist
    if might_be_summary and has_week_day_ref:
        logger.info("Command: WEEK_DAY_SUMMARY (LLM analysis)")

        # Use LLM to extract intent from natural language
        from services.llm.qwen_client import get_client
        import json

        extraction_prompt = f"""Analyze this user query about their course progress and extract structured information.

User query: "{message}"

User's available courses:
{chr(10).join([f"- {c['course_name']} ({c['level']}, {c['duration_weeks']} weeks)" for c in user_courses])}

Extract the following as JSON:
{{
    "intent": "summary",  // Always "summary" for this endpoint
    "course_name": "exact course name from the list above or null if not specified",
    "week_number": 1,  // integer or null
    "day_number": 2,   // integer or null  
    "summary_type": "day" | "week" | "course" | null,  // based on what they're asking about
    "confidence": 0.9  // your confidence in the extraction (0-1)
}}

Rules:
- Match course names EXACTLY from the list above (case-insensitive)
- If user says "my course" or doesn't specify, return the first/most recent course
- Week/day numbers can be written as "week 1", "w1", "day 2", "d2", etc.
- If asking about "day X of week Y" or "day X week Y", extract both numbers
- If only week mentioned, summary_type is "week"
- If both week and day mentioned, summary_type is "day"
- If no week/day mentioned but asking about course, summary_type is "course"

Return ONLY the JSON, no other text."""

        client = get_client()
        extraction_text = ""
        
        @async_to_sync
        async def extract_intent():
            nonlocal extraction_text
            async for token in client.stream_generate(prompt=extraction_prompt, context="", max_tokens=500):
                extraction_text += token
        
        try:
            extract_intent()
            # Parse JSON from response
            json_match = regex_module.search(r'\{[^}]+\}', extraction_text, regex_module.DOTALL)
            if json_match:
                extracted = json_module.loads(json_match.group())
            else:
                raise ValueError("No JSON found in LLM response")
            
            logger.info("LLM extracted: %s", extracted)
            
            course_name_from_llm = extracted.get("course_name")
            week_num = extracted.get("week_number")
            day_num = extracted.get("day_number")
            summary_type = extracted.get("summary_type")
            
            # Find matched course
            matched_course = None
            if course_name_from_llm:
                for course in user_courses:
                    if course_name_from_llm.lower() in course.get("course_name", "").lower():
                        matched_course = course
                        break
            
            # Fallback to first course if none matched
            if not matched_course and user_courses:
                matched_course = user_courses[0]
            
            if not matched_course:
                return _ok({
                    "command": "week_day_summary",
                    "action": "respond",
                    "response": "Which course would you like a summary for? Here are your courses:",
                    "courses": user_courses,
                })

            # Now fetch content and generate summary
            course = Course.objects.get(id=matched_course["id"], user=user)
            
            content_to_summarize = ""
            
            if week_num and day_num:
                # Get specific day content
                try:
                    day = DayPlan.objects.get(course=course, week_number=week_num, day_number=day_num)
                    content_to_summarize = f"""Day {day_num} of Week {week_num}: {day.day_title}
                    
Theory Content:
{day.theory_content or 'No theory content'}

Code Content:
{day.code_content or 'No code examples'}

Tasks:
{chr(10).join([f"- {task.title}: {task.description}" for task in day.tasks.all()]) if day.tasks.exists() else 'No tasks'}
"""
                    summary_type = "day"
                except DayPlan.DoesNotExist:
                    return _ok({
                        "command": "week_day_summary",
                        "action": "error",
                        "response": f"Sorry, I couldn't find Week {week_num} Day {day_num} in your {course.course_name} course. The course might still be generating or this day doesn't exist yet.",
                    })
            elif week_num:
                # Get week content
                try:
                    week = WeekPlan.objects.get(course=course, week_number=week_num)
                    days_content = []
                    for day in week.days.all().order_by('day_number'):
                        days_content.append(f"""Day {day.day_number}: {day.day_title}
- Theory: {day.theory_content[:200] if day.theory_content else 'No content'}...
- Tasks: {day.tasks.count()} tasks
""")
                    content_to_summarize = f"""Week {week_num}: {week.week_title}

Description: {week.description or 'No description'}

Days Overview:
{chr(10).join(days_content)}
"""
                    summary_type = "week"
                except WeekPlan.DoesNotExist:
                    return _ok({
                        "command": "week_day_summary",
                        "action": "error",
                        "response": f"Sorry, I couldn't find Week {week_num} in your {course.course_name} course. The course might still be generating.",
                    })
            else:
                # Course overview
                content_to_summarize = f"""Course: {course.course_name}
Level: {course.level}
Duration: {course.total_days} days
Progress: {course.generation_progress}/{course.total_days} days completed
Status: {course.generation_status}

Description: {course.description or 'No description'}

Weeks:
{chr(10).join([f"Week {w.week_number}: {w.week_title} - {w.days.count()} days" for w in course.weeks.all().order_by('week_number')]) if course.weeks.exists() else 'Course is still generating...'}
"""
                summary_type = "course"
            
            # Generate LLM summary with natural language prompt
            summary_prompt = f"""You are a friendly, knowledgeable learning assistant. Generate an engaging, personalized summary based on the following course content.

Course: {course.course_name}
User's Question: "{message}"
Summary Type: {summary_type}

Content to summarize:
{content_to_summarize}

Guidelines:
1. Start with a friendly greeting or acknowledgment
2. Highlight the KEY concepts and learning objectives in an exciting way
3. Use a conversational, encouraging tone (like a tutor talking to a student)
4. Include practical insights, tips, or real-world connections if applicable
5. Structure with short paragraphs, bullet points, or numbered lists for readability
6. Keep it around 150-300 words (adjust based on content depth)
7. End with encouragement or a question to keep them engaged
8. Use formatting like **bold** for key terms and concepts
9. If code was covered, mention what they learned to build/create
10. Make connections to what they might have learned before

Make it sound NATURAL and PERSONALIZED, as if you're excited to share what they've learned!"""

            summary_text = ""
            
            @async_to_sync
            async def generate_summary():
                nonlocal summary_text
                async for token in client.stream_generate(prompt=summary_prompt, context="", max_tokens=1000):
                    summary_text += token
            
            generate_summary()
            
            return _ok({
                "command": "week_day_summary",
                "action": "show_llm_summary",
                "course_id": str(course.id),
                "course_name": course.course_name,
                "week_number": week_num,
                "day_number": day_num,
                "summary_type": summary_type,
                "summary": summary_text,
                "response": summary_text,
            })
            
        except Exception as e:
            logger.exception("Error in LLM summary generation: %s", e)
            return _ok({
                "command": "week_day_summary",
                "action": "error",
                "response": f"Sorry, I encountered an error while analyzing your request: {str(e)}",
            })

    # ============ DEFAULT: CHAT ============
    logger.info("Command: CHAT (no matching command)")
    return _ok({
        "command": "chat",
        "action": "respond",
        "response": "I understand. How can I help you with your learning today?",
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat_create_course(request):
    """
    Create a course from chat.
    Called after user fills the form or provides all details.

    Request:
    {
        "course_name": "Python",
        "duration_weeks": 4,
        "level": "beginner",
        "description": "For data science"
    }
    """
    user = request.user
    data = request.data

    course_name = data.get("course_name", "").strip()
    duration_weeks = data.get("duration_weeks", 4)
    level = data.get("level", "beginner")
    description = data.get("description")

    if not course_name:
        return _err("Course name is required")

    # Validate duration
    try:
        duration_weeks = int(duration_weeks)
        if duration_weeks < 1 or duration_weeks > 52:
            return _err("Duration must be between 1 and 52 weeks")
    except (ValueError, TypeError):
        return _err("Invalid duration value")

    # Validate level
    if level not in ["beginner", "intermediate", "advanced"]:
        return _err("Level must be beginner, intermediate, or advanced")

    # Create the course directly (same logic as course_generate endpoint)
    from apps.courses.models import Course, WeekPlan, DayPlan, CourseProgress
    from apps.courses.tasks import generate_course_content_task
    from rest_framework import status

    # Create course row immediately with status="generating"
    course = Course.objects.create(
        user=user,
        course_name=course_name,
        topic=course_name,  # Will be updated by Celery task
        description=description,  # Optional user-provided description
        level=level,
        duration_weeks=duration_weeks,
        hours_per_day=2,
        goals=[],
        status="generating",
        generation_status="pending",
        generation_progress=0,
    )

    # Create CourseProgress record
    CourseProgress.objects.get_or_create(
        user=user,
        course=course,
        defaults={
            "total_days": duration_weeks * 5,
            "total_weeks": duration_weeks,
            "overall_percentage": 0.0,
            "completed_days": 0,
            "current_week": 1,
            "current_day": 1
        }
    )

    # Create empty week/day skeleton in DB
    for week_num in range(1, duration_weeks + 1):
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
                is_locked=not (week_num == 1 and day_num == 1),
                theory_generated=False,
                code_generated=False,
                quiz_generated=False,
            )

    # Fire Celery task in background
    generate_course_content_task.delay(
        course_id=str(course.id),
        course_name=course_name,
        duration_weeks=duration_weeks,
        level=level,
        goals=[],
        description=description,
    )

    # Add generating course to chat session (if session_id provided)
    session_id = data.get("session_id")
    if session_id:
        try:
            from services.chat.session import ChatSession
            session = ChatSession(
                user_id=str(user.id),
                session_id=str(session_id),
            )
            session.add_generating_course(str(course.id), course_name)
            session.save()
            logger.info("Added generating course %s to session %s", course.id, session_id)
        except Exception as exc:
            logger.warning("Failed to add generating course to session: %s", exc)

    # Return course_id instantly
    return _ok({
        "course_id": str(course.id),
        "course_name": course_name,
        "level": level,
        "duration_weeks": duration_weeks,
        "total_days": duration_weeks * 5,
        "status": "generating",
        "session_id": session_id,  # Return session_id for frontend reference
        "message": "Course creation started. Poll /api/courses/{id}/generation-progress/ for progress.",
    }, status.HTTP_202_ACCEPTED)
