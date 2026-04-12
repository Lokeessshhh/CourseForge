"""
WebSocket ChatConsumer for LearnAI AI Tutor.

Connection URL patterns:
ws/chat/                           → global chat (all courses context)
ws/chat/{course_id}/               → course-specific chat
ws/chat/{course_id}/{week}/{day}/  → day-specific chat

Full RAG pipeline with:
- Semantic cache (Redis MD5 + pgvector cosine)
- 4-Tier memory injection
- HyDE + Query decomposition
- Hybrid retrieval (pgvector + BM25 + RRF)
- Reranking (bge-reranker-v2-m3)
- Streaming response generation
- Post-response persistence
"""
import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


# Rate limit constants
RATE_LIMIT_MESSAGES_PER_HOUR = 100
RATE_LIMIT_MESSAGES_PER_MINUTE = 20
MAX_MESSAGE_LENGTH = 2000


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Async WebSocket consumer for the AI tutor chat.
    
    Supports three scopes:
    - global: All courses visible, general tutor mode
    - course: Single course context, week/day aware
    - day: Specific day content + quiz context
    """

    async def connect(self):
        """
        Authenticate and initialize chat session.

        On connect:
        1. Extract JWT from query param and verify
        2. Extract scope from URL (global/course/day)
        3. Create or resume session
        4. Load full user context
        5. Send welcome message
        """
        # Get connection details for logging
        # Note: headers in ASGI are a list of (name, value) tuples
        headers_dict = {k: v for k, v in self.scope.get("headers", [])}
        scope_info = {
            "type": self.scope.get("type"),
            "path": self.scope.get("path"),
            "user_agent": headers_dict.get(b"user-agent", b"").decode(),
        }

        logger.info("=" * 80)
        logger.info(" WEBSOCKET CONNECTION ATTEMPT")
        logger.info(f"   Scope: {scope_info}")
        logger.info(f"   Query: {self.scope.get('query_string', b'').decode()[:200]}")
        logger.info("=" * 80)

        logger.info("[WS] Connect attempt - scope keys: %s", list(self.scope.keys()))
        logger.info("[WS] Connect - query_string: %s", self.scope.get("query_string", b"").decode()[:100])

        # Get authenticated user from middleware
        user = self.scope.get("user")
        auth_error = self.scope.get("auth_error")

        logger.info("[WS] Connect - user: %s, auth_error: %s", user.id if user else None, auth_error)

        if not user or auth_error:
            logger.warning("[WS]  WebSocket connection refused: %s", auth_error or "no user")
            await self.close(code=4001)
            return

        self.user = user
        self.user_id = str(user.id)

        logger.info("[WS]  User authenticated: %s (%s)", user.email, user.id)

        # Extract scope from URL kwargs
        url_kwargs = self.scope["url_route"]["kwargs"]
        self.course_id = url_kwargs.get("course_id")
        self.week = int(url_kwargs["week"]) if url_kwargs.get("week") else None
        self.day = int(url_kwargs["day"]) if url_kwargs.get("day") else None

    def _should_trigger_web_search(self, query: str) -> bool:
        """
        Check if query should trigger web search based on keywords.
        
        Matches the same keywords as the frontend for consistency.
        
        Args:
            query: User's query string
            
        Returns:
            True if web search should be triggered
        """
        WEB_SEARCH_KEYWORDS = [
            # Search intent
            'search', 'web search', 'google', 'bing', 'look up',
            'find online', 'search the web', 'search online',
            
            # Time-sensitive
            'latest', 'current', 'recent', 'new', 'today',
            'yesterday', 'this week', 'this month', '2026', '2025',
            
            # News/Events
            'news', 'announcement', 'release', 'update', 'breaking',
            
            # Facts/Data
            'statistics', 'price', 'cost', 'population', 'market share',
            'ranking', 'report', 'study', 'survey',
            
            # People/Companies
            'who is', 'what company', 'founder', 'ceo', 'owner',
            
            # Technology
            'version', 'release date', 'documentation', 'changelog',
            
            # Weather/Current events
            'weather', 'temperature', 'forecast', 'score', 'result',
            
            # Conflict/Events
            'conflict', 'war', 'attack', 'election', 'protest',
        ]

        query_lower = query.lower()
        return any(keyword in query_lower for keyword in WEB_SEARCH_KEYWORDS)

    async def connect(self):
        """
        Authenticate and initialize chat session.

        On connect:
        1. Extract JWT from query param and verify
        2. Extract scope from URL (global/course/day)
        3. Create or resume session
        4. Load full user context
        5. Send welcome message
        """
        # Get connection details for logging
        # Note: headers in ASGI are a list of (name, value) tuples
        headers_dict = {k: v for k, v in self.scope.get("headers", [])}
        scope_info = {
            "type": self.scope.get("type"),
            "path": self.scope.get("path"),
            "user_agent": headers_dict.get(b"user-agent", b"").decode(),
        }

        logger.info("=" * 80)
        logger.info(" WEBSOCKET CONNECTION ATTEMPT")
        logger.info(f"   Scope: {scope_info}")
        logger.info(f"   Query: {self.scope.get('query_string', b'').decode()[:200]}")
        logger.info("=" * 80)

        logger.info("[WS] Connect attempt - scope keys: %s", list(self.scope.keys()))
        logger.info("[WS] Connect - query_string: %s", self.scope.get("query_string", b"").decode()[:100])

        # Get authenticated user from middleware
        user = self.scope.get("user")
        auth_error = self.scope.get("auth_error")

        logger.info("[WS] Connect - user: %s, auth_error: %s", user.id if user else None, auth_error)

        if not user or auth_error:
            logger.warning("[WS]  WebSocket connection refused: %s", auth_error or "no user")
            await self.close(code=4001)
            return

        self.user = user
        self.user_id = str(user.id)

        logger.info("[WS]  User authenticated: %s (%s)", user.email, user.id)

        # Extract scope from URL kwargs
        url_kwargs = self.scope["url_route"]["kwargs"]
        self.course_id = url_kwargs.get("course_id")
        self.week = int(url_kwargs["week"]) if url_kwargs.get("week") else None
        self.day = int(url_kwargs["day"]) if url_kwargs.get("day") else None

        # Determine scope
        if self.course_id and self.week and self.day:
            self.scope_type = "day"
        elif self.course_id:
            self.scope_type = "course"
        else:
            self.scope_type = "global"

        # Validate course ownership if course-specific
        if self.course_id:
            if not await self._validate_course_ownership():
                logger.warning("Course access denied: user=%s course=%s", self.user_id, self.course_id)
                await self.close(code=4004)
                return

        # Get or create session
        query_params = self.scope.get("query_string", "").decode() if isinstance(self.scope.get("query_string"), bytes) else self.scope.get("query_string", "")
        params = dict(p.split("=") for p in query_params.split("&") if "=" in p)
        self.session_id = params.get("session_id") or str(uuid.uuid4())

        # Include sources flag
        self.include_sources = params.get("include_sources", "true").lower() == "true"

        # Join channel group
        self.room_group_name = f"chat_{self.session_id}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Accept connection
        await self.accept()

        # Set heartbeat to keep connection alive during long operations
        # Daphne may kill idle connections, so we send periodic pings
        self.heartbeat_task = None

        # Track initialization state to prevent race conditions
        self.session_initialized = False

        # Load user context in background to avoid blocking connection
        # Use ensure_future to guarantee the task is scheduled
        init_task = asyncio.create_task(self._initialize_session_background())
        self.init_task = init_task  # Keep reference for cleanup

        logger.info(
            "WS connected: user=%s session=%s scope=%s course=%s",
            self.user.email, self.session_id, self.scope_type, self.course_id
        )

    async def disconnect(self, close_code):
        """
        Save session state and cleanup on disconnect.

        NOTE: Message processing continues in background even after disconnect.
        The _process_message method saves all data to database before attempting
        to send responses to client, so conversations are never lost.
        """
        logger.info("=" * 80)
        logger.info(" WEBSOCKET DISCONNECTED")
        logger.info(f"   User: {self.user.email if hasattr(self, 'user') else 'Unknown'}")
        logger.info(f"   Session: {getattr(self, 'session_id', 'N/A')}")
        logger.info(f"   Close Code: {close_code}")
        logger.info("=" * 80)
        
        # Cancel heartbeat task if running
        if hasattr(self, "heartbeat_task") and self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass

        # Cancel init task if still running
        if hasattr(self, "init_task") and self.init_task and not self.init_task.done():
            self.init_task.cancel()
            try:
                await self.init_task
            except asyncio.CancelledError:
                pass
            
        logger.info("[WS]  Cleanup completed for session %s", getattr(self, 'session_id', 'N/A'))

        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        # Save session state
        if hasattr(self, "session"):
            await self.session.save_async()

        logger.info("WS disconnected: code=%s session=%s", close_code, getattr(self, "session_id", "unknown"))
        logger.info("NOTE: Any in-progress message generation will continue in background")

    async def receive(self, text_data):
        """
        Process incoming message through full RAG pipeline.

        Input format:
        {
            "message": "I don't understand recursion",
            "message_id": "uuid",
            "include_sources": true,
            "session_id": "uuid" (optional)
        }
        """
        logger.info("=" * 60)
        logger.info(" MESSAGE RECEIVED")
        logger.info(f"   User: {self.user.email if hasattr(self, 'user') else 'Unknown'}")
        logger.info(f"   Session: {getattr(self, 'session_id', 'N/A')}")
        logger.info(f"   Message: {text_data[:200]}")
        logger.info("=" * 60)

        # Parse message
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            logger.error("WS JSON decode error: %s", text_data[:200])
            await self._send_error("Invalid JSON format")
            return

        message = data.get("message", "").strip()
        message_id = data.get("message_id", str(uuid.uuid4()))
        include_sources = data.get("include_sources", self.include_sources)
        web_search = data.get("web_search", False)
        rag_enabled = data.get("rag_enabled", False)

        logger.info("[WS]  Processing message: '%s...' (ID: %s, web_search: %s, rag_enabled: %s)", message[:50], message_id, web_search, rag_enabled)
        
        # Use session_id from message payload if provided (for new sessions)
        message_session_id = data.get("session_id")
        if message_session_id:
            previous_session_id = getattr(self, "session_id", None)
            if previous_session_id != message_session_id:
                # Move this socket connection to the correct session group.
                # Without this, the consumer remains in the old group created at connect-time,
                # and can cause the frontend to look "stuck" due to responses being scoped incorrectly.
                if hasattr(self, "room_group_name"):
                    try:
                        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
                    except Exception:
                        logger.exception("WS failed to discard previous group: %s", self.room_group_name)

                self.session_id = message_session_id
                self.room_group_name = f"chat_{self.session_id}"
                await self.channel_layer.group_add(self.room_group_name, self.channel_name)

                # Refresh session object to match the new session_id
                try:
                    from services.chat.session import ChatSession

                    self.session = await ChatSession.get_or_create(
                        user_id=self.user_id,
                        session_id=self.session_id,
                        scope=self.scope_type,
                        course_id=self.course_id,
                        week=self.week,
                        day=self.day,
                    )
                except Exception:
                    logger.exception("WS failed to hydrate session after session switch")

                logger.info("WS switched session from %s to %s", previous_session_id, self.session_id)
            else:
                logger.info("WS using session_id from message (no-op): %s", self.session_id)

        logger.info("WS parsed message: message_id=%s, message=%s, session=%s", message_id, message[:100], self.session_id[:20])

        # Wait for session initialization (with timeout)
        if not getattr(self, "session_initialized", False):
            logger.info("WS waiting for session initialization...")
            for _ in range(20):  # Wait up to 2 seconds
                if getattr(self, "session_initialized", False):
                    break
                await asyncio.sleep(0.1)
            
            if not getattr(self, "session_initialized", False):
                logger.warning("WS message rejected: session not initialized")
                await self._send_error("Session not ready. Please try again.", message_id)
                return

        # Validate message
        if not message:
            logger.warning("WS empty message rejected")
            await self._send_error("Empty message", message_id)
            return

        if len(message) > MAX_MESSAGE_LENGTH:
            logger.warning("WS message too long: %d chars", len(message))
            await self._send_error(f"Message too long (max {MAX_MESSAGE_LENGTH} chars)", message_id)
            return

        # Check rate limit
        rate_limit_result = await self._check_rate_limit()
        if not rate_limit_result["allowed"]:
            logger.warning("WS rate limit exceeded: %s", rate_limit_result["message"])
            await self._send_error(rate_limit_result["message"], message_id)
            return

        logger.info("WS processing message: message_id=%s", message_id)

        # Send thinking indicator
        logger.info(
            "WS sending thinking: session=%s message_id=%s",
            self.session_id, message_id
        )
        await self.send(json.dumps({
            "type": "thinking",
            "message_id": message_id,
        }))

        try:
            # Run chat pipeline
            logger.info(
                "WS calling _process_message: session=%s message_id=%s include_sources=%s web_search=%s rag_enabled=%s",
                self.session_id, message_id, include_sources, web_search, rag_enabled
            )
            await self._process_message(message, message_id, include_sources, web_search, rag_enabled)
        except Exception as exc:
            logger.exception("Chat pipeline error: %s", exc)
            await self._send_error("Processing error. Please try again.", message_id)

    async def _process_message(self, query: str, message_id: str, include_sources: bool, web_search: bool = False, rag_enabled: bool = True):
        """
        Process message with full RAG pipeline:
        1. Web search if enabled (Tavily API)
        2. Load user context + knowledge state
        3. Check semantic cache (Redis)
        4. If cache miss → hybrid RAG retrieval + rerank
        5. Build RAG prompt with chunks + history + knowledge state
        6. Stream LLM response
        7. Save conversation + cache response
        8. Update session metadata
        """
        from services.chat.context import UserContextLoader
        from services.chat.session import ChatSession
        from services.llm.qwen_client import get_client

        # ── Step 1: Web search if enabled ──
        web_search_results = None
        enhanced_query = query

        if web_search:
            try:
                from services.chat.web_search import perform_web_search, format_web_search_for_prompt

                logger.info("WS performing SILENT web search for: %s", query[:100])

                try:
                    await self.send(json.dumps({
                        "type": "web_search_start",
                        "message_id": message_id,
                        "query": query,
                    }))
                except Exception:
                    pass

                web_search_results = await perform_web_search(query)

                try:
                    await self.send(json.dumps({
                        "type": "web_search_end",
                        "message_id": message_id,
                        "success": web_search_results.get('success', False) if web_search_results else False,
                        "results": web_search_results.get('frontend_results', []) if web_search_results else [],
                        "query": web_search_results.get('query', query) if web_search_results else query,
                    }))
                except Exception:
                    pass

                if web_search_results and web_search_results.get('success'):
                    search_formatted = format_web_search_for_prompt(web_search_results)
                    enhanced_query = search_formatted + "\n\nUser Question: " + query
                    logger.info("WS silent web search successful: %d results", len(web_search_results.get('frontend_results', [])))
                else:
                    error_msg = web_search_results.get('error', 'Unknown error') if web_search_results else 'Search failed'
                    logger.warning("WS silent web search failed: %s", error_msg)

            except Exception as exc:
                logger.exception("WS silent web search error: %s", exc)

        # ── Step 2: Load user context ──
        context_loader = UserContextLoader()
        try:
            user_context = await asyncio.wait_for(
                context_loader.load_full_context(
                    user_id=self.user_id,
                    scope=self.scope_type,
                    course_id=self.course_id,
                    week=self.week,
                    day=self.day,
                ),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Context loading timed out, using minimal context")
            user_context = {"profile": {"name": "Student"}, "knowledge_state": {}}
        except Exception as exc:
            logger.exception("Context loading failed: %s", exc)
            user_context = {"profile": {"name": "Student"}, "knowledge_state": {}}

        context_string = context_loader.build_context_string(user_context)

        # ── Step 3: Check semantic cache ──
        try:
            from apps.memory.cache import get_cached_response
            cached = await get_cached_response(query)
            if cached:
                logger.info("WS semantic cache HIT for: %s", query[:80])
                await self._stream_cached_response(cached, message_id, include_sources)
                await self._save_conversation(query, cached)
                return
        except Exception as exc:
            logger.warning("Semantic cache check failed: %s", exc)

        # ── Step 4: RAG retrieval + rerank ──
        rag_chunks = []
        knowledge_state = {}

        if rag_enabled:
            try:
                # Load knowledge state for adaptive prompting
                from apps.memory.knowledge import get_knowledge_state
                knowledge_state = await get_knowledge_state(self.user_id)

                # Run hybrid RAG retrieval
                from services.rag_pipeline.retriever import hybrid_retrieve
                rag_chunks = await hybrid_retrieve(
                    query=query,
                    top_k=60,
                    course_id=self.course_id,
                    use_hyde=True,
                    use_decomposition=True,
                )

                if rag_chunks:
                    # Rerank
                    from services.rag_pipeline.reranker import reranker
                    rag_chunks = reranker.rerank(query, rag_chunks, top_k=10)
                    logger.info("WS RAG retrieved %d chunks for: %s", len(rag_chunks), query[:80])
                else:
                    logger.info("WS RAG returned no chunks for: %s", query[:80])

            except Exception as exc:
                logger.warning("WS RAG retrieval failed (falling back to no-RAG): %s", exc)
                rag_chunks = []
                knowledge_state = {}
        else:
            logger.info("WS RAG disabled, skipping retrieval for: %s", query[:80])

        # ── Step 5: Build RAG prompt ──
        if rag_chunks:
            # Use RAG prompt with context chunks
            from services.rag_pipeline.generator import build_rag_prompt

            # Load conversation history for context
            try:
                from apps.memory.history import get_recent_history
                conversation_history = await get_recent_history(self.session_id, limit=6)
            except Exception:
                conversation_history = []

            rag_prompt = build_rag_prompt(
                question=enhanced_query,
                context_chunks=rag_chunks,
                conversation_history=conversation_history,
                knowledge_state=knowledge_state,
            )
            logger.info("WS RAG prompt built with %d chunks", len(rag_chunks))
        else:
            # Fallback: use original enhanced query (no RAG context)
            rag_prompt = enhanced_query

        # ── Step 6: Stream LLM response ──
        full_response = ""
        client = get_client()

        logger.info(
            "WS stream_start: session=%s message_id=%s",
            self.session_id, message_id
        )

        client_connected = True

        try:
            await self.send(json.dumps({
                "type": "stream_start",
                "message_id": message_id,
            }))
        except Exception as exc:
            logger.warning("Client disconnected during stream_start: %s", exc)
            client_connected = False

        try:
            async for token in client.stream_generate(
                prompt=rag_prompt,
                context=context_string,
                max_tokens=2000,
            ):
                full_response += token
                if len(full_response) <= 5:
                    logger.info(
                        "WS first_token: session=%s message_id=%s",
                        self.session_id, message_id
                    )
                if client_connected:
                    try:
                        await self.send(json.dumps({
                            "type": "stream_token",
                            "token": token,
                            "message_id": message_id,
                        }))
                    except Exception as exc:
                        logger.warning("Client disconnected during streaming: %s", exc)
                        client_connected = False
        except Exception as exc:
            logger.error("Streaming error: %s", exc)
            if not full_response:
                full_response = "I apologize, but I encountered an error generating a response. Please try again."

        # ── Step 7: Save conversation ──
        try:
            await self._save_conversation(query, full_response)
            logger.info("Conversation saved to database (user query + response)")
        except Exception as exc:
            logger.warning("Failed to save conversation: %s", exc)

        # ── Step 8: Cache response ──
        try:
            from apps.memory.cache import set_cached_response
            await set_cached_response(query, full_response)
        except Exception as exc:
            logger.warning("Response caching failed: %s", exc)

        # ── Step 9: Update session ──
        try:
            self.session = await ChatSession.get_or_create(
                user_id=self.user_id,
                session_id=self.session_id,
                scope=self.scope_type,
                course_id=self.course_id,
            )
            await self.session.add_message("user", query)
            await self.session.add_message("assistant", full_response)

            logger.info(
                "Session message count: %d, session_id=%s",
                len(self.session.messages), self.session_id
            )
        except Exception as exc:
            logger.warning("Session update failed: %s", exc)

        # ── Step 10: Send stream_end ──
        logger.info(
            "WS stream_end: session=%s message_id=%s response_len=%s",
            self.session_id, message_id, len(full_response)
        )

        if client_connected:
            try:
                sources = []
                if include_sources and rag_chunks:
                    sources = [
                        {
                            "chunk_id": c.get("chunk_id", ""),
                            "title": c.get("title", "Document"),
                            "content": c.get("content", "")[:300],
                            "score": c.get("rerank_score", c.get("score", 0.0)),
                        }
                        for c in rag_chunks[:5]
                    ]

                await self.send(json.dumps({
                    "type": "stream_end",
                    "message_id": message_id,
                    "sources": sources,
                    "full_response": full_response,
                }))
            except Exception as exc:
                logger.warning("Client disconnected before stream_end: %s", exc)
                client_connected = False

        # ── Step 11: Generate session title (background) ──
        try:
            if hasattr(self, 'session') and len(self.session.messages) == 2:
                asyncio.create_task(self._generate_session_title_background(query))
            else:
                logger.info("Skipping title generation (not first message): session=%s", self.session_id)
        except Exception as exc:
            logger.warning("Title generation failed: %s", exc)

        logger.info(
            "Chat message processed: user=%s session=%s rag_chunks=%d",
            self.user_id, self.session_id, len(rag_chunks)
        )

    async def _save_conversation(self, query: str, full_response: str):
        """Save conversation to database (synchronous within async)."""
        from apps.conversations.models import Conversation

        @sync_to_async
        def save_conversation():
            Conversation.objects.create(
                user_id=self.user_id,
                session_id=self.session_id,
                course_id=self.course_id,
                role="user",
                content=query,
            )
            Conversation.objects.create(
                user_id=self.user_id,
                session_id=self.session_id,
                course_id=self.course_id,
                role="assistant",
                content=full_response,
            )

        await save_conversation()

    async def _generate_session_title_immediate(self, first_message: str):
        """
        Generate session title immediately (awaited, not background).
        Updates both session metadata and database Conversation.
        """
        from services.llm.qwen_client import get_client
        from services.chat.session import ChatSession
        from apps.conversations.models import Conversation

        try:
            client = get_client()
            prompt = f"""Generate a concise, descriptive title (max 5 words) for a chat session based on this first message:

