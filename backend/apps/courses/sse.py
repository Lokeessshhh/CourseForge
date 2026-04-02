"""
Server-Sent Events (SSE) for course generation progress.
Streams real-time progress updates to clients.

Production-grade implementation with:
- Async generator for streaming
- In-memory queue for event distribution
- Automatic cleanup on disconnect
- Heartbeat to keep connections alive
"""
import asyncio
import json
import logging
from typing import AsyncGenerator
from uuid import UUID

from django.http import StreamingHttpResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

# Redis channel for SSE broadcasts
REDIS_SSE_CHANNEL = "sse_progress_updates"

# Global store for SSE queues: course_id -> list of asyncio.Queue
_sse_queues: dict[str, list[asyncio.Queue]] = {}

# Redis client for pub/sub
_redis_client = None


def get_redis_client():
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        import redis
        from django.conf import settings
        
        # Get Redis connection from Django settings
        redis_config = getattr(settings, 'CACHES', {}).get('default', {}).get('LOCATION', 'redis://localhost:6379/0')
        _redis_client = redis.from_url(redis_config)
    
    return _redis_client


class SSEEventGenerator:
    """
    Async generator that yields SSE-formatted events.
    Uses a queue to receive progress updates from Celery tasks via Redis.
    """

    def __init__(self, course_id: str | UUID, user_id: str):
        self.course_id = str(course_id)
        self.user_id = user_id
        self.queue: asyncio.Queue = asyncio.Queue()
        self._redis_listener_task = None

    async def _listen_to_redis(self):
        """Listen to Redis channel and forward messages to queue."""
        import redis.asyncio as redis
        
        try:
            redis_client = redis.from_url(
                'redis://localhost:6379/0',
                decode_responses=True
            )
            
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(REDIS_SSE_CHANNEL)
            
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        payload = json.loads(message['data'])
                        if payload.get('course_id') == self.course_id:
                            await self.queue.put(payload['data'])
                    except (json.JSONDecodeError, KeyError) as exc:
                        logger.warning("Failed to process Redis message: %s", exc)
                        
        except Exception as exc:
            logger.exception("Redis listener error: %s", exc)
        
    @staticmethod
    def _format_sse_event(event_type: str, data: dict) -> str:
        """Format data as SSE event."""
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    
    async def __aiter__(self) -> AsyncGenerator[str, None]:
        """
        Main event loop - yields SSE events from queue.
        """
        # Register this queue for the course
        if self.course_id not in _sse_queues:
            _sse_queues[self.course_id] = []
        _sse_queues[self.course_id].append(self.queue)
        
        # Start Redis listener
        self._redis_listener_task = asyncio.create_task(self._listen_to_redis())

        logger.info("📡 SSE connection opened for course %s user %s",
                   self.course_id, self.user_id)

        try:
            # Send initial connection event
            yield self._format_sse_event("connected", {
                "course_id": self.course_id,
                "status": "connected",
                "message": "Connected to progress stream",
            })

            # Listen for events from queue
            while True:
                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=30.0
                    )

                    # Send progress event
                    yield self._format_sse_event("progress", event)

                    # Check if generation is complete
                    if event.get("generation_status") in ("ready", "failed"):
                        logger.info("✅ SSE generation complete for course %s",
                                   self.course_id)
                        yield self._format_sse_event("complete", event)
                        break

                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield self._format_sse_event("heartbeat", {
                        "type": "heartbeat",
                        "timestamp": asyncio.get_event_loop().time(),
                    })

        except asyncio.CancelledError:
            logger.info("⚠️ SSE connection cancelled for course %s", self.course_id)
        except GeneratorExit:
            logger.info("⚠️ SSE generator closed for course %s", self.course_id)
        except Exception as exc:
            logger.exception("❌ SSE error for course %s: %s", self.course_id, exc)
            yield self._format_sse_event("error", {
                "error": str(exc),
            })
        finally:
            # Cancel Redis listener
            if self._redis_listener_task:
                self._redis_listener_task.cancel()
                try:
                    await self._redis_listener_task
                except asyncio.CancelledError:
                    pass
            
            # Cleanup: remove queue from list
            if self.course_id in _sse_queues:
                try:
                    _sse_queues[self.course_id].remove(self.queue)
                    if not _sse_queues[self.course_id]:
                        del _sse_queues[self.course_id]
                except (ValueError, KeyError):
                    pass
            logger.info("🔌 SSE connection closed for course %s", self.course_id)


