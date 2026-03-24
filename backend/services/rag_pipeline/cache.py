"""
Semantic cache service for query caching.
Uses vector similarity for cache hits with Redis for exact-match fallback.
"""
import logging
from typing import Optional, Dict, Any
import hashlib

from django.core.cache import cache as django_cache
from django.db import models

logger = logging.getLogger(__name__)

# Cache settings
CACHE_TTL = 3600  # 1 hour default TTL
SIMILARITY_THRESHOLD = 0.95  # High threshold for cache hits


class SemanticCache:
    """
    Two-tier cache system:
    1. Redis exact-match cache (fast)
    2. pgvector semantic cache (similarity-based)
    """

    def __init__(
        self,
        ttl: int = CACHE_TTL,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
    ):
        """
        Initialize semantic cache.
        
        Args:
            ttl: Time-to-live in seconds
            similarity_threshold: Minimum similarity for cache hit
        """
        self.ttl = ttl
        self.similarity_threshold = similarity_threshold

    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Get cached response for query.
        
        Args:
            query: Query text
            
        Returns:
            Cached response dict or None
        """
        # First, try exact match in Redis
        exact_hit = self._get_exact(query)
        if exact_hit:
            logger.debug("Exact cache hit for query")
            return exact_hit
        
        # Then, try semantic similarity in pgvector
        semantic_hit = self._get_semantic(query)
        if semantic_hit:
            logger.debug("Semantic cache hit for query (similarity: %.3f)", 
                        semantic_hit.get("similarity", 0))
            return semantic_hit
        
        return None

    def set(
        self,
        query: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Cache a query-response pair.
        
        Args:
            query: Query text
            response: Response text
            metadata: Optional metadata dict
        """
        # Store in Redis for exact match
        self._set_exact(query, response, metadata)
        
        # Store in pgvector for semantic search
        self._set_semantic(query, response, metadata)

    def _get_exact(self, query: str) -> Optional[Dict[str, Any]]:
        """Get from Redis exact-match cache."""
        cache_key = self._make_cache_key(query)
        
        cached = django_cache.get(cache_key)
        if cached:
            return {
                "hit": True,
                "type": "exact",
                "query": query,
                "response": cached.get("response"),
                "metadata": cached.get("metadata"),
            }
        
        return None

    def _set_exact(
        self,
        query: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Set in Redis exact-match cache."""
        cache_key = self._make_cache_key(query)
        
        django_cache.set(
            cache_key,
            {
                "response": response,
                "metadata": metadata,
            },
            self.ttl,
        )

    def _get_semantic(self, query: str) -> Optional[Dict[str, Any]]:
        """Get from pgvector semantic cache."""
        from django.db import connection
        from services.llm.embeddings import EmbeddingService
        
        embedder = EmbeddingService()
        query_vec = embedder.embed_text(query, model="fallback")
        
        vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"
        
        sql = """
        SELECT 
            id, query_text, response, 
            1 - (query_embedding <=> %s::vector) as similarity,
            hit_count
        FROM query_cache
        WHERE query_embedding IS NOT NULL
        ORDER BY query_embedding <=> %s::vector
        LIMIT 1
        """
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, [vec_str, vec_str])
                row = cursor.fetchone()
            
            if row:
                similarity = float(row[3])
                if similarity >= self.similarity_threshold:
                    # Increment hit count
                    self._increment_hit_count(row[0])
                    
                    return {
                        "hit": True,
                        "type": "semantic",
                        "query": row[1],
                        "response": row[2],
                        "similarity": similarity,
                        "hit_count": row[4] + 1,
                    }
        except Exception as e:
            logger.warning("Semantic cache lookup failed: %s", e)
        
        return None

    def _set_semantic(
        self,
        query: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Set in pgvector semantic cache."""
        from apps.cache.models import QueryCache
        from services.llm.embeddings import EmbeddingService
        
        embedder = EmbeddingService()
        embedding = embedder.embed_text(query, model="fallback")
        
        QueryCache.objects.create(
            query_text=query,
            query_embedding=embedding,
            response=response,
        )

    def _increment_hit_count(self, cache_id) -> None:
        """Increment hit count for a cache entry."""
        from apps.cache.models import QueryCache
        
        QueryCache.objects.filter(id=cache_id).update(
            hit_count=models.F("hit_count") + 1
        )

    def _make_cache_key(self, query: str) -> str:
        """Generate cache key from query."""
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        return f"semantic_cache:{query_hash}"

    def clear(self) -> int:
        """
        Clear all cache entries.
        
        Returns:
            Number of entries cleared
        """
        from apps.cache.models import QueryCache
        
        # Clear Redis
        # Note: This clears all cache, not just semantic cache
        # In production, use a dedicated Redis database or namespaced keys
        
        # Clear pgvector
        count, _ = QueryCache.objects.all().delete()
        
        return count

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Stats dict with counts and hit rates
        """
        from apps.cache.models import QueryCache
        from django.db.models import Sum, Avg, Count
        
        stats = QueryCache.objects.aggregate(
            total_entries=Count("id"),
            total_hits=Sum("hit_count"),
            avg_hits=Avg("hit_count"),
        )
        
        return {
            "total_entries": stats["total_entries"] or 0,
            "total_hits": stats["total_hits"] or 0,
            "average_hits_per_entry": round(stats["avg_hits"] or 0, 2),
        }


def get_semantic_cache() -> SemanticCache:
    """Factory function to get semantic cache instance."""
    return SemanticCache()


def cached_query(func):
    """
    Decorator for caching query responses.
    
    Usage:
        @cached_query
        def process_query(query: str) -> str:
            ...
    """
    def wrapper(query: str, *args, **kwargs):
        cache = get_semantic_cache()
        
        # Check cache
        cached = cache.get(query)
        if cached:
            return cached["response"]
        
        # Process query
        response = func(query, *args, **kwargs)
        
        # Cache response
        if response:
            cache.set(query, response)
        
        return response
    
    return wrapper
