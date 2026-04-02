"""
LLM-based intent classifier for complex course management queries.
Uses vLLM/Qwen to detect intent and extract entities from natural language.
"""
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMIntentResult:
    """Result of LLM intent classification."""
    intent: str  # create_course, update_course, delete_course, list_courses, read_day, chat
    confidence: float  # 0.0 to 1.0
    entities: Dict[str, Any]  # Extracted entities
    missing_fields: List[str]  # For course creation: what's missing


async def classify_intent_with_llm(
    message: str,
    user_courses: Optional[List[Dict]] = None,
) -> LLMIntentResult:
    """
    Use LLM to classify intent and extract entities from complex queries.
    
    Args:
        message: User message
        user_courses: Optional list of user's courses for context
    
    Returns:
        LLMIntentResult with intent, confidence, entities, and missing_fields
    """
    from services.llm.qwen_client import QwenClient
    
    courses_context = ""
    if user_courses:
        courses_context = "\n".join([
            f"- {c['course_name']} ({c['level']}, {c['duration_weeks']} weeks) - Progress: {c['progress']}%"
            for c in user_courses[:5]  # Limit to 5 courses
        ])
    
    prompt = f"""Analyze this user message and extract intent and entities for course management.

User message: "{message}"

{'Available courses:\n' + courses_context if courses_context else 'No courses yet.'}

Return ONLY valid JSON with this exact structure:
{{
    "intent": "create_course" | "update_course" | "delete_course" | "list_courses" | "read_day" | "chat",
    "confidence": 0.95,
    "entities": {{
        "course_name": "Python Programming" | null,
        "duration_weeks": 4 | null,
        "level": "beginner" | "intermediate" | "advanced" | null,
        "description": "optional description" | null,
        "update_query": "what user wants to add/learn/update" | null,
        "update_type": "50%" | "75%" | "extend" | "compact" | null,
        "week_number": 1 | null,
        "day_number": 1 | null
    }},
    "missing_fields": ["duration_weeks", "level"],
    "reasoning": "User wants to update Python course to include OOP"
}}

Rules:
1. For CREATE: Look for "create", "make", "start", "learn", "build", "generate", "i want"
2. For UPDATE: Look for "update", "modify", "change", "add to", "extend", "include", "which includes"
3. For DELETE: Look for "delete", "remove", "drop", "get rid of"
4. For LIST: Look for "list", "show all", "my courses", "what courses"
5. For READ_DAY: Look for "week X day Y", "show me week", "go to week"
6. For CHAT: Everything else (questions, discussions, etc.)

Extract entities:
- course_name: The course topic/name (e.g., "Python", "Java course")
- duration_weeks: Number if mentioned (e.g., "4 weeks", "2 months")
- level: "beginner", "intermediate", or "advanced" if mentioned
- description: Any additional context about what to learn
- update_query: **CRITICAL FOR UPDATE** - what user wants to add/learn/include (everything after "update X course" or "which includes")
- update_type: If updating, detect if they want "extend", "compact", "50%", or "75%"

For UPDATE intent:
- Extract course_name from the course being updated
- Extract update_query as the TOPIC/REQUIREMENT user wants to add (e.g., "oops", "Django REST framework", "deployment")
- Set missing_fields to [] if update_query is found

Be generous with confidence (0.7+) if intent is clear.
Return ONLY the JSON, no other text."""

    try:
        client = QwenClient(max_tokens=500, temperature=0.1)
        # Use sync generate in async context via asyncio.to_thread
        import asyncio
        response = await asyncio.to_thread(client.generate, prompt)
        
        # Parse JSON from response with robust error handling
        import json as json_module
        import re as regex_module
        
        # Try to extract JSON from response
        json_match = regex_module.search(r'\{[^}]+\}', response, regex_module.DOTALL)
        if not json_match:
            logger.warning("No JSON found in LLM response: %s", response[:200])
            return LLMIntentResult(
                intent="update_course",  # Default to update since keyword matched
                confidence=0.8,
                entities={"course_name": message.split()[1].title() if len(message.split()) > 1 else None},
                missing_fields=[]
            )
        
        try:
            result = json_module.loads(json_match.group())
        except json_module.JSONDecodeError as e:
            logger.warning("JSON parse error, using fallback extraction: %s", e)
            # Fallback: extract course name and update query from message
            words = message.split()
            course_name = None
            update_query = message  # Default to full message
            
            # Find update keyword and extract course + query
            for i, word in enumerate(words):
                if word.lower() in ['update', 'modify', 'change', 'add']:
                    # Next word is usually the course name
                    if i + 1 < len(words) and words[i + 1].lower() not in ['the', 'my', 'a', 'an']:
                        course_name = words[i + 1].title()
                    
                    # Everything after "course" or "which includes" is the query
                    message_lower = message.lower()
                    if 'which includes' in message_lower:
                        update_query = message_lower.split('which includes')[1].strip()
                    elif 'course' in message_lower:
                        update_query = message_lower.split('course')[1].strip()
                    break

            return LLMIntentResult(
                intent="update_course",
                confidence=0.8,
                entities={
                    "course_name": course_name,
                    "update_query": update_query
                },
                missing_fields=[]
            )
        
        return LLMIntentResult(
            intent=result.get("intent", "update_course"),
            confidence=result.get("confidence", 0.8),
            entities=result.get("entities", {}),
            missing_fields=result.get("missing_fields", [])
        )
        
    except Exception as e:
        logger.exception("LLM intent classification failed: %s", e)
        return LLMIntentResult(
            intent="chat",
            confidence=0.3,
            entities={},
            missing_fields=[]
        )


def should_use_llm(message: str) -> bool:
    """
    Determine if a message should use LLM classification.
    
    Use LLM for:
    - Long messages (>30 chars)
    - Messages without clear keywords
    - Complex/natural language queries
    
    Use keywords for:
    - Short, simple commands
    - Clear keyword matches
    """
    message_lower = message.lower().strip()
    
    # Always use LLM for long messages
    if len(message) > 50:
        return True
    
    # Clear keyword patterns - use fast keyword matching
    simple_patterns = [
        r'^create\s+\w+',  # "create java course"
        r'^make\s+\w+',  # "make python course"
        r'^delete\s+',  # "delete course"
        r'^remove\s+',  # "remove course"
        r'^list\s+',  # "list courses"
        r'^show\s+all',  # "show all courses"
        r'^my\s+courses',  # "my courses"
        r'^week\s*\d+\s*day\s*\d+',  # "week 1 day 2"
    ]
    
    for pattern in simple_patterns:
        if regex_module.match(pattern, message_lower):
            return False
    
    # Use LLM for everything else
    return True


# Import regex_module for should_use_llm
import re as regex_module
