import database as db
from typing import Dict

async def get_source_score(channel_id: int) -> Dict[str, float]:
    """Return trust, speed, priority scores for a channel."""
    channel = await db.get_channel(channel_id)
    if not channel:
        return {'trust': 0.5, 'speed': 0.5, 'priority': 0.5}
    return {
        'trust': channel.get('trust_score', 0.5),
        'speed': channel.get('speed_score', 0.5),
        'priority': channel.get('priority_score', 0.5)
    }

async def adjust_importance_with_source(importance: float, channel_id: int) -> float:
    """Adjust importance based on source scores."""
    scores = await get_source_score(channel_id)
    # Boost by trust and priority
    adjusted = importance * (0.5 + 0.5 * scores['trust']) * (0.5 + 0.5 * scores['priority'])
    return min(adjusted, 1.0)

async def adjust_urgency_with_source(urgency: float, channel_id: int) -> float:
    """Adjust urgency based on source speed."""
    scores = await get_source_score(channel_id)
    adjusted = urgency * (0.5 + 0.5 * scores['speed'])
    return min(adjusted, 1.0)
