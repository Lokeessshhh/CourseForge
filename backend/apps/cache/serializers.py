"""
Cache serializers for API responses.
"""
from rest_framework import serializers
from .models import QueryCache


class QueryCacheSerializer(serializers.ModelSerializer):
    """Serializer for QueryCache model."""

    class Meta:
        model = QueryCache
        fields = ["id", "query_text", "response", "hit_count", "created_at"]
        read_only_fields = ["id", "created_at"]


class CacheHitSerializer(serializers.Serializer):
    """Serializer for cache hit response."""
    hit = serializers.BooleanField()
    query = serializers.CharField()
    response = serializers.CharField(required=False)
    similarity = serializers.FloatField(required=False)
