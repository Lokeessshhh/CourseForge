"""
Hybrid retriever: Zilliz Cloud (dense vector) + PostgreSQL BM25 (sparse) + RRF fusion.
Returns top-N ranked chunk dicts ready for reranking.
"""
import asyncio
import logging
from typing import List, Optional, Dict, Any
from collections import defaultdict

from django.db import connection

logger = logging.getLogger(__name__)

RRF_K = 60  # RRF constant

class HybridRetriever:
    """Hybrid vector (Zilliz) + BM25 (Postgres) retriever with RRF score fusion."""

    async def hybrid_retrieve(
        self,
        query: str,
        top_k: int = 60,
        course_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        1. Embed query
        2. Zilliz vector similarity (dense)
        3. PostgreSQL full-text BM25 (sparse)
        4. RRF fusion
        """
        from services.rag_pipeline.embedder import embedder
        from services.rag_pipeline.zilliz_client import zilliz

        # Ensure Zilliz is connected
        if not zilliz._connected:
            zilliz.connect()

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
        """Run dense (Zilliz) + sparse (Postgres) retrieval and fuse with RRF."""
        
        from services.rag_pipeline.zilliz_client import zilliz

        # --- 1. Dense Retrieval (Zilliz) ---
        filter_expr = None
        if course_id:
            # Zilliz filter syntax: meta_json contains course_id?
            # Since course_id is inside meta_json, we can't easily filter by it in Zilliz
            # unless we stored it as a separate field. 
            # For now, we fetch more results and filter in python if needed, 
            # or rely on the fact that we migrated everything.
            # TODO: Add 'course_id' as a separate field in Zilliz schema for filtering.
            pass

        dense_results = await asyncio.to_thread(
            zilliz.search, 
            query_vec, 
            top_k=top_k * 2  # Fetch more to account for overlap
        )

        # --- 2. Sparse Retrieval (Postgres BM25) ---
        sparse_results = await self._bm25_retrieve(query_text or "", top_k=top_k * 2, course_id=course_id)

        # --- 3. RRF Fusion ---
        fused = self._rrf_fusion(dense_results, sparse_results, top_k)

        # --- 4. Enrich with Document Info (Title/Topic) ---
        # Zilliz has content/metadata, but Postgres has Document title/topic
        fused = await self._enrich_with_document_info(fused)

        return fused

    async def _bm25_retrieve(self, query: str, top_k: int, course_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve using PostgreSQL BM25 (ParadeDB)."""
        if not query.strip():
            return []

        params = [query, query]
        course_filter = ""
        if course_id:
            course_filter = "AND c.metadata->>'course_id' = %s"
            params.append(str(course_id))
        params.append(top_k)

        sql = f"""
        SELECT 
            c.id::text AS chunk_id,
            c.content,
            c.level,
            c.metadata,
            d.title,
            d.topic
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', %s)
        {course_filter}
        ORDER BY ts_rank(to_tsvector('english', c.content), plainto_tsquery('english', %s)) DESC
        LIMIT %s
        """

        try:
            def _execute():
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
                    return cursor.fetchall()
            
            rows = await asyncio.to_thread(_execute)
            return [
                {
                    "chunk_id": row[0],
                    "content": row[1],
                    "level": row[2],
                    "metadata": row[3] or {},
                    "title": row[4] or "Document",
                    "topic": row[5] or "",
                    "sparse_rank": i + 1,
                    "dense_rank": None,
                }
                for i, row in enumerate(rows)
            ]
        except Exception as exc:
            logger.exception("BM25 retrieval failed: %s", exc)
            return []

    def _rrf_fusion(self, dense_results: List[Dict], sparse_results: List[Dict], top_k: int) -> List[Dict]:
        """Fuse results using Reciprocal Rank Fusion."""
        rank_map = {}

        # Process Dense (Zilliz) results
        # Zilliz results are already sorted by score
        for i, hit in enumerate(dense_results):
            cid = str(hit.get("doc_id") or hit.get("id"))
            if cid not in rank_map:
                rank_map[cid] = {
                    "chunk_id": cid,
                    "content": hit.get("content", ""),
                    "level": hit.get("level", 0),
                    "metadata": hit.get("metadata", {}),
                    "title": hit.get("title", "Document"),
                    "topic": hit.get("topic", ""),
                    "dense_rank": i + 1,
                    "sparse_rank": None,
                    "score": 0.0
                }
            else:
                rank_map[cid]["dense_rank"] = i + 1

        # Process Sparse (Postgres) results
        for i, hit in enumerate(sparse_results):
            cid = hit["chunk_id"]
            if cid not in rank_map:
                rank_map[cid] = {
                    "chunk_id": cid,
                    "content": hit["content"],
                    "level": hit["level"],
                    "metadata": hit["metadata"],
                    "title": hit["title"],
                    "topic": hit["topic"],
                    "dense_rank": None,
                    "sparse_rank": i + 1,
                    "score": 0.0
                }
            else:
                rank_map[cid]["sparse_rank"] = i + 1

        # Calculate RRF Score
        fused_list = []
        for item in rank_map.values():
            d_rank = item["dense_rank"] or 1000000
            s_rank = item["sparse_rank"] or 1000000
            
            rrf_score = (1.0 / (RRF_K + d_rank)) + (1.0 / (RRF_K + s_rank))
            item["score"] = rrf_score
            item["source"] = "hybrid"
            fused_list.append(item)

        # Sort by RRF score
        fused_list.sort(key=lambda x: x["score"], reverse=True)
        return fused_list[:top_k]

    async def _enrich_with_document_info(self, results: List[Dict]) -> List[Dict]:
        """
        Fetch title/topic from Postgres 'documents' table for chunks returned by Zilliz.
        Zilliz doesn't store document titles directly, only chunk content.
        """
        doc_ids = set()
        for item in results:
            # document_id is stored in Zilliz
            d_id = item.get("metadata", {}).get("document_id")
            if d_id:
                doc_ids.add(d_id)
            # Fallback: check if doc_id is in top level (from migration)
            elif item.get("document_id"):
                doc_ids.add(item["document_id"])

        if not doc_ids:
            return results

        doc_map = {}
        try:
            def _fetch_docs():
                with connection.cursor() as cursor:
                    # Use ANY for multiple IDs
                    cursor.execute(
                        "SELECT id, title, topic FROM documents WHERE id = ANY(%s)",
                        (list(doc_ids),)
                    )
                    return cursor.fetchall()
            
            rows = await asyncio.to_thread(_fetch_docs)
            doc_map = {str(row[0]): {"title": row[1], "topic": row[2]} for row in rows}
        except Exception as e:
            logger.warning("Failed to fetch document info: %s", e)

        # Update results
        for item in results:
            d_id = item.get("document_id") or item.get("metadata", {}).get("document_id")
            if d_id and d_id in doc_map:
                item["title"] = item.get("title") or doc_map[d_id].get("title", "Document")
                item["topic"] = item.get("topic") or doc_map[d_id].get("topic", "")
            else:
                item["title"] = item.get("title", "Document")
                item["topic"] = item.get("topic", "")

        return results


async def hybrid_retrieve(
    query: str,
    top_k: int = 60,
    course_id: Optional[str] = None,
    use_hyde: bool = True,
    use_decomposition: bool = True,
) -> List[Dict[str, Any]]:
    """
    Full async hybrid retrieval pipeline.
    Uses Zilliz for dense search.
    """
    from services.rag_pipeline.hyde import decompose_query, get_hyde_embedding
    from services.rag_pipeline.embedder import embedder

    retriever = HybridRetriever()

    if use_decomposition:
        sub_queries = await decompose_query(query)
    else:
        sub_queries = [query]

    logger.info("Retrieving for %d queries using Zilliz Cloud", len(sub_queries))

    all_results = []

    for q in sub_queries:
        # HyDE embedding
        if use_hyde:
            hyde_embedding = await get_hyde_embedding(q)
        else:
            hyde_embedding = await embedder.aembed(q)

        v_results = await retriever.retrieve_by_vector(
            hyde_embedding, top_k=20, course_id=course_id, query_text=q
        )
        all_results.extend(v_results)

    # Deduplicate
    seen = {}
    for doc in all_results:
        cid = doc["chunk_id"]
        if cid not in seen or doc["score"] > seen[cid]["score"]:
            seen[cid] = doc

    fused = list(seen.values())
    fused.sort(key=lambda x: x["score"], reverse=True)
    return fused[:60]