"{first_message[:200]}"

Rules:
- Return ONLY the title, no quotes or extra text
- Make it specific and descriptive
- Use title case
- Keep it under 50 characters"""

            title = ""
            async for token in client.stream_generate(
                prompt=prompt,
                context="",
                max_tokens=50,
            ):
                title += token
                if len(title) > 50:
                    break

            # Clean up the title
            title = title.strip().strip('"\'').strip()
            if not title:
                title = first_message[:30] + "..." if len(first_message) > 30 else first_message

            # Update session metadata
            self.session.metadata["title"] = title
            await self.session.save_async()

            # Update placeholder Conversation in database immediately
            @sync_to_async
            def update_placeholder():
                placeholder = Conversation.objects.filter(
                    user_id=self.user_id,
                    session_id=self.session_id,
                    content="[Session created]",
                    role="system"
                ).first()
                if placeholder:
                    placeholder.content = title
                    placeholder.save()

            await update_placeholder()

            logger.info("Generated session title: %s", title)

        except Exception as exc:
            logger.error("Error generating session title: %s", exc)

    async def _generate_session_title_background(self, first_message: str):
        """
        Generate session title in background (non-blocking).
        Updates both session metadata and database Conversation.
        
        This runs AFTER stream_end is sent, so client disconnect won't affect it.
        """
        from services.llm.qwen_client import get_client
        from services.chat.session import ChatSession
        from apps.conversations.models import Conversation

        try:
            client = get_client()
            prompt = f"""Generate a concise, descriptive title (max 5 words) for a chat session based on this first message:

