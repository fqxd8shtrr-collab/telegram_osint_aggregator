import asyncio
import logging
import sys
import datetime
import config
import database as db
from listener import Listener
from bot import ControlBot
from queue_manager import QueueManager
from health_monitor import HealthMonitor
import triage_engine
import alert_engine
import correlation_engine
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Initialize DB
    db.init_sync_db()
    await db.set_bot_state("start_time", datetime.datetime.utcnow().isoformat())

    # Create queue manager
    queue_manager = QueueManager()

    # Create listener
    listener = Listener(queue_manager)

    # Create bot
    bot = ControlBot(listener, queue_manager)

    # Start listener and bot
    await listener.start()
    await bot.start()

    # Start workers
    # Define worker functions that will be called by queue manager
    async def triage_worker(item):
        # Perform fast triage
        eval_result = await triage_engine.fast_triage(item)
        # Add eval result to item
        item['eval_result'] = eval_result
        # Save to DB
        await db.save_ai_evaluation(item['message_id'], item['channel_id'], eval_result)
        # Determine if alert needed
        importance_thresh = float(await db.get_bot_state("ai_importance_threshold", config.AI_IMPORTANCE_THRESHOLD))
        urgency_thresh = float(await db.get_bot_state("ai_urgency_threshold", config.AI_URGENCY_THRESHOLD))
        confidence_thresh = float(await db.get_bot_state("ai_confidence_threshold", config.AI_CONFIDENCE_THRESHOLD))
        if (eval_result['importance'] >= importance_thresh and
            eval_result['urgency'] >= urgency_thresh and
            eval_result['confidence'] >= confidence_thresh):
            # Send to alert queue
            await queue_manager.alert_queue.put(item)
        # Always send to correlation queue for clustering
        await queue_manager.correlation_queue.put(item)
        # If deep analysis enabled, also to analysis queue
        if config.DEEP_ANALYSIS_ENABLED:
            await queue_manager.analysis_queue.put(item)

    async def alert_worker(item):
        # Add send_func to item
        item['send_func'] = listener.send_message
        await alert_engine.process_alert(item)

    async def correlation_worker(item):
        await correlation_engine.process_correlation(item)

    async def analysis_worker(item):
        # Deep analysis placeholder - can be implemented later
        logger.debug(f"Deep analysis for message {item['message_id']}")
        pass

    await queue_manager.start_workers(
        triage_func=triage_worker,
        alert_func=alert_worker,
        correlation_func=correlation_worker,
        analysis_func=analysis_worker if config.DEEP_ANALYSIS_ENABLED else None
    )

    # Start health monitor
    health_monitor = HealthMonitor(queue_manager)
    await health_monitor.start(interval=60)

    logger.info("System fully started. Press Ctrl+C to stop.")

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await health_monitor.stop()
        await queue_manager.stop_workers()
        await listener.stop()
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
