"""RAG app configuration."""
import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class RagConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.rag"
    verbose_name = "RAG (Retrieval-Augmented Generation)"

    def ready(self):
        """RAG app is ready."""
        logger.info("RAG app loaded - using OpenRouter for embeddings and reranking")
