"""Conversations app — serializers."""
from rest_framework import serializers
from .models import Conversation


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = [
            "id", "session_id", "role", "content",
            "module_context", "course", "is_summarized", "created_at",
        ]
        read_only_fields = ["id", "created_at", "embedding"]
