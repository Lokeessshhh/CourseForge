"""
Semantic Cache for LearnAI AI Tutor.

Two-layer caching:
- Layer 1: Redis exact match (MD5 hash, 1hr TTL)
- Layer 2: pgvector semantic similarity (>0.97 cosine)

Cache hit returns stored response without LLM call.
"""
import asyncio
import hashlib
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from asgiref.sync import sync_to_async
from django.db.models.expressions import RawSQL
from django.utils import timezone

from services.chat.session import get_redis

logger = logging.getLogger(__name__)

# Cache configuration
EXACT_CACHE_TTL = 3600  # 1 hour for exact match
SEMANTIC_CACHE_TTL = 86400  # 24 hours for semantic cache
SIMILARITY_THRESHOLD = 0.97  # Cosine similarity threshold


async def check_cache(query: str) -> Dict[str, Any]:
    """
    Check cache for existing response.
    
    Two-layer check:
    1. Redis exact match (MD5 hash)
    2. pgvector semantic similarity (>0.97)
    
    Args:
        query: User query string
        
    Returns:
        Dict with:
        - hit: bool
        - response: str (if hit)
        - type: "exact" | "semantic" (if hit)
        - cache_key: str (for saving)
    """
    # Layer 1: Redis exact match
    md5_key = _make_md5_key(query)
    redis_client = get_redis()
    
    cached = redis_client.get(md5_key)
    if cached:
        logger.debug("Cache hit (exact): %s", md5_key)
        return {
            "hit": True,
            "response": cached,
            "type": "exact",
            "cache_key": md5_key,
        }
    
    # Layer 2: pgvector semantic similarity
    semantic_result = await _check_semantic_cache(query)
    if semantic_result["hit"]:
        logger.debug("Cache hit (semantic): similarity=%.2f", semantic_result.get("similarity", 0))
        return semantic_result
    
    # No hit
    return {
        "hit": False,
        "response": None,
        "type": None,
        "cache_key": md5_key,
    }


async def _check_semantic_cache(query: str) -> Dict[str, Any]:
    """
    Check pgvector for semantically similar cached queries.
    
    Args:
        query: User query
        
    Returns:
        Dict with hit info
    """
    from apps.cache.models import QueryCache
    from services.llm.embeddings import embed_text
    
    try:
        # Embed the query
        embedding = embed_text(query)
        
        @sync_to_async
        def _find_similar():
            # Find similar cached queries within last 24 hours
            cutoff = timezone.now() - timedelta(hours=24)
            
            similar = (
                QueryCache.objects.filter(
                    created_at__gte=cutoff,
                )
                .order_by(
                    RawSQL("query_embedding <=> %s::vector", [str(embedding)])
                )
                .first()
            )
            
            if not similar:
                return {"hit": False}
            
            # Calculate actual similarity
            # pgvector <=> returns cosine distance (0-2)
            # similarity = 1 - distance
            distance = _calculate_distance(embedding, similar.query_embedding)
            similarity = 1 - distance
            
            if similarity >= SIMILARITY_THRESHOLD:
                # Update hit count
                similar.hit_count += 1
                similar.last_hit_at = timezone.now()
                similar.save(update_fields=["hit_count", "last_hit_at"])
                
                return {
                    "hit": True,
                    "response": similar.response,
                    "type": "semantic",
                    "similarity": similarity,
                    "original_query": similar.query_text,
                    "cache_id": str(similar.id),
                }
            
            return {"hit": False}
        
        return await _find_similar()
    
    except Exception as exc:
        logger.warning("Semantic cache check failed: %s", exc)
        return {"hit": False}


def _calculate_distance(embedding1: List[float], embedding2: List[float]) -> float:
    """
    Calculate cosine distance between two embeddings.
    
    Args:
        embedding1: First embedding
        embedding2: Second embedding
        
    Returns:
        Cosine distance (0 = identical, 2 = opposite)
    """
    import numpy as np
    
    try:
        v1 = np.array(embedding1)
        v2 = np.array(embedding2)
        
        # Cosine similarity = dot(v1, v2) / (||v1|| * ||v2||)
        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        
        if norm1 == 0 or norm2 == 0:
            return 1.0  # Maximum distance for zero vectors
        
        similarity = dot_product / (norm1 * norm2)
        
        # Convert to distance (0-2 range)
        distance = 1 - similarity
        
        # Clamp to valid range
        return max(0.0, min(2.0, distance))
    
    except Exception:
        return 1.0


