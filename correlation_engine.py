import hashlib
import json
import logging
import config
import database as db

logger = logging.getLogger(__name__)

async def correlate(message: dict):
    """
    message: dict with keys: message_id, channel_id, text, content_hash, normalized_text
    """
    content_hash = message["content_hash"]
    # Check if we already have a cluster for this hash within the correlation window
    window = int(await db.get_state("correlation_window", str(config.CORRELATION_WINDOW)))
    rows = await db.fetch_all(
        "SELECT c.* FROM clusters c JOIN cluster_messages cm ON c.id = cm.cluster_id JOIN messages m ON cm.message_id = m.message_id AND cm.channel_id = m.channel_id WHERE m.content_hash = ? AND c.last_seen > datetime('now', ?)",
        (content_hash, f"-{window} seconds")
    )
    if rows:
        # Found existing cluster
        cluster_id = rows[0]["id"]
        # Update cluster
        await db.update_cluster(
            cluster_id,
            rows[0]["importance"],  # will average later? we'll keep simple: keep existing importance and update message count
            rows[0]["urgency"],
            rows[0]["confidence"],
            json.loads(rows[0]["channels"]),
            [(message["message_id"], message["channel_id"])]
        )
        logger.info(f"Correlated message {message['message_id']} to cluster {cluster_id}")
    else:
        # Create new cluster
        cluster_hash = hashlib.sha256(f"{content_hash}_{message.get('eval_result', {}).get('event_type', 'unknown')}".encode()).hexdigest()
        eval_res = message.get("eval_result", {})
        await db.add_cluster(
            cluster_hash,
            eval_res.get("event_type", "عام"),
            eval_res.get("importance", 0.5),
            eval_res.get("urgency", 0.5),
            eval_res.get("confidence", 0.5),
            [message["channel_id"]],
            [(message["message_id"], message["channel_id"])]
        )
        logger.info(f"Created new cluster for message {message['message_id']}")
