"""
Hybrid retriever: pgvector (dense) + PostgreSQL full-text BM25 (sparse) + RRF fusion.
Returns top-N ranked chunk dicts ready for reranking.
"""
import logging
from typing import List, Optional, Dict, Any

from django.db import connection

logger = logging.getLogger(__name__)

RRF_K = 60  # RRF constant


class HybridRetriever:
    """Hybrid vector + BM25 retriever with RRF score fusion."""

    def hybrid_retrieve(
        self,
        query: str,
        top_k: int = 60,
        course_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        1. Embed query with MiniLM (384 dim)
        2. pgvector cosine similarity (dense)
        3. PostgreSQL tsvector BM25 rank (sparse)
        4. RRF fusion
        Returns up to top_k chunk dicts.
        """
        from services.llm.embeddings import EmbeddingService
        embedder = EmbeddingService()
        query_vec = embedder.embed_text(query, model="fallback")
        return self.retrieve_by_vector(query_vec, top_k=top_k, course_id=course_id, query_text=query)

    def retrieve_by_vector(
        self,
        query_vec: List[float],
        top_k: int = 60,
        course_id: Optional[str] = None,
        query_text: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Run dense + sparse retrieval and fuse with RRF."""
        vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"

        # Build optional course filter SQL
        course_filter = ""
        params_extra: list = []
        if course_id:
            course_filter = "AND c.metadata->>'course_id' = %s"
            params_extra = [str(course_id)]

        sql = f"""
WITH dense AS (
    SELECT
        c.id::text AS chunk_id,
        c.content,
        c.level,
        c.metadata,
        ROW_NUMBER() OVER (ORDER BY c.dense_embedding <=> %s::vector) AS dense_rank
    FROM chunks c
    WHERE c.dense_embedding IS NOT NULL {course_filter}
    ORDER BY c.dense_embedding <=> %s::vector
    LIMIT %s
),
sparse AS (
    SELECT
        c.id::text AS chunk_id,
        c.content,
        c.level,
        c.metadata,
        ROW_NUMBER() OVER (
            ORDER BY ts_rank(to_tsvector('english', c.content), plainto_tsquery('english', %s)) DESC
        ) AS sparse_rank
    FROM chunks c
    WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', %s) {course_filter}
    LIMIT %s
),
fused AS (
    SELECT
        COALESCE(d.chunk_id, s.chunk_id) AS chunk_id,
        COALESCE(d.content, s.content) AS content,
        COALESCE(d.level, s.level) AS level,
        COALESCE(d.metadata, s.metadata) AS metadata,
        COALESCE(1.0 / ({RRF_K} + d.dense_rank), 0) +
        COALESCE(1.0 / ({RRF_K} + s.sparse_rank), 0) AS rrf_score
    FROM dense d
    FULL OUTER JOIN sparse s ON d.chunk_id = s.chunk_id
)
SELECT chunk_id, content, level, metadata, rrf_score
FROM fused
ORDER BY rrf_score DESC
LIMIT %s
        """

        q_text = query_text or ""
        params = [vec_str] + params_extra + [vec_str, top_k, q_text, q_text] + params_extra + [top_k, top_k]

        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()

            return [
                {
                    "chunk_id": row[0],
                    "content": row[1],
                    "level": row[2],
                    "metadata": row[3] or {},
                    "score": float(row[4]),
                }
                for row in rows
            ]
        except Exception as exc:
            logger.exception("hybrid_retrieve() failed: %s", exc)
            return []
