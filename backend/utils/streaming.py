"""
Streaming utilities for Server-Sent Events (SSE) and WebSocket streaming.
Provides helpers for real-time AI response streaming.
"""
import logging
import json
from typing import AsyncGenerator, Optional, Dict, Any, List, Callable
import asyncio

from django.http import StreamingHttpResponse

logger = logging.getLogger(__name__)


class SSEEncoder:
    """Encoder for Server-Sent Events format."""

    @staticmethod
    def encode(data: Dict[str, Any], event: Optional[str] = None) -> str:
        """
        Encode data as SSE format.
        
        Args:
            data: Data to encode
            event: Optional event type
            
        Returns:
            SSE formatted string
        """
        lines = []
        
        if event:
            lines.append(f"event: {event}")
        
        json_data = json.dumps(data)
        lines.append(f"data: {json_data}")
        lines.append("")
        lines.append("")
        
        return "\n".join(lines)

    @staticmethod
    def encode_done() -> str:
        """Encode SSE done signal."""
        return "data: [DONE]\n\n"


class SSEStream:
    """Server-Sent Events stream generator."""

    def __init__(self):
        """Initialize SSE stream."""
        self.encoder = SSEEncoder()

    async def stream_response(
        self,
        generator: AsyncGenerator[str, None],
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream response chunks as SSE.
        
        Args:
            generator: Async generator yielding text chunks
            on_chunk: Optional callback for each chunk
            
        Yields:
            SSE formatted strings
        """
        try:
            async for chunk in generator:
                if on_chunk:
                    on_chunk(chunk)
                
                yield self.encoder.encode({"content": chunk})
            
            yield self.encoder.encode_done()
            
        except Exception as e:
            logger.exception("SSE streaming error: %s", e)
            yield self.encoder.encode({"error": str(e)}, event="error")


def sse_response(
    generator: AsyncGenerator[str, None],
    headers: Optional[Dict[str, str]] = None,
) -> StreamingHttpResponse:
    """
    Create SSE streaming response.
    
    Args:
        generator: Async generator yielding text chunks
        headers: Optional additional headers
        
    Returns:
        StreamingHttpResponse
    """
    stream = SSEStream()
    
    default_headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # Disable nginx buffering
    }
    
    if headers:
        default_headers.update(headers)
    
    return StreamingHttpResponse(
        stream.stream_response(generator),
        headers=default_headers,
    )


async def stream_from_llm(
    llm_client,
    messages: List[Dict[str, str]],
    system_prompt: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """
    Stream response from LLM client.
    
    Args:
        llm_client: LLM client with streaming support
        messages: Chat messages
        system_prompt: Optional system prompt
        max_tokens: Maximum tokens
        temperature: Temperature setting
        
    Yields:
        Text chunks
    """
    try:
        async for chunk in llm_client.stream_chat(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        ):
            yield chunk
            
    except Exception as e:
        logger.exception("LLM streaming error: %s", e)
        yield f"[Error: {str(e)}]"


class TokenBuffer:
    """Buffer for accumulating tokens with sentence boundary detection."""

    def __init__(self, flush_on_sentence: bool = True, min_flush_size: int = 10):
        """
        Initialize token buffer.
        
        Args:
            flush_on_sentence: Whether to flush on sentence boundaries
            min_flush_size: Minimum tokens before flush
        """
        self.flush_on_sentence = flush_on_sentence
        self.min_flush_size = min_flush_size
        self.buffer = ""

    def add(self, token: str) -> Optional[str]:
        """
        Add token to buffer.
        
        Args:
            token: Token to add
            
        Returns:
            Flushed content if conditions met, else None
        """
        self.buffer += token
        
        if self._should_flush():
            return self.flush()
        
        return None

    def _should_flush(self) -> bool:
        """Check if buffer should be flushed."""
        if len(self.buffer) < self.min_flush_size:
            return False
        
        if self.flush_on_sentence:
            # Check for sentence-ending punctuation
            if self.buffer.rstrip().endswith((".", "!", "?", "。", "！", "？")):
                return True
        
        return False

    def flush(self) -> str:
        """
        Flush buffer contents.
        
        Returns:
            Buffer contents
        """
        content = self.buffer
        self.buffer = ""
        return content

    def has_remaining(self) -> bool:
        """Check if buffer has remaining content."""
        return bool(self.buffer)


class RateLimiter:
    """Rate limiter for streaming responses."""

    def __init__(self, tokens_per_second: int = 100):
        """
        Initialize rate limiter.
        
        Args:
            tokens_per_second: Maximum tokens per second
        """
        self.tokens_per_second = tokens_per_second
        self.interval = 1.0 / tokens_per_second

    async def limit(self, generator: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
        """
        Rate-limited generator.
        
        Args:
            generator: Input generator
            
        Yields:
            Rate-limited chunks
        """
        async for chunk in generator:
            yield chunk
            await asyncio.sleep(self.interval)


def create_streaming_generator(
    chunks: List[str],
    delay: float = 0.01,
) -> AsyncGenerator[str, None]:
    """
    Create async generator from list of chunks.
    
    Args:
        chunks: List of text chunks
        delay: Delay between chunks
        
    Yields:
        Text chunks
    """
    async def generator():
        for chunk in chunks:
            yield chunk
            if delay > 0:
                await asyncio.sleep(delay)
    
    return generator()


async def merge_streams(
    *generators: AsyncGenerator[str, None],
) -> AsyncGenerator[str, None]:
    """
    Merge multiple async generators.
    
    Args:
        generators: Multiple async generators
        
    Yields:
        Combined chunks
    """
    async def consume(gen, queue):
        try:
            async for item in gen:
                await queue.put(item)
        finally:
            await queue.put(None)  # Signal completion

    queue = asyncio.Queue()
    tasks = [
        asyncio.create_task(consume(gen, queue))
        for gen in generators
    ]

    completed = 0
    while completed < len(generators):
        item = await queue.get()
        if item is None:
            completed += 1
        else:
            yield item

    # Clean up tasks
    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
