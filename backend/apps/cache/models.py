"""
Cache app model.
Maps to SQL table: query_cache.
Vector similarity + Redis exact-match semantic cache.
"""
import uuid
from django.db import models
from pgvector.django import VectorField


class QueryCache(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    query_text = models.TextField()
    query_embedding = VectorField(dimensions=384, null=True, blank=True)
    response = models.TextField()
    hit_count = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "query_cache"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Cache: {self.query_text[:60]}…"
