"""Certificates app — serializers."""
from rest_framework import serializers
from .models import Certificate


class CertificateSerializer(serializers.ModelSerializer):
    course_topic = serializers.CharField(source="course.topic", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.name", read_only=True)
    download_url = serializers.CharField(source="pdf_url", read_only=True)

    class Meta:
        model = Certificate
        fields = [
            "id", "course", "course_topic", "user_email", "user_name",
            "is_unlocked", "quiz_score_avg", "test_score_avg",
            "total_study_hours", "download_url", "issued_at",
        ]
        read_only_fields = ["id", "issued_at"]


class CertificateStatsSerializer(serializers.Serializer):
    """Serializer for certificate stats response."""
    is_unlocked = serializers.BooleanField()
    issued_at = serializers.DateTimeField(allow_null=True)
    download_url = serializers.CharField()
    stats = serializers.DictField()
