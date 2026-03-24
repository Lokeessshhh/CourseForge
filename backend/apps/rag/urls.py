"""RAG app URL patterns — /api/rag/"""
from django.urls import path
from . import views

urlpatterns = [
    path("query/",     views.rag_query,     name="rag-query"),
    path("index/",     views.rag_index,     name="rag-index"),
    path("documents/", views.document_list, name="document-list"),
]
