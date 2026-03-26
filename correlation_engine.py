import asyncio
import hashlib
import json
import logging
import time
import database as db
import utils
import config

logger = logging.getLogger(__name__)

async def process_correlation(item: Dict):
    """Correlate a new message with existing clusters."""
    # item contains: message_id, channel_id, text, eval_result, content_hash
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
            # Merge scores (average)
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
            # If cluster now has high confidence and multiple sources, consider upgrading alert
            if len(channels) >= 2 and new_confidence > 0.8:
                # Trigger an updated alert? Could be handled by alert_engine later
                logger.info(f"Cluster {existing_cluster_id} confirmed with {len(channels)} sources")
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
    except Exception as e:
        logger.error(f"Correlation error: {e}")
