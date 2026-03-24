"""
Users app models.
Maps exactly to the SQL tables: users, user_knowledge_state.
"""
import uuid
from django.db import models


class User(models.Model):
    """
    Custom user model — does NOT extend AbstractUser.
    Authentication is entirely delegated to Clerk.
    """
    SKILL_CHOICES = [
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("advanced", "Advanced"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clerk_id = models.CharField(max_length=255, unique=True, db_index=True)
    email = models.EmailField(unique=True)
    name = models.TextField(blank=True, null=True)
    skill_level = models.CharField(
        max_length=12, choices=SKILL_CHOICES, blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} ({self.clerk_id})"


class UserKnowledgeState(models.Model):
    """
    Tracks per-concept confidence scores for a user.
    Maps to: user_knowledge_state
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="knowledge_states",
        db_column="user_id",
    )
    concept = models.TextField()
    confidence_score = models.FloatField(default=0.0)
    times_practiced = models.IntegerField(default=0)
    last_error = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_knowledge_state"
        unique_together = [("user", "concept")]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user.email} — {self.concept} ({self.confidence_score:.2f})"
