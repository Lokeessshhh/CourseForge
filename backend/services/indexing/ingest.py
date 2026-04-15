"""
Full PDF ingestion pipeline.
Extracts text → chunks → contextual RAG → embed → store → build RAPTOR.
Adapted from reference FastAPI repo for Django.
"""
import logging
import re
import uuid
from typing import Optional

import fitz  # PyMuPDF

from services.rag_pipeline.embedder import embedder
from services.indexing.chunker import chunk_text
from services.indexing.contextual import contextualize_chunks_batch
from services.indexing.raptor import build_raptor_levels

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract all text from PDF bytes with layout cleaning.
    Handles dehyphenation, reading order, and artifact removal.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    full_text = ""

    for page_num, page in enumerate(doc):
        text = page.get_text(
            "text",
            sort=True,
            flags=fitz.TEXT_DEHYPHENATE | fitz.TEXT_PRESERVE_LIGATURES,
        )
        if text.strip():
            full_text += f"\n[Page {page_num + 1}]\n{text}"

    doc.close()

    # Clean repeated fragments (PDF extraction artifacts)
    full_text = clean_repeated_fragments(full_text)

    # Clean null bytes and non-UTF8 chars
    full_text = full_text.replace("\x00", "")
    full_text = full_text.encode("utf-8", errors="ignore").decode("utf-8")

    logger.info("Extracted %d characters from PDF", len(full_text))
    return full_text


def clean_repeated_fragments(text: str) -> str:
    """Clean common PDF extraction artifacts like repeated words/fragments."""
    if not text:
        return text

    # 1. Re-join obvious hyphenated words
    text = re.sub(r"(\w+)-\s*(\w+)", r"\1\2", text)

    # 2. Remove repeated words (e.g. "lay lay lay lay" → "lay")
    text = re.sub(r"\b(\w+)\s+\1(?:\s+\1){1,}", r"\1", text, flags=re.IGNORECASE)

    # 3. Remove repeated short fragments (e.g. "ers ers ers" → "ers")
    text = re.sub(r"(\b\w{2,6}\b)(?:\s+\1){3,}", r"\1", text, flags=re.IGNORECASE)

    # 4. Collapse excessive whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


async def ingest_pdf(
    title: str,
    pdf_bytes: bytes,
    topic: str = "",
    course_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    use_contextual_rag: bool = True,
    use_raptor: bool = True,
) -> dict:
    """
    Full ingestion pipeline:
    1. Extract text from PDF
    2. Save document record
    3. Chunk the text
    4. Contextual RAG — prepend context to each chunk
    5. Embed contextualized chunks
    6. Store Level 0 chunks in PostgreSQL
    7. RAPTOR — build Level 1, 2 summaries
    """
    from apps.rag.models import Document, Chunk

    # Step 1 — Extract text
    content = extract_text_from_pdf(pdf_bytes)
    if not content.strip():
        raise ValueError("PDF appears to be empty or scanned")

    # Step 2 — Save document record
    doc_id = str(uuid.uuid4())
    doc_metadata = dict(metadata or {})
    if course_id:
        doc_metadata["course_id"] = str(course_id)

    doc = Document.objects.create(
        id=doc_id,
        title=title,
        doc_type="textbook",
        topic=topic,
        metadata=doc_metadata,
    )

    # Step 3 — Chunk
    raw_chunks = chunk_text(content, chunk_size=500, overlap=50)
    logger.info("PDF '%s' → %d raw chunks", title, len(raw_chunks))

    if not raw_chunks:
        raise ValueError("No chunks created")

    # Step 4 — Contextual RAG
    if use_contextual_rag:
        logger.info("Applying Contextual RAG…")
        chunks_to_embed = await contextualize_chunks_batch(
            chunks=raw_chunks,
            document_title=title,
            max_chunks=50,
        )
    else:
        chunks_to_embed = raw_chunks

    # Step 5 — Embed all chunks
    logger.info("Embedding %d chunks…", len(chunks_to_embed))
    embeddings = await embedder.aembed_batch(chunks_to_embed)

    # Step 6 — Store Level 0 chunks (bulk create for performance)
    raw_chunk_ids = []
    chunk_objects = []
    for i, (raw_chunk, embedding) in enumerate(zip(raw_chunks, embeddings)):
        chunk_id = str(uuid.uuid4())
        raw_chunk_ids.append(chunk_id)

        chunk_objects.append(
            Chunk(
                id=chunk_id,
                document=doc,
                content=raw_chunk,
                chunk_index=i,
                level=0,
                dense_embedding=embedding,
                metadata=doc_metadata,
            )
        )

    Chunk.objects.bulk_create(chunk_objects, batch_size=100)
    logger.info("Stored %d Level 0 chunks in Postgres", len(raw_chunks))

    # --- Push to Zilliz Cloud ---
    try:
        from services.rag_pipeline.zilliz_client import zilliz
        import json
        from datetime import datetime

        zilliz_entities = []
        for i, (chunk_obj, embedding) in enumerate(zip(chunk_objects, embeddings)):
            zilliz_entities.append({
                "doc_id": str(chunk_obj.id),
                "document_id": str(chunk_obj.document_id),
                "content": chunk_obj.content,
                "chunk_index": chunk_obj.chunk_index,
                "level": chunk_obj.level,
                "parent_id": "",  # Base chunks have no parent
                "embedding": embedding,
                "meta_json": json.dumps(chunk_obj.metadata or {}),
                "created_at": datetime.now().isoformat()
            })
        
        if zilliz_entities:
            zilliz.insert(zilliz_entities)
            logger.info("Pushed %d chunks to Zilliz Cloud", len(zilliz_entities))
    except Exception as zilliz_exc:
        logger.warning("Failed to push to Zilliz Cloud (non-fatal): %s", zilliz_exc)

    # Step 7 — RAPTOR hierarchical indexing
    raptor_stats = {}
    if use_raptor and len(raw_chunks) >= 5:
        logger.info("Building RAPTOR hierarchy…")
        raptor_stats = await build_raptor_levels(
            document_id=doc_id,
            raw_chunks=raw_chunks,
            raw_chunk_ids=raw_chunk_ids,
        )

    return {
        "document_id": doc_id,
        "title": title,
        "topic": topic,
        "level0_chunks": len(raw_chunks),
        "raptor": raptor_stats,
        "contextual_rag": use_contextual_rag,
        "pages_processed": content.count("[Page "),
        "level2_summary": raptor_stats.get("doc_summary_preview", ""),
    }
