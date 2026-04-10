"""
Hybrid retriever: pgvector (dense) + PostgreSQL full-text BM25 (sparse) + RRF fusion.
Returns top-N ranked chunk dicts ready for reranking.
Adapted from reference FastAPI repo to work with Django.
"""
import asyncio
import logging
from typing import List, Optional, Dict, Any

from django.db import connection

logger = logging.getLogger(__name__)

RRF_K = 60  # RRF constant


class HybridRetriever:
    """Hybrid vector + BM25 retriever with RRF score fusion."""

    async def hybrid_retrieve(
        self,
        query: str,
        top_k: int = 60,
        course_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        1. Embed query with embedding service
        2. pgvector cosine similarity (dense)
        3. PostgreSQL full-text BM25 rank (sparse)
        4. RRF fusion
        Returns up to top_k chunk dicts.
        """
        from services.rag_pipeline.embedder import embedder
        # Run sync embed in thread to avoid blocking
        query_vec = await asyncio.to_thread(embedder.embed, query)
        return await self.retrieve_by_vector(
            query_vec, top_k=top_k, course_id=course_id, query_text=query
        )

    async def retrieve_by_vector(
        self,
        query_vec: List[float],
        top_k: int = 60,
        course_id: Optional[str] = None,
        query_text: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Run dense + sparse retrieval and fuse with RRF."""
        vec_str = "[" + ",".join(f"{v:.8f}" for v in query_vec) + "]"

        # Build optional course filter SQL
        course_filter = ""
        if course_id:
            course_filter = "AND c.metadata->>'course_id' = %s"

        sql = f"""
WITH dense AS (
    SELECT
        c.id::text AS chunk_id,
        c.content,
        c.level,
        c.metadata,
        d.title,
        d.topic,
        ROW_NUMBER() OVER (ORDER BY c.dense_embedding <=> %s::vector) AS dense_rank
    FROM chunks c
    JOIN documents d ON c.document_id = d.id
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
        d.title,
        d.topic,
        ROW_NUMBER() OVER (
            ORDER BY ts_rank(to_tsvector('english', c.content), plainto_tsquery('english', %s)) DESC
        ) AS sparse_rank
    FROM chunks c
    JOIN documents d ON c.document_id = d.id
    WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', %s) {course_filter}
    LIMIT %s
),
fused AS (
    SELECT
        COALESCE(d.chunk_id, s.chunk_id) AS chunk_id,
        COALESCE(d.content, s.content) AS content,
        COALESCE(d.level, s.level) AS level,
        COALESCE(d.metadata, s.metadata) AS metadata,
        COALESCE(d.title, s.title) AS title,
        COALESCE(d.topic, s.topic) AS topic,
        COALESCE(1.0 / ({RRF_K} + d.dense_rank), 0) +
        COALESCE(1.0 / ({RRF_K} + s.sparse_rank), 0) AS rrf_score
    FROM dense d
    FULL OUTER JOIN sparse s ON d.chunk_id = s.chunk_id
)
SELECT chunk_id, content, level, metadata, rrf_score, title, topic
FROM fused
ORDER BY rrf_score DESC
LIMIT %s
        """

        q_text = query_text or ""
        params = []

        # Dense section params
        params.append(vec_str)  # ROW_NUMBER() OVER (... <=> %s::vector)
        if course_id:
            params.append(str(course_id))  # course_filter in WHERE
        params.append(vec_str)  # ORDER BY ... <=> %s::vector
        params.append(top_k)    # LIMIT %s

        # Sparse section params
        params.append(q_text)   # plainto_tsquery('english', %s) in ROW_NUMBER
        params.append(q_text)   # plainto_tsquery('english', %s) in WHERE
        if course_id:
            params.append(str(course_id))  # course_filter in WHERE
        params.append(top_k)    # LIMIT %s

        # Final LIMIT
        params.append(top_k)

        try:
            # Run sync DB query in thread pool to avoid blocking event loop
            def _execute_query():
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
                    return cursor.fetchall()

            rows = await asyncio.to_thread(_execute_query)

            return [
                {
                    "chunk_id": row[0],
                    "content": row[1],
                    "level": row[2],
                    "metadata": row[3] or {},
                    "score": float(row[4]),
                    "title": row[5] or "Document",
                    "topic": row[6] or "",
                    "source": "hybrid",
                }
                for row in rows
            ]
        except Exception as exc:
            logger.exception("hybrid_retrieve() failed: %s", exc)
            return []


async def hybrid_retrieve(
    query: str,
    top_k: int = 60,
    course_id: Optional[str] = None,
    use_hyde: bool = True,
    use_decomposition: bool = True,
) -> List[Dict[str, Any]]:
    """
    Full async hybrid retrieval pipeline:
    1. Query decomposition → multiple sub-queries
    2. HyDE → hypothetical answer embedding per sub-query
    3. Hybrid search (vector + BM25) for each sub-query
    4. Merge all results with RRF
    Returns top 60 candidates for reranker.
    """
    import asyncio
    from services.rag_pipeline.hyde import (
        decompose_query,
        get_hyde_embedding,
    )
    from services.rag_pipeline.embedder import embedder

    retriever = HybridRetriever()

    # Step 1 — Query decomposition
    if use_decomposition:
        sub_queries = await decompose_query(query)
    else:
        sub_queries = [query]

    logger.info("Retrieving for %d queries", len(sub_queries))

    # Step 2 — For each sub-query, run hybrid search
    all_vector_results = []
    all_keyword_results = []

    for q in sub_queries:
        # HyDE embedding for vector search
        if use_hyde:
            hyde_embedding = await get_hyde_embedding(q)
        else:
            hyde_embedding = await embedder.aembed(q)

        v_results = await retriever.retrieve_by_vector(
            hyde_embedding, top_k=20, course_id=course_id
        )
        k_results = await retriever.retrieve_by_vector(
            [0.0] * len(hyde_embedding),  # dummy — keyword search uses text
            top_k=20,
            course_id=course_id,
            query_text=q,
        )

        all_vector_results.extend(v_results)
        all_keyword_results.extend(k_results)

    # Step 3 — Deduplicate by chunk_id, keep highest score
    seen = {}
    for doc in all_vector_results + all_keyword_results:
        cid = doc["chunk_id"]
        if cid not in seen or doc["score"] > seen[cid]["score"]:
            seen[cid] = doc

    fused = list(seen.values())
    fused.sort(key=lambda x: x["score"], reverse=True)

    return fused[:60]
