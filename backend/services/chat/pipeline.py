"""
Full RAG Pipeline for LearnAI AI Tutor Chat.

Integrates:
- HyDE (Hypothetical Document Embeddings)
- Query Decomposition
- Hybrid Retrieval (pgvector + BM25 + RRF)
- Reranking (bge-reranker-v2-m3)
- Context building with user context + memory + sources
"""
import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from asgiref.sync import sync_to_async

from services.chat.context import UserContextLoader
from services.chat.memory import inject_memory, build_memory_context_string
from services.chat.cache import check_cache, save_cache
from services.chat.prompts import build_chat_prompt, get_system_prompt

logger = logging.getLogger(__name__)


async def run_chat_pipeline(
    query: str,
    user_id: str,
    session_id: str,
    scope: str = "global",
    course_id: Optional[str] = None,
    week: Optional[int] = None,
    day: Optional[int] = None,
    include_sources: bool = True,
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Run the full chat pipeline.
    
    Steps:
    1. Check semantic cache
    2. Load user context
    3. Inject 4-tier memory
    4. HyDE + Query decomposition
    5. Hybrid retrieval for all queries
    6. Merge and deduplicate
    7. Rerank top 60 → top 10
    8. Build final prompt
    9. Return prompt + sources + metadata
    
    Args:
        query: User's question
        user_id: User UUID
        session_id: Session UUID
        scope: Context scope (global/course/day)
        course_id: Optional course UUID
        week: Optional week number
        day: Optional day number
        include_sources: Whether to include source references
        
    Returns:
        Tuple of (prompt, sources, metadata)
    """
    import time
    start_time = time.time()
    
    metadata = {
        "cache_hit": False,
        "cache_type": None,
        "chunks_retrieved": 0,
        "context_scope": scope,
        "course_id": course_id,
    }
    
    # Step 1: Check cache
    cache_result = await check_cache(query)
    if cache_result["hit"]:
        metadata["cache_hit"] = True
        metadata["cache_type"] = cache_result["type"]
        # Return cached response with empty sources
        return cache_result["response"], [], metadata
    
    # Step 2: Load user context (parallel with memory)
    context_loader = UserContextLoader()
    
    context_task = context_loader.load_full_context(
        user_id=user_id,
        scope=scope,
        course_id=course_id,
        week=week,
        day=day,
    )
    
    memory_task = inject_memory(
        user_id=user_id,
        session_id=session_id,
        course_id=course_id,
        query=query,
    )
    
    # Run context and memory loading in parallel
    context, memory = await asyncio.gather(context_task, memory_task)
    
    # Build context string
    context_string = context_loader.build_context_string(context)
    
    # Step 3: HyDE + Query decomposition + Retrieval
    retrieval_result = await _run_retrieval_pipeline(query, course_id)
    
    chunks = retrieval_result["chunks"]
    source_refs = retrieval_result["sources"]
    
    metadata["chunks_retrieved"] = len(chunks)
    metadata["hyde_generated"] = retrieval_result.get("hyde_generated", False)
    metadata["sub_queries"] = retrieval_result.get("sub_queries", [])
    
    # Step 4: Build final prompt
    prompt = build_chat_prompt(
        query=query,
        context=context_string,
        memory=memory,
        sources=[c["content"] for c in chunks[:5]],
        scope=scope,
    )
    
    metadata["latency_ms"] = int((time.time() - start_time) * 1000)
    
    return prompt, source_refs if include_sources else [], metadata


async def _run_retrieval_pipeline(
    query: str,
    course_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the retrieval pipeline: HyDE + Decomposition + Hybrid + Rerank.
    
    Args:
        query: User query
        course_id: Optional course filter
        
    Returns:
        Dict with chunks, sources, and metadata
    """
    from services.rag_pipeline.retriever import HybridRetriever
    from services.rag_pipeline.reranker import Reranker
    
    # Step 1: Generate HyDE embedding
    hyde_embedding = await _generate_hyde_embedding(query)
    
    # Step 2: Decompose query into sub-questions
    sub_queries = await _decompose_query(query)
    
    # Step 3: Build all queries to retrieve
    all_queries = [query]
    if hyde_embedding:
        all_queries.append("hyde")  # Marker for HyDE embedding
    all_queries.extend(sub_queries)
    
    # Step 4: Run hybrid retrieval for each query
    retriever = HybridRetriever()
    
    retrieval_tasks = []

    # Main query retrieval
    retrieval_tasks.append(retriever.hybrid_retrieve(query, top_k=20, course_id=course_id))

    # HyDE retrieval (if available)
    if hyde_embedding:
        retrieval_tasks.append(retriever.retrieve_by_vector(hyde_embedding, top_k=20, course_id=course_id))

    # Sub-query retrievals
    for sq in sub_queries[:3]:  # Limit to 3 sub-queries
        retrieval_tasks.append(retriever.hybrid_retrieve(sq, top_k=15, course_id=course_id))
    
    # Run all retrievals in parallel
    all_results = await asyncio.gather(*retrieval_tasks, return_exceptions=True)
    
    # Step 5: Merge and deduplicate
    merged_chunks = _merge_chunks(all_results)
    
    # Step 6: Rerank top 60 → top 10
    reranker = Reranker()
    top_chunks = await sync_to_async(reranker.rerank)(query, merged_chunks[:60], top_k=10)
    
    # Build source references
    sources = [
        {
            "chunk_id": c.get("chunk_id"),
            "title": c.get("metadata", {}).get("title"),
            "page": c.get("metadata", {}).get("page"),
            "content_preview": c.get("content", "")[:200],
            "score": c.get("rerank_score") or c.get("score"),
        }
        for c in top_chunks
    ]
    
    return {
        "chunks": top_chunks,
        "sources": sources,
        "hyde_generated": hyde_embedding is not None,
        "sub_queries": sub_queries,
    }


async def _generate_hyde_embedding(query: str) -> Optional[List[float]]:
    """
    Generate HyDE embedding for the query.
    
    Args:
        query: User query
        
    Returns:
        Embedding vector or None on failure
    """
    from services.rag_pipeline.hyde import HyDEGenerator
    
    @sync_to_async
    def _generate():
        try:
            hyde = HyDEGenerator()
            return hyde.generate_embedding(query)
        except Exception as exc:
            logger.warning("HyDE generation failed: %s", exc)
            return None
    
    return await _generate()


async def _decompose_query(query: str) -> List[str]:
    """
    Decompose complex query into sub-questions.
    
    Args:
        query: User query
        
    Returns:
        List of sub-questions
    """
    from services.rag_pipeline.query_decompose import QueryDecomposer
    
    @sync_to_async
    def _decompose():
        try:
            decomposer = QueryDecomposer()
            result = decomposer.decompose(query)
            return result.get("sub_questions", [])
        except Exception as exc:
            logger.warning("Query decomposition failed: %s", exc)
            return []
    
    return await _decompose()


def _merge_chunks(all_results: List[Any]) -> List[Dict[str, Any]]:
    """
    Merge and deduplicate chunks from multiple retrievals.
    
    Args:
        all_results: List of retrieval results (may include exceptions)
        
    Returns:
        Deduplicated list of chunks
    """
    seen_ids = set()
    merged = []
    
    for result in all_results:
        # Skip exceptions
        if isinstance(result, Exception):
            continue
        
        # Skip None or empty results
        if not result:
            continue
        
        for chunk in result:
            chunk_id = chunk.get("chunk_id")
            if chunk_id and chunk_id not in seen_ids:
                seen_ids.add(chunk_id)
                merged.append(chunk)
    
    return merged


async def generate_streaming_response(
    prompt: str,
    system_type: str = "tutor",
) -> AsyncGenerator[str, None]:
    """
    Generate streaming response from LLM.
    
    Args:
        prompt: Full prompt with context
        system_type: System prompt type
        
    Yields:
        Tokens as they arrive
    """
    from services.llm.client import stream_generate
    
    async for token in stream_generate(
        prompt=prompt,
        system_type=system_type,
        extra_context="",
        conversation_history=None,
    ):
        yield token


async def generate_response(
    prompt: str,
    system_type: str = "tutor",
) -> str:
    """
    Generate non-streaming response from LLM.
    
    Args:
        prompt: Full prompt with context
        system_type: System prompt type
        
    Returns:
        Complete response string
    """
    from services.llm.client import generate
    
    response = await generate(
        prompt=prompt,
        system_type=system_type,
        param_type="chat",
    )
    
    return response


async def save_conversation(
    user_id: str,
    session_id: str,
    course_id: Optional[str],
    query: str,
    response: str,
    sources: List[Dict[str, Any]],
) -> None:
    """
    Save conversation to database and update caches.
    
    Args:
        user_id: User UUID
        session_id: Session UUID
        course_id: Optional course UUID
        query: User query
        response: Assistant response
        sources: Source references
    """
    from apps.conversations.models import Conversation
    from services.llm.embeddings import embed_text
    from services.chat.memory import update_memory_after_response
    
    # Embed the query for semantic search
    query_embedding = embed_text(query)
    
    @sync_to_async
    def _save():
        # Save user message
        Conversation.objects.create(
            user_id=user_id,
            session_id=session_id,
            course_id=course_id,
            role="user",
            content=query,
            embedding=query_embedding,
        )
        
        # Save assistant message
        Conversation.objects.create(
            user_id=user_id,
            session_id=session_id,
            course_id=course_id,
            role="assistant",
            content=response,
        )
    
    # Run all post-response tasks in parallel
    await asyncio.gather(
        _save(),
        save_cache(query, response, course_id, sources),
        update_memory_after_response(user_id, session_id, course_id, query, response),
        return_exceptions=True,
    )


__all__ = [
    "run_chat_pipeline",
    "generate_streaming_response",
    "generate_response",
    "save_conversation",
]
