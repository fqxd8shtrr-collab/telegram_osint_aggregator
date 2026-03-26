import logging
from database import AsyncSessionLocal, SourceChannel
import config

logger = logging.getLogger(__name__)

class SourceScoring:
    async def update_source_score(self, source_channel_id, triage_result):
        async with AsyncSessionLocal() as session:
            source = await session.get(SourceChannel, source_channel_id)
            if source:
                # Increase trust if messages are often important
                importance = triage_result.get("importance", 0)
                if importance > 0.8:
                    source.trust_score = min(1.0, source.trust_score + 0.01)
                elif importance < 0.3:
                    source.trust_score = max(0, source.trust_score - 0.005)
                await session.commit()

source_scoring = SourceScoring()
