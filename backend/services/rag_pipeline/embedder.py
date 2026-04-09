"""
Embedding service — supports both external API and local sentence-transformers.
Singleton pattern to avoid reloading models.
"""
import logging
import asyncio
from typing import List

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Singleton embedding service with external API + local fallback."""

    _instance = None

    def __init__(self):
        self.use_external = bool(settings.EMBEDDING_API_URL)
        self.dimension = settings.EMBEDDING_DIM

        if self.use_external:
            self.url = f"{settings.EMBEDDING_API_URL.rstrip('/')}/v1/embeddings"
            self.model_name = settings.EMBEDDING_MODEL_NAME
            logger.info(
                "Embedding model: %s @ %s [dim=%d]",
                self.model_name, self.url, self.dimension,
            )
        else:
            # Lazy-load local model on first use
            self._local_model = None
            logger.info(
                "Embedding model: %s (local, dim=%d)",
                settings.EMBEDDING_MODEL_FALLBACK, self.dimension,
            )

    @classmethod
    def get_instance(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def embed(self, text: str) -> List[float]:
        """Synchronous embedding."""
        return asyncio.get_event_loop().run_until_complete(self.aembed(text))

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Synchronous batch embedding."""
        return asyncio.get_event_loop().run_until_complete(self.aembed_batch(texts))

    async def aembed(self, text: str) -> List[float]:
        """Async single embedding."""
        if self.use_external:
            return await self._external_embed(text)
        return await self._local_embed(text)

    async def aembed_batch(self, texts: List[str]) -> List[List[float]]:
        """Async batch embedding with chunking to avoid timeout."""
        if self.use_external:
            return await self._external_embed_batch(texts)
        return await self._local_embed_batch(texts)

    # ── External API ─────────────────────────────────────────────
    async def _external_embed(self, text: str) -> List[float]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.url,
                json={
                    "model": self.model_name,
                    "input": text,
                    "dimensions": self.dimension,
                },
            )
            response.raise_for_status()
            return response.json()["data"][0]["embedding"]

    async def _external_embed_batch(self, texts: List[str]) -> List[List[float]]:
        batch_size = 16
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.url,
                    json={
                        "model": self.model_name,
                        "input": batch,
                        "dimensions": self.dimension,
                    },
                )
                response.raise_for_status()
                data = response.json()["data"]
                data.sort(key=lambda x: x["index"])
                batch_embeddings = [d["embedding"] for d in data]
                all_embeddings.extend(batch_embeddings)

            logger.info("Embedded batch %d (%d texts)", i // batch_size + 1, len(batch))

        return all_embeddings

    # ── Local sentence-transformers fallback ─────────────────────
    def _get_local_model(self):
        if self._local_model is None:
            from sentence_transformers import SentenceTransformer
            self._local_model = SentenceTransformer(
                settings.EMBEDDING_MODEL_FALLBACK, device="cpu"
            )
        return self._local_model

    async def _local_embed(self, text: str) -> List[float]:
        loop = asyncio.get_event_loop()
        model = await loop.run_in_executor(None, self._get_local_model)
        embedding = await loop.run_in_executor(
            None, lambda: model.encode(text, convert_to_numpy=True)
        )
        return embedding.tolist()

    async def _local_embed_batch(self, texts: List[str]) -> List[List[float]]:
        loop = asyncio.get_event_loop()
        model = await loop.run_in_executor(None, self._get_local_model)
        embeddings = await loop.run_in_executor(
            None, lambda: model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        )
        return embeddings.tolist()


# Module-level singleton
embedder = EmbeddingService.get_instance()
