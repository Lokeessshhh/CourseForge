"""
Knowledge state tracking.
Per-concept confidence scores updated by quiz performance.
Uses the existing UserKnowledgeState model from apps.users.
"""
import asyncio
import logging

from django.db import connection

logger = logging.getLogger(__name__)


async def get_knowledge_state(user_id: str) -> dict:
    """
    Get the user's knowledge state as a dict: {concept: {confidence, times_practiced}}.
    """
    def _fetch():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT concept, confidence_score, times_practiced
                FROM user_knowledge_state
                WHERE user_id = %s
                """,
                [user_id],
            )
            return cursor.fetchall()

    rows = await asyncio.to_thread(_fetch)

    return {
        row[0]: {"confidence": row[1], "times_practiced": row[2]}
        for row in rows
    }


async def update_knowledge_state(
    user_id: str,
    concept: str,
    is_correct: bool,
) -> dict:
    """
    Update per-concept confidence based on quiz answer.
    Correct: +0.1 confidence
    Incorrect: -0.05 confidence
    Clamped to [0.0, 1.0].
    """
    score_change = 0.1 if is_correct else -0.05

    def _update():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_knowledge_state
                    (user_id, concept, confidence_score, times_practiced)
                VALUES
                    (%s, %s, %s, 1)
                ON CONFLICT (user_id, concept)
                DO UPDATE SET
                    confidence_score = LEAST(1.0, GREATEST(0.0,
                        user_knowledge_state.confidence_score + %s)),
                    times_practiced = user_knowledge_state.times_practiced + 1
                RETURNING confidence_score, times_practiced
                """,
                [user_id, concept, 0.5 if is_correct else 0.5, score_change],
            )
            return cursor.fetchone()

    row = await asyncio.to_thread(_update)

    if row:
        return {"confidence": row[0], "times_practiced": row[1]}
    return {}


async def get_struggling_concepts(user_id: str, threshold: float = 0.6) -> list:
    """Get concepts where user confidence is below threshold."""
    def _fetch():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT concept, confidence_score
                FROM user_knowledge_state
                WHERE user_id = %s AND confidence_score < %s
                ORDER BY confidence_score ASC
                """,
                [user_id, threshold],
            )
            return cursor.fetchall()

    rows = await asyncio.to_thread(_fetch)

    return [{"concept": row[0], "confidence": row[1]} for row in rows]


async def get_strong_concepts(user_id: str, threshold: float = 0.8) -> list:
    """Get concepts where user confidence is above threshold."""
    def _fetch():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT concept, confidence_score
                FROM user_knowledge_state
                WHERE user_id = %s AND confidence_score >= %s
                ORDER BY confidence_score DESC
                """,
                [user_id, threshold],
            )
            return cursor.fetchall()

    rows = await asyncio.to_thread(_fetch)

    return [{"concept": row[0], "confidence": row[1]} for row in rows]
