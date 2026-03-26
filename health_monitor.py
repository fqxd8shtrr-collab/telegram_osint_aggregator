import asyncio
import psutil
import time
import logging
import database as db

logger = logging.getLogger(__name__)

class HealthMonitor:
    def __init__(self, queue_manager):
        self.queue_manager = queue_manager
        self._task = None
        self._running = False

    async def start(self, interval: int = 60):
        self._running = True
        self._task = asyncio.create_task(self._monitor(interval))

    async def _monitor(self, interval):
        while self._running:
            try:
                # CPU usage
                cpu = psutil.cpu_percent(interval=1)
                # Memory usage
                mem = psutil.virtual_memory().percent
                # Queue sizes
                incoming_size = self.queue_manager.incoming_queue.qsize()
                alert_size = self.queue_manager.alert_queue.qsize()
                correlation_size = self.queue_manager.correlation_queue.qsize()
                analysis_size = self.queue_manager.analysis_queue.qsize()

                # Record metrics
                await db.record_health_metric("cpu_usage", cpu)
                await db.record_health_metric("memory_usage", mem)
                await db.record_health_metric("queue_incoming", incoming_size)
                await db.record_health_metric("queue_alert", alert_size)
                await db.record_health_metric("queue_correlation", correlation_size)
                await db.record_health_metric("queue_analysis", analysis_size)

                # Also update uptime
                start_time_str = await db.get_bot_state("start_time")
                if start_time_str:
                    import datetime
                    start = datetime.datetime.fromisoformat(start_time_str)
                    uptime = (datetime.datetime.utcnow() - start).total_seconds()
                    await db.set_bot_state("uptime", str(int(uptime)))

                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(interval)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            await self._task
