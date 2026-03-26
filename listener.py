import asyncio
import logging
from telethon import TelegramClient, events
import config
from database import AsyncSessionLocal, SourceChannel
from queue_manager import queue_manager
from utils import compute_content_hash
import traceback

logging.basicConfig(level=config.LOG_LEVEL)
logger = logging.getLogger(__name__)

class TelegramListener:
    def __init__(self):
        self.client = TelegramClient(
            'osint_session',
            config.API_ID,
            config.API_HASH,
            connection_retries=5,
            auto_reconnect=True
        )
        self.running = False

    async def start(self):
        await self.client.start(config.SESSION_STRING)
        logger.info("Telegram client started")
        # Fetch all subscribed channels from database and add to event handler
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                "SELECT telegram_id FROM source_channels WHERE enabled = 1"
            )
            channels = result.scalars().all()
            for channel_id in channels:
                # Ensure we are a member
                try:
                    await self.client.get_entity(channel_id)
                except:
                    logger.warning(f"Cannot access channel {channel_id}, skipping")
                    continue

        @self.client.on(events.NewMessage(chats=channels))
        async def handler(event):
            await self.on_message(event)

        self.running = True
        await self.client.run_until_disconnected()

    async def on_message(self, event):
        try:
            # Extract message details
            message = event.message
            if not message.text and not message.media:
                return

            # Compute hashes for deduplication
            content_hash = compute_content_hash(message)
            normalized_text = message.text.lower().strip() if message.text else ""
            normalized_text_hash = compute_content_hash(normalized_text)

            # Push to queue for processing
            await queue_manager.push({
                "type": "message",
                "message": message,
                "channel_id": event.chat_id,
                "content_hash": content_hash,
                "normalized_text_hash": normalized_text_hash,
                "raw_text": message.text or "",
                "media": message.media,
            })
        except Exception as e:
            logger.error(f"Error handling message: {e}\n{traceback.format_exc()}")

    async def stop(self):
        self.running = False
        await self.client.disconnect()
        logger.info("Listener stopped")

listener = TelegramListener()
