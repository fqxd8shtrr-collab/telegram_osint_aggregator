import logging
from telegram.ext import Application
from telegram import Bot
import config
from formatter import format_alert_message
from database import AsyncSessionLocal, OutputTarget, ForwardedMessage
from routing_engine import routing_engine

logger = logging.getLogger(__name__)

class AlertEngine:
    def __init__(self):
        self.bot = Bot(token=config.BOT_TOKEN)
        self.app = None

    async def initialize(self):
        # No need to start application for just sending, but we can use Bot directly
        pass

    async def send_alert(self, db_message, triage_result):
        """
        Send alert to appropriate output channels based on routing.
        """
        # Determine targets
        target_ids = await routing_engine.get_targets_for_message(db_message.source_channel_id, triage_result)

        # Format message
        formatted = format_alert_message(db_message, triage_result)

        # Send to each target
        for target_id in target_ids:
            try:
                await self.bot.send_message(chat_id=target_id, text=formatted, parse_mode="HTML")
                logger.info(f"Alert sent to target {target_id}")
            except Exception as e:
                logger.error(f"Failed to send to {target_id}: {e}")

        # Update database with sent_to
        async with AsyncSessionLocal() as session:
            db_message.sent_to = target_ids
            await session.commit()

alert_engine = AlertEngine()
