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
        # Purge stale Celery queues on startup
        self._purge_celery_queues()
        
        # Register shutdown handler
        atexit.register(self._on_shutdown)

    def _purge_celery_queues(self):
        """Purge all Celery task queues to remove stale tasks from previous sessions."""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            from config.celery import app
            from kombu.exceptions import OperationalError
            
            # Get list of queues from task routes
            queues_to_purge = ['course_generation', 'quiz_generation', 'certificates']
            
            total_purged = 0
            for queue_name in queues_to_purge:
                try:
                    with app.connection() as conn:
                        queue = conn.SimpleQueue(queue_name)
                        depth = queue.qsize()
                        queue.close()
                        
                        if depth > 0:
                            # Purge the queue
                            purged = app.control.purge(queue=queue_name)
                            count = len(purged) if purged else 0
                            total_purged += count
                            logger.info(f"Purged {count} stale task(s) from queue: {queue_name}")
                except OperationalError:
                    # Queue doesn't exist yet - Celery worker not started
                    pass
                except Exception as queue_error:
                    logger.debug(f"Could not purge queue {queue_name}: {queue_error}")
            
            if total_purged > 0:
                logger.info(f"[CLEANUP] Cleared {total_purged} stale Celery task(s) on startup")
            else:
                logger.info("[CLEANUP] No stale Celery tasks found on startup")
                
        except Exception as e:
            # Don't crash startup if Redis isn't available
            logger.warning(f"Could not purge Celery queues on startup: {e}")
    
    def _on_shutdown(self):
        """Called when Django process is terminating."""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            from config.celery import app
            
            logger.info("[SHUTDOWN] Purging all Celery queues before exit...")
            
            # Purge all queues
            queues = ['course_generation', 'quiz_generation', 'certificates']
            total_purged = 0
            
            for queue_name in queues:
                try:
                    purged = app.control.purge(queue=queue_name)
                    count = len(purged) if purged else 0
                    total_purged += count
                except Exception:
                    pass  # Don't block shutdown on errors
            
            if total_purged > 0:
                logger.info("[SHUTDOWN] Purged %d pending task(s)", total_purged)
            else:
                logger.info("[SHUTDOWN] No pending tasks to purge")
            
            logger.info("[SHUTDOWN] Django shutdown complete - Celery worker will finish current tasks")
            
        except Exception as e:
            logger.debug("[SHUTDOWN] Cleanup completed with note: %s", e)
