"""
Cohere Rerank v3.5 via OpenRouter: rerank top-60 chunks to top-10 by cross-encoder relevance.
FREE on OpenRouter - no cost for reranking!
"""
import logging
from typing import List, Dict, Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class Reranker:
    """Cross-encoder reranker for candidate chunks via OpenRouter."""

    def __init__(self):
        self.model = getattr(settings, "OPENROUTER_RERANKER_MODEL", "cohere/rerank-v3.5")
        self.api_key = getattr(settings, "OPENROUTER_API_KEY", "")
        self.base_url = getattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.url = f"{self.base_url.rstrip('/')}/rerank"

    async def rerank(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Rerank up to 60 chunks against the query using Cohere Rerank v3.5.
        Falls back to original RRF ordering if the API is unavailable.
        """
        if not chunks:
            return []

        if not self.api_key:
            logger.warning("OpenRouter API key not set, using original RRF ordering")
            return chunks[:top_k]

        try:
            # Prepare documents for Cohere rerank API
            documents = [c["content"] for c in chunks[:60]]  # Limit to top 60

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://github.com/your-org/ai-course-generator",
                "X-Title": "AI Course Generator",
                "Content-Type": "application/json",
            }

            payload = {
                "model": self.model,
                "query": query,
                "documents": documents,
                "top_n": min(top_k, len(documents)),
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.url,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

            # Extract results and map back to chunks
            results = data.get("results", [])
            
            # Create a mapping of index to score
            score_map = {result["index"]: result["relevance_score"] for result in results}

            # Add scores to chunks
            scored_chunks = []
            for idx, chunk in enumerate(chunks[:60]):
                score = score_map.get(idx, 0.0)
                chunk_copy = chunk.copy()
                chunk_copy["rerank_score"] = score
                scored_chunks.append((score, chunk_copy))

            # Sort by score descending
            scored_chunks.sort(key=lambda x: x[0], reverse=True)

            # Return top_k chunks
            return [chunk for _, chunk in scored_chunks[:top_k]]

        except Exception as exc:
            logger.warning("Reranking failed (%s). Using original order.", exc)
            return chunks[:top_k]


# Module-level singleton
reranker = Reranker()
