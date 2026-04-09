"""RAG app URL patterns — /api/rag/"""
from django.urls import path
from . import views

urlpatterns = [
    path("ingest-pdf/", views.rag_ingest_pdf, name="rag-ingest-pdf"),
    path("query/", views.rag_query, name="rag-query"),
    path("search/", views.rag_search, name="rag-search"),
    path("documents/", views.document_list, name="document-list"),
    path("documents/<uuid:document_id>/", views.document_delete, name="document-delete"),
]
