import time
from database import AsyncSessionLocal, ForwardedMessage, AIEvaluation
from sqlalchemy import func, select
from datetime import datetime, timedelta

async def get_stats():
    async with AsyncSessionLocal() as session:
        # Messages per minute (last minute)
        minute_ago = datetime.utcnow() - timedelta(minutes=1)
        msg_count = await session.execute(
            select(func.count()).where(ForwardedMessage.processed_at >= minute_ago)
        )
        messages_per_minute = msg_count.scalar() or 0

        # Alerts sent count (from sent_to not empty)
        alerts = await session.execute(
            select(func.count()).where(ForwardedMessage.sent_to != "[]")
        )
        alerts_sent = alerts.scalar() or 0

        # Queue size (from queue manager)
        from queue_manager import queue_manager
        queue_size = queue_manager.queue.qsize()

        # Uptime from health_monitor
        from health_monitor import health_monitor
        uptime = time.time() - health_monitor.start_time

        return {
            "messages_per_minute": messages_per_minute,
            "alerts_sent": alerts_sent,
            "queue_size": queue_size,
            "uptime": uptime,
            "last_error": health_monitor.last_error,
        }
