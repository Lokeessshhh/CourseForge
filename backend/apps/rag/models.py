"""
RAG app models.
Maps to SQL tables: documents, chunks.
Uses pgvector for dense embeddings with HNSW index.
GIN full-text search index on chunks.content.
"""
import uuid
from django.db import models
from pgvector.django import VectorField


class Document(models.Model):
    """A source document in the knowledge base."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.TextField()
    doc_type = models.TextField(blank=True, null=True)
    topic = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "documents"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Chunk(models.Model):
    """
    A text chunk derived from a Document.
    Supports RAPTOR hierarchy via level + parent_chunk self-FK.
    Levels:
      0 = raw leaf chunk (~500 words)
      1 = section summary (5-10 chunks)
      2 = document summary (whole doc)
      3 = course summary (all content for topic)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="chunks",
        db_column="document_id",
    )
    content = models.TextField()
    chunk_index = models.IntegerField(null=True, blank=True)
    level = models.IntegerField(default=0)
    parent_chunk = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
        db_column="parent_chunk_id",
    )
    # pgvector field — 384 dims (matches SQL schema exactly)
    dense_embedding = VectorField(dimensions=384, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chunks"
        ordering = ["chunk_index"]

    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document.title} (level {self.level})"
