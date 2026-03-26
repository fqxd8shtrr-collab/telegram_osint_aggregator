import asyncio
import logging
import psutil
import database as db
import config

logger = logging.getLogger(__name__)

class HealthMonitor:
    def __init__(self, queue_manager):
        self.qm = queue_manager
        self._task = None
        self._running = False

    async def start(self, interval: int = 60):
        self._running = True
        self._task = asyncio.create_task(self._monitor(interval))

    async def _monitor(self, interval):
        while self._running:
            try:
                # Queue sizes
                await db.record_health("queue_incoming", self.qm.incoming_queue.qsize())
                await db.record_health("queue_alert", self.qm.alert_queue.qsize())
                await db.record_health("queue_correlation", self.qm.correlation_queue.qsize())
                await db.record_health("queue_analysis", self.qm.analysis_queue.qsize())
                # CPU/Memory
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory().percent
                await db.record_health("cpu_usage", cpu)
                await db.record_health("memory_usage", mem)
                # Uptime
                start_time = await db.get_state("start_time")
                if start_time:
                    import datetime
                    start = datetime.datetime.fromisoformat(start_time)
                    uptime = (datetime.datetime.now(datetime.UTC) - start).total_seconds()
                    await db.set_state("uptime", str(int(uptime)))
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
            await asyncio.sleep(interval)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            await self._task
