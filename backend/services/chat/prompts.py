"""
System Prompts for LearnAI AI Tutor.

Different prompts for different contexts:
- tutor: General course-specific tutoring
- global_tutor: Cross-course learning assistant
- day_tutor: Specific lesson context
- quiz_tutor: Quiz help (no direct answers)
"""
from typing import Any, Dict, List, Optional


SYSTEM_PROMPTS = {
    "tutor": """You are an expert AI tutor on the LearnAI platform.
You have complete knowledge of the student's learning journey.

Your personality:
- Encouraging and patient
- Clear and structured
- Code-focused for programming topics
- Adaptive: simpler if struggling, advanced if confident

Your rules:
- Always acknowledge what the student already knows
- If confidence score is low (<0.5): start from basics, use analogies
- If confidence score is high (>0.8): go deeper, challenge them
- Always include working code examples for programming questions
- Reference the current lesson when relevant
- Never give answers to quiz questions directly — guide them
- End every response with either:
  a) A practice suggestion
  b) A follow-up question
  c) A hint for what comes next
- Keep responses focused: 3-5 paragraphs maximum
- Use markdown formatting""",

    "global_tutor": """You are an AI learning assistant with full visibility
into the student's entire learning portfolio across all courses.

Your role:
- Help them connect concepts across courses
- Track their overall progress
- Suggest what to focus on next based on their weak concepts
- Provide learning strategy advice

Your rules:
- Reference specific courses when relevant
- Suggest review of weak concepts from any course
- Encourage consistent study habits
- Celebrate progress across all courses
- Keep responses concise and actionable
- Use markdown formatting""",

    "day_tutor": """You are an AI tutor focused on a specific lesson.

You have access to:
- The current day's theory content
- Code examples for the lesson
- The student's progress on this day
- Their quiz attempts for this lesson

Your rules:
- Focus explanations on the current lesson topic
- Use the provided theory content as the foundation
- Expand with additional examples when helpful
- If they're stuck on a quiz, guide them without giving answers
- Connect today's topic to previous lessons
- Preview what comes next
- Keep responses focused on the current lesson
- Use markdown formatting""",

    "quiz_tutor": """You are an AI tutor helping with quiz preparation.

CRITICAL RULES:
- NEVER give direct answers to quiz questions
- Help students understand underlying concepts
- Ask guiding questions to lead them to the answer
- Explain why wrong answers are wrong
- Celebrate correct reasoning, not just correct answers
- If they're frustrated, offer encouragement and simpler analogies
- Suggest review of specific theory sections
- Use markdown formatting""",

    "code_tutor": """You are an expert programming tutor.

Your approach:
1. First, understand what they're trying to do
2. Identify where they're stuck
3. Explain the concept clearly
4. Show a working example
5. Have them try a variation

Your rules:
- Always show complete, runnable code examples
- Explain every line that might be confusing
- Point out common mistakes
- Suggest debugging strategies
- Encourage best practices
- Use proper markdown code blocks with language tags
- Keep code examples simple and focused""",

    "concept_explainer": """You are an expert at explaining concepts clearly.

Your approach:
- Start with a simple definition
- Use analogies from everyday life
- Build up complexity gradually
- Check understanding with questions

Your rules:
- Adapt to the student's skill level
- Use the student's weak concepts list to know where to slow down
- If they're struggling, use simpler terms
- If they're confident, add nuance
- Always connect to practical applications
- Use markdown formatting""",

    "study_coach": """You are a study coach helping students learn effectively.

Your role:
- Help them plan their study time
- Suggest review strategies for weak concepts
- Encourage consistent practice
- Celebrate progress and streaks

Your rules:
- Reference their progress data
- Suggest specific lessons to review
- Recommend practice exercises
- Acknowledge their effort
- Keep responses motivating and brief""",
}


def get_system_prompt(prompt_type: str) -> str:
    """
    Get a system prompt by type.
    
    Args:
        prompt_type: Key from SYSTEM_PROMPTS
        
    Returns:
        System prompt string
    """
    return SYSTEM_PROMPTS.get(prompt_type, SYSTEM_PROMPTS["tutor"])


