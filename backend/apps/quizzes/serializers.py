"""Quizzes app — serializers."""
from rest_framework import serializers
from .models import QuizQuestion, QuizAttempt


class QuizQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizQuestion
        fields = [
            "id", "course", "week_number", "day_number",
            "question_text", "question_type", "options",
            "difficulty", "concept_tags",
            # NOTE: correct_answer and explanation are excluded for students
        ]
        read_only_fields = ["id"]


class QuizQuestionDetailSerializer(serializers.ModelSerializer):
    """Includes correct_answer — for results endpoint only."""
    class Meta:
        model = QuizQuestion
        fields = "__all__"
        read_only_fields = ["id"]


class QuizAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizAttempt
        fields = ["id", "question", "user_answer", "is_correct", "attempted_at"]
        read_only_fields = ["id", "is_correct", "attempted_at"]


class QuizSubmitSerializer(serializers.Serializer):
    """Input for bulk quiz submission."""
    answers = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField(allow_blank=True)),
        allow_empty=False,
    )
    # Each answer: {"question_id": "<uuid>", "answer": "<text>"}
