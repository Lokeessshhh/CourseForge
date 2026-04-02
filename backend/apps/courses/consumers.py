"""
SSE Consumer for handling channel layer messages.
"""
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
import json

logger = logging.getLogger(__name__)


class SSEConsumer(AsyncWebsocketConsumer):
    """
    Consumer for handling SSE broadcast messages.
    This is used internally by the SSE event generator.
    """
    
    async def connect(self):
        """Accept connection."""
        self.course_id = getattr(self, "course_id", None)
        if self.course_id:
            self.room_group_name = f"course_progress_{self.course_id}"
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
        await self.accept()
        logger.info("SSE Consumer connected for course %s", self.course_id)
    
    async def disconnect(self, close_code):
        """Clean up on disconnect."""
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        logger.info("SSE Consumer disconnected for course %s", self.course_id)
    
    async def progress_update(self, event):
        """
        Handle progress update messages from channel layer.
        """
        data = event.get("data", {})
        logger.info("SSE received progress update for course %s: %d%%", 
                   self.course_id, data.get("progress", 0))
        
        # Send to client
        await self.send(text_data=json.dumps(data))
