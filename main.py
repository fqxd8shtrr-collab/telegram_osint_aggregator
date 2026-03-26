import asyncio
import logging
import datetime
import config
import database as db
from listener import Listener
from bot import ControlBot
from queue_manager import QueueManager
from health import HealthMonitor
import triage
import correlation
import alert

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Initialize database
    db.init_sync_db()
    await db.set_state("start_time", datetime.datetime.now(datetime.UTC).isoformat())

    # Create queue manager
    qm = QueueManager()

    # Create listener
    listener = Listener(qm)

    # Create bot
    bot = ControlBot(listener, qm)

    # Start listener and bot
    await listener.start()
    await bot.start()

    # Worker functions
    async def triage_worker(item):
        # Get channel info (already in item)
        channel_info = item["channel_info"]
        # Fast triage
        eval_result = await triage.fast_triage(item["text"], item["channel_id"], item["content_type"])
        item["eval_result"] = eval_result
        # Save to DB
        await db.save_evaluation(
            item["message_id"], item["channel_id"],
            eval_result["importance"], eval_result["urgency"],
            eval_result["confidence"], eval_result["event_type"]
        )
        # Check if alert needed
        await alert.send_alert(item, eval_result, channel_info, listener.send_message)
        # Send to correlation queue
        await qm.correlation_queue.put(item)
        # If deep analysis enabled, also to analysis queue
        if config.DEEP_ANALYSIS_WORKERS > 0:
            await qm.analysis_queue.put(item)

    async def alert_worker(item):
        # This is already handled in triage_worker, but we keep for completeness
        pass

    async def correlation_worker(item):
        await correlation.correlate(item)

    async def analysis_worker(item):
        # Placeholder for deep analysis
        logger.debug(f"Deep analysis for message {item['message_id']}")
        pass

    # Start workers
    await qm.start_workers(
        triage_func=triage_worker,
        alert_func=alert_worker,
        correlation_func=correlation_worker,
        analysis_func=analysis_worker if config.DEEP_ANALYSIS_WORKERS > 0 else None
    )

    # Start health monitor
    health = HealthMonitor(qm)
    await health.start(interval=60)

    logger.info("System fully started. Press Ctrl+C to stop.")

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await health.stop()
        await qm.stop_workers()
        await listener.stop()
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
