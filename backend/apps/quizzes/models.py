"""
Quizzes app models.
Maps to SQL tables: quiz_questions, quiz_attempts.
"""
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.postgres.fields import ArrayField


class QuizQuestion(models.Model):
    QUESTION_TYPE_CHOICES = [
        ("mcq", "Multiple Choice"),
        ("code", "Code"),
        ("short_answer", "Short Answer"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="quiz_questions",
        db_column="course_id",
    )
    week_number = models.IntegerField(null=True, blank=True)
    day_number = models.IntegerField(null=True, blank=True)
    question_text = models.TextField()
    question_type = models.CharField(max_length=15, choices=QUESTION_TYPE_CHOICES)
    options = models.JSONField(null=True, blank=True)
    correct_answer = models.TextField(blank=True, null=True)
    explanation = models.TextField(blank=True, null=True)
    difficulty = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
    )
    concept_tags = ArrayField(models.TextField(), blank=True, default=list)

    class Meta:
        db_table = "quiz_questions"
        ordering = ["course", "week_number", "day_number"]

    def __str__(self):
        return f"[{self.question_type}] {self.question_text[:80]}"


class QuizAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="quiz_attempts",
        db_column="user_id",
    )
    question = models.ForeignKey(
        QuizQuestion,
        on_delete=models.CASCADE,
        related_name="attempts",
        db_column="question_id",
    )
    user_answer = models.TextField(blank=True, null=True)
    is_correct = models.BooleanField(null=True, blank=True)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "quiz_attempts"
        ordering = ["-attempted_at"]

    def __str__(self):
        return f"{self.user.email} — {self.question_id} ({'' if self.is_correct else ''})"
