"""
HyDE (Hypothetical Document Embedding) + Query Decomposition.
Both improve retrieval recall on complex or vague queries.
"""
import json
import logging
from typing import List

from services.rag_pipeline.generator import llm_invoke_with_retry
from services.rag_pipeline.embedder import embedder

logger = logging.getLogger(__name__)


async def decompose_query(query: str) -> List[str]:
    """
    Break complex query into 3 simpler sub-questions.
    Falls back to original query if decomposition fails.
    """
    prompt = f"""Break the following question into exactly 3 simpler sub-questions.
Return ONLY a JSON array of 3 strings. No explanation, no markdown.

QUESTION: {query}

JSON ARRAY:"""

    try:
        result = await llm_invoke_with_retry(prompt, max_retries=2)
        result = result.strip()

        # Clean markdown code blocks
        if "```" in result:
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
            result = result.strip()

        sub_questions = json.loads(result)

        if isinstance(sub_questions, list) and len(sub_questions) >= 2:
            logger.info("Query decomposed into %d sub-questions", len(sub_questions))
            return sub_questions[:3]
    except Exception as e:
        logger.warning("Query decomposition failed: %s, using original query", e)

    return [query]


async def generate_hypothetical_answer(query: str) -> str:
    """
    HyDE: Generate a hypothetical ideal answer for the query.
    We then embed this answer and search for similar chunks.
    This improves recall on vague/paraphrased queries.
    """
    prompt = f"""Write a short, factual answer (3-5 sentences) to the following question.
Write as if you are an expert. Be specific and technical.
Do not say "I don't know" — always provide a substantive answer.

QUESTION: {query}

ANSWER:"""

    try:
        answer = await llm_invoke_with_retry(prompt, max_retries=2)
        logger.info("HyDE answer generated (%d chars)", len(answer))
        return answer.strip()
    except Exception as e:
        logger.warning("HyDE generation failed: %s, using original query", e)
        return query


async def get_hyde_embedding(query: str) -> List[float]:
    """Generate hypothetical answer and return its embedding."""
    hypothetical = await generate_hypothetical_answer(query)
    embedding = await embedder.aembed(hypothetical)
    return embedding
