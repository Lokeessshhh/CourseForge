"""RAG app configuration with reranker preload at startup."""
import logging
import sys
import threading

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class RagConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.rag"
    verbose_name = "RAG (Retrieval-Augmented Generation)"

    def ready(self):
        """Preload reranker model in a background thread at startup."""
        # Skip for management commands except server commands
        if len(sys.argv) > 1 and sys.argv[1] not in (
            "runserver", "rundev", "runserver_plus", "daphne", "runworker"
        ):
            logger.info("Skipping reranker preload (command: %s)", sys.argv[1])
            return

        thread = threading.Thread(
            target=self._preload_reranker,
            daemon=True,
            name="reranker-preload",
        )
        thread.start()
        logger.info("Reranker preload started in background thread")

    @staticmethod
    def _preload_reranker():
        """Load reranker model to avoid first-request latency."""
        try:
            from services.rag_pipeline.reranker import preload_reranker
            preload_reranker()
            logger.info("Reranker preload complete")
        except Exception as exc:
            logger.warning("Reranker preload failed: %s", exc)
