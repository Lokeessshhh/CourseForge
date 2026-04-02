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
    progress = serializers.SerializerMethodField()
    current_week = serializers.SerializerMethodField()
    current_day = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id", "course_name", "topic", "level", "duration_weeks", "hours_per_day",
            "goals", "status", "generation_status", "generation_progress",
            "total_days", "created_at", "weeks",
            "progress", "current_week", "current_day",
        ]
        read_only_fields = ["id", "topic", "created_at", "status", "generation_status", "generation_progress", "progress", "current_week", "current_day"]

    def get_progress(self, obj):
        """Calculate progress percentage from CourseProgress."""
        try:
            from .models import CourseProgress
            request = self.context.get('request')
            if request and request.user:
                cp = CourseProgress.objects.filter(course=obj, user=request.user).first()
                if cp:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"CourseSerializer: Course {obj.id}, User {request.user.id}, progress={cp.overall_percentage}, completed_days={cp.completed_days}")
                    return cp.overall_percentage
            else:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("CourseSerializer: No request context or user available")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"CourseSerializer: Error getting progress for course {obj.id}: {e}")
        return 0.0

    def get_current_week(self, obj):
        """Get current week from CourseProgress."""
        try:
            from .models import CourseProgress
            request = self.context.get('request')
            if request and request.user:
                cp = CourseProgress.objects.filter(course=obj, user=request.user).first()
                if cp:
                    return cp.current_week
        except Exception:
            pass
        return 1

    def get_current_day(self, obj):
        """Get current day from CourseProgress."""
        try:
            from .models import CourseProgress
            request = self.context.get('request')
            if request and request.user:
                cp = CourseProgress.objects.filter(course=obj, user=request.user).first()
                if cp:
                    return cp.current_day
        except Exception:
            pass
        return 1


class CourseListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list endpoint (no nested weeks)."""
    total_days = serializers.ReadOnlyField()
    generation_status = serializers.CharField(read_only=True)
    generation_progress = serializers.IntegerField(read_only=True)
    progress = serializers.SerializerMethodField()
    current_week = serializers.SerializerMethodField()
    current_day = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id", "course_name", "topic", "level", "duration_weeks", "hours_per_day",
            "goals", "status", "generation_status", "generation_progress", "total_days", "created_at",
            "progress", "current_week", "current_day",
        ]
        read_only_fields = ["id", "topic", "created_at", "progress", "current_week", "current_day"]

    def get_progress(self, obj):
        """Calculate progress percentage from CourseProgress."""
        try:
            from .models import CourseProgress
            # Get the current request context to access the user
            request = self.context.get('request')
            if request and request.user:
                cp = CourseProgress.objects.filter(course=obj, user=request.user).first()
                if cp:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"Serializer: Course {obj.id}, User {request.user.id}, progress={cp.overall_percentage}, completed_days={cp.completed_days}")
                    return cp.overall_percentage
                else:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Serializer: No CourseProgress found for course {obj.id}, user {request.user.id}")
            else:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("Serializer: No request context or user available")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Serializer: Error getting progress for course {obj.id}: {e}")
        return 0.0

    def get_current_week(self, obj):
        """Get current week from CourseProgress."""
        try:
            from .models import CourseProgress
            request = self.context.get('request')
            if request and request.user:
                cp = CourseProgress.objects.filter(course=obj, user=request.user).first()
                if cp:
                    return cp.current_week
        except Exception:
            pass
        return 1

    def get_current_day(self, obj):
        """Get current day from CourseProgress."""
        try:
            from .models import CourseProgress
            request = self.context.get('request')
            if request and request.user:
                cp = CourseProgress.objects.filter(course=obj, user=request.user).first()
                if cp:
                    return cp.current_day
        except Exception:
            pass
        return 1


class CourseGenerateSerializer(serializers.Serializer):
    """Serializer for course creation with 3 fields."""
    course_name = serializers.CharField(
        max_length=255,
        help_text="Name/title of the course (e.g., 'Python for Data Science')"
    )
    duration_weeks = serializers.IntegerField(
        required=False,
        default=4,
        min_value=1,
        max_value=52,
        help_text="Duration in weeks (1-52)"
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
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Optional user-provided course description/requirements"
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


class CourseUpdateSerializer(serializers.Serializer):
    """Serializer for course update requests."""
    update_type = serializers.ChoiceField(
        choices=["percentage", "extend", "compact"],
        help_text="Type of update: percentage (replace 50%/75%), extend (add weeks), compact (compress course)"
    )
    user_query = serializers.CharField(
        max_length=2000,
        help_text="User's update request (what to add/modify in the course)"
    )
    web_search_enabled = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Whether to use web search for updated content"
    )
    percentage = serializers.IntegerField(
        required=False,
        help_text="Percentage for 'percentage' update type (50 or 75)"
    )
    extend_weeks = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=52,
        help_text="Number of weeks to add for 'extend' update type"
    )
    target_weeks = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=52,
        help_text="Target number of weeks for 'compact' update type"
    )

    def validate(self, data):
        update_type = data.get("update_type")

        # Validate based on update type
        if update_type == "percentage":
            percentage = data.get("percentage")
            if not percentage:
                raise serializers.ValidationError({
                    "percentage": "percentage must be 50 or 75 for percentage update type"
                })
            if percentage not in [50, 75]:
                raise serializers.ValidationError({
                    "percentage": "percentage must be 50 or 75"
                })

        elif update_type == "extend":
            extend_weeks = data.get("extend_weeks")
            if not extend_weeks or extend_weeks < 1:
                raise serializers.ValidationError({
                    "extend_weeks": "extend_weeks must be at least 1 for extend update type"
                })

        elif update_type == "compact":
            target_weeks = data.get("target_weeks")
            if not target_weeks or target_weeks < 1:
                raise serializers.ValidationError({
                    "target_weeks": "target_weeks is required for compact update type"
                })

        return data


class CourseUpdatePreviewSerializer(serializers.Serializer):
    """Serializer for course update preview response."""
    course_id = serializers.UUIDField()
    course_name = serializers.CharField()
    current_duration_weeks = serializers.IntegerField()
    new_duration_weeks = serializers.IntegerField()
    update_type = serializers.CharField()
    weeks_to_update = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of week numbers that will be updated/added"
    )
    weeks_to_preserve = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of week numbers that will remain unchanged"
    )
    total_days_affected = serializers.IntegerField()
    estimated_new_days = serializers.IntegerField()
    requires_confirmation = serializers.BooleanField()
