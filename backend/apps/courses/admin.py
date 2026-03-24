from django.contrib import admin
from django.utils.safestring import mark_safe
import json
from .models import Course, WeekPlan, DayPlan, WeeklyTest, CodingTest


class WeekPlanInline(admin.TabularInline):
    model = WeekPlan
    extra = 0


class DayPlanInline(admin.TabularInline):
    model = DayPlan
    extra = 0
    fields = ["day_number", "title", "theory_generated", "code_generated", "quiz_generated"]


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["topic", "user", "status", "duration_weeks", "created_at"]
    list_filter = ["status"]
    search_fields = ["topic", "user__email"]
    readonly_fields = ["id", "created_at"]
    inlines = [WeekPlanInline]


@admin.register(WeekPlan)
class WeekPlanAdmin(admin.ModelAdmin):
    list_display = ["course", "week_number", "theme", "is_completed"]
    list_filter = ["is_completed"]
    inlines = [DayPlanInline]


@admin.register(DayPlan)
class DayPlanAdmin(admin.ModelAdmin):
    list_display = [
        "week_plan",
        "day_number",
        "title",
        "is_completed",
        "theory_generated",
        "code_generated",
        "quiz_generated",
        "completed_at",
    ]
    list_filter = ["is_completed", "theory_generated", "code_generated", "quiz_generated"]
    readonly_fields = ["id", "quiz_raw_formatted"]
    search_fields = ["title"]

    def quiz_raw_formatted(self, obj):
        if obj.quiz_raw:
            try:
                # Try to parse and pretty-print
                parsed = json.loads(obj.quiz_raw)
                formatted = json.dumps(parsed, indent=2)
                return mark_safe(f"<pre style='white-space: pre-wrap; max-height: 300px; overflow: auto;'>{formatted}</pre>")
            except json.JSONDecodeError:
                return mark_safe(f"<pre style='white-space: pre-wrap;'>{obj.quiz_raw}</pre>")
        return "-"
    quiz_raw_formatted.short_description = "Quiz Questions (JSON)"


@admin.register(WeeklyTest)
class WeeklyTestAdmin(admin.ModelAdmin):
    list_display = ["course", "week_number", "total_questions", "generated_at"]
    list_filter = ["week_number"]
    search_fields = ["course__course_name"]
    readonly_fields = ["id", "generated_at", "questions_formatted"]

    def questions_formatted(self, obj):
        if obj.questions:
            formatted = json.dumps(obj.questions, indent=2)
            return mark_safe(f"<pre style='white-space: pre-wrap; max-height: 400px; overflow: auto;'>{formatted}</pre>")
        return "-"
    questions_formatted.short_description = "Questions (JSON)"


@admin.register(CodingTest)
class CodingTestAdmin(admin.ModelAdmin):
    list_display = ["course", "week_number", "total_problems", "generated_at"]
    list_filter = ["week_number"]
    search_fields = ["course__course_name"]
    readonly_fields = ["id", "generated_at", "problems_formatted"]

    def problems_formatted(self, obj):
        if obj.problems:
            formatted = json.dumps(obj.problems, indent=2)
            return mark_safe(f"<pre style='white-space: pre-wrap; max-height: 400px; overflow: auto;'>{formatted}</pre>")
        return "-"
    problems_formatted.short_description = "Problems (JSON)"
