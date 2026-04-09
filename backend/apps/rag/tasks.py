"""
RAG app — Celery tasks for async document indexing and RAPTOR building.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def index_document_task(self, document_id: str, content: str, title: str):
    """
    Legacy task: chunk a document and embed each chunk.
    For PDF uploads, use the full ingest_pdf pipeline in views instead.
    """
    try:
        from apps.rag.models import Document, Chunk
        from services.rag_pipeline.embedder import embedder
        from services.indexing.chunker import chunk_text

        doc = Document.objects.get(id=document_id)

        # Simple fixed-size chunking (~500 words)
        raw_chunks = chunk_text(content, chunk_size=500, overlap=50)
        logger.info("Document '%s' → %d chunks", title, len(raw_chunks))

        # Embed and store
        embeddings = embedder.embed_batch(raw_chunks)

        chunk_objects = []
        for i, (chunk_text_item, embedding) in enumerate(zip(raw_chunks, embeddings)):
            chunk_objects.append(
                Chunk(
                    document=doc,
                    content=chunk_text_item,
                    chunk_index=i,
                    level=0,
                    dense_embedding=embedding,
                    metadata={"source": title},
                )
            )

        Chunk.objects.bulk_create(chunk_objects, batch_size=100)
        logger.info("Indexed %d chunks for document %s", len(raw_chunks), document_id)

    except Exception as exc:
        logger.exception("index_document_task failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=120)
def build_raptor_for_document(self, document_id: str):
    """
    Build RAPTOR hierarchy for an already-indexed document.
    Useful when documents were indexed without RAPTOR.
    """
    try:
        from apps.rag.models import Chunk
        from services.indexing.raptor import build_raptor_levels

        chunks = Chunk.objects.filter(document_id=document_id, level=0).order_by(
            "chunk_index"
        )
        raw_chunks = [c.content for c in chunks]
        raw_chunk_ids = [str(c.id) for c in chunks]

        if len(raw_chunks) < 5:
            logger.info("Too few chunks (%d) for RAPTOR on doc %s", len(raw_chunks), document_id)
            return {"skipped": True, "reason": "too_few_chunks"}

        result = build_raptor_levels(
            document_id=document_id,
            raw_chunks=raw_chunks,
            raw_chunk_ids=raw_chunk_ids,
        )
        logger.info("RAPTOR built for document %s: %s", document_id, result)
        return result

    except Exception as exc:
        logger.exception("build_raptor_for_document failed: %s", exc)
        raise self.retry(exc=exc)
