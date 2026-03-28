"""
4-Tier Memory Injection for LearnAI AI Tutor.

Memory tiers (from immediate to long-term):
- Tier 1: Current session messages (last 10 from Redis)
- Tier 2: Daily session summary (today's interactions from Redis)
- Tier 3: Semantic history (similar past conversations via pgvector)
- Tier 4: Knowledge state (weak concepts relevant to query)

All tiers load in parallel for performance.
"""
import asyncio
import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from asgiref.sync import sync_to_async
from django.db.models.expressions import RawSQL

from services.chat.session import ChatSession, get_redis

logger = logging.getLogger(__name__)


async def inject_memory(
    user_id: str,
    session_id: str,
    course_id: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build full memory context from 4 tiers.
    All tiers run in parallel.
    
    Args:
        user_id: User UUID
        session_id: Current session ID
        course_id: Optional course UUID for course-specific memory
        query: Current query for semantic matching
        
    Returns:
        Memory dict with:
        - recent_messages: last 10 from current session
        - session_summary: today's session summary
        - relevant_history: semantically similar past messages
        - struggling_concepts: weak concepts relevant to query
    """
    # Run all 4 tiers in parallel
    tier1, tier2, tier3, tier4 = await asyncio.gather(
        _tier1_session_messages(user_id, session_id),
        _tier2_redis_session(user_id),
        _tier3_semantic_history(user_id, course_id, query),
        _tier4_knowledge_state(user_id, query),
        return_exceptions=True,
    )
    
    # Handle exceptions
    if isinstance(tier1, Exception):
        logger.warning("Tier 1 memory failed: %s", tier1)
        tier1 = []
    if isinstance(tier2, Exception):
        logger.warning("Tier 2 memory failed: %s", tier2)
        tier2 = {}
    if isinstance(tier3, Exception):
        logger.warning("Tier 3 memory failed: %s", tier3)
        tier3 = []
    if isinstance(tier4, Exception):
        logger.warning("Tier 4 memory failed: %s", tier4)
        tier4 = []
    
    return {
        "recent_messages": tier1,
        "session_summary": tier2,
        "relevant_history": tier3,
        "struggling_concepts": tier4,
    }


async def _tier1_session_messages(user_id: str, session_id: str) -> List[Dict[str, Any]]:
    """
    Tier 1: Get recent messages from current session.
    
    Args:
        user_id: User UUID
        session_id: Session ID
        
    Returns:
        List of recent messages (max 10)
    """
    session = await ChatSession.get_or_create(user_id, session_id)
    return session.get_recent_messages(10)


async def _tier2_redis_session(user_id: str) -> Dict[str, Any]:
    """
    Tier 2: Get today's session summary from Redis.
    
    Args:
        user_id: User UUID
        
    Returns:
        Daily session summary dict
    """
    redis_client = get_redis()
    key = f"chat:daily:{user_id}:{date.today().isoformat()}"
    
    data = redis_client.get(key)
    if data:
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return {}
    
    return {}


async def _tier3_semantic_history(
    user_id: str,
    course_id: Optional[str],
    query: Optional[str],
) -> List[str]:
    """
    Tier 3: Find semantically similar past conversations using pgvector.
    
    Args:
        user_id: User UUID
        course_id: Optional course filter
        query: Query to match against (will be embedded)
        
    Returns:
        List of similar past conversation contents
    """
    if not query:
        return []
    
    from apps.conversations.models import Conversation
    from services.llm.embeddings import embed_text
    
    try:
        # Embed the query
        embedding = embed_text(query)
        
        @sync_to_async
        def _fetch_similar():
            # Build base queryset
            qs = Conversation.objects.filter(user_id=user_id)
            
            if course_id:
                qs = qs.filter(course_id=course_id)
            
            # Order by vector similarity (cosine distance)
            # pgvector uses <=> for cosine distance
            similar = list(
                qs.filter(role="user")  # Only match against user queries
                .exclude(embedding__isnull=True)
                .order_by(
                    RawSQL("embedding <=> %s::vector", [str(embedding)])
                )
                .values("content", "role")[:5]
            )
            
            return [s["content"] for s in similar]
        
        return await _fetch_similar()
    
    except Exception as exc:
        logger.warning("Semantic history lookup failed: %s", exc)
        return []


async def _tier4_knowledge_state(
    user_id: str,
    query: Optional[str],
) -> List[Dict[str, Any]]:
    """
    Tier 4: Find weak concepts that might be relevant to the query.
    
    Args:
        user_id: User UUID
        query: Current query (to match against concept names)
        
    Returns:
        List of struggling concepts with confidence scores
    """
    from apps.users.models import UserKnowledgeState
    
    @sync_to_async
    def _fetch_weak():
        # Get all weak concepts (confidence < 0.5)
        weak = list(
            UserKnowledgeState.objects.filter(
                user_id=user_id,
                confidence_score__lt=0.5,
            )
            .order_by("confidence_score")
            .values("concept", "confidence_score", "times_practiced", "last_error")[:10]
        )
        
        # If query provided, prioritize concepts mentioned in query
        if query and weak:
            query_lower = query.lower()
            # Split into relevant (mentioned in query) and other
            relevant = [w for w in weak if w["concept"].lower() in query_lower]
            other = [w for w in weak if w["concept"].lower() not in query_lower]
            
            # Return relevant first, then other
            result = relevant[:5] + other[:5]
            return [
                {
                    "concept": w["concept"],
                    "confidence": round(w["confidence_score"], 2),
                    "times_practiced": w["times_practiced"],
                    "last_error": w.get("last_error"),
                }
                for w in result
            ]
        
        return [
            {
                "concept": w["concept"],
                "confidence": round(w["confidence_score"], 2),
                "times_practiced": w["times_practiced"],
            }
            for w in weak
        ]
    
    return await _fetch_weak()


def build_memory_context_string(memory: Dict[str, Any]) -> str:
    """
    Build a formatted string from memory for LLM prompt injection.
    
    Args:
        memory: Memory dict from inject_memory
        
    Returns:
        Formatted memory string
    """
    parts = []
    
    # Tier 1: Recent messages
    recent = memory.get("recent_messages", [])
    if recent:
        parts.append("RECENT MESSAGES IN THIS SESSION:")
        for msg in recent[-6:]:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")[:200]
            parts.append(f"{role}: {content}")
        parts.append("")
    
    # Tier 2: Session summary
    summary = memory.get("session_summary", {})
    if summary:
        count = summary.get("message_count", 0)
        if count > 0:
            parts.append(f"MESSAGES TODAY: {count}")
    
    # Tier 3: Relevant history
    history = memory.get("relevant_history", [])
    if history:
        parts.append("\nSIMILAR PAST QUESTIONS:")
        for i, h in enumerate(history[:3], 1):
            parts.append(f"{i}. {h[:150]}")
    
    # Tier 4: Struggling concepts
    struggling = memory.get("struggling_concepts", [])
    if struggling:
        parts.append("\nSTUDENT IS STRUGGLING WITH:")
        for s in struggling[:5]:
            confidence_pct = int(s["confidence"] * 100)
            parts.append(f"- {s['concept']} ({confidence_pct}% confidence)")
    
    return "\n".join(parts)


async def update_memory_after_response(
    user_id: str,
    session_id: str,
    course_id: Optional[str],
    query: str,
    response: str,
) -> None:
    """
    Update memory systems after a response is generated.
    
    Updates:
    - Session messages (Tier 1)
    - Daily session tracker (Tier 2)
    - Knowledge state if concepts mentioned (Tier 4)
    
    Args:
        user_id: User UUID
        session_id: Session ID
        course_id: Optional course ID
        query: User's query
        response: Assistant's response
    """
    from services.chat.session import DailySessionTracker
    
    tasks = [
        # Update session messages
        _update_session_messages(user_id, session_id, query, response),
        # Update daily tracker
        DailySessionTracker.add_interaction(user_id, query, response, course_id),
        # Maybe update knowledge state
        _maybe_update_knowledge_state(user_id, query, response),
    ]
    
    # Run all updates in parallel
    await asyncio.gather(*tasks, return_exceptions=True)


async def _update_session_messages(
    user_id: str,
    session_id: str,
    query: str,
    response: str,
) -> None:
    """Add messages to session history."""
    session = await ChatSession.get_or_create(user_id, session_id)
    await session.add_message("user", query)
    await session.add_message("assistant", response)


async def _maybe_update_knowledge_state(
    user_id: str,
    query: str,
    response: str,
) -> None:
    """
    Update knowledge state if query mentions a weak concept.
    Engaging with a weak concept gives a small confidence boost.
    
    Args:
        user_id: User UUID
        query: User's query
        response: Assistant's response
    """
    from apps.users.models import UserKnowledgeState
    
    @sync_to_async
    def _update():
        # Find weak concepts mentioned in query
        weak = list(
            UserKnowledgeState.objects.filter(
                user_id=user_id,
                confidence_score__lt=0.5,
            )[:15]
        )
        
        query_lower = query.lower()
        updated = []
        
        for state in weak:
            if state.concept.lower() in query_lower:
                # Small confidence boost for engaging with weak concept
                state.confidence_score = min(1.0, state.confidence_score + 0.03)
                state.times_practiced += 1
                state.save(update_fields=["confidence_score", "times_practiced"])
                updated.append(state.concept)
        
        if updated:
            logger.info("Updated knowledge state for concepts: %s", updated)
        
        return updated
    
    try:
        await _update()
    except Exception as exc:
        logger.warning("Failed to update knowledge state: %s", exc)


class ConversationSummarizer:
    """
    Summarizes long conversations for efficient context.
    Used when conversation exceeds token limits.
    """
    
    @staticmethod
    async def summarize_session(session_id: str, user_id: str) -> str:
        """
        Generate a summary of the session for context compression.
        
        Args:
            session_id: Session ID
            user_id: User UUID
            
        Returns:
            Summary string
        """
        from services.llm.client import generate
        
        session = await ChatSession.get_or_create(user_id, session_id)
        messages = session.get_recent_messages(20)
        
        if not messages:
            return ""
        
        # Build conversation text
        conv_text = "\n".join([
            f"{m['role'].upper()}: {m['content']}"
            for m in messages
        ])
        
        prompt = f"""Summarize this conversation between a student and AI tutor in 2-3 sentences.
Focus on the main topics discussed and any concepts the student struggled with.

Conversation:
{conv_text[:2000]}

Summary:"""
        
        try:
            summary = await generate(prompt, system_type="chat", param_type="chat")
            return summary.strip()
        except Exception as exc:
            logger.warning("Failed to summarize session: %s", exc)
            return ""


# Export functions
__all__ = [
    "inject_memory",
    "build_memory_context_string",
    "update_memory_after_response",
    "ConversationSummarizer",
]
