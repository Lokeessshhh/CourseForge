"""
Add DailyActivity model for tracking daily study activity.
"""
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0005_add_coding_test_tracking"),
        ("users", "0001_initial"),  # For user reference
    ]

    operations = [
        migrations.CreateModel(
            name="DailyActivity",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("date", models.DateField()),
                ("study_minutes", models.IntegerField(default=0)),
                ("days_completed", models.IntegerField(default=0)),
                ("quizzes_taken", models.IntegerField(default=0)),
                ("user", models.ForeignKey(db_column="user_id", on_delete=models.deletion.CASCADE, related_name="daily_activities", to="users.user")),
                ("course", models.ForeignKey(db_column="course_id", on_delete=models.deletion.CASCADE, related_name="daily_activities", to="courses.course")),
            ],
            options={
                "db_table": "daily_activities",
                "ordering": ["-date"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="dailyactivity",
            unique_together={("user", "course", "date")},
        ),
    ]