@csrf_exempt
@require_GET
def course_progress_sse(request, course_id):
    """
    SSE endpoint for course generation progress.

    URL: /api/courses/{course_id}/progress/sse/

    Response: Server-Sent Events stream

    Events:
    - connected: Initial connection confirmation
    - progress: Progress update with percentage and stage
    - complete: Generation complete (ready or failed)
    - heartbeat: Keep-alive ping every 30s
    - error: Error occurred
    """
    from apps.courses.models import Course

    # For SSE, standard auth middleware may not work
    # Just verify course exists (owner check skipped for SSE)
    # TODO: Add token-based auth via query param for production
    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        logger.warning("❌ SSE: Course not found: %s", course_id)
        return StreamingHttpResponse(
            SSEEventGenerator._format_sse_event("error", {"error": "Course not found"}),
            content_type="text/event-stream",
            status=404,
        )
    except Exception as exc:
        logger.exception("❌ SSE: Error accessing course %s: %s", course_id, exc)
        return StreamingHttpResponse(
            SSEEventGenerator._format_sse_event("error", {"error": str(exc)}),
            content_type="text/event-stream",
            status=500,
        )

    # Create SSE generator
    generator = SSEEventGenerator(course_id, str(course.user_id))

    # Return streaming response
    response = StreamingHttpResponse(
        generator,
        content_type="text/event-stream",
    )

    # Critical headers for SSE
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # Disable nginx buffering
    response["Connection"] = "keep-alive"
    response["Access-Control-Allow-Origin"] = "*"  # CORS for development

    logger.info("✅ SSE response created for course %s", course_id)
    return response


def broadcast_progress_update(course_id: str | UUID, data: dict):
    """
    Broadcast progress update to all SSE clients via Redis.
    Called from Celery tasks.

    Usage:
        broadcast_progress_update(course_id, {
            "progress": 25,
            "completed_days": 5,
            "total_days": 20,
            "generation_status": "generating",
            "current_stage": "Generating Week 2...",
        })

    Args:
        course_id: Course UUID or string
        data: Progress data to broadcast
    """
    course_id_str = str(course_id)

    try:
        # Publish to Redis channel
        redis_client = get_redis_client()
        message = json.dumps({
            "course_id": course_id_str,
            "data": data,
        })

        redis_client.publish(REDIS_SSE_CHANNEL, message)

        logger.info("📢 Broadcast progress update for course %s: %d%% via Redis",
                   course_id_str, data.get("progress", 0))

    except Exception as exc:
        logger.exception("❌ Failed to broadcast progress update: %s", exc)


def broadcast_generation_complete(course_id: str | UUID, data: dict):
    """
    Broadcast FINAL completion event to all SSE clients via Redis.
    This tells frontend to CLOSE the SSE connection and dismiss the toast.
    
    MUST be called when the LAST weekly test completes.
    
    Usage:
        broadcast_generation_complete(course_id, {
            "progress": 100,
            "completed_days": 28,
            "total_days": 28,
            "generation_status": "ready",
            "current_stage": "Course generation complete!",
        })

    Args:
        course_id: Course UUID or string
        data: Final progress data
    """
    course_id_str = str(course_id)

    try:
        redis_client = get_redis_client()
        
        # Send with 'complete' event type - frontend will close connection on this
        message = json.dumps({
            "course_id": course_id_str,
            "data": data,
            "event_type": "complete",  # ← Critical: tells frontend to close
        })

        redis_client.publish(REDIS_SSE_CHANNEL, message)

        logger.info("✅📢 Broadcast GENERATION COMPLETE for course %s via Redis", course_id_str)

    except Exception as exc:
        logger.exception("❌ Failed to broadcast generation complete: %s", exc)
