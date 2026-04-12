"""
Chat handlers for course management.
Each handler processes a specific intent and returns a response.
"""
import logging
from typing import Dict, List, Any, Optional
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class CourseCreationHandler:
    """Handle course creation intents."""
    
    async def handle(
        self,
        entities: Dict[str, Any],
        missing_fields: List[str],
        user_courses: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Handle course creation request.
        
        Returns:
            Dict with:
            - response: Text response for user
            - action: 'show_form' | 'create_course' | 'none'
            - form_schema: Form fields if action is 'show_form'
            - course_data: Course data if action is 'create_course'
        """
        if missing_fields:
            # Need to collect more information
            form_schema = self._build_form_schema(entities, missing_fields)
            return {
                'response': self._build_missing_fields_message(missing_fields, entities),
                'action': 'show_form',
                'form_schema': form_schema,
                'course_data': entities,
            }
        else:
            # All fields present, ready to create
            return {
                'response': f"Creating your {entities.get('duration_weeks', 4)}-week {entities.get('level', 'beginner')} course on **{entities.get('course_name', 'Unknown')}'**! I'll start generating the content now.",
                'action': 'create_course',
                'course_data': entities,
            }
    
    def _build_form_schema(
        self,
        entities: Dict[str, Any],
        missing_fields: List[str],
    ) -> Dict[str, Any]:
        """Build form schema for missing fields."""
        schema = {
            'fields': [],
            'prefilled': entities,
        }
        
        field_configs = {
            'course_name': {
                'type': 'text',
                'label': 'Course Name',
                'placeholder': 'e.g., Python Programming',
                'required': True,
            },
            'duration_weeks': {
                'type': 'number',
                'label': 'Duration (weeks)',
                'placeholder': '4',
                'min': 1,
                'max': 52,
                'required': True,
            },
            'level': {
                'type': 'select',
                'label': 'Skill Level',
                'options': [
                    {'value': 'beginner', 'label': 'Beginner'},
                    {'value': 'intermediate', 'label': 'Intermediate'},
                    {'value': 'advanced', 'label': 'Advanced'},
                ],
                'required': True,
            },
            'description': {
                'type': 'textarea',
                'label': 'Description (Optional)',
                'placeholder': 'Describe what you want to learn...',
                'required': False,
                'rows': 3,
            },
        }
        
        for field in missing_fields:
            if field in field_configs:
                schema['fields'].append({
                    'name': field,
                    **field_configs[field]
                })
        
        return schema
    
    def _build_missing_fields_message(
        self,
        missing_fields: List[str],
        entities: Dict[str, Any],
    ) -> str:
        """Build message asking for missing fields."""
        course_name = entities.get('course_name', '')
        
        if course_name and len(missing_fields) < 3:
            return f"Great! Let's create a course on **{course_name}**. I just need a few more details:"
        elif course_name:
            return f"Let's create your **{course_name}** course! Please fill in the details below:"
        else:
            return "I'd be happy to help you create a course! Please fill in the details below:"


class CourseDeletionHandler:
    """Handle course deletion intents."""
    
    async def handle(
        self,
        entities: Dict[str, Any],
        user_courses: List[Dict],
        confirmation: bool = False,
    ) -> Dict[str, Any]:
        """
        Handle course deletion request.
        
        Returns:
            Dict with:
            - response: Text response for user
            - action: 'confirm' | 'delete' | 'show_options' | 'none'
            - course_id: Course ID if single match
            - courses: List of matching courses if multiple
        """
        course_name = entities.get('course_name', '').lower()
        
        if not course_name:
            return {
                'response': "Which course would you like to delete? Please provide the course name.",
                'action': 'none',
            }
        
        # Find matching courses
        matches = [
            c for c in user_courses
            if course_name in c.get('course_name', '').lower() or
               course_name in c.get('topic', '').lower()
        ]
        
        if not matches:
            return {
                'response': f"I couldn't find any course matching '{course_name}'. Your courses are: " +
                           ", ".join([c.get('course_name', 'Unknown') for c in user_courses]),
                'action': 'none',
            }
        
        if len(matches) > 1:
            # Multiple matches - show options
            options = "\n".join([
                f"{i+1}. **{c.get('course_name')}** ({c.get('duration_weeks', 0)} weeks, {c.get('level', 'beginner')})"
                for i, c in enumerate(matches)
            ])
            return {
                'response': f"You have multiple courses matching '{course_name}':\n\n{options}\n\nWhich one would you like to delete?",
                'action': 'show_options',
                'courses': matches,
            }
        
        # Single match
        course = matches[0]
        
        if not confirmation:
            return {
                'response': f"Are you sure you want to delete **{course.get('course_name')}**? This action cannot be undone.",
                'action': 'confirm',
                'course_id': course.get('id'),
                'course_name': course.get('course_name'),
            }
        else:
            # Perform deletion (caller will handle actual deletion)
            return {
                'response': f"Course **{course.get('course_name')}** has been deleted.",
                'action': 'delete',
                'course_id': course.get('id'),
                'course_name': course.get('course_name'),
            }


class CourseReaderHandler:
    """Handle course/day reading intents."""
    
    async def handle_read_day(
        self,
        entities: Dict[str, Any],
        user_courses: List[Dict],
    ) -> Dict[str, Any]:
        """
        Handle request to show specific day content.
        
        Returns:
            Dict with:
            - response: Text response
            - action: 'show_day' | 'ask_course' | 'ask_week_day' | 'none'
            - course: Matched course
            - week_number: Week number
            - day_number: Day number
        """
        week = entities.get('week_number')
        day = entities.get('day_number')
        course_name = entities.get('course_name', '').lower()
        
        if not week or not day:
            return {
                'response': "Which week and day would you like to see? Please specify (e.g., 'Week 2 Day 3').",
                'action': 'ask_week_day',
            }
        
        if not course_name:
            # Show all courses and ask which one
            courses_list = "\n".join([
                f"- **{c.get('course_name')}** ({c.get('duration_weeks', 0)} weeks)"
                for c in user_courses[:5]
            ])
            return {
                'response': f"Which course would you like to view? Your courses:\n\n{courses_list}",
                'action': 'ask_course',
            }
        
        # Find matching course
        matches = [
            c for c in user_courses
            if course_name in c.get('course_name', '').lower() or
               course_name in c.get('topic', '').lower()
        ]
        
        if not matches:
            return {
                'response': f"I couldn't find a course matching '{course_name}'.",
                'action': 'none',
            }
        
        course = matches[0]
        
        # Fetch day content (caller will handle actual fetch)
        return {
            'response': f"Fetching Week {week} Day {day} from **{course.get('course_name')}**...",
            'action': 'show_day',
            'course_id': course.get('id'),
            'course_name': course.get('course_name'),
            'week_number': week,
            'day_number': day,
        }
    
    async def handle_list_courses(
        self,
        user_courses: List[Dict],
    ) -> Dict[str, Any]:
        """
        Handle request to list all courses.
        
        Returns:
            Dict with courses list and summary
        """
        if not user_courses:
            return {
                'response': "You don't have any courses yet. Would you like to create one?",
                'action': 'none',
                'courses': [],
            }
        
        # Build course list with progress
        courses_summary = []
        for course in user_courses:
            progress = course.get('progress', 0)
            status = course.get('generation_status', 'ready')
            
            if status == 'generating':
                status_text = " Generating"
            elif progress >= 100:
                status_text = " Completed"
            else:
                status_text = f" {progress}% complete"
            
            courses_summary.append({
                'id': course.get('id'),
                'name': course.get('course_name'),
                'topic': course.get('topic'),
                'level': course.get('level'),
                'duration_weeks': course.get('duration_weeks'),
                'progress': progress,
                'status_text': status_text,
            })
        
        summary = "\n".join([
            f"**{c['name']}** - {c['duration_weeks']} weeks ({c['level']})\n  {c['status_text']}"
            for c in courses_summary
        ])
        
        return {
            'response': f"Here are your courses:\n\n{summary}",
            'action': 'list_courses',
            'courses': courses_summary,
        }


class MCQHelperHandler:
    """Handle MCQ question answering intents."""
    
    async def handle(
        self,
        entities: Dict[str, Any],
        user_courses: List[Dict],
    ) -> Dict[str, Any]:
        """
        Handle MCQ help request.
        
        Returns:
            Dict with:
            - response: Text response with explanation
            - action: 'show_mcq' | 'ask_context' | 'none'
            - course_id: Course ID
            - week_number: Week number
            - day_number: Day number
            - question_number: Question number (optional)
        """
        week = entities.get('week_number')
        day = entities.get('day_number')
        question_num = entities.get('question_number')
        course_name = entities.get('course_name', '').lower()
        
        if not week or not day:
            return {
                'response': "Which week and day's quiz question do you need help with? Please specify (e.g., 'Week 1 Day 3').",
                'action': 'ask_context',
            }
        
        if not course_name:
            courses_list = "\n".join([
                f"- **{c.get('course_name')}**"
                for c in user_courses[:5]
            ])
            return {
                'response': f"Which course? Your courses:\n\n{courses_list}",
                'action': 'ask_context',
            }
        
        # Find matching course
        matches = [
            c for c in user_courses
            if course_name in c.get('course_name', '').lower() or
               course_name in c.get('topic', '').lower()
        ]
        
        if not matches:
            return {
                'response': f"I couldn't find a course matching '{course_name}'.",
                'action': 'none',
            }
        
        course = matches[0]
        
        # Fetch and explain (caller will handle actual fetch)
        return {
            'response': f"Let me help you with the quiz question from Week {week} Day {day} of **{course.get('course_name')}**...",
            'action': 'show_mcq',
            'course_id': course.get('id'),
            'week_number': week,
            'day_number': day,
            'question_number': question_num,
        }


class ChatHandler:
    """Main chat handler that routes to specific handlers."""
    
    def __init__(self):
        """Initialize handlers."""
        self.course_creation = CourseCreationHandler()
        self.course_deletion = CourseDeletionHandler()
        self.course_reader = CourseReaderHandler()
        self.mcq_helper = MCQHelperHandler()
    
    async def handle(
        self,
        intent: str,
        entities: Dict[str, Any],
        missing_fields: List[str],
        user_courses: List[Dict],
        confirmation: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Route intent to appropriate handler.
        
        Returns:
            Dict with response, action, and any additional data
        """
        if intent == 'create_course':
            return await self.course_creation.handle(entities, missing_fields, user_courses)
        
        elif intent == 'delete_course':
            return await self.course_deletion.handle(entities, user_courses, confirmation)
        
        elif intent == 'read_day':
            return await self.course_reader.handle_read_day(entities, user_courses)
        
        elif intent == 'list_courses':
            return await self.course_reader.handle_list_courses(user_courses)
        
        elif intent == 'answer_mcq':
            return await self.mcq_helper.handle(entities, user_courses)
        
        else:
            return {
                'response': "I'm not sure I understand. Could you rephrase that?",
                'action': 'none',
            }
