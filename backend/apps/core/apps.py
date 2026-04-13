"""
Core app configuration.
Handles startup/shutdown signals for cleanup tasks.
"""
import atexit
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        """Run initialization code when Django starts."""
        # Register shutdown handler
        atexit.register(self._on_shutdown)

    def _on_shutdown(self):
        """Called when Django process is terminating."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info("[SHUTDOWN] Django process shutting down...")
