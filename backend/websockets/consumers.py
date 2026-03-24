"""
WebSocket consumers for real-time chat.
Each course has its own chat with AI tutor context.
Uses vLLM server via services/llm/client.py for streaming responses.
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


class CourseChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for course-specific AI tutor chat.
    Injects memory, RAG retrieval, and streams responses from vLLM.
    """

    async def connect(self):
        """Handle WebSocket connection."""
        self.course_id = self.scope["url_route"]["kwargs"]["course_id"]
        self.user = self.scope.get("user")

        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        self.room_group_name = f"chat_{self.course_id}"

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Load course context
        self.course_context = await self._load_course_context()

        # Load conversation history
        self.conversation_history = await self._load_conversation_history()

        logger.info("WebSocket connected for course %s, user %s", self.course_id, self.user.id)

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

        logger.info("WebSocket disconnected for course %s", self.course_id)

    async def receive(self, text_data):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(text_data)
            message = data.get("message", "")

            if not message:
                return

            # Save user message to conversation
            await self._save_message("user", message)

            # Add to conversation history
            self.conversation_history.append({
                "role": "user",
                "content": message,
            })

            # Stream AI response
            full_response = await self._stream_generate_response(message)

            # Save AI response
            await self._save_message("assistant", full_response)

            # Add to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": full_response,
            })

            # Keep only last 10 messages in history
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]

            # Update knowledge state
            await self._update_knowledge_from_chat(message, full_response)

            # Send completion signal
            await self.send(text_data=json.dumps({
                "type": "complete",
            }))

        except Exception as exc:
            logger.exception("Error processing message: %s", exc)
            await self.send(text_data=json.dumps({
                "error": "Failed to process message"
            }))

    async def _load_course_context(self):
        """Load course context and user knowledge state."""
        from apps.courses.models import Course, CourseProgress

        @database_sync_to_async
        def get_context():
            try:
                course = Course.objects.get(id=self.course_id)
                progress = CourseProgress.objects.filter(
                    user=self.user,
                    course=course
                ).first()

                # Get user knowledge state
                from apps.users.models import UserKnowledgeState
                knowledge = UserKnowledgeState.objects.filter(user=self.user)
                weak_concepts = [
                    ks.concept_tag for ks in knowledge
                    if ks.confidence_score < 0.5
                ]

                return {
                    "course_name": course.course_name,
                    "topic": course.topic,
                    "level": course.level,
                    "current_week": progress.current_week if progress else 1,
                    "current_day": progress.current_day if progress else 1,
                    "weak_concepts": weak_concepts,
                }
            except Exception:
                return {}

        return await get_context()

    async def _load_conversation_history(self):
        """Load last 10 messages from conversation history."""
        from apps.chat.models import Conversation

        @database_sync_to_async
        def get_history():
            try:
                conversations = Conversation.objects.filter(
                    user=self.user,
                    course_id=self.course_id,
                ).order_by("-created_at")[:10]

                # Reverse to get chronological order
                history = list(reversed(list(conversations.values_list("content", flat=True))))
                return history
            except Exception:
                return []

        history = await get_history()
        # Convert to message format
        messages = []
        for i, content in enumerate(history):
            role = "user" if i % 2 == 0 else "assistant"
            messages.append({"role": role, "content": content})
        return messages

    async def _stream_generate_response(self, message: str) -> str:
        """
        Stream AI response using vLLM server.
        Yields tokens as they arrive and returns full response.
        """
        from services.llm.client import stream_generate

        # Build extra context
        extra_context = self._build_extra_context()

        full_response = ""

        try:
            async for token in stream_generate(
                prompt=message,
                system_type="chat",
                extra_context=extra_context,
                conversation_history=self.conversation_history[:-1],  # Exclude current message
            ):
                full_response += token
                # Send token to client
                await self.send(text_data=json.dumps({
                    "type": "token",
                    "content": token,
                }))

            return full_response

        except Exception as exc:
            logger.exception("Error streaming response: %s", exc)
            error_msg = "I apologize, I encountered an error. Please try again."
            await self.send(text_data=json.dumps({
                "type": "error",
                "content": error_msg,
            }))
            return error_msg

    def _build_extra_context(self) -> str:
        """Build extra context string for LLM."""
        context_parts = []

        # Course info
        if self.course_context:
            context_parts.append(
                f"Course: {self.course_context.get('course_name', 'Unknown')}\n"
                f"Topic: {self.course_context.get('topic', 'programming')}\n"
                f"Level: {self.course_context.get('level', 'beginner')}\n"
                f"Progress: Week {self.course_context.get('current_week', 1)}, "
                f"Day {self.course_context.get('current_day', 1)}"
            )

            weak = self.course_context.get('weak_concepts', [])
            if weak:
                context_parts.append(f"Student's weak areas: {', '.join(weak)}")

        return "\n\n".join(context_parts)

    @database_sync_to_async
    def _save_message(self, role: str, content: str):
        """Save message to conversations table."""
        from apps.chat.models import Conversation

        try:
            Conversation.objects.create(
                user=self.user,
                course_id=self.course_id,
                role=role,
                content=content,
            )
        except Exception as exc:
            logger.warning("Could not save message: %s", exc)

    @database_sync_to_async
    def _update_knowledge_from_chat(self, user_message: str, ai_response: str):
        """Update user knowledge state based on chat."""
        # Simple heuristic: extract concepts from user questions
        # In production, use NLP to extract concepts
        pass

    async def chat_message(self, event):
        """Handle messages from channel layer."""
        message = event["message"]
        await self.send(text_data=json.dumps({
            "type": "message",
            "content": message,
        }))
