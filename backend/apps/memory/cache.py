"""
Redis semantic cache.
1. Embed the query
2. Compare against all cached query embeddings in Redis
3. If cosine similarity > 0.97, return cached response instantly
"""
import hashlib
import json
import logging

import numpy as np
from django.core.cache import cache

from services.rag_pipeline.embedder import embedder

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.97
CACHE_TTL = 3600  # 1 hour
MAX_CACHE_ENTRIES = 1000


def _cosine_similarity(a: list, b: list) -> float:
    """Calculate cosine similarity between two vectors."""
    a_arr = np.array(a, dtype=np.float32)
    b_arr = np.array(b, dtype=np.float32)
    dot = np.dot(a_arr, b_arr)
    norm = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    if norm == 0:
        return 0.0
    return float(dot / norm)


async def get_cached_response(query: str) -> str | None:
    """
    Semantic cache lookup.
    Embeds query, compares against all cached entries, returns hit if similar enough.
    """
    try:
        query_embedding = await embedder.aembed(query)

        # Get all cached keys
        cache_keys = cache.keys("cache:entry:*")
        if not cache_keys:
            return None

        best_similarity = 0.0
        best_response = None

        for key in cache_keys[:MAX_CACHE_ENTRIES]:
            cached_data = cache.get(key)
            if not cached_data:
                continue
            try:
                entry = json.loads(cached_data)
                cached_embedding = entry["embedding"]
                similarity = _cosine_similarity(query_embedding, cached_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_response = entry["response"]
            except Exception:
                continue

        if best_similarity >= SIMILARITY_THRESHOLD and best_response:
            logger.info("Cache HIT (similarity: %.3f)", best_similarity)
            return best_response

        logger.info("Cache MISS (best similarity: %.3f)", best_similarity)
        return None

    except Exception as e:
        logger.warning("Cache lookup failed: %s", e)
        return None


async def set_cached_response(query: str, response: str):
    """Save query + embedding + response to Redis cache."""
    try:
        query_embedding = await embedder.aembed(query)
        cache_key = f"cache:entry:{hashlib.md5(query.encode()).hexdigest()}"

        entry = {
            "query": query,
            "embedding": query_embedding,
            "response": response,
        }
        cache.set(cache_key, json.dumps(entry), CACHE_TTL)
        logger.info("Cache SET for query: %s…", query[:50])

    except Exception as e:
        logger.warning("Cache save failed: %s", e)


async def get_session_context(session_id: str) -> dict | None:
    """Get session context from cache."""
    key = f"session:{session_id}"
    data = cache.get(key)
    if data:
        return json.loads(data)
    return None


async def set_session_context(session_id: str, context: dict, ttl: int = 86400):
    """Save session context to cache."""
    key = f"session:{session_id}"
    cache.set(key, json.dumps(context), ttl)
