"""
Contextual RAG — prepend 2-3 sentences of context before embedding each chunk.
Based on Anthropic's approach: 49% fewer retrieval failures.
"""
import logging
from typing import List

from services.rag_pipeline.generator import llm_invoke_with_retry

logger = logging.getLogger(__name__)


async def prepend_context_to_chunk(
    chunk: str,
    document_title: str,
    document_summary: str = "",
) -> str:
    """
    Before embedding a chunk, prepend 2-3 sentences of context
    so the chunk makes sense when retrieved in isolation.
    Falls back to raw chunk if LLM call fails.
    """
    prompt = f"""Here is a document titled: "{document_title}"

Document overview: {document_summary[:500] if document_summary else "A technical document"}

Here is a specific chunk from this document:
<chunk>
{chunk}
</chunk>

In 2-3 sentences, explain what this chunk is about in the context
of the full document. Be very concise. Do not repeat the chunk content.

CONTEXT:"""

    try:
        context = await llm_invoke_with_retry(prompt, max_retries=2)
        contextualized = f"{context.strip()}\n\n{chunk}"
        return contextualized
    except Exception as e:
        logger.warning("Contextual prepend failed, using raw chunk: %s", e)
        return chunk


async def contextualize_chunks_batch(
    chunks: List[str],
    document_title: str,
    document_summary: str = "",
    max_chunks: int = 50,
) -> List[str]:
    """
    Contextualize all chunks for a document.
    Limits to first max_chunks to control cost.
    Remaining chunks use raw text.
    """
    chunks_to_process = chunks[:max_chunks]
    logger.info(
        "Contextualizing %d chunks for '%s'", len(chunks_to_process), document_title
    )

    # Process sequentially to avoid overwhelming the LLM
    contextualized = []
    for i, chunk in enumerate(chunks_to_process):
        result = await prepend_context_to_chunk(chunk, document_title, document_summary)
        contextualized.append(result)
        if (i + 1) % 10 == 0:
            logger.info("Contextualized %d/%d chunks", i + 1, len(chunks_to_process))

    # For remaining chunks beyond max_chunks, use raw
    if len(chunks) > max_chunks:
        contextualized.extend(chunks[max_chunks:])

    return contextualized
