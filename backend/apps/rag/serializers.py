"""RAG app — serializers."""
from rest_framework import serializers
from .models import Document, Chunk


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "title", "doc_type", "topic", "metadata", "created_at"]
        read_only_fields = ["id", "created_at"]


class ChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chunk
        fields = [
            "id", "document", "content", "chunk_index",
            "level", "parent_chunk", "metadata", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class RAGQuerySerializer(serializers.Serializer):
    query = serializers.CharField(max_length=2000)
    course_id = serializers.UUIDField(required=False, allow_null=True)
    top_k = serializers.IntegerField(min_value=1, max_value=100, default=10)
    use_hyde = serializers.BooleanField(default=True)
    use_decompose = serializers.BooleanField(default=True)


class RAGSearchSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=2000)
    course_id = serializers.UUIDField(required=False, allow_null=True)
    top_k = serializers.IntegerField(min_value=1, max_value=100, default=10)


class ChunkResultSerializer(serializers.Serializer):
    chunk_id = serializers.CharField()
    content = serializers.CharField()
    score = serializers.FloatField()
    level = serializers.IntegerField()
    title = serializers.CharField(required=False, default="Document")
    topic = serializers.CharField(required=False, default="")
    metadata = serializers.DictField()
