import logging
import hashlib
from datetime import datetime, timedelta
from database import AsyncSessionLocal, EventCluster, ClusterMessage, ForwardedMessage
from sqlalchemy import select, func

logger = logging.getLogger(__name__)

class CorrelationEngine:
    async def process_message(self, db_message, triage_result):
        # Check for duplicates via hash
        async with AsyncSessionLocal() as session:
            # Check if content_hash already exists
            existing = await session.execute(
                select(ForwardedMessage).where(ForwardedMessage.content_hash == db_message.content_hash)
            )
            if existing.scalar_one_or_none() and existing.scalar_one_or_none().id != db_message.id:
                # Duplicate, add to cluster of existing
                # Find cluster of original message
                cluster_msg = await session.execute(
                    select(ClusterMessage).where(ClusterMessage.message_id == existing.scalar_one_or_none().id)
                )
                if cluster_msg:
                    cluster_id = cluster_msg.scalar_one().cluster_id
                    await self._add_to_cluster(session, cluster_id, db_message.id)
                return

            # Find recent messages with high similarity (text similarity)
            # For simplicity, we'll just check if same event_type and close in time
            cutoff = datetime.utcnow() - timedelta(minutes=30)
            similar = await session.execute(
                select(EventCluster).where(
                    EventCluster.start_time >= cutoff,
                    EventCluster.event_type == triage_result.get("event_type")
                )
            )
            cluster = similar.scalar_one_or_none()
            if cluster:
                await self._add_to_cluster(session, cluster.id, db_message.id)
                # Update cluster scores
                cluster.importance_score = max(cluster.importance_score, triage_result.get("importance", 0))
                cluster.urgency_score = max(cluster.urgency_score, triage_result.get("urgency", 0))
                cluster.confidence_score = (cluster.confidence_score + triage_result.get("confidence", 0)) / 2
                await session.commit()
            else:
                # Create new cluster
                new_cluster = EventCluster(
                    title=triage_result.get("summary", "Event"),
                    start_time=datetime.utcnow(),
                    importance_score=triage_result.get("importance", 0),
                    urgency_score=triage_result.get("urgency", 0),
                    confidence_score=triage_result.get("confidence", 0),
                    event_type=triage_result.get("event_type", "unknown"),
                )
                session.add(new_cluster)
                await session.flush()
                await self._add_to_cluster(session, new_cluster.id, db_message.id)
                await session.commit()

    async def _add_to_cluster(self, session, cluster_id, message_id):
        cluster_msg = ClusterMessage(cluster_id=cluster_id, message_id=message_id)
        session.add(cluster_msg)

correlation_engine = CorrelationEngine()
