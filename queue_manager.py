import asyncio
from typing import Any, Callable, Coroutine
import logging
import config

logger = logging.getLogger(__name__)

class QueueManager:
    def __init__(self):
        self.incoming_queue = asyncio.Queue(maxsize=config.QUEUE_MAX_SIZE)
        self.alert_queue = asyncio.Queue(maxsize=config.QUEUE_MAX_SIZE)
        self.analysis_queue = asyncio.Queue(maxsize=config.QUEUE_MAX_SIZE)
        self.correlation_queue = asyncio.Queue(maxsize=config.QUEUE_MAX_SIZE)

        self.triage_workers = []
        self.alert_workers = []
        self.analysis_workers = []
        self.correlation_workers = []

        self._running = False

    async def start_workers(self,
                           triage_func: Callable[[Any], Coroutine],
                           alert_func: Callable[[Any], Coroutine],
                           correlation_func: Callable[[Any], Coroutine],
                           analysis_func: Callable[[Any], Coroutine] = None):
        self._running = True
        # Triage workers
        for i in range(config.TRIAGE_WORKERS):
            task = asyncio.create_task(self._worker(self.incoming_queue, triage_func, name=f"triage_{i}"))
            self.triage_workers.append(task)
        # Alert workers
        for i in range(config.ALERT_WORKERS):
            task = asyncio.create_task(self._worker(self.alert_queue, alert_func, name=f"alert_{i}"))
            self.alert_workers.append(task)
        # Correlation workers
        for i in range(config.CORRELATION_WORKERS):
            task = asyncio.create_task(self._worker(self.correlation_queue, correlation_func, name=f"correlation_{i}"))
            self.correlation_workers.append(task)
        # Deep analysis workers (optional)
        if config.DEEP_ANALYSIS_ENABLED and analysis_func:
            for i in range(config.DEEP_ANALYSIS_WORKERS):
                task = asyncio.create_task(self._worker(self.analysis_queue, analysis_func, name=f"analysis_{i}"))
                self.analysis_workers.append(task)

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
        for task in self.triage_workers + self.alert_workers + self.correlation_workers + self.analysis_workers:
            task.cancel()
        await asyncio.gather(*self.triage_workers, *self.alert_workers, *self.correlation_workers, *self.analysis_workers, return_exceptions=True)
