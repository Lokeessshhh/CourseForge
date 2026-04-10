"""
LLM generator — calls OpenRouter API for RAG operations.
Uses the same OpenRouter configuration as the main course generation.
"""
import json
import logging
from typing import AsyncGenerator, Dict, Any, List, Optional

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

# Use OpenRouter instead of local vLLM
OPENROUTER_BASE_URL = getattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = getattr(settings, "OPENROUTER_API_KEY", "")
MODEL_NAME = getattr(settings, "OPENROUTER_LLM_MODEL", "qwen/qwen-2.5-7b-instruct")

# OpenRouter URL
LLM_URL = f"{OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"


def get_llm_url() -> str:
    return LLM_URL


async def call_llm(
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.7,
    stream: bool = False,
) -> str:
    """Call OpenRouter API."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    timeout = httpx.Timeout(connect=30.0, read=180.0, write=30.0, pool=180.0)
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://github.com/your-org/ai-course-generator",
        "X-Title": "AI Course Generator",
    }
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            OPENROUTER_BASE_URL + "/chat/completions",
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": stream,
            },
            headers=headers,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


async def llm_invoke_with_retry(
    prompt: str,
    system_prompt: str = "",
    max_retries: int = 3,
    delay_seconds: float = 2.0,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    """Call LLM with automatic retry on failure."""
    import asyncio

    last_error = None
    for attempt in range(max_retries):
        try:
            return await call_llm(
                prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as e:
            last_error = e
            logger.warning(
                "LLM call failed (attempt %d/%d): %s", attempt + 1, max_retries, e
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(delay_seconds)

    raise Exception(f"LLM failed after {max_retries} attempts: {last_error}")


async def stream_llm(prompt: str, system_prompt: str = "") -> AsyncGenerator[str, None]:
    """
    Stream tokens from the LLM.
    Yields one token at a time.
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    timeout = httpx.Timeout(connect=30.0, read=180.0, write=30.0, pool=180.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            LLM_URL,
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "max_tokens": settings.VLLM_MAX_TOKENS,
                "temperature": 0.7,
                "stream": True,
            },
            headers={
                "Authorization": f"Bearer {settings.VLLM_API_KEY}",
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"]
                        if "content" in delta and delta["content"]:
                            yield delta["content"]
                    except Exception:
                        continue


def build_rag_prompt(
    question: str,
    context_chunks: List[Dict[str, Any]],
    conversation_history: List[Dict] = None,
    knowledge_state: Optional[Dict] = None,
) -> str:
    """Build the full RAG prompt for the LLM."""

    # Format retrieved chunks
    context = "\n\n".join(
        f"[Source {i + 1}: {c.get('title', 'Document')}]\n{c['content']}"
        for i, c in enumerate(context_chunks)
    )

    # Format conversation history
    history_text = ""
    if conversation_history:
        history_text = "\n".join(
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in conversation_history[-6:]
        )
        history_text = f"\nConversation so far:\n{history_text}\n"

    # Format knowledge state
    knowledge_text = ""
    if knowledge_state:
        struggling = [
            c for c, d in knowledge_state.items()
            if d.get("confidence", 1) < 0.6
        ]
        strong = [
            c for c, d in knowledge_state.items()
            if d.get("confidence", 0) >= 0.8
        ]
        if struggling:
            knowledge_text += f"\nUser struggles with: {', '.join(struggling)}"
            knowledge_text += " → explain these carefully with examples."
        if strong:
            knowledge_text += f"\nUser already knows: {', '.join(strong)}"
            knowledge_text += " → don't over-explain these."

    return f"""You are an expert AI tutor helping students learn.
Use the context below to answer the question. Be clear, concise, and educational.
If the context doesn't have the answer, use your own knowledge but stay factual.
{knowledge_text}

CONTEXT:
{context}
{history_text}
STUDENT QUESTION: {question}

ANSWER:"""