"{first_message[:200]}"

Rules:
- Return ONLY the title, no quotes or extra text
- Make it specific and descriptive
- Use title case
- Keep it under 50 characters"""

            title = ""
            async for token in client.stream_generate(
                prompt=prompt,
                context="",
                max_tokens=50,
            ):
                title += token
                if len(title) > 50:
                    break

            # Clean up the title
            title = title.strip().strip('"\'').strip()
            if not title:
                title = first_message[:30] + "..." if len(first_message) > 30 else first_message

            # Update session metadata
            if hasattr(self, 'session') and self.session:
                self.session.metadata["title"] = title
                await self.session.save_async()

            # Update placeholder Conversation in database
            @sync_to_async
            def update_placeholder():
                placeholder = Conversation.objects.filter(
                    user_id=self.user_id,
                    session_id=self.session_id,
                    content="[Session created]",
                    role="system"
                ).first()
                if placeholder:
                    placeholder.content = title
                    placeholder.save()
                    logger.info("Updated conversation title in DB: %s", title)
                else:
                    logger.warning("Placeholder conversation not found for session: %s", self.session_id)

            await update_placeholder()

            # Send title update to client (they might still be connected)
            try:
                await self.send(json.dumps({
                    "type": "title_updated",
                    "session_id": self.session_id,
                    "title": title,
                }))
                logger.info("Sent title_updated to client: %s", title)
            except Exception as send_exc:
                # Client likely disconnected, but title is saved in DB
                logger.info("Could not send title_updated (client disconnected): %s", send_exc)

            logger.info("Generated session title (background): %s", title)

        except Exception as exc:
            logger.error("Error generating session title (background): %s", exc)

    async def _generate_session_title(self, first_message: str):
        """
        Generate a concise session title from the first user message using LLM.
        
        Args:
            first_message: The first user message content
        """
        from services.llm.qwen_client import get_client

        try:
            client = get_client()
            prompt = f"""Generate a concise, descriptive title (max 5 words) for a chat session based on this first message:

