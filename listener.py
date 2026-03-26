import asyncio
import logging
from telethon import TelegramClient, events
from telethon.tl.types import Message, MessageMediaDocument, MessageMediaPhoto, MessageMediaVideo
import config
import database as db
import utils
import queue_manager as qm

logger = logging.getLogger(__name__)

class Listener:
    def __init__(self, queue_manager: qm.QueueManager):
        self.client = TelegramClient('user_session', config.API_ID, config.API_HASH)
        self.queue_manager = queue_manager
        self.is_running = False
        self.active_channels = {}

    async def start(self):
        await self.client.start(phone=config.PHONE_NUMBER)
        logger.info("User client started.")
        await self._reload_channels()
        self.is_running = True

        @self.client.on(events.NewMessage(incoming=True))
        async def handler(event):
            await self.handle_message(event.message)

    async def _reload_channels(self):
        channels = await db.get_all_channels()
        self.active_channels = {c['channel_id']: c for c in channels if c['enabled']}
        logger.info(f"Loaded {len(self.active_channels)} active channels.")

    async def reload_channels(self):
        await self._reload_channels()

    async def handle_message(self, message: Message):
        if not self.is_running:
            return
        # Check if from active channel
        if not hasattr(message.peer_id, 'channel_id'):
            return
        channel_id = message.peer_id.channel_id
        if channel_id not in self.active_channels:
            return

        # Basic dedup by message_id (quick)
        if await db.is_message_forwarded(channel_id, message.id):
            logger.debug(f"Message {message.id} already forwarded.")
            return

        # Extract content
        text = message.text or message.caption or ""
        content_type = self._get_content_type(message)

        # Generate content hash
        media_ids = []
        if message.photo:
            media_ids.append(message.photo.id)
        elif message.video:
            media_ids.append(message.video.id)
        elif message.document:
            media_ids.append(message.document.id)
        content_hash = utils.generate_content_hash(text, media_ids)

        # Normalized text for dedup
        normalized_text = utils.normalize_text(text)

        # Prepare payload for queue
        payload = {
            'message_id': message.id,
            'channel_id': channel_id,
            'text': text,
            'content_type': content_type,
            'content_hash': content_hash,
            'normalized_text': normalized_text,
            'original_message': message,
            'channel_info': self.active_channels[channel_id]
        }

        # Put into incoming queue for triage
        await self.queue_manager.incoming_queue.put(payload)

        # Mark as forwarded (prevent future processing by listener, but we will still use hash for dedup)
        # Actually we mark after successful processing? Better mark after triage/alert to avoid duplicates if something fails.
        # But to prevent double processing by listener, we mark now.
        await db.mark_message_forwarded(channel_id, message.id, content_hash, None, normalized_text)

    def _get_content_type(self, message: Message) -> str:
        if message.text:
            return "text"
        if message.photo:
            return "photo"
        if message.video:
            return "video"
        if message.document:
            if hasattr(message.document, 'mime_type') and message.document.mime_type.startswith('audio'):
                return "audio"
            return "document"
        return "text"

    async def send_message(self, destination: str, formatted_text: str, original_payload: dict):
        """Send a message to a destination using the user client."""
        try:
            dest_entity = await self.client.get_entity(destination)
            original_message = original_payload.get('original_message')
            if original_message:
                # If we have original message, we can forward or copy
                mode = await db.get_bot_state("forward_mode", "copy")
                if mode == "forward":
                    try:
                        await self.client.forward_messages(dest_entity, messages=original_message)
                        return
                    except:
                        pass
                # Copy
                media = None
                if original_message.photo:
                    media = original_message.photo
                elif original_message.video:
                    media = original_message.video
                elif original_message.document:
                    media = original_message.document
                if media:
                    await self.client.send_file(dest_entity, media, caption=formatted_text)
                else:
                    await self.client.send_message(dest_entity, formatted_text)
            else:
                await self.client.send_message(dest_entity, formatted_text)
        except Exception as e:
            logger.error(f"Send error to {destination}: {e}")

    async def stop(self):
        self.is_running = False
        await self.client.disconnect()
        logger.info("Listener stopped.")
