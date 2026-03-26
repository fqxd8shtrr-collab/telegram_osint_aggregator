import asyncio
import logging
import time
from database import AsyncSessionLocal, HealthLog
from queue_manager import queue_manager
import config

logger = logging.getLogger(__name__)

class HealthMonitor:
    def __init__(self):
        self.start_time = time.time()
        self.running = False
        self.last_error = None

    async def start(self):
        self.running = True
        while self.running:
            await asyncio.sleep(config.HEALTH_INTERVAL)
            await self.check_health()

    async def check_health(self):
        health_data = {
            "listener": "running" if listener.running else "stopped",
            "queue_size": queue_manager.queue.qsize(),
            "workers": config.MAX_WORKERS,
            "uptime": time.time() - self.start_time,
            "last_error": self.last_error,
        }
        async with AsyncSessionLocal() as session:
            log = HealthLog(
                component="system",
                status="ok" if queue_manager.running else "warning",
                details=health_data
            )
            session.add(log)
            await session.commit()

    async def stop(self):
        self.running = False

health_monitor = HealthMonitor()
