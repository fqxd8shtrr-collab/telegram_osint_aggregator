import logging
import database as db
import config
import utils

logger = logging.getLogger(__name__)

async def send_alert(message: dict, eval_result: dict, channel_info: dict, send_func):
    """
    Check thresholds and send alert if needed.
    """
    importance = eval_result["importance"]
    urgency = eval_result["urgency"]
    confidence = eval_result["confidence"]

    imp_thresh = float(await db.get_state("importance_threshold", str(config.IMPORTANCE_THRESHOLD)))
    urg_thresh = float(await db.get_state("urgency_threshold", str(config.URGENCY_THRESHOLD)))
    conf_thresh = float(await db.get_state("confidence_threshold", str(config.CONFIDENCE_THRESHOLD)))

    if importance >= imp_thresh and urgency >= urg_thresh and confidence >= conf_thresh:
        # Determine destination
        dest = await db.get_forward_target("critical_alert")
        if not dest:
            dest = await db.get_forward_target("primary")
        if not dest:
            logger.warning("No alert destination set")
            return

        # Build alert text
        source_name = channel_info.get("label") or channel_info.get("title") or str(channel_info["channel_id"])
        summary = utils.simple_summarize(message["text"], 150)
        alert_text = (
            f"🚨 **تنبيه عاجل جدًا**\n"
            f"**النوع:** {eval_result['event_type']}\n"
            f"**الخطورة:** {'عالية جدًا' if urgency > 0.8 else 'عالية'}\n"
            f"**الثقة:** {confidence*100:.0f}%\n"
            f"**المصدر:** {source_name}\n"
            f"**الخلاصة:** {summary}\n"
        )
        await send_func(dest, alert_text, message)
        await db.increment_counter("total_alerts")
        logger.info(f"Alert sent for message {message['message_id']}")
