"""
RAG app — views.
Endpoints:
  POST   /api/rag/ingest-pdf/    — upload PDF and run full ingestion pipeline
  POST   /api/rag/query/        — hybrid RAG query
  POST   /api/rag/search/       — hybrid search over knowledge base
  GET    /api/rag/documents/    — list documents
  DELETE /api/rag/documents/<id>/ — delete a document
"""
import logging
import traceback

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Document, Chunk
from .serializers import (
    DocumentSerializer,
    RAGQuerySerializer,
    RAGSearchSerializer,
    ChunkResultSerializer,
)

logger = logging.getLogger(__name__)


def _ok(data, status_code=status.HTTP_200_OK):
    return Response({"success": True, "data": data, "error": None}, status=status_code)


def _err(msg, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"success": False, "data": None, "error": msg}, status=status_code)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
async def rag_ingest_pdf(request):
    """
    Upload and ingest a PDF into the knowledge base.
    Full pipeline: extract → chunk → contextualize → embed → store → RAPTOR.
    Expects multipart/form-data with fields:
      - file: PDF file
      - title: document title
      - topic: optional topic/subject
      - course_id: optional course ID for filtering
      - use_contextual_rag: optional bool (default true)
      - use_raptor: optional bool (default true)
    """
    pdf_file = request.FILES.get("file")
    if not pdf_file:
        return _err("No file provided")

    if not pdf_file.name.endswith(".pdf"):
        return _err("Only PDF files are supported")

    title = request.data.get("title", pdf_file.name)
    topic = request.data.get("topic", "")
    course_id = request.data.get("course_id")
    use_contextual = request.data.get("use_contextual_rag", "true").lower() == "true"
    use_raptor = request.data.get("use_raptor", "true").lower() == "true"

    pdf_bytes = pdf_file.read()
    if not pdf_bytes:
        return _err("Uploaded file is empty")

    try:
        from services.indexing.ingest import ingest_pdf

        result = await ingest_pdf(
            title=title,
            pdf_bytes=pdf_bytes,
            topic=topic,
            course_id=course_id,
            use_contextual_rag=use_contextual,
            use_raptor=use_raptor,
        )
        return _ok(result, status.HTTP_201_CREATED)

    except ValueError as e:
        return _err(str(e), status.HTTP_422_UNPROCESSABLE_ENTITY)
    except Exception as e:
        logger.exception("PDF ingestion error: %s", e)
        return _err(str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
async def rag_query(request):
    """
    Full hybrid RAG query pipeline:
    1. Check semantic cache
    2. Query decomposition + HyDE
    3. Hybrid retrieval (pgvector + BM25 + RRF)
    4. bge-reranker-v2-m3 reranking
    5. Return top results
    """
    serializer = RAGQuerySerializer(data=request.data)
    if not serializer.is_valid():
        return _err(serializer.errors)

    data = serializer.validated_data
    query = data["query"]
    top_k = data["top_k"]
    course_id = data.get("course_id")
    use_hyde = data.get("use_hyde", True)
    use_decompose = data.get("use_decompose", True)

    try:
        # 1. Cache check
        from apps.memory.cache import get_cached_response
        cached = await get_cached_response(query)
        if cached:
            return _ok({"cached": True, "response": cached, "chunks": []})

        # 2. Hybrid retrieval
        from services.rag_pipeline.retriever import hybrid_retrieve
        chunks = await hybrid_retrieve(
            query=query,
            top_k=60,
            course_id=course_id,
            use_hyde=use_hyde,
            use_decomposition=use_decompose,
        )

        # 3. Rerank
        from services.rag_pipeline.reranker import reranker
        reranked = await reranker.rerank(query, chunks, top_k=top_k)

        results = [
            {
                "chunk_id": c["chunk_id"],
                "content": c["content"],
                "score": c.get("rerank_score", c.get("score", 0.0)),
                "level": c.get("level", 0),
                "title": c.get("title", "Document"),
                "topic": c.get("topic", ""),
                "metadata": c.get("metadata", {}),
            }
            for c in reranked
        ]
        return _ok({"cached": False, "chunks": results})

    except Exception as exc:
        logger.exception("RAG query error: %s", exc)
        return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def rag_search(request):
    """
    Simple hybrid search over the knowledge base.
    No HyDE, no decomposition, no reranking — just dense + sparse + RRF.
    Useful for document search UI.
    """
    serializer = RAGSearchSerializer(data=request.data)
    if not serializer.is_valid():
        return _err(serializer.errors)

    data = serializer.validated_data
    query = data["query"]
    top_k = data.get("top_k", 10)
    course_id = data.get("course_id")

    try:
        from services.rag_pipeline.retriever import HybridRetriever
        from asgiref.sync import async_to_sync
        retriever = HybridRetriever()
        results = async_to_sync(retriever.hybrid_retrieve)(query, top_k=top_k, course_id=course_id)

        return _ok({"results_count": len(results), "results": results})

    except Exception as exc:
        logger.exception("RAG search error: %s", exc)
        return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def document_list(request):
    """List all documents in the knowledge base."""
    docs = Document.objects.all().order_by("-created_at")
    return _ok(DocumentSerializer(docs, many=True).data)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def document_delete(request, document_id):
    """Delete a document and all its chunks."""
    try:
        doc = Document.objects.get(id=document_id)
        doc.delete()  # CASCADE deletes chunks
        return _ok({"message": "Document deleted"})
    except Document.DoesNotExist:
        return _err("Document not found", status.HTTP_404_NOT_FOUND)
    except Exception as exc:
        logger.exception("Document delete error: %s", exc)
        return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
