"""
HyDE — Hypothetical Document Embeddings.
Generates a hypothetical ideal answer, then embeds it for retrieval.
"""
import logging
from typing import List

logger = logging.getLogger(__name__)


class HyDEGenerator:
    """
    Generate a hypothetical document answer to a query,
    then embed that hypothetical doc for retrieval.
    """

    def generate_embedding(self, query: str) -> List[float]:
        """
        1. Call Qwen to write an ideal answer for the query
        2. Embed the answer with MiniLM (384 dim)
        3. Return vector
        Falls back to direct query embedding on any error.
        """
        try:
            from services.llm.qwen_client import QwenClient
            from services.llm.embeddings import EmbeddingService

            client = QwenClient()
            prompt = (
                f"Write a detailed, accurate, educational answer to the following question. "
                f"Assume you are an expert and answer comprehensively:\n\n{query}"
            )
            hypothetical_doc = client.generate(prompt, max_tokens=512)

            embedder = EmbeddingService()
            return embedder.embed_text(hypothetical_doc, model="fallback")

        except Exception as exc:
            logger.warning("HyDE generation failed (%s). Falling back to direct query embedding.", exc)
            from services.llm.embeddings import EmbeddingService
            return EmbeddingService().embed_text(query, model="fallback")