async def save_cache(
    query: str,
    response: str,
    course_id: Optional[str] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    """
    Save response to both cache layers.
    
    Args:
        query: User query
        response: Generated response
        course_id: Optional course ID
        sources: Optional source references
        
    Returns:
        True if saved successfully
    """
    from apps.cache.models import QueryCache
    from services.llm.embeddings import embed_text
    
    tasks = [
        # Save to Redis (exact match)
        _save_to_redis(query, response),
        # Save to pgvector (semantic)
        _save_to_semantic_cache(query, response, course_id, sources),
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Log any failures
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning("Cache save task %d failed: %s", i, result)
    
    return True


async def _save_to_redis(query: str, response: str) -> bool:
    """
    Save to Redis with MD5 key.
    
    Args:
        query: User query
        response: Generated response
        
    Returns:
        True if saved
    """
    redis_client = get_redis()
    md5_key = _make_md5_key(query)
    
    try:
        redis_client.set(md5_key, response, ex=EXACT_CACHE_TTL)
        logger.debug("Saved to Redis: %s", md5_key)
        return True
    except Exception as exc:
        logger.warning("Failed to save to Redis: %s", exc)
        return False


async def _save_to_semantic_cache(
    query: str,
    response: str,
    course_id: Optional[str],
    sources: Optional[List[Dict[str, Any]]],
) -> bool:
    """
    Save to pgvector semantic cache.
    
    Args:
        query: User query
        response: Generated response
        course_id: Optional course ID
        sources: Optional source references
        
    Returns:
        True if saved
    """
    from apps.cache.models import QueryCache
    from services.llm.embeddings import embed_text
    
    try:
        embedding = embed_text(query)
        
        @sync_to_async
        def _save():
            QueryCache.objects.create(
                query_text=query,
                query_embedding=embedding,
                response=response,
                course_id=course_id,
                sources=sources or [],
                hit_count=0,
            )
            return True
        
        await _save()
        logger.debug("Saved to semantic cache")
        return True
    
    except Exception as exc:
        logger.warning("Failed to save to semantic cache: %s", exc)
        return False


def _make_md5_key(query: str) -> str:
    """
    Generate MD5 key for exact match cache.
    
    Args:
        query: User query
        
    Returns:
        Redis key string
    """
    # Normalize query (lowercase, strip whitespace)
    normalized = query.lower().strip()
    
    # Generate MD5 hash
    md5_hash = hashlib.md5(normalized.encode()).hexdigest()
    
    return f"chat:cache:{md5_hash}"


def invalidate_cache(query: str) -> bool:
    """
    Invalidate cache for a specific query.
    
    Args:
        query: Query to invalidate
        
    Returns:
        True if invalidated
    """
    redis_client = get_redis()
    md5_key = _make_md5_key(query)
    
    try:
        redis_client.delete(md5_key)
        return True
    except Exception as exc:
        logger.warning("Failed to invalidate cache: %s", exc)
        return False


def invalidate_user_cache(user_id: str) -> int:
    """
    Invalidate all cache entries for a user.
    
    Note: This only clears Redis cache patterns.
    Semantic cache entries expire naturally.
    
    Args:
        user_id: User UUID
        
    Returns:
        Number of keys deleted
    """
    redis_client = get_redis()
    pattern = f"chat:*:{user_id}:*"
    
    try:
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
            return len(keys)
        return 0
    except Exception as exc:
        logger.warning("Failed to invalidate user cache: %s", exc)
        return 0


class CacheStats:
    """
    Track cache statistics for monitoring.
    """
    
    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Stats dict
        """
        from apps.cache.models import QueryCache
        
        redis_client = get_redis()
        
        # Redis stats
        redis_info = redis_client.info("memory")
        
        # Count cache keys
        cache_keys = len(redis_client.keys("chat:cache:*"))
        
        # Semantic cache stats
        total_semantic = QueryCache.objects.count()
        total_hits = sum(
            QueryCache.objects.values_list("hit_count", flat=True)
        )
        
        return {
            "redis": {
                "used_memory": redis_info.get("used_memory_human", "unknown"),
                "cache_keys": cache_keys,
            },
            "semantic": {
                "total_entries": total_semantic,
                "total_hits": total_hits,
                "hit_rate": round(total_hits / max(total_semantic, 1), 2),
            },
        }


__all__ = [
    "check_cache",
    "save_cache",
    "invalidate_cache",
    "invalidate_user_cache",
    "CacheStats",
]
