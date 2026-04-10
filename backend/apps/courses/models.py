"""
Courses app models.
Maps exactly to SQL tables: courses, week_plans, day_plans, weekly_tests, coding_tests, course_progress.
"""
import uuid
from django.db import models
from django.contrib.postgres.fields import ArrayField


class Course(models.Model):
    """Top-level course object."""
    STATUS_CHOICES = [
        ("active", "Active"),
        ("archived", "Archived"),
        ("generating", "Generating"),
    ]

    GENERATION_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("generating", "Generating"),
        ("ready", "Ready"),
        ("failed", "Failed"),
    ]

    LEVEL_CHOICES = [
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("advanced", "Advanced"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="courses",
        db_column="user_id",
    )
    course_name = models.CharField(max_length=255)  # User-defined course name
    topic = models.TextField()  # AI-detected topic from course_name
    description = models.TextField(blank=True, null=True, help_text="Optional user-provided course description/requirements")  # User-provided description
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default="beginner")
    duration_weeks = models.IntegerField(null=True, blank=True)
    hours_per_day = models.IntegerField(null=True, blank=True)
    goals = ArrayField(models.TextField(), blank=True, default=list)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    generation_status = models.CharField(
        max_length=20,
        choices=GENERATION_STATUS_CHOICES,
        default="pending",
    )
    generation_progress = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "courses"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.course_name} ({self.user.email})"

    @property
    def total_days(self) -> int:
        """Total days in course (weeks × 5)."""
        return (self.duration_weeks or 0) * 5


class WeekPlan(models.Model):
    """A single week within a course."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="weeks",
        db_column="course_id",
    )
    week_number = models.IntegerField()
    theme = models.TextField(blank=True, null=True)
    objectives = ArrayField(models.TextField(), blank=True, default=list)
    is_completed = models.BooleanField(default=False)
    # Weekly test fields
    test_generated = models.BooleanField(default=False)
    test_unlocked = models.BooleanField(default=False)  # Unlocks after all 5 days completed
    # Coding test tracking
    coding_tests_generated = models.BooleanField(default=False)
    coding_test_1_unlocked = models.BooleanField(default=False)
    coding_test_1_completed = models.BooleanField(default=False)
    coding_test_2_unlocked = models.BooleanField(default=False)
    coding_test_2_completed = models.BooleanField(default=False)

    class Meta:
        db_table = "week_plans"
        ordering = ["week_number"]
        unique_together = [("course", "week_number")]

    def __str__(self):
        return f"Week {self.week_number} — {self.course.topic}"


class DayPlan(models.Model):
    """A single day within a week plan."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    week_plan = models.ForeignKey(
        WeekPlan,
        on_delete=models.CASCADE,
        related_name="days",
        db_column="week_plan_id",
    )
    day_number = models.IntegerField()
    title = models.TextField(blank=True, null=True)
    tasks = models.JSONField(default=dict, blank=True)
    # Content fields - filled by AI
    theory_content = models.TextField(blank=True, default="")
    code_content = models.TextField(blank=True, default="")
    quiz_raw = models.TextField(blank=True, default="")  # Raw JSON from LLM
    # Status fields
    is_completed = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=True)
    theory_generated = models.BooleanField(default=False)
    code_generated = models.BooleanField(default=False)
    quiz_generated = models.BooleanField(default=False)
    # Time tracking fields
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_spent_minutes = models.IntegerField(default=0)
    # Quiz tracking
    quiz_score = models.FloatField(null=True, blank=True)
    quiz_attempts = models.IntegerField(default=0)

    class Meta:
        db_table = "day_plans"
        ordering = ["day_number"]
        unique_together = [("week_plan", "day_number")]

    def __str__(self):
        return f"Day {self.day_number} of Week {self.week_plan.week_number}"


class WeeklyTest(models.Model):
    """Weekly test covering all 5 days of a week - 10 MCQ questions."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="weekly_tests",
        db_column="course_id",
    )
    week_number = models.IntegerField()
    questions = models.JSONField(default=list)  # List of 10 MCQ questions
    total_questions = models.IntegerField(default=10)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "weekly_tests"
        unique_together = [("course", "week_number")]

    def __str__(self):
        return f"Week {self.week_number} MCQ Test - {self.course.course_name}"


class CodingTest(models.Model):
    """Weekly coding test - 2 separate tests per week."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="coding_tests",
        db_column="course_id",
    )
    week_number = models.IntegerField()
    test_number = models.IntegerField(default=1)  # 1 or 2
    problems = models.JSONField(default=list)  # List of coding problems
    total_problems = models.IntegerField(default=2)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "coding_tests"
        unique_together = [("course", "week_number", "test_number")]

    def __str__(self):
        return f"Week {self.week_number} Coding Test {self.test_number} - {self.course.course_name}"


class CodingTestAttempt(models.Model):
    """User attempt at a coding test."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="coding_test_attempts",
        db_column="user_id",
    )
    coding_test = models.ForeignKey(
        CodingTest,
        on_delete=models.CASCADE,
        related_name="attempts",
        db_column="coding_test_id",
    )
    submissions = models.JSONField(default=dict)  # {problem_number: {code, language, passed, output}}
    score = models.IntegerField()  # Number of problems passed
    total = models.IntegerField(default=2)
    percentage = models.FloatField()
    passed = models.BooleanField(default=False)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "coding_test_attempts"
        ordering = ["-attempted_at"]

    def __str__(self):
        return f"Coding Test Week {self.coding_test.week_number} by {self.user.email}"


class WeeklyTestAttempt(models.Model):
    """User attempt at a weekly test."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="weekly_test_attempts",
        db_column="user_id",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="weekly_test_attempts",
        db_column="course_id",
    )
    week_number = models.IntegerField()
    answers = models.JSONField(default=dict)
    score = models.IntegerField()
    total = models.IntegerField()
    percentage = models.FloatField()
    passed = models.BooleanField(default=False)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "weekly_test_attempts"
        ordering = ["-attempted_at"]

    def __str__(self):
        return f"Week {self.week_number} Attempt by {self.user.email}"


class CourseProgress(models.Model):
    """Complete progress tracking for a user in a course."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="course_progress",
        db_column="user_id",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="progress_records",
        db_column="course_id",
    )
    total_days = models.IntegerField(default=0)
    completed_days = models.IntegerField(default=0)
    total_weeks = models.IntegerField(default=0)
    completed_weeks = models.IntegerField(default=0)
    current_week = models.IntegerField(default=1)
    current_day = models.IntegerField(default=1)
    overall_percentage = models.FloatField(default=0.0)
    avg_quiz_score = models.FloatField(default=0.0)
    avg_test_score = models.FloatField(default=0.0)
    total_study_time = models.IntegerField(default=0)  # in minutes
    streak_days = models.IntegerField(default=0)
    last_activity = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "course_progress"
        unique_together = [("user", "course")]

    def __str__(self):
        return f"Progress: {self.user.email} - {self.course.topic}"
