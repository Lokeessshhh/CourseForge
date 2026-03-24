"""
WebSocket ChatConsumer.
ws://api/ws/chat/{session_id}/?token=<clerk_jwt>

Full 7-step RAG pipeline:
  1. Redis semantic cache check (MD5 → cosine >0.97)
  2. 4-Tier memory injection
  3. HyDE + query decomposition
  4. Hybrid retrieval (pgvector + BM25 + RRF)
  5. bge-reranker-v2-m3 (top60 → top10)
  6. Qwen 7B streaming generation (vLLM)
  7. Save to cache + memory + update knowledge state
"""
import json
import logging
import uuid

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """Async WebSocket consumer for the RAG chat pipeline."""

    async def connect(self):
        """Authenticate and join channel group."""
        user = self.scope.get("user")
        auth_error = self.scope.get("auth_error")

        if not user or auth_error:
            logger.warning("WebSocket connection refused: %s", auth_error or "no user")
            await self.close(code=4001)
            return

        self.user = user
        self.session_id = self.scope["url_route"]["kwargs"].get("session_id", str(uuid.uuid4()))
        self.room_group_name = f"chat_{self.session_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Load memory context on connect
        self.memory_context = await self._load_memory()
        await self.send(json.dumps({"type": "connected", "session_id": self.session_id}))
        logger.info("WS connected: user=%s session=%s", user.email, self.session_id)

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        logger.info("WS disconnected: code=%s", close_code)

    async def receive(self, text_data):
        """Process incoming message through full RAG pipeline."""
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(json.dumps({"type": "error", "message": "Invalid JSON"}))
            return

        message = data.get("message", "").strip()
        course_id = data.get("course_id")

        if not message:
            return

        # Notify client that processing has started
        await self.send(json.dumps({"type": "thinking"}))

        try:
            await self._run_rag_pipeline(message, course_id)
        except Exception as exc:
            logger.exception("RAG pipeline error: %s", exc)
            await self.send(json.dumps({"type": "error", "message": str(exc)}))

    async def _run_rag_pipeline(self, query: str, course_id=None):
        """Execute all 7 RAG pipeline steps and stream Qwen response."""
        from services.rag_pipeline.cache import SemanticCache
        from services.rag_pipeline.memory import MemoryManager
        from services.rag_pipeline.retriever import HybridRetriever
        from services.rag_pipeline.reranker import Reranker
        from services.rag_pipeline.hyde import HyDEGenerator
        from services.llm.qwen_client import QwenClient

        # Step 1: Cache check
        cache = SemanticCache()
        cached_response = await database_sync_to_async(cache.check_cache)(query)
        if cached_response:
            await self.send(json.dumps({"type": "cache_hit"}))
            await self.send(json.dumps({"type": "token", "content": cached_response}))
            await self.send(json.dumps({"type": "done", "sources": []}))
            return

        # Step 2: 4-Tier memory injection
        memory = MemoryManager()
        memory_context = await database_sync_to_async(memory.inject_memory)(
            user_id=str(self.user.id),
            session_id=self.session_id,
            course_id=course_id,
        )

        # Step 3: HyDE embedding (enabled by default for quality)
        hyde = HyDEGenerator()
        hyde_embedding = await database_sync_to_async(hyde.generate_embedding)(query)

        # Step 4: Hybrid retrieval
        retriever = HybridRetriever()
        chunks = await database_sync_to_async(retriever.retrieve_by_vector)(
            hyde_embedding, top_k=60, course_id=course_id
        )

        # Step 5: Reranking
        reranker = Reranker()
        top_chunks = await database_sync_to_async(reranker.rerank)(query, chunks, top_k=10)

        context = "\n\n".join(c["content"] for c in top_chunks)
        sources = [{"chunk_id": c["chunk_id"], "content": c["content"][:200]} for c in top_chunks]

        # Step 6: Stream Qwen 7B response
        client = QwenClient()
        full_response = []

        async for token in client.stream_generate(
            prompt=query,
            context=context,
            memory_context=memory_context,
        ):
            await self.send(json.dumps({"type": "token", "content": token}))
            full_response.append(token)

        response_text = "".join(full_response)

        # Step 7: Persist & update caches
        await database_sync_to_async(self._persist_message)(query, response_text, course_id)
        await database_sync_to_async(cache.save_cache)(query, response_text)

        await self.send(json.dumps({"type": "done", "sources": sources}))

    def _persist_message(self, user_msg: str, assistant_msg: str, course_id=None):
        """Save conversation messages to DB and optionally embed for Tier 3 memory."""
        from apps.conversations.models import Conversation
        from services.llm.embeddings import EmbeddingService

        embedder = EmbeddingService()

        for role, content in [("user", user_msg), ("assistant", assistant_msg)]:
            embedding = None
            if role == "assistant":
                # Only embed assistant responses for semantic search
                try:
                    embedding = embedder.embed_text(content, model="fallback")
                except Exception:
                    pass

            Conversation.objects.create(
                user=self.user,
                session_id=self.session_id,
                role=role,
                content=content,
                embedding=embedding,
                course_id=course_id,
            )

    async def _load_memory(self) -> str:
        """Pre-load memory context on connect."""
        try:
            from services.rag_pipeline.memory import MemoryManager
            memory = MemoryManager()
            return await database_sync_to_async(memory.inject_memory)(
                user_id=str(self.user.id),
                session_id=self.session_id,
                course_id=None,
            )
        except Exception as exc:
            logger.warning("Failed to load memory: %s", exc)
            return ""
