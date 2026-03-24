from django.contrib import admin
from .models import User, UserKnowledgeState


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["email", "name", "skill_level", "clerk_id", "created_at"]
    search_fields = ["email", "name", "clerk_id"]
    list_filter = ["skill_level"]
    readonly_fields = ["id", "clerk_id", "created_at"]


@admin.register(UserKnowledgeState)
class UserKnowledgeStateAdmin(admin.ModelAdmin):
    list_display = ["user", "concept", "confidence_score", "times_practiced", "updated_at"]
    search_fields = ["user__email", "concept"]
    list_filter = ["confidence_score"]
    readonly_fields = ["id", "updated_at"]
