"""
Chat intent classifier for course management.
Detects user intent and extracts entities from chat messages.
"""
import re
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent: str  # create_course, delete_course, read_course, read_day, answer_mcq, list_courses, unknown
    confidence: float  # 0.0 to 1.0
    entities: Dict[str, Any]  # Extracted entities
    missing_fields: List[str]  # For course creation: what's missing
    requires_confirmation: bool  # Whether action needs user confirmation


class ChatIntentClassifier:
    """
    Classifies chat intents for course management.
    Uses pattern matching and keyword detection.
    
    Supported Intents:
    - create_course: Create a new course
    - update_course: Update/modify an existing course
    - delete_course: Delete a course
    - read_course/list_courses: View courses
    - read_day: View specific week/day
    - answer_mcq: Help with quiz questions
    """
    
    # Intent patterns
    CREATE_COURSE_PATTERNS = [
        r'create\s+(a\s+)?course',
        r'make\s+(a\s+)?course',
        r'start\s+(a\s+)?course',
        r'begin\s+(a\s+)?course',
        r'i\s+want\s+to\s+learn',
        r'i\s+want\s+to\s+study',
        r'teach\s+me',
        r'help\s+me\s+learn',
    ]

    UPDATE_COURSE_PATTERNS = [
        r'update\s+(course)?',
        r'modify\s+(course)?',
        r'change\s+(course)?',
        r'add\s+(to\s+)?(this\s+)?course',
        r'add\s+this\s+to',
        r'update\s+this\s+course',
        r'update\s+my\s+course',
        r'change\s+my\s+course',
        r'modify\s+my\s+course',
        r'extend\s+(this\s+)?course',
        r'add\s+more\s+(content|weeks|topics)\s+(to\s+)?(this\s+)?course',
        r'include\s+',
        r'cover\s+',
    ]
    
    DELETE_COURSE_PATTERNS = [
        r'delete\s+(course)?',
        r'remove\s+(course)?',
        r'destroy\s+(course)?',
        r'get\s+rid\s+of',
        r'drop\s+(course)?',
    ]
    
    READ_COURSE_PATTERNS = [
        r'show\s+me\s+course',
        r'show\s+my\s+courses?',
        r'list\s+courses?',
        r'my\s+courses?',
        r'all\s+courses?',
        r'view\s+courses?',
    ]
    
    READ_DAY_PATTERNS = [
        r'show\s+me\s+(week|wk)\s*\d+\s*(day|d)\s*\d+',
        r'show\s+(week|wk)\s*\d+\s*(day|d)\s*\d+',
        r'open\s+(week|wk)\s*\d+\s*(day|d)\s*\d+',
        r'go\s+to\s+(week|wk)\s*\d+\s*(day|d)\s*\d+',
        r'week\s*\d+\s*day\s*\d+',
        r'(week|wk)\s*\d+\s*(day|d)\s*\d+\s+of',
    ]
    
    MCQ_PATTERNS = [
        r'answer\s+to\s+(quiz|question|mcq)',
        r"what'?s?\s+(the\s+)?answer",
        r'help\s+me\s+with\s+(quiz|question|mcq)',
        r'explain\s+(this\s+)?question',
        r'quiz\s+help',
        r'question\s+help',
    ]
    
    # Entity extraction patterns
    COURSE_NAME_PATTERNS = [
        r'(?:create|make|start|begin|learn|study)\s+(?:a\s+)?(?:course\s+)?(?:on|about|in|for)?\s*(.+?)(?:\s*(?:for|with|of|to|$))',
        r'course\s+(?:on|about|in)?\s*(.+?)(?:\s*(?:for|with|of|to|$))',
        r"'([^']+)'",  # Quoted course name
        r'"([^"]+)"',  # Double quoted course name
    ]
    
    DURATION_PATTERNS = [
        r'(\d+)\s*(?:week|wk|w)',
        r'(\d+)\s*(?:month|mo|m)',
        r'for\s+(\d+)\s*(?:weeks?|months?)',
        r'(\d+)\s*(?:weeks?|months?)\s*(?:long)?',
    ]
    
    LEVEL_PATTERNS = [
        r'\b(beginner|basic|intro|introductory|entry\s*level)\b',
        r'\b(intermediate|mid|middle|moderate)\b',
        r'\b(advanced|expert|pro|professional|senior)\b',
    ]
    
    WEEK_DAY_PATTERN = r'(?:week|wk)\s*(\d+)\s*(?:day|d)\s*(\d+)'
    
    def __init__(self):
        """Initialize classifier."""
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns."""
        self.create_course_regex = [re.compile(p, re.IGNORECASE) for p in self.CREATE_COURSE_PATTERNS]
        self.update_course_regex = [re.compile(p, re.IGNORECASE) for p in self.UPDATE_COURSE_PATTERNS]
        self.delete_course_regex = [re.compile(p, re.IGNORECASE) for p in self.DELETE_COURSE_PATTERNS]
        self.read_course_regex = [re.compile(p, re.IGNORECASE) for p in self.READ_COURSE_PATTERNS]
        self.read_day_regex = [re.compile(p, re.IGNORECASE) for p in self.READ_DAY_PATTERNS]
        self.mcq_regex = [re.compile(p, re.IGNORECASE) for p in self.MCQ_PATTERNS]
        self.course_name_regex = [re.compile(p, re.IGNORECASE) for p in self.COURSE_NAME_PATTERNS]
        self.duration_regex = [re.compile(p, re.IGNORECASE) for p in self.DURATION_PATTERNS]
        self.level_regex = [re.compile(p, re.IGNORECASE) for p in self.LEVEL_PATTERNS]
        self.week_day_regex = re.compile(self.WEEK_DAY_PATTERN, re.IGNORECASE)
    
    def classify(self, message: str, user_courses: Optional[List[Dict]] = None) -> IntentResult:
        """
        Classify user message intent.

        Args:
            message: User message text
            user_courses: Optional list of user's courses for context

        Returns:
            IntentResult with intent, confidence, entities, and missing_fields
        """
        message_lower = message.lower().strip()

        # Try each intent type
        intent, confidence = self._detect_intent(message_lower)
        entities = {}

        # Extract entities based on intent
        if intent == 'create_course':
            entities = self._extract_course_entities(message_lower)
            missing_fields = self._get_missing_course_fields(entities)
            return IntentResult(
                intent=intent,
                confidence=confidence,
                entities=entities,
                missing_fields=missing_fields,
                requires_confirmation=len(missing_fields) == 0  # Only confirm if all fields present
            )

        elif intent == 'update_course':
            entities = self._extract_update_entities(message_lower)
            return IntentResult(
                intent=intent,
                confidence=confidence,
                entities=entities,
                missing_fields=[],
                requires_confirmation=True  # Always confirm update
            )

        elif intent == 'delete_course':
            entities = self._extract_course_name(message_lower)
            return IntentResult(
                intent=intent,
                confidence=confidence,
                entities=entities,
                missing_fields=[],
                requires_confirmation=True  # Always confirm deletion
            )
        
        elif intent == 'read_day':
            entities = self._extract_week_day(message_lower)
            entities.update(self._extract_course_name(message_lower))
            return IntentResult(
                intent=intent,
                confidence=confidence,
                entities=entities,
                missing_fields=[],
                requires_confirmation=False
            )
        
        elif intent == 'answer_mcq':
            entities = self._extract_mcq_context(message_lower)
            return IntentResult(
                intent=intent,
                confidence=confidence,
                entities=entities,
                missing_fields=[],
                requires_confirmation=False
            )
        
        elif intent in ['read_course', 'list_courses']:
            return IntentResult(
                intent=intent,
                confidence=confidence,
                entities={},
                missing_fields=[],
                requires_confirmation=False
            )
        
        # Unknown intent
        return IntentResult(
            intent='unknown',
            confidence=0.0,
            entities={},
            missing_fields=[],
            requires_confirmation=False
        )
    
    def _detect_intent(self, message: str) -> tuple:
        """Detect intent type from message."""
        # Check each intent type in priority order
        
        # Update course - check before create (more specific)
        for regex in self.update_course_regex:
            if regex.search(message):
                return ('update_course', 0.9)

        for regex in self.delete_course_regex:
            if regex.search(message):
                return ('delete_course', 0.9)

        for regex in self.read_day_regex:
            if regex.search(message):
                return ('read_day', 0.95)

        for regex in self.mcq_regex:
            if regex.search(message):
                return ('answer_mcq', 0.85)

        for regex in self.read_course_regex:
            if regex.search(message):
                return ('list_courses', 0.9)

        for regex in self.create_course_regex:
            if regex.search(message):
                return ('create_course', 0.85)

        return ('unknown', 0.0)
    
    def _extract_course_entities(self, message: str) -> Dict[str, Any]:
        """Extract course creation entities from message."""
        entities = {}

        # Extract course name
        course_name = self._extract_course_name(message).get('course_name')
        if course_name:
            entities['course_name'] = course_name

        # Extract duration
        for regex in self.duration_regex:
            match = regex.search(message)
            if match:
                duration_num = int(match.group(1))
                # Convert months to weeks
                if 'month' in message[match.start():match.end()].lower():
                    duration_num *= 4
                entities['duration_weeks'] = duration_num
                break

        # Extract skill level
        for regex in self.level_regex:
            match = regex.search(message)
            if match:
                level_text = match.group(1).lower()
                if level_text in ['beginner', 'basic', 'intro', 'introductory', 'entry level']:
                    entities['level'] = 'beginner'
                elif level_text in ['intermediate', 'mid', 'middle', 'moderate']:
                    entities['level'] = 'intermediate'
                elif level_text in ['advanced', 'expert', 'pro', 'professional', 'senior']:
                    entities['level'] = 'advanced'
                break

        # Extract description (everything after course name that's not a field)
        # Look for descriptive text
        desc_patterns = [
            r'for\s+(.+?)(?:\s*(?:with|of|to|in|on|$))',
            r'about\s+(.+?)(?:\s*(?:with|of|to|in|on|$))',
            r'in\s+(.+?)(?:\s*(?:with|of|to|for|on|$))',
        ]
        for pattern in desc_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match and match.group(1):
                desc = match.group(1).strip()
                # Don't capture if it's a duration or level
                if not re.search(r'\d+\s*(?:week|month)', desc) and \
                   not re.search(r'\b(beginner|intermediate|advanced)\b', desc):
                    entities['description'] = desc
                    break

        return entities

    def _extract_update_entities(self, message: str) -> Dict[str, Any]:
        """Extract entities for course update from message."""
        entities = {}

        # Extract course name (which course to update)
        entities.update(self._extract_course_name(message))

        # Extract update query (what to add/change)
        # Look for patterns like "add X", "include X", "with X", "for X"
        update_patterns = [
            r'(?:add|include|with|for|change|modify|update)\s+(?:to\s+)?(?:this\s+)?(?:course\s+)?(.+?)(?:\s*$)',
            r'add\s+(.+?)(?:\s*$)',
            r'include\s+(.+?)(?:\s*$)',
            r'covering\s+(.+?)(?:\s*$)',
        ]
        
        for pattern in update_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match and match.group(1):
                query = match.group(1).strip()
                # Clean up common phrases
                if query and len(query) > 2:
                    entities['user_query'] = query
                    break

        # Try to detect update type from message
        if 'extend' in message or 'add more weeks' in message or 'make it longer' in message:
            entities['update_type'] = 'extend_50%'
        elif 'half' in message or '50%' in message or 'last half' in message:
            entities['update_type'] = '50%'
        elif '75%' in message or 'most' in message or 'majority' in message:
            entities['update_type'] = '75%'
        else:
            # Default to showing options
            entities['update_type'] = 'show_options'

        return entities
    
    def _extract_course_name(self, message: str) -> Dict[str, str]:
        """Extract course name from message."""
        # Try quoted names first
        for regex in self.course_name_regex[2:]:
            match = regex.search(message)
            if match:
                return {'course_name': match.group(1).strip()}
        
        # Try other patterns
        for regex in self.course_name_regex[:2]:
            match = regex.search(message)
            if match and match.group(1):
                name = match.group(1).strip()
                # Clean up common phrases
                name = re.sub(r'\b(a|an|the)\b', '', name).strip()
                name = re.sub(r'\b(course|program|curriculum)\b', '', name).strip()
                if name and len(name) > 2:
                    return {'course_name': name}
        
        return {}
    
    def _extract_week_day(self, message: str) -> Dict[str, int]:
        """Extract week and day numbers from message."""
        match = self.week_day_regex.search(message)
        if match:
            return {
                'week_number': int(match.group(1)),
                'day_number': int(match.group(2))
            }
        return {}
    
    def _extract_mcq_context(self, message: str) -> Dict[str, Any]:
        """Extract MCQ context from message."""
        entities = {}
        
        # Try to extract question number
        q_match = re.search(r'(?:question|quiz|q|mcq)\s*(?:#?|number)?\s*(\d+)', message, re.IGNORECASE)
        if q_match:
            entities['question_number'] = int(q_match.group(1))
        
        # Extract week/day if present
        entities.update(self._extract_week_day(message))
        
        # Extract course name
        entities.update(self._extract_course_name(message))
        
        return entities
    
    def _get_missing_course_fields(self, entities: Dict[str, Any]) -> List[str]:
        """Determine which required fields are missing for course creation."""
        required_fields = ['course_name', 'duration_weeks', 'level']
        missing = []
        
        for field in required_fields:
            if field not in entities:
                missing.append(field)
        
        return missing
