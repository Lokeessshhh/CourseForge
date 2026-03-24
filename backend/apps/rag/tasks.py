"""RAG app — Celery task for async document indexing."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def index_document(self, document_id: str, content: str):
    """Chunk a document and embed each chunk with pgvector."""
    try:
        from apps.rag.models import Document, Chunk
        from services.llm.embeddings import EmbeddingService

        doc = Document.objects.get(id=document_id)
        embedder = EmbeddingService()

        # Simple fixed-size chunking (~500 words)
        words = content.split()
        chunk_size = 500
        chunks_text = [
            " ".join(words[i : i + chunk_size])
            for i in range(0, len(words), chunk_size)
        ]

        for idx, chunk_text in enumerate(chunks_text):
            vector = embedder.embed_text(chunk_text, model="fallback")
            Chunk.objects.create(
                document=doc,
                content=chunk_text,
                chunk_index=idx,
                level=0,
                dense_embedding=vector,
                metadata={"source": doc.title},
            )

        logger.info("Indexed %d chunks for document %s", len(chunks_text), document_id)
    except Exception as exc:
        logger.exception("index_document task failed: %s", exc)
        raise self.retry(exc=exc)