"{first_message[:200]}"

Rules:
- Return ONLY the title, no quotes or extra text
- Make it specific and descriptive
- Use title case
- Keep it under 50 characters"""

            title = ""
            async for token in client.stream_generate(
                prompt=prompt,
                context="",
                max_tokens=50,
            ):
                title += token
                if len(title) > 50:
                    break

            # Clean up the title
            title = title.strip().strip('"\'').strip()
            if not title:
                title = first_message[:30] + "..." if len(first_message) > 30 else first_message

            # Update session metadata
            self.session.metadata["title"] = title
            await self.session.save_async()

            # Update placeholder Conversation in database
            @sync_to_async
            def update_placeholder():
                from apps.conversations.models import Conversation
                placeholder = Conversation.objects.filter(
                    user_id=self.user_id,
                    session_id=self.session_id,
                    content="[Session created]",
                    role="system"
                ).first()
                if placeholder:
                    placeholder.content = title
                    placeholder.save()

            await update_placeholder()

            logger.info("Generated session title: %s", title)

        except Exception as exc:
            logger.error("Error generating session title: %s", exc)

    async def _stream_response(
        self,
        prompt: str,
        message_id: str,
        sources: List[Dict[str, Any]],
        include_sources: bool,
    ) -> str:
        """
        Stream LLM response token by token.
        
        Args:
            prompt: Full prompt with context
            message_id: Client message ID
            sources: Source references
            include_sources: Whether to include sources
            
        Returns:
            Complete response string
        """
        from services.chat.pipeline import generate_streaming_response

        full_response = ""

        # Send stream start
        await self.send(json.dumps({
            "type": "stream_start",
            "message_id": message_id,
        }))

        # Stream tokens
        try:
            async for token in generate_streaming_response(prompt, system_type=self._get_system_type()):
                full_response += token
                await self.send(json.dumps({
                    "type": "stream_token",
                    "token": token,
                    "message_id": message_id,
                }))
        except Exception as exc:
            logger.error("Streaming error: %s", exc)
            # Send partial response
            if not full_response:
                full_response = "I apologize, but I encountered an error generating a response. Please try again."

        # Send stream end with sources
        await self.send(json.dumps({
            "type": "stream_end",
            "message_id": message_id,
            "sources": sources if include_sources else [],
            "full_response": full_response,
        }))

        return full_response

    async def _stream_cached_response(self, response: str, message_id: str, include_sources: bool):
        """Stream a cached response as if it were new."""
        await self.send(json.dumps({
            "type": "stream_start",
            "message_id": message_id,
        }))

        # Send in chunks for realistic streaming feel
        chunk_size = 10
        for i in range(0, len(response), chunk_size):
            chunk = response[i:i + chunk_size]
            await self.send(json.dumps({
                "type": "stream_token",
                "token": chunk,
                "message_id": message_id,
            }))

        await self.send(json.dumps({
            "type": "stream_end",
            "message_id": message_id,
            "sources": [],
            "full_response": response,
            "from_cache": True,
        }))

    async def _load_user_context(self):
        """Load user context and session."""
        from services.chat.session import ChatSession
        from services.chat.context import UserContextLoader

        # Create or resume session
        self.session = await ChatSession.get_or_create(
            user_id=self.user_id,
            session_id=self.session_id,
            scope=self.scope_type,
            course_id=self.course_id,
            week=self.week,
            day=self.day,
        )

        # Load context
        self.context_loader = UserContextLoader()
        self.user_context = await self.context_loader.load_full_context(
            user_id=self.user_id,
            scope=self.scope_type,
            course_id=self.course_id,
            week=self.week,
            day=self.day,
        )

    async def _initialize_session_background(self):
        """
        Initialize session in background (non-blocking).
        Loads user context and sends welcome message.
        """
        try:
            logger.info("WS background init started: session=%s", self.session_id)
            
            # Load context with timeout
            await asyncio.wait_for(self._load_user_context(), timeout=10.0)
            logger.info("WS context loaded: session=%s", self.session_id)
            
            # Send welcome message
            await self._send_welcome()
            logger.info("WS welcome sent: session=%s", self.session_id)
            
            # Mark as initialized
            self.session_initialized = True
            logger.info("WS session initialized: session=%s", self.session_id)
            
            # Start heartbeat to keep connection alive during idle periods
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info("WS heartbeat started: session=%s", self.session_id)
            
        except asyncio.TimeoutError:
            logger.warning("Session initialization timed out: session=%s", self.session_id)
            await self._send_error("Session initialization timed out. Please reconnect.")
        except Exception as exc:
            logger.exception("Background session initialization failed: %s", exc)
            await self._send_error("Failed to initialize session")

    async def _heartbeat_loop(self):
        """
        Send periodic ping to keep WebSocket connection alive.
        Daphne may kill idle connections, so we send a ping every 30 seconds.
        """
        try:
            while True:
                await asyncio.sleep(30)
                # Send a ping message (client should ignore if not handled)
                await self.send(json.dumps({
                    "type": "ping",
                    "timestamp": time.time(),
                }))
        except asyncio.CancelledError:
            # Task cancelled on disconnect - normal
            pass
        except Exception as exc:
            logger.warning("Heartbeat loop error: %s", exc)

    async def _send_welcome(self):
        """Send welcome message with context info."""
        from services.chat.prompts import build_welcome_message

        # Get context summary
        profile = self.user_context.get("profile", {})
        course = self.user_context.get("current_course", {})

        welcome = build_welcome_message(
            user_name=profile.get("name", "Student"),
            scope=self.scope_type,
            course_topic=course.get("topic") if self.scope_type != "global" else None,
            current_day=f"Week {course.get('current_week')} Day {course.get('current_day')}" if course.get("current_week") else None,
            progress=f"{course.get('overall_percentage', 0):.0f}%" if course.get("overall_percentage") else None,
        )

        await self.send(json.dumps({
            "type": "connected",
            "session_id": self.session_id,
            "scope": self.scope_type,
            "course_id": self.course_id,
            "context": {
                "scope": self.scope_type,
                "course_topic": course.get("topic") if self.scope_type != "global" else None,
                "current_day": f"Week {course.get('current_week')} Day {course.get('current_day')}" if course.get("current_week") else None,
                "user_name": profile.get("name", "Student"),
            },
            "welcome": welcome,
        }))

    async def _send_error(self, message: str, message_id: Optional[str] = None):
        """Send error message to client."""
        await self.send(json.dumps({
            "type": "error",
            "message": message,
            "message_id": message_id,
        }))

    async def _validate_course_ownership(self) -> bool:
        """Validate that user owns the course."""
        from apps.courses.models import Course

        @sync_to_async
        def _check():
            try:
                Course.objects.get(id=self.course_id, user_id=self.user_id)
                return True
            except Course.DoesNotExist:
                return False

        return await _check()

    async def _check_rate_limit(self) -> Dict[str, Any]:
        """
        Check rate limits for the user.
        
        Returns:
            Dict with 'allowed' bool and 'message' if not allowed
        """
        from services.chat.session import get_redis

        redis_client = get_redis()
        now = int(time.time())
        minute_key = f"chat:ratelimit:{self.user_id}:minute:{now // 60}"
        hour_key = f"chat:ratelimit:{self.user_id}:hour:{now // 3600}"

        # Check minute limit
        minute_count = int(redis_client.get(minute_key) or 0)
        if minute_count >= RATE_LIMIT_MESSAGES_PER_MINUTE:
            return {
                "allowed": False,
                "message": f"Rate limit exceeded. Max {RATE_LIMIT_MESSAGES_PER_MINUTE} messages per minute.",
            }

        # Check hour limit
        hour_count = int(redis_client.get(hour_key) or 0)
        if hour_count >= RATE_LIMIT_MESSAGES_PER_HOUR:
            return {
                "allowed": False,
                "message": f"Rate limit exceeded. Max {RATE_LIMIT_MESSAGES_PER_HOUR} messages per hour.",
            }

        # Increment counters
        pipe = redis_client.pipeline()
        pipe.incr(minute_key)
        pipe.expire(minute_key, 60)
        pipe.incr(hour_key)
        pipe.expire(hour_key, 3600)
        pipe.execute()

        return {"allowed": True}

    def _get_system_type(self) -> str:
        """Get the appropriate system prompt type based on scope."""
        if self.scope_type == "global":
            return "global_tutor"
        elif self.scope_type == "day":
            return "day_tutor"
        return "tutor"


# REST fallback view for non-WebSocket clients


class ChatAPIView(APIView):
    """
    REST endpoint fallback for non-WebSocket clients.

    POST /api/chat/
    POST /api/chat/{course_id}/

    Request: {"message": "...", "session_id": "uuid", "web_search": true}
    Response: {"response": "...", "sources": [...], "session_id": "uuid", "web_search_results": [...]}
    """
    permission_classes = [IsAuthenticated]

    async def post(self, request, course_id=None):
        from services.chat.pipeline import run_chat_pipeline, generate_response, save_conversation
        from services.chat.web_search import perform_web_search, format_web_search_for_prompt

        message = request.data.get("message", "").strip()
        session_id = request.data.get("session_id") or str(uuid.uuid4())
        include_sources = request.data.get("include_sources", True)
        web_search = request.data.get("web_search", False)

        if not message:
            return Response({"error": "Empty message"}, status=status.HTTP_400_BAD_REQUEST)

        if len(message) > MAX_MESSAGE_LENGTH:
            return Response(
                {"error": f"Message too long (max {MAX_MESSAGE_LENGTH} chars)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_id = str(request.user.id)

        # Perform web search if enabled
        web_search_result = None
        if web_search:
            web_search_result = await perform_web_search(message)

        # Run pipeline (non-streaming)
        prompt, sources, metadata = await run_chat_pipeline(
            query=message,
            user_id=user_id,
            session_id=session_id,
            scope="course" if course_id else "global",
            course_id=course_id,
            include_sources=include_sources,
        )

        # Inject web search results into prompt
        if web_search_result and web_search_result.get('success'):
            prompt = format_web_search_for_prompt(web_search_result) + "\n\n" + prompt

        # Generate response
        response = await generate_response(prompt)

        # Save conversation
        await save_conversation(
            user_id=user_id,
            session_id=session_id,
            course_id=course_id,
            query=message,
            response=response,
            sources=sources,
        )

        return Response({
            "response": response,
            "sources": sources if include_sources else [],
            "session_id": session_id,
            "metadata": metadata,
            "web_search_used": web_search,
            "web_search_results": web_search_result.get('frontend_results', []) if web_search_result and web_search_result.get('success') else [],
            "search_query": web_search_result.get('query', message) if web_search_result else None,
        })
