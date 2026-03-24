from django.contrib import admin
from .models import Conversation


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "role", "session_id", "course", "is_summarized", "created_at"]
    list_filter = ["role", "is_summarized"]
    search_fields = ["user__email", "content", "session_id"]
    readonly_fields = ["id", "embedding", "created_at"]
    raw_id_fields = ["user", "course"]
