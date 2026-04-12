"""
Conversation history helpers.
Saves messages with embeddings, retrieves recent history,
searches past conversations semantically.
Uses the existing Conversation model from apps.conversations.
"""
import asyncio
import uuid
import logging

from django.db import connection

from services.rag_pipeline.embedder import embedder

logger = logging.getLogger(__name__)


async def save_message(
    user_id: str,
    session_id: str,
    role: str,
    content: str,
    course_id: str = None,
):
    """
    Save a message to the conversations table with embedding.
    Uses raw SQL to avoid model import circular deps.
    """
    msg_id = str(uuid.uuid4())
    embedding = await embedder.aembed(content)
    vec_str = "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"

    def _insert():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO conversations
                    (id, user_id, session_id, role, content, embedding, course_id)
                VALUES
                    (%s, %s, %s, %s, %s, %s::vector, %s)
                """,
                [msg_id, user_id, session_id, role, content, vec_str, course_id],
            )

    await asyncio.to_thread(_insert)


async def get_recent_history(
    session_id: str,
    limit: int = 10,
) -> list:
    """Get last N messages for a session."""
    from apps.conversations.models import Conversation

    def _fetch():
        return list(
            Conversation.objects.filter(session_id=session_id)
            .order_by("created_at")[:limit]
        )

    messages = await asyncio.to_thread(_fetch)
    return [{"role": m.role, "content": m.content} for m in messages]


async def search_past_conversations(
    user_id: str,
    query: str,
    top_k: int = 3,
) -> list:
    """
    Find semantically similar past messages for context injection.
    Uses pgvector similarity on the conversations table.
    """
    query_embedding = await embedder.aembed(query)
    vec_str = "[" + ",".join(f"{v:.8f}" for v in query_embedding) + "]"

    def _search():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT role, content,
                    1 - (embedding <=> %s::vector) AS similarity
                FROM conversations
                WHERE user_id = %s
                    AND embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                [vec_str, user_id, vec_str, top_k],
            )
            return cursor.fetchall()

    rows = await asyncio.to_thread(_search)

    return [
        {"role": row[0], "content": row[1], "similarity": float(row[2])}
        for row in rows
    ]
