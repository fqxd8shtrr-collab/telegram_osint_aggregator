import asyncio
import logging
import config
from triage_engine import triage_engine
from alert_engine import alert_engine
from correlation_engine import correlation_engine
from database import AsyncSessionLocal, ForwardedMessage, AIEvaluation
from utils import save_message_to_db
import traceback

logger = logging.getLogger(__name__)

class QueueManager:
    def __init__(self):
        self.queue = asyncio.Queue(maxsize=config.QUEUE_SIZE)
        self.workers = []
        self.running = False

    async def start(self):
        self.running = True
        for i in range(config.MAX_WORKERS):
            worker = asyncio.create_task(self._worker(i))
            self.workers.append(worker)
        logger.info(f"Queue manager started with {config.MAX_WORKERS} workers")

    async def push(self, item):
        await self.queue.put(item)

    async def _worker(self, worker_id):
        logger.info(f"Worker {worker_id} started")
        while self.running:
            try:
                item = await self.queue.get()
                await self._process(item, worker_id)
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}\n{traceback.format_exc()}")

    async def _process(self, item, worker_id):
        # Step 1: Save message to DB
        message = item["message"]
        channel_id = item["channel_id"]
        content_hash = item["content_hash"]
        normalized_text_hash = item["normalized_text_hash"]
        raw_text = item["raw_text"]
        media = item["media"]

        # Save to DB and get ID
        db_message = await save_message_to_db(
            channel_id, message.id, content_hash, normalized_text_hash,
            raw_text, bool(media), media.__class__.__name__.lower() if media else None
        )
        if not db_message:
            # Duplicate detected, skip
            return

        # Step 2: Fast AI triage (synchronous, but we run in thread pool to avoid blocking)
        triage_result = await asyncio.to_thread(
            triage_engine.fast_triage, raw_text, media
        )

        # Step 3: If high importance, send immediately (alert engine)
        if triage_result.get("importance", 0) > 0.8 or triage_result.get("urgency", 0) > 0.8:
            # Send to output channels based on routing rules
            await alert_engine.send_alert(db_message, triage_result)

        # Step 4: Store AI evaluation
        async with AsyncSessionLocal() as session:
            ai_eval = AIEvaluation(
                message_id=db_message.id,
                importance_score=triage_result.get("importance", 0),
                urgency_score=triage_result.get("urgency", 0),
                confidence_score=triage_result.get("confidence", 0),
                event_type=triage_result.get("event_type", "unknown"),
                summary=triage_result.get("summary", ""),
            )
            session.add(ai_eval)
            await session.commit()

        # Step 5: Trigger deep analysis in background (if needed)
        if triage_result.get("importance", 0) > 0.5:
            asyncio.create_task(self._deep_analysis(db_message.id, raw_text, media))

        # Step 6: Correlation (can run later)
        await correlation_engine.process_message(db_message, triage_result)

    async def _deep_analysis(self, message_id, text, media):
        # Deep analysis (translation, summarization, etc.)
        await triage_engine.deep_analysis(message_id, text, media)

    async def stop(self):
        self.running = False
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        logger.info("Queue manager stopped")

queue_manager = QueueManager()
