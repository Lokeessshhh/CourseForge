"""
RAG app — views.
Endpoints:
  POST /api/rag/query/    — hybrid RAG query
  POST /api/rag/index/    — index a document
  GET  /api/rag/documents/ — list documents
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Document, Chunk
from .serializers import (
    DocumentSerializer,
    RAGQuerySerializer,
    RAGIndexSerializer,
    ChunkResultSerializer,
)

logger = logging.getLogger(__name__)


def _ok(data, status_code=status.HTTP_200_OK):
    return Response({"success": True, "data": data, "error": None}, status=status_code)


def _err(msg, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"success": False, "data": None, "error": msg}, status=status_code)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def rag_query(request):
    """
    Full hybrid RAG pipeline:
    1. Check semantic cache
    2. HyDE / query decomposition (optional)
    3. Hybrid retrieval (pgvector + BM25 + RRF)
    4. bge-reranker-v2-m3 reranking
    5. Return top results + cache hit flag
    """
    serializer = RAGQuerySerializer(data=request.data)
    if not serializer.is_valid():
        return _err(serializer.errors)

    data = serializer.validated_data
    query = data["query"]
    top_k = data["top_k"]
    course_id = data.get("course_id")

    try:
        # 1. Cache check
        from services.rag_pipeline.cache import SemanticCache
        cache = SemanticCache()
        cached = cache.check_cache(query)
        if cached:
            return _ok({"cached": True, "response": cached, "chunks": []})

        # 2. HyDE or decompose
        from services.rag_pipeline.retriever import HybridRetriever
        from services.rag_pipeline.reranker import Reranker
        from services.rag_pipeline.hyde import HyDEGenerator
        from services.rag_pipeline.query_decompose import QueryDecomposer

        retriever = HybridRetriever()
        reranker = Reranker()

        if data["use_hyde"]:
            hyde = HyDEGenerator()
            query_vec = hyde.generate_embedding(query)
            chunks = retriever.retrieve_by_vector(query_vec, top_k=60, course_id=course_id)
        elif data["use_decompose"]:
            decomposer = QueryDecomposer()
            chunks = decomposer.decompose_and_retrieve(query, course_id=course_id)
        else:
            chunks = retriever.hybrid_retrieve(query, top_k=60, course_id=course_id)

        # 3. Rerank
        reranked = reranker.rerank(query, chunks, top_k=top_k)

        results = [
            {
                "chunk_id": str(c["chunk_id"]),
                "content": c["content"],
                "score": c.get("score", 0.0),
                "level": c.get("level", 0),
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
def rag_index(request):
    """Index a document into the knowledge base."""
    serializer = RAGIndexSerializer(data=request.data)
    if not serializer.is_valid():
        return _err(serializer.errors)

    data = serializer.validated_data

    try:
        # Create document record
        doc = Document.objects.create(
            title=data.get("title", "Untitled"),
            doc_type=data.get("doc_type", "text"),
            metadata={"course_id": str(data["course_id"])} if data.get("course_id") else {},
        )

        # Trigger async chunking + embedding via Celery
        from apps.rag.tasks import index_document
        index_document.delay(str(doc.id), data.get("content", ""))

        return _ok({"document_id": str(doc.id), "status": "indexing"}, status.HTTP_202_ACCEPTED)

    except Exception as exc:
        logger.exception("RAG index error: %s", exc)
        return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def document_list(request):
    """List all documents in the knowledge base."""
    docs = Document.objects.all().order_by("-created_at")
    return _ok(DocumentSerializer(docs, many=True).data)
