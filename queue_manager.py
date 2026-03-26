import asyncio
import logging
from typing import Callable, Coroutine
import config

logger = logging.getLogger(__name__)

class QueueManager:
    def __init__(self):
        self.incoming_queue = asyncio.Queue(maxsize=config.MAX_QUEUE_SIZE)
        self.alert_queue = asyncio.Queue(maxsize=config.MAX_QUEUE_SIZE)
        self.correlation_queue = asyncio.Queue(maxsize=config.MAX_QUEUE_SIZE)
        self.analysis_queue = asyncio.Queue(maxsize=config.MAX_QUEUE_SIZE)

        self._workers = []
        self._running = False

    async def start_workers(self,
                           triage_func: Callable[[dict], Coroutine],
                           alert_func: Callable[[dict], Coroutine],
                           correlation_func: Callable[[dict], Coroutine],
                           analysis_func: Callable[[dict], Coroutine] = None):
        self._running = True

        # Triage workers
        for i in range(config.TRIAGE_WORKERS):
            task = asyncio.create_task(self._worker(self.incoming_queue, triage_func, f"triage_{i}"))
            self._workers.append(task)
        # Alert workers
        for i in range(config.ALERT_WORKERS):
            task = asyncio.create_task(self._worker(self.alert_queue, alert_func, f"alert_{i}"))
            self._workers.append(task)
        # Correlation workers
        for i in range(config.CORRELATION_WORKERS):
            task = asyncio.create_task(self._worker(self.correlation_queue, correlation_func, f"correlation_{i}"))
            self._workers.append(task)
        # Deep analysis (optional)
        if config.DEEP_ANALYSIS_WORKERS > 0 and analysis_func:
            for i in range(config.DEEP_ANALYSIS_WORKERS):
                task = asyncio.create_task(self._worker(self.analysis_queue, analysis_func, f"analysis_{i}"))
                self._workers.append(task)

    async def _worker(self, queue: asyncio.Queue, func: Callable, name: str):
        logger.info(f"Worker {name} started")
        while self._running:
            try:
                item = await queue.get()
                await func(item)
                queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {name} error: {e}")
        logger.info(f"Worker {name} stopped")

    async def stop_workers(self):
        self._running = False
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        logger.info("All workers stopped")
