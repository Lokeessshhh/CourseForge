from django.contrib import admin
from .models import QueryCache


@admin.register(QueryCache)
class QueryCacheAdmin(admin.ModelAdmin):
    list_display = ["query_text", "hit_count", "created_at"]
    readonly_fields = ["id", "created_at"]
    search_fields = ["query_text"]