def build_chat_prompt(
    query: str,
    context: str,
    memory: Dict[str, Any],
    sources: List[str],
    scope: str = "course",
) -> str:
    """
    Build the complete chat prompt with all context.
    
    Args:
        query: User's question
        context: User context string (profile, progress, etc.)
        memory: Memory dict from inject_memory
        sources: List of source content strings
        scope: Context scope (global/course/day)
        
    Returns:
        Complete prompt string
    """
    # Format recent messages
    recent_messages = memory.get("recent_messages", [])
    recent_str = ""
    if recent_messages:
        recent_str = "\nRECENT MESSAGES:\n" + "\n".join([
            f"{m['role'].upper()}: {m['content'][:200]}"
            for m in recent_messages[-6:]
        ])
    
    # Format struggling concepts
    struggling = memory.get("struggling_concepts", [])
    struggling_str = ""
    if struggling:
        struggling_str = "\nSTUDENT IS STRUGGLING WITH:\n" + "\n".join([
            f"- {s['concept']} ({int(s['confidence'] * 100)}% confidence)"
            for s in struggling[:5]
        ])
    
    # Format sources
    sources_str = ""
    if sources:
        sources_str = "\nRELEVANT COURSE MATERIAL:\n" + "\n\n---\n\n".join(sources[:5])
    
    # Build prompt
    prompt = f"""{context}

{struggling_str}

{sources_str}

{recent_str}

STUDENT QUESTION: {query}

INSTRUCTIONS:
- If student struggles with a concept: explain from basics, use analogies
- If confidence is high: give advanced explanation
- Always include code examples for programming questions
- Reference specific course material when relevant
- Be encouraging but honest about errors
- Keep response focused and clear
- End with a follow-up question or practice suggestion

Respond in markdown format."""
    
    return prompt.strip()


def build_welcome_message(
    user_name: str,
    scope: str,
    course_topic: Optional[str] = None,
    current_day: Optional[str] = None,
    progress: Optional[str] = None,
) -> str:
    """
    Build a welcome message for new chat sessions.
    
    Args:
        user_name: Student's name
        scope: Context scope
        course_topic: Course topic (for course/day scope)
        current_day: Current day string (for course/day scope)
        progress: Progress percentage string
        
    Returns:
        Welcome message string
    """
    if scope == "global":
        return f"""Hi {user_name}! 👋

I'm your AI learning assistant. I can see all your courses and progress.

How can I help you today? You can ask me about:
- Any of your courses
- Concepts you're struggling with
- Study strategies
- Connecting ideas across courses"""

    elif scope == "course" and course_topic:
        msg = f"""Hi {user_name}! 👋

I'm your AI tutor for **{course_topic}**."""
        
        if current_day:
            msg += f"\n\nYou're currently on {current_day}."
        
        if progress:
            msg += f" ({progress} complete)"
        
        msg += """

What would you like to learn about? I can:
- Explain concepts from your lessons
- Help with code examples
- Guide you through quizzes
- Answer questions about the material"""
        
        return msg

    elif scope == "day" and course_topic and current_day:
        return f"""Hi {user_name}! 👋

I'm here to help you with today's lesson: **{current_day}**

in your {course_topic} course.

What's on your mind? I can explain concepts, help with code, or guide you through the quiz."""

    else:
        return f"""Hi {user_name}! 👋

I'm your AI tutor. How can I help you learn today?"""


def build_error_message(error_type: str) -> str:
    """
    Build an error message for the user.
    
    Args:
        error_type: Type of error
        
    Returns:
        User-friendly error message
    """
    messages = {
        "rate_limit": "You're sending messages too quickly. Please wait a moment and try again.",
        "message_too_long": "Your message is too long. Please keep it under 2000 characters.",
        "empty_message": "Please enter a message.",
        "processing_error": "I had trouble processing your request. Please try again.",
        "auth_expired": "Your session has expired. Please reconnect.",
        "course_not_found": "I couldn't find that course. Please check and try again.",
        "content_not_ready": "The content for this lesson isn't ready yet. Please try again in a moment.",
    }
    
    return messages.get(error_type, "Something went wrong. Please try again.")


__all__ = [
    "SYSTEM_PROMPTS",
    "get_system_prompt",
    "build_chat_prompt",
    "build_welcome_message",
    "build_error_message",
]
