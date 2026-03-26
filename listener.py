import asyncio
import logging
from telethon import TelegramClient, events
from telethon.tl.types import Message
import config
import database as db
import utils
from queue_manager import QueueManager

logger = logging.getLogger(__name__)

class Listener:
    def __init__(self, queue_manager: QueueManager):
        self.client = TelegramClient('user_session', config.API_ID, config.API_HASH)
        self.queue_manager = queue_manager
        self.is_running = False
        self.active_channels = set()  # set of channel IDs that are enabled in DB

    async def start(self):
        await self.client.start(phone=config.PHONE_NUMBER)
        logger.info("User client started.")
        await self._reload_active_channels()
        self.is_running = True

        @self.client.on(events.NewMessage(incoming=True))
        async def handler(event):
            await self.handle_message(event.message)

    async def _reload_active_channels(self):
        channels = await db.get_all_channels()
        self.active_channels = {c["channel_id"] for c in channels if c["enabled"]}
        logger.info(f"Loaded {len(self.active_channels)} active channels.")

    async def reload_channels(self):
        await self._reload_active_channels()

    async def handle_message(self, message: Message):
        if not self.is_running:
            return
        # Check if from a dialog (group/channel)
        if not hasattr(message.peer_id, 'channel_id'):
            return
        channel_id = message.peer_id.channel_id
        if channel_id not in self.active_channels:
            return

        # Dedup by message_id (quick)
        if await db.is_message_processed(channel_id, message.id):
            logger.debug(f"Message {message.id} already processed.")
            return

        text = message.text or message.caption or ""
        content_type = self._get_content_type(message)

        media_ids = []
        if message.photo:
            media_ids.append(message.photo.id)
        elif message.document:
            media_ids.append(message.document.id)
        content_hash = utils.generate_content_hash(text, media_ids)
        normalized_text = utils.normalize_text(text)

        # Save message immediately to prevent duplicates
        await db.save_message(channel_id, message.id, content_hash, normalized_text)

        # Create payload for queue
        payload = {
            "message_id": message.id,
            "channel_id": channel_id,
            "text": text,
            "content_type": content_type,
            "content_hash": content_hash,
            "normalized_text": normalized_text,
            "original_message": message,
            "channel_info": await db.get_channel(channel_id)
        }

        await self.queue_manager.incoming_queue.put(payload)
        logger.debug(f"Message {message.id} from channel {channel_id} queued")

    def _get_content_type(self, message: Message) -> str:
        if message.text:
            return "text"
        if message.photo:
            return "photo"
        if message.document:
            mime = getattr(message.document, 'mime_type', '')
            if mime.startswith('audio'):
                return "audio"
            if mime.startswith('video'):
                return "video"
            return "document"
        return "text"

    async def send_message(self, destination: str, text: str, original_payload: dict = None):
        """Send a text message (or forward) using the user client."""
        try:
            dest_entity = await self.client.get_entity(destination)
            if original_payload and original_payload.get("original_message"):
                # Try forward
                mode = await db.get_state("forward_mode", "copy")
                if mode == "forward":
                    try:
                        await self.client.forward_messages(dest_entity, messages=original_payload["original_message"])
                        return
                    except:
                        pass
                # Fallback to copy
                media = None
                msg = original_payload["original_message"]
                if msg.photo:
                    media = msg.photo
                elif msg.document:
                    media = msg.document
                if media:
                    await self.client.send_file(dest_entity, media, caption=text)
                else:
                    await self.client.send_message(dest_entity, text)
            else:
                await self.client.send_message(dest_entity, text)
        except Exception as e:
            logger.error(f"Send error: {e}")

    async def get_my_channels(self):
        """Fetch all dialogs and return channels where user is member."""
        dialogs = await self.client.get_dialogs()
        channels = []
        for d in dialogs:
            if d.is_channel:
                channels.append({
                    "id": d.id,
                    "title": d.title,
                    "username": d.username,
                    "is_participant": True  # Since we are in the dialog, we are participant
                })
        return channels

    async def stop(self):
        self.is_running = False
        await self.client.disconnect()
        logger.info("Listener stopped.")
