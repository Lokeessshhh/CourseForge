"""
Certificates app model.
Maps to SQL table: certificates.
UNIQUE(user_id, course_id).
"""
import uuid
from django.db import models


class Certificate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="certificates",
        db_column="user_id",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="certificates",
        db_column="course_id",
    )
    is_unlocked = models.BooleanField(default=False)
    quiz_score_avg = models.FloatField(default=0.0)
    test_score_avg = models.FloatField(default=0.0)
    total_study_hours = models.FloatField(default=0.0)
    pdf_url = models.TextField(blank=True, default="")
    issued_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "certificates"
        unique_together = [("user", "course")]
        ordering = ["-issued_at"]

    def __str__(self):
        return f"Certificate: {self.user.email} — {self.course.topic}"
