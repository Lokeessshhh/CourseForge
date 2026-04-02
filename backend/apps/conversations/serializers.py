"""Conversations app — serializers."""
from rest_framework import serializers
from .models import Conversation


class ConversationSerializer(serializers.ModelSerializer):
    date = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id", "session_id", "role", "content",
            "module_context", "course", "is_summarized", "created_at", "date",
        ]
        read_only_fields = ["id", "created_at", "embedding"]

    def get_date(self, obj):
        """Return formatted date string for display."""
        if obj.created_at:
            return obj.created_at.strftime("%Y-%m-%d")
        return None
