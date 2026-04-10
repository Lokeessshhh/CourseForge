"""
Embedding service — Qwen3-Embedding-8B via OpenRouter.
Supports both OpenRouter API and local sentence-transformers fallback.
Singleton pattern to avoid reloading models.
"""
import logging
import asyncio
from typing import List

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Singleton embedding service with OpenRouter API + local fallback."""

    _instance = None

    def __init__(self):
        self.api_key = getattr(settings, "OPENROUTER_API_KEY", "")
        self.model = getattr(settings, "OPENROUTER_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")
        self.dimension = getattr(settings, "EMBEDDING_DIM", 1536)
        self.base_url = getattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        
        self.use_external = bool(self.api_key)
        
        if self.use_external:
            self.url = f"{self.base_url.rstrip('/')}/chat/completions"
            logger.info(
                "Embedding model: %s via OpenRouter [dim=%d]",
                self.model, self.dimension,
            )
        else:
            # Lazy-load local model on first use
            self._local_model = None
            logger.info(
                "Embedding model: %s (local fallback, dim=%d)",
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

    # ── OpenRouter API ─────────────────────────────────────────────
    async def _external_embed(self, text: str) -> List[float]:
        """Get embedding from OpenRouter Qwen3-Embedding-8B."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/your-org/ai-course-generator",
            "X-Title": "AI Course Generator",
            "Content-Type": "application/json",
        }

        # OpenRouter uses chat completions API for embeddings via Qwen
        payload = {
            "model": self.model,
            "input": text,
            "dimensions": self.dimension,
            "encoding_format": "float",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.url.replace("/chat/completions", "/embeddings"),
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]

    async def _external_embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch embedding via OpenRouter with chunking."""
        batch_size = 16  # OpenRouter batch limit
        all_embeddings = []

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/your-org/ai-course-generator",
            "X-Title": "AI Course Generator",
            "Content-Type": "application/json",
        }

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            
            payload = {
                "model": self.model,
                "input": batch,
                "dimensions": self.dimension,
                "encoding_format": "float",
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.url.replace("/chat/completions", "/embeddings"),
                    json=payload,
                    headers=headers,
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
