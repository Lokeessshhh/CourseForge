"""Users app — DRF serializers."""
from rest_framework import serializers
from .models import User, UserKnowledgeState


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name", "skill_level", "created_at"]
        read_only_fields = ["id", "email", "created_at"]


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["name", "skill_level"]


class UserKnowledgeStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserKnowledgeState
        fields = [
            "id", "concept", "confidence_score",
            "times_practiced", "last_error", "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]


class UserKnowledgeStateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserKnowledgeState
        fields = ["confidence_score", "times_practiced", "last_error"]
