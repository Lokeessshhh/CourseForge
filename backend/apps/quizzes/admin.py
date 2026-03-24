from django.contrib import admin
from django.utils.safestring import mark_safe
import json
from .models import QuizQuestion, QuizAttempt


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ["course", "week_number", "day_number", "question_type", "difficulty", "question_preview"]
    list_filter = ["question_type", "difficulty", "week_number", "day_number"]
    search_fields = ["question_text", "course__course_name"]
    readonly_fields = ["id", "options_formatted", "explanation"]

    def question_preview(self, obj):
        return obj.question_text[:60] + "..." if len(obj.question_text) > 60 else obj.question_text
    question_preview.short_description = "Question"

    def options_formatted(self, obj):
        if obj.options:
            formatted = json.dumps(obj.options, indent=2)
            return mark_safe(f"<pre style='white-space: pre-wrap;'>{formatted}</pre>")
        return "-"
    options_formatted.short_description = "Options"


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ["user", "question", "is_correct", "attempted_at"]
    list_filter = ["is_correct"]
    search_fields = ["user__email", "question__question_text"]
    readonly_fields = ["id", "attempted_at"]
