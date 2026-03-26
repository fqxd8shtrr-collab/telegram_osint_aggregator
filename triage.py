import re
import config
import utils
from typing import Dict

# Pre-compiled patterns for speed
URGENT_PATTERN = re.compile(r'(عاجل|فوري|طارئ|انفجار|هجوم|اغتيال|قصف|تحرك عسكري)', re.IGNORECASE)
EVENT_PATTERNS = {
    "عسكري": re.compile(r'(جيش|قصف|عسكري|صاروخ|طائرة|حرب)', re.IGNORECASE),
    "سياسي": re.compile(r'(سياسي|وزير|حكومة|انتخابات)', re.IGNORECASE),
    "أمني": re.compile(r'(أمن|شرطة|انفجار|هجوم|تفجير)', re.IGNORECASE),
    "اقتصادي": re.compile(r'(اقتصاد|دولار|سعر|نفط)', re.IGNORECASE),
    "إعلامي": re.compile(r'(إعلام|صحيفة|وكالة)', re.IGNORECASE),
    "دبلوماسي": re.compile(r'(دبلوماسي|سفير|لقاء)', re.IGNORECASE),
    "محلي": re.compile(r'(محلي|بلدية)', re.IGNORECASE),
    "دولي": re.compile(r'(عالمي|دولي|أمم متحدة)', re.IGNORECASE)
}

async def fast_triage(text: str, channel_id: int, content_type: str) -> Dict[str, float]:
    """
    Returns dict with keys: importance, urgency, confidence, event_type
    """
    if not text:
        return {"importance": 0.0, "urgency": 0.0, "confidence": 0.0, "event_type": "عام"}

    importance = 0.0
    urgency = 0.0
    event_type = "عام"

    # Urgent pattern
    if URGENT_PATTERN.search(text):
        urgency = 0.8
        importance = 0.7

    # Event type patterns
    for etype, pattern in EVENT_PATTERNS.items():
        if pattern.search(text):
            importance += 0.2
            urgency += 0.1
            event_type = etype

    # Boost for certain keywords
    if any(k in text.lower() for k in ["انفجار", "هجوم", "اغتيال", "قصف"]):
        importance += 0.3
        urgency += 0.3

    # Boost if media is photo/video
    if content_type in ["photo", "video"]:
        importance = min(importance + 0.2, 1.0)
        urgency = min(urgency + 0.1, 1.0)

    # Clamp to [0,1]
    importance = min(importance, 1.0)
    urgency = min(urgency, 1.0)

    # Confidence based on content length and patterns
    confidence = 0.3 + (importance * 0.4) + (urgency * 0.3)
    confidence = min(confidence, 1.0)

    # Get channel scores (trust, speed) from DB? We'll do in main worker.
    return {
        "importance": importance,
        "urgency": urgency,
        "confidence": confidence,
        "event_type": event_type
    }
