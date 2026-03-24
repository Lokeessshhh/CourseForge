from django.contrib import admin
from .models import Document, Chunk


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "doc_type", "topic", "created_at"]
    search_fields = ["title", "topic"]
    readonly_fields = ["id", "created_at"]


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ["document", "chunk_index", "level", "created_at"]
    list_filter = ["level"]
    search_fields = ["content"]
    readonly_fields = ["id", "created_at"]
