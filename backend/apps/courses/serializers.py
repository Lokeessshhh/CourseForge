"""Courses app — serializers."""
from rest_framework import serializers
from .models import Course, WeekPlan, DayPlan


class DayPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = DayPlan
        fields = [
            "id", "day_number", "title", "tasks",
            "theory_content", "code_content",
            "theory_generated", "code_generated", "quiz_generated",
            "is_completed", "is_locked",
            "completed_at",
        ]
        read_only_fields = [
            "id", "completed_at",
            "theory_generated", "code_generated", "quiz_generated",
        ]


class DayPlanDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single day view - includes content."""
    class Meta:
        model = DayPlan
        fields = [
            "id", "day_number", "title", "tasks",
            "theory_content", "code_content",
            "theory_generated", "code_generated", "quiz_generated",
            "is_completed", "is_locked",
            "completed_at",
        ]
        read_only_fields = [
            "id", "completed_at",
            "theory_generated", "code_generated", "quiz_generated",
        ]


class QuizQuestionSerializer(serializers.Serializer):
    """Serializer for quiz questions (without answers)."""
    id = serializers.UUIDField()
    question_number = serializers.IntegerField()
    question_text = serializers.CharField()
    options = serializers.DictField()


class QuizSubmitSerializer(serializers.Serializer):
    """Serializer for quiz submission."""
    answers = serializers.DictField(
        child=serializers.CharField(),
        help_text="Map of question_number to answer (a/b/c/d)"
    )


class WeekPlanSerializer(serializers.ModelSerializer):
    days = DayPlanSerializer(many=True, read_only=True)
    test_unlocked = serializers.BooleanField(read_only=True)
    test_generated = serializers.BooleanField(read_only=True)

    class Meta:
        model = WeekPlan
        fields = ["id", "week_number", "theme", "objectives", "is_completed", "test_unlocked", "test_generated", "days"]
        read_only_fields = ["id"]


class CourseSerializer(serializers.ModelSerializer):
    weeks = WeekPlanSerializer(many=True, read_only=True)
    total_days = serializers.ReadOnlyField()
    generation_status = serializers.CharField(read_only=True)
    generation_progress = serializers.IntegerField(read_only=True)

    class Meta:
        model = Course
        fields = [
            "id", "course_name", "topic", "level", "duration_weeks", "hours_per_day",
            "goals", "status", "generation_status", "generation_progress",
            "total_days", "created_at", "weeks",
        ]
        read_only_fields = ["id", "topic", "created_at", "status", "generation_status", "generation_progress"]


class CourseListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list endpoint (no nested weeks)."""
    total_days = serializers.ReadOnlyField()
    generation_status = serializers.CharField(read_only=True)

    class Meta:
        model = Course
        fields = [
            "id", "course_name", "topic", "level", "duration_weeks", "hours_per_day",
            "goals", "status", "generation_status", "total_days", "created_at",
        ]
        read_only_fields = ["id", "topic", "created_at"]


class CourseGenerateSerializer(serializers.Serializer):
    """Serializer for course creation with 3 fields."""
    course_name = serializers.CharField(
        max_length=255,
        help_text="Name/title of the course (e.g., 'Python for Data Science')"
    )
    duration = serializers.CharField(
        max_length=50,
        required=False,
        default="1 month",
        help_text="Duration string like '2 weeks', '1 month', '3 months'"
    )
    level = serializers.ChoiceField(
        choices=["beginner", "intermediate", "advanced"],
        required=False,
        default="beginner",
        help_text="Course difficulty level"
    )
    hours_per_day = serializers.IntegerField(
        min_value=1, max_value=12, default=2,
        help_text="Hours of study per day"
    )
    goals = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
        help_text="Learning goals (optional)"
    )


class CodingProblemSerializer(serializers.Serializer):
    """Serializer for coding problem."""
    problem_number = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField()
    difficulty = serializers.CharField()
    starter_code = serializers.CharField()
    test_cases = serializers.ListField()
    hints = serializers.ListField()


class CodingTestSerializer(serializers.Serializer):
    """Serializer for coding test (without solutions)."""
    week_number = serializers.IntegerField()
    total_problems = serializers.IntegerField()
    problems = CodingProblemSerializer(many=True)


class CodingSubmissionSerializer(serializers.Serializer):
    """Serializer for coding test submission."""
    submissions = serializers.DictField(
        child=serializers.DictField(),
        help_text="Map of problem_number to {code, language}"
    )


class CourseProgressSerializer(serializers.Serializer):
    course_id = serializers.UUIDField()
    total_days = serializers.IntegerField()
    completed_days = serializers.IntegerField()
    percentage = serializers.FloatField()
    current_week = serializers.IntegerField()
    current_day = serializers.IntegerField()
    weeks = serializers.ListField()
    average_quiz_score = serializers.FloatField(allow_null=True)
    certificate_earned = serializers.BooleanField()


class CourseStatusSerializer(serializers.Serializer):
    """Serializer for course generation status polling."""
    course_id = serializers.UUIDField()
    status = serializers.CharField()
    generation_status = serializers.CharField()
    progress = serializers.CharField()
    total_days = serializers.IntegerField()
    days_filled = serializers.IntegerField()
