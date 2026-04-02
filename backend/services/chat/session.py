"""
ChatSession management for LearnAI AI Tutor.

Handles session lifecycle:
- Creation and retrieval from Redis
- Message history management
- Session state persistence
- Scope tracking (global/course/day)
"""
import json
import logging
import uuid
from datetime import datetime, date
from typing import Any, Dict, List, Optional

import redis
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Redis client singleton
_redis_client = None


def get_redis() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.from_url(redis_url, decode_responses=True)
    return _redis_client


class ChatSession:
    """
    Manages a chat session with Redis-backed persistence.
    
    Session scopes:
    - global: All courses visible, general tutor mode
    - course: Single course context, week/day aware
    - day: Specific day content + quiz context
    
    Redis keys:
    - chat:session:{user_id}:{session_id} → session data (24hr TTL)
    - chat:active:{user_id} → list of active session IDs
    - chat:history:{user_id}:{course_id} → course-specific history
    """
    
    SESSION_TTL = 86400  # 24 hours
    MAX_MESSAGES = 20    # Keep last 20 messages in session
    
    SCOPE_GLOBAL = "global"
    SCOPE_COURSE = "course"
    SCOPE_DAY = "day"
    
    def __init__(
        self,
        user_id: str,
        session_id: str,
        scope: str = "global",
        course_id: Optional[str] = None,
        week: Optional[int] = None,
        day: Optional[int] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        created_at: Optional[datetime] = None,
        last_activity: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.user_id = user_id
        self.session_id = session_id
        self.scope = scope
        self.course_id = course_id
        self.week = week
        self.day = day
        self.messages = messages or []
        self.created_at = created_at or timezone.now()
        self.last_activity = last_activity or timezone.now()
        self.metadata = metadata or {}
    
    @classmethod
    async def get_or_create(
        cls,
        user_id: str,
        session_id: Optional[str] = None,
        scope: str = "global",
        course_id: Optional[str] = None,
        week: Optional[int] = None,
        day: Optional[int] = None,
    ) -> "ChatSession":
        """
        Get existing session from Redis or create new one.
        
        Args:
            user_id: User UUID
            session_id: Optional session ID (generates new if None)
            scope: Session scope (global/course/day)
            course_id: Course UUID for course/day scope
            week: Week number for day scope
            day: Day number for day scope
            
        Returns:
            ChatSession instance
        """
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        redis_client = get_redis()
        key = f"chat:session:{user_id}:{session_id}"
        
        # Try to get existing session
        data = redis_client.get(key)
        if data:
            try:
                parsed = json.loads(data)
                session = cls.from_dict(parsed)
                session.last_activity = timezone.now()
                return session
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("Failed to parse session data: %s", exc)
        
        # Create new session
        session = cls(
            user_id=user_id,
            session_id=session_id,
            scope=scope,
            course_id=course_id,
            week=week,
            day=day,
            created_at=timezone.now(),
            last_activity=timezone.now(),
        )
        
        # Add to active sessions list
        active_key = f"chat:active:{user_id}"
        redis_client.lpush(active_key, session_id)
        redis_client.ltrim(active_key, 0, 9)  # Keep last 10 active sessions
        redis_client.expire(active_key, cls.SESSION_TTL)
        
        await session.save_async()
        return session
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatSession":
        """Create session from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        
        last_activity = data.get("last_activity")
        if isinstance(last_activity, str):
            last_activity = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
        
        return cls(
            user_id=data["user_id"],
            session_id=data["session_id"],
            scope=data.get("scope", "global"),
            course_id=data.get("course_id"),
            week=data.get("week"),
            day=data.get("day"),
            messages=data.get("messages", []),
            created_at=created_at,
            last_activity=last_activity,
            metadata=data.get("metadata", {}),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for Redis storage."""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "scope": self.scope,
            "course_id": self.course_id,
            "week": self.week,
            "day": self.day,
            "messages": self.messages,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_activity": timezone.now().isoformat(),
            "metadata": self.metadata,
        }
    
    async def save_async(self) -> bool:
        """
        Save session to Redis with TTL.
        
        Returns:
            True if saved successfully
        """
        redis_client = get_redis()
        key = f"chat:session:{self.user_id}:{self.session_id}"
        
        try:
            redis_client.set(
                key,
                json.dumps(self.to_dict()),
                ex=self.SESSION_TTL,
            )
            return True
        except Exception as exc:
            logger.exception("Failed to save session: %s", exc)
            return False
    
    def save(self) -> bool:
        """Synchronous save for use in non-async contexts."""
        redis_client = get_redis()
        key = f"chat:session:{self.user_id}:{self.session_id}"
        
        try:
            redis_client.set(
                key,
                json.dumps(self.to_dict()),
                ex=self.SESSION_TTL,
            )
            return True
        except Exception as exc:
            logger.exception("Failed to save session: %s", exc)
            return False
    
    async def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Add a message to the session history.
        
        Args:
            role: Message role (user/assistant)
            content: Message content
            metadata: Optional metadata (tokens, sources, etc.)
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": timezone.now().isoformat(),
            "metadata": metadata or {},
        }
        
        self.messages.append(message)
        
        # Keep only last N messages
        if len(self.messages) > self.MAX_MESSAGES:
            self.messages = self.messages[-self.MAX_MESSAGES:]
        
        self.last_activity = timezone.now()
        await self.save_async()
    
    def get_recent_messages(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        Get the N most recent messages.
        
        Args:
            n: Number of messages to return
            
        Returns:
            List of message dictionaries
        """
        return self.messages[-n:] if self.messages else []
    
    def get_last_user_message(self) -> Optional[Dict[str, Any]]:
        """Get the most recent user message."""
        for msg in reversed(self.messages):
            if msg["role"] == "user":
                return msg
        return None
    
    def get_last_assistant_message(self) -> Optional[Dict[str, Any]]:
        """Get the most recent assistant message."""
        for msg in reversed(self.messages):
            if msg["role"] == "assistant":
                return msg
        return None

    def add_generating_course(self, course_id: str, course_name: str) -> None:
        """
        Add a course ID to the list of generating courses for this session.

        Args:
            course_id: Course UUID
            course_name: Course name
        """
        if "generating_courses" not in self.metadata:
            self.metadata["generating_courses"] = {}

        self.metadata["generating_courses"][course_id] = {
            "course_name": course_name,
            "started_at": timezone.now().isoformat(),
            "status": "generating",
        }
        self.last_activity = timezone.now()

    def update_generating_course_status(self, course_id: str, status: str, progress: int = 0) -> None:
        """
        Update the status of a generating course.

        Args:
            course_id: Course UUID
            status: Status (generating/ready/failed)
            progress: Progress percentage (0-100)
        """
        if "generating_courses" not in self.metadata:
            return

        if course_id in self.metadata["generating_courses"]:
            self.metadata["generating_courses"][course_id]["status"] = status
            self.metadata["generating_courses"][course_id]["progress"] = progress
            if status in ("ready", "failed"):
                self.metadata["generating_courses"][course_id]["completed_at"] = timezone.now().isoformat()
        self.last_activity = timezone.now()

    def remove_generating_course(self, course_id: str) -> None:
        """
        Remove a course from the generating list.

        Args:
            course_id: Course UUID
        """
        if "generating_courses" in self.metadata and course_id in self.metadata["generating_courses"]:
            del self.metadata["generating_courses"][course_id]
        self.last_activity = timezone.now()

    def get_generating_courses(self) -> Dict[str, Any]:
        """
        Get all generating courses for this session.

        Returns:
            Dictionary of course_id -> course info
        """
        return self.metadata.get("generating_courses", {})

    @staticmethod
    def get_redis() -> redis.Redis:
        """
        Get the Redis client.
        
        Returns:
            Redis client instance
        """
        return get_redis()

    async def clear(self) -> bool:
        """
        Clear session messages (keep session alive).
        
        Returns:
            True if cleared successfully
        """
        self.messages = []
        self.last_activity = timezone.now()
        return await self.save_async()
    
    async def delete(self) -> bool:
        """
        Delete session from Redis.
        
        Returns:
            True if deleted successfully
        """
        redis_client = get_redis()
        key = f"chat:session:{self.user_id}:{self.session_id}"
        
        try:
            redis_client.delete(key)
            
            # Remove from active sessions
            active_key = f"chat:active:{self.user_id}"
            redis_client.lrem(active_key, 0, self.session_id)
            
            return True
        except Exception as exc:
            logger.exception("Failed to delete session: %s", exc)
            return False
    
    @classmethod
    async def get_active_sessions(cls, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all active sessions for a user.
        
        Args:
            user_id: User UUID
            
        Returns:
            List of session summaries
        """
        redis_client = get_redis()
        active_key = f"chat:active:{user_id}"
        
        # Get session IDs
        session_ids = redis_client.lrange(active_key, 0, 9)
        sessions = []
        
        for sid in session_ids:
            key = f"chat:session:{user_id}:{sid}"
            data = redis_client.get(key)
            if data:
                try:
                    parsed = json.loads(data)
                    sessions.append({
                        "session_id": parsed["session_id"],
                        "scope": parsed.get("scope", "global"),
                        "course_id": parsed.get("course_id"),
                        "message_count": len(parsed.get("messages", [])),
                        "last_activity": parsed.get("last_activity"),
                        "last_message": parsed["messages"][-1]["content"][:100] if parsed.get("messages") else None,
                    })
                except (json.JSONDecodeError, KeyError):
                    continue
        
        return sessions
    
    def get_context_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the session context.
        
        Returns:
            Context summary dictionary
        """
        return {
            "session_id": self.session_id,
            "scope": self.scope,
            "course_id": self.course_id,
            "week": self.week,
            "day": self.day,
            "message_count": len(self.messages),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
        }


class DailySessionTracker:
    """
    Tracks daily chat activity for analytics and context.
    
    Redis key: chat:daily:{user_id}:{date}
    """
    
    TTL = 86400  # 24 hours
    
    @classmethod
    async def add_interaction(
        cls,
        user_id: str,
        query: str,
        response: str,
        course_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add an interaction to daily tracking.
        
        Args:
            user_id: User UUID
            query: User query (truncated to 100 chars)
            response: Assistant response (truncated to 200 chars)
            course_id: Optional course ID
            
        Returns:
            Updated daily stats
        """
        redis_client = get_redis()
        today = date.today().isoformat()
        key = f"chat:daily:{user_id}:{today}"
        
        # Get existing data
        data = redis_client.get(key)
        daily = json.loads(data) if data else {"messages": [], "message_count": 0}
        
        # Add new interaction
        daily["messages"].append({
            "q": query[:100],
            "a": response[:200],
            "course_id": course_id,
            "t": timezone.now().isoformat(),
        })
        daily["message_count"] = daily.get("message_count", 0) + 1
        daily["last_activity"] = timezone.now().isoformat()
        
        # Save with TTL
        redis_client.set(key, json.dumps(daily), ex=cls.TTL)
        
        return daily
    
    @classmethod
    async def get_daily_stats(cls, user_id: str) -> Dict[str, Any]:
        """
        Get daily chat statistics.
        
        Args:
            user_id: User UUID
            
        Returns:
            Daily stats dictionary
        """
        redis_client = get_redis()
        today = date.today().isoformat()
        key = f"chat:daily:{user_id}:{today}"
        
        data = redis_client.get(key)
        if data:
            return json.loads(data)
        
        return {"messages": [], "message_count": 0}
    
    @classmethod
    def get_message_count(cls, user_id: str) -> int:
        """
        Get message count for current day (synchronous).
        
        Args:
            user_id: User UUID
            
        Returns:
            Number of messages today
        """
        redis_client = get_redis()
        today = date.today().isoformat()
        key = f"chat:daily:{user_id}:{today}"
        
        data = redis_client.get(key)
        if data:
            return json.loads(data).get("message_count", 0)
        return 0
