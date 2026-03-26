import asyncio
import hashlib
import json
import logging
import database as db
import utils
import config
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

async def process_correlation(item: Dict[str, Any]):
    """Correlate a new message with existing clusters."""
    try:
        text = item.get('text', '')
        content_hash = item.get('content_hash')
        if not content_hash:
            content_hash = utils.generate_content_hash(text, [])

        # Check if already in a recent cluster
        existing_cluster_id = await db.get_existing_cluster(content_hash, config.AI_CORRELATION_WINDOW)
        if existing_cluster_id:
            # Update cluster
            cluster = await db.get_event_cluster_by_id(existing_cluster_id)
            if cluster:
                new_importance = (cluster['importance'] + item['eval_result']['importance']) / 2
                new_urgency = (cluster['urgency'] + item['eval_result']['urgency']) / 2
                new_confidence = (cluster['confidence'] + item['eval_result']['confidence']) / 2
                channels = json.loads(cluster['channels'])
                if item['channel_id'] not in channels:
                    channels.append(item['channel_id'])
                await db.update_event_cluster(
                    existing_cluster_id,
                    new_importance,
                    new_urgency,
                    new_confidence,
                    channels,
                    [(item['message_id'], item['channel_id'])]
                )
                logger.info(f"Cluster {existing_cluster_id} updated with {len(channels)} sources")
        else:
            # Create new cluster
            cluster_hash = hashlib.sha256(f"{item['eval_result']['event_type']}_{content_hash}".encode()).hexdigest()
            await db.add_event_cluster(
                cluster_hash,
                item['eval_result']['event_type'],
                item['eval_result']['importance'],
                item['eval_result']['urgency'],
                item['eval_result']['confidence'],
                [item['channel_id']],
                [(item['message_id'], item['channel_id'])]
            )
            logger.info(f"New cluster created for message {item['message_id']}")
    except Exception as e:
        logger.error(f"Correlation error: {e}")
