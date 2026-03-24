"""
Embedding service using sentence-transformers locally.
Primary model: all-MiniLM-L6-v2 (384 dim) for:
- conversation embeddings
- semantic cache embeddings
- RAG document embeddings
"""
import logging
from typing import List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# Singleton model instance
_model = None


def _get_model():
    """Lazy-load the sentence-transformers model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        model_name = getattr(settings, "EMBEDDING_MODEL_FALLBACK", "sentence-transformers/all-MiniLM-L6-v2")
        logger.info("Loading embedding model: %s", model_name)
        _model = SentenceTransformer(model_name)
    return _model


class EmbeddingService:
    """
    Unified embedding service using sentence-transformers.
    Uses all-MiniLM-L6-v2 (384 dimensions) for all embeddings.
    """

    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize embedding service.

        Args:
            model_name: Optional model name override
        """
        self.model_name = model_name or getattr(
            settings, "EMBEDDING_MODEL_FALLBACK", "sentence-transformers/all-MiniLM-L6-v2"
        )
        self._model_instance = None

    @property
    def model(self):
        """Lazy-load model on first access."""
        if self._model_instance is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model: %s", self.model_name)
            self._model_instance = SentenceTransformer(self.model_name)
        return self._model_instance

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions (384 for MiniLM)."""
        return 384

    def embed_text(self, text: str) -> List[float]:
        """
        Embed a single text string.

        Args:
            text: Text to embed

        Returns:
            List of floats (384 dimensions)
        """
        text = text.strip()
        if not text:
            return [0.0] * self.dimensions

        try:
            embedding = self.model.encode(text, normalize_embeddings=True)
            return embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
        except Exception as exc:
            logger.exception("embed_text() failed: %s", exc)
            return [0.0] * self.dimensions

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding lists (each 384 dimensions)
        """
        if not texts:
            return []

        try:
            embeddings = self.model.encode(texts, normalize_embeddings=True)
            return [e.tolist() if hasattr(e, "tolist") else list(e) for e in embeddings]
        except Exception as exc:
            logger.exception("embed_batch() failed: %s", exc)
            return [[0.0] * self.dimensions for _ in texts]


# Convenience functions
def embed_text(text: str) -> List[float]:
    """
    Convenience function to embed a single text.

    Args:
        text: Text to embed

    Returns:
        Embedding as list of floats
    """
    service = EmbeddingService()
    return service.embed_text(text)


def embed_batch(texts: List[str]) -> List[List[float]]:
    """
    Convenience function to embed multiple texts.

    Args:
        texts: List of texts to embed

    Returns:
        List of embeddings
    """
    service = EmbeddingService()
    return service.embed_batch(texts)
