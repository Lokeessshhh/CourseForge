"""
RAPTOR — Recursive Abstractive Processing for Tree-Organized Retrieval.
Builds a 4-level hierarchical summary tree:
  Level 0 → raw chunks (already stored)
  Level 1 → section summaries (groups of 5 chunks)
  Level 2 → document summary (summary of all L1)
  Level 3 → course-level summary across all documents
"""
import logging
import uuid
from typing import List, Dict

from django.db import connection

from services.rag_pipeline.embedder import embedder
from services.rag_pipeline.generator import llm_invoke_with_retry

logger = logging.getLogger(__name__)


async def summarize_chunks(chunks: List[str]) -> str:
    """
    Summarize a group of chunks using Map-Reduce approach.
    Handles large sets by recursive collapsing.
    """
    if not chunks:
        return ""

    if len(chunks) == 1:
        prompt = f"""Summarize the following text in 2-3 sentences only.
Be very concise. Key concepts only.
TEXT:
{chunks[0]}
SUMMARY:"""
        return await llm_invoke_with_retry(prompt, max_retries=2)

    # ── MAP: Summarize each chunk individually (parallel via asyncio) ──
    import asyncio

    map_prompts = [
        f"""Summarize the following text in 1-2 sentences only.
Be very concise. Extract only the key concepts.
TEXT:
{c}
SUMMARY:"""
        for c in chunks
    ]

    individual_summaries = await asyncio.gather(
        *[llm_invoke_with_retry(p, max_retries=2) for p in map_prompts],
        return_exceptions=True,
    )

    valid_summaries = [
        s for s in individual_summaries if isinstance(s, str) and s.strip()
    ]

    if not valid_summaries:
        return "No valid summaries generated."

    # ── RECURSIVE COLLAPSE if too many summaries ──
    if len(valid_summaries) > 15:
        batches = [
            valid_summaries[i : i + 10]
            for i in range(0, len(valid_summaries), 10)
        ]
        collapsed = await asyncio.gather(
            *[summarize_chunks(batch) for batch in batches]
        )
        valid_summaries = [
            s for s in collapsed if isinstance(s, str) and s.strip()
        ]

    # ── REDUCE: Merge individual summaries ──
    combined = "\n\n".join(valid_summaries)
    reduce_prompt = f"""Summarize the following key points into 2-3 sentences only.
Be very concise. Focus only on the most important concept across all points.
KEY POINTS:
{combined}
SUMMARY:"""

    return await llm_invoke_with_retry(reduce_prompt, max_retries=2)


async def build_raptor_levels(
    document_id: str,
    raw_chunks: List[str],
    raw_chunk_ids: List[str],
) -> Dict:
    """
    Build 4-level RAPTOR hierarchy:
    Level 0 → raw chunks (already stored)
    Level 1 → section summaries (every 5 raw chunks)
    Level 2 → document summary (merged from all L1)
    """
    logger.info(
        "Building RAPTOR for doc %s with %d chunks", document_id, len(raw_chunks)
    )

    level1_ids = []
    level1_summaries = []

    # ── Level 1: Section summaries (every 5 raw chunks) ──
    group_size = 5
    for i in range(0, len(raw_chunks), group_size):
        group = raw_chunks[i : i + group_size]
        group_ids = raw_chunk_ids[i : i + group_size]

        summary = await summarize_chunks(group)
        if not summary:
            continue

        embedding = await embedder.aembed(summary)
        vec_str = "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"

        chunk_id = str(uuid.uuid4())
        parent_id = group_ids[0] if group_ids else None

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO chunks
                    (id, document_id, content, chunk_index, level,
                     parent_chunk_id, dense_embedding)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s::vector)
                """,
                [
                    chunk_id,
                    document_id,
                    summary,
                    i // group_size,
                    1,
                    parent_id,
                    vec_str,
                ],
            )

        level1_ids.append(chunk_id)
        level1_summaries.append(summary)
        logger.info("Level 1 chunk %d created", i // group_size + 1)

    if not level1_summaries:
        return {
            "level0_chunks": len(raw_chunks),
            "level1_sections": 0,
            "level2_doc_summary": 0,
        }

    # ── Level 2.0: Intermediate summaries (groups of 8 L1) ──
    l2_group_size = 8
    intermediate_summaries = []
    l2_batches = [
        level1_summaries[i : i + l2_group_size]
        for i in range(0, len(level1_summaries), l2_group_size)
    ]
    logger.info(
        "Level 2.0: %d L1 summaries → %d intermediate groups",
        len(level1_summaries),
        len(l2_batches),
    )

    import asyncio

    for batch in l2_batches:
        inter_summary = await summarize_chunks(batch)
        intermediate_summaries.append(inter_summary)

    # ── Level 2.5: Final document summary ──
    doc_summary = await summarize_chunks(intermediate_summaries)
    logger.info(
        "Level 2.5: merged %d intermediates → final doc summary",
        len(intermediate_summaries),
    )

    embedding = await embedder.aembed(doc_summary)
    vec_str = "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"

    doc_summary_id = str(uuid.uuid4())
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO chunks
                (id, document_id, content, chunk_index, level,
                 parent_chunk_id, dense_embedding)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s::vector)
            """,
            [
                doc_summary_id,
                document_id,
                doc_summary,
                0,
                2,
                level1_ids[0] if level1_ids else None,
                vec_str,
            ],
        )

    return {
        "level0_chunks": len(raw_chunks),
        "level1_sections": len(level1_ids),
        "level2_doc_summary": 1,
        "doc_summary_preview": doc_summary[:200],
        "doc_summary_full": doc_summary,
    }


async def build_level3_course_summary(
    topic: str,
    level2_summaries: List[str],
    document_ids: List[str],
) -> str:
    """
    Level 3: Course-level summary across ALL documents in a subject.
    Called after all PDFs in a topic are ingested.
    """
    if not level2_summaries:
        return ""

    logger.info("Building Level 3 course summary for topic: %s", topic)

    course_summary = await summarize_chunks(level2_summaries)

    embedding = await embedder.aembed(course_summary)
    vec_str = "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"

    chunk_id = str(uuid.uuid4())
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO chunks
                (id, document_id, content, chunk_index, level,
                 parent_chunk_id, dense_embedding, metadata)
            VALUES
                (%s, %s, %s, %s, %s, NULL, %s::vector, %s::jsonb)
            """,
            [
                chunk_id,
                document_ids[0],
                course_summary,
                0,
                3,
                vec_str,
                '{"topic": "%s", "type": "course_summary", "covers_documents": %d}'
                % (topic, len(document_ids)),
            ],
        )

    logger.info("Level 3 course summary created for '%s'", topic)
    return course_summary
