import asyncio
import logging
from typing import Dict, Any, Optional
import database as db
import formatter
import config

logger = logging.getLogger(__name__)

async def process_alert(item: Dict[str, Any]):
    """
    Send alert if message qualifies.
    item contains: message_payload, eval_result, channel_info, cluster_info (optional)
    """
    try:
        eval_result = item.get('eval_result', {})
        importance = eval_result.get('importance', 0)
        urgency = eval_result.get('urgency', 0)
        confidence = eval_result.get('confidence', 0)

        # Get thresholds from DB (or config)
        importance_thresh = float(await db.get_bot_state("ai_importance_threshold", config.AI_IMPORTANCE_THRESHOLD))
        urgency_thresh = float(await db.get_bot_state("ai_urgency_threshold", config.AI_URGENCY_THRESHOLD))
        confidence_thresh = float(await db.get_bot_state("ai_confidence_threshold", config.AI_CONFIDENCE_THRESHOLD))

        # Determine alert level
        if (importance >= importance_thresh and urgency >= urgency_thresh and confidence >= confidence_thresh):
            target_type = 'critical_alert'
        elif importance >= 0.5:
            target_type = 'priority_feed'
        else:
            target_type = 'normal_feed'

        # Get destination
        dest = await db.get_forward_target(target_type)
        if not dest:
            dest = await db.get_forward_target('primary')
            if not dest:
                logger.warning(f"No destination for {target_type} and no primary")
                return

        # Format message
        channel_info = item.get('channel_info', {})
        message_text = item.get('text', '')
        content_type = item.get('content_type', 'text')
        cluster_info = item.get('cluster_info')

        if target_type == 'critical_alert':
            formatted = await formatter.format_critical_alert(message_text, channel_info, eval_result, cluster_info)
        elif target_type == 'priority_feed':
            formatted = await formatter.format_priority_feed(message_text, channel_info, content_type, eval_result)
        else:
            formatted = await formatter.format_normal_feed(message_text, channel_info, content_type)

        # Send using listener's client
        send_func = item.get('send_func')
        if send_func:
            await send_func(dest, formatted, item)
            # Update stats
            await db.increment_total_alerts()
            await db.update_daily_stats(channel_info.get('channel_id'), is_alert=True)
            logger.info(f"Alert sent to {dest} for message {item.get('message_id')}")
        else:
            logger.error("No send function provided for alert")
    except Exception as e:
        logger.error(f"Alert processing error: {e}")
