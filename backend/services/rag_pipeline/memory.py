"""
Conversation memory service with vector-based semantic search.
Implements Tier 3 memory: long-term semantic memory with pgvector.
"""
import logging
from typing import List, Optional, Dict, Any

from django.db import connection

logger = logging.getLogger(__name__)


class ConversationMemory:
    """
    Manages conversation history with semantic search capabilities.
    Provides both short-term (session) and long-term (semantic) memory.
    """

    def __init__(self, similarity_threshold: float = 0.7, max_short_term: int = 10):
        """
        Initialize memory service.
        
        Args:
            similarity_threshold: Minimum cosine similarity for semantic recall
            max_short_term: Maximum messages in short-term buffer
        """
        self.similarity_threshold = similarity_threshold
        self.max_short_term = max_short_term

    def get_session_history(
        self,
        user_id: str,
        session_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history for a specific session.
        
        Args:
            user_id: User ID
            session_id: Session ID
            limit: Maximum messages to return
            
        Returns:
            List of message dicts with role and content
        """
        from apps.conversations.models import Conversation
        
        messages = Conversation.objects.filter(
            user_id=user_id,
            session_id=session_id,
        ).order_by("-created_at")[:limit]
        
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in reversed(messages)
        ]

    def get_semantic_memory(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
        course_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve semantically similar past conversations.
        
        Args:
            query: Query text to find similar conversations
            user_id: User ID
            top_k: Number of results to return
            course_id: Optional course context filter
            
        Returns:
            List of similar conversation snippets
        """
        from services.llm.embeddings import EmbeddingService
        
        embedder = EmbeddingService()
        query_vec = embedder.embed_text(query, model="fallback")
        
        vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"
        
        # Build SQL with optional course filter
        course_filter = ""
        params_extra = []
        if course_id:
            course_filter = "AND course_id = %s"
            params_extra = [str(course_id)]
        
        sql = f"""
        SELECT 
            id, role, content, created_at, 
            1 - (embedding <=> %s::vector) as similarity
        FROM conversations
        WHERE user_id = %s
          AND embedding IS NOT NULL
          {course_filter}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """
        
        params = [vec_str, str(user_id)] + params_extra + [vec_str, top_k]
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
            
            return [
                {
                    "id": str(row[0]),
                    "role": row[1],
                    "content": row[2],
                    "created_at": row[3].isoformat() if row[3] else None,
                    "similarity": float(row[4]),
                }
                for row in rows
                if float(row[4]) >= self.similarity_threshold
            ]
        except Exception as e:
            logger.exception("Semantic memory retrieval failed: %s", e)
            return []

    def add_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        course_id: Optional[str] = None,
        module_context: Optional[str] = None,
    ) -> Any:
        """
        Add a message to conversation memory with embedding.
        
        Args:
            user_id: User ID
            session_id: Session ID
            role: Message role (user/assistant)
            content: Message content
            course_id: Optional course context
            module_context: Optional module context
            
        Returns:
            Created Conversation instance
        """
        from apps.conversations.models import Conversation
        from services.llm.embeddings import EmbeddingService
        
        # Generate embedding for semantic search
        embedder = EmbeddingService()
        embedding = embedder.embed_text(content, model="fallback")
        
        conversation = Conversation.objects.create(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            embedding=embedding,
            course_id=course_id,
            module_context=module_context,
        )
        
        return conversation

    def summarize_session(self, session_id: str, user_id: str) -> str:
        """
        Create a summary of a conversation session.
        
        Args:
            session_id: Session ID
            user_id: User ID
            
        Returns:
            Summary text
        """
        from apps.conversations.models import Conversation
        
        messages = Conversation.objects.filter(
            user_id=user_id,
            session_id=session_id,
        ).order_by("created_at")
        
        if not messages.exists():
            return ""
        
        # Build conversation text
        conv_text = "\n".join([
            f"{msg.role}: {msg.content}"
            for msg in messages
        ])
        
        # Mark messages as summarized
        messages.update(is_summarized=True)
        
        return conv_text

    def get_context_window(
        self,
        user_id: str,
        session_id: str,
        current_query: str,
        max_messages: int = 5,
        include_semantic: bool = True,
    ) -> List[Dict[str, str]]:
        """
        Get context window for a query combining session and semantic memory.
        
        Args:
            user_id: User ID
            session_id: Current session ID
            current_query: The current query
            max_messages: Maximum messages in context
            include_semantic: Whether to include semantic memory
            
        Returns:
            List of context messages
        """
        context = []
        
        # Get recent session history
        session_history = self.get_session_history(
            user_id=user_id,
            session_id=session_id,
            limit=max_messages,
        )
        context.extend(session_history)
        
        # Add semantic memory if enabled and room available
        if include_semantic and len(context) < max_messages:
            semantic = self.get_semantic_memory(
                query=current_query,
                user_id=user_id,
                top_k=max_messages - len(context),
            )
            
            # Add semantic memories that aren't duplicates
            session_contents = {m.get("content", "") for m in context}
            for mem in semantic:
                if mem.get("content") not in session_contents:
                    context.append({
                        "role": "memory",
                        "content": f"[Past conversation] {mem['content']}",
                    })
        
        return context[:max_messages]

    def clear_session(self, session_id: str, user_id: str) -> int:
        """
        Clear all messages for a session.
        
        Args:
            session_id: Session ID
            user_id: User ID
            
        Returns:
            Number of messages deleted
        """
        from apps.conversations.models import Conversation
        
        deleted, _ = Conversation.objects.filter(
            user_id=user_id,
            session_id=session_id,
        ).delete()
        
        return deleted


def get_memory_service() -> ConversationMemory:
    """Factory function to get memory service instance."""
    return ConversationMemory()
