"""
Conversations app model.
Maps to SQL table: conversations.
Stores chat messages with pgvector embedding for semantic search.
"""
import uuid
from django.db import models
from pgvector.django import VectorField


class Conversation(models.Model):
    ROLE_CHOICES = [("user", "User"), ("assistant", "Assistant")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="conversations",
        db_column="user_id",
    )
    session_id = models.UUIDField(db_index=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    # 384-dim embedding for semantic similarity search (Tier 3 memory)
    embedding = VectorField(dimensions=384, null=True, blank=True)
    module_context = models.TextField(blank=True, null=True)
    course = models.ForeignKey(
        "courses.Course",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="conversations",
        db_column="course_id",
    )
    is_summarized = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "conversations"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["user", "session_id", "created_at"], name="conv_user_session"),
        ]

    def __str__(self):
        return f"[{self.role}] {self.content[:60]}…"
