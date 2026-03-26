import re
import time
import logging
import database as db
import source_scoring as scoring
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Pre-compiled patterns for speed
# Event type patterns (can be loaded from DB in the future)
EVENT_PATTERNS = {
    'عسكري': re.compile(r'(جيش|قصف|عسكري|صاروخ|طائرة|حرب|معركة)', re.IGNORECASE),
    'أمني': re.compile(r'(أمن|شرطة|انفجار|تفجير|هجوم|اشتباك)', re.IGNORECASE),
    'سياسي': re.compile(r'(سياسي|وزير|حكومة|انتخابات|برلمان)', re.IGNORECASE),
    'اقتصادي': re.compile(r'(اقتصاد|دولار|سعر|نفط|بترول|مالي)', re.IGNORECASE),
    'دبلوماسي': re.compile(r'(دبلوماسي|سفير|لقاء|اتفاق|علاقات)', re.IGNORECASE),
    'محلي': re.compile(r'(محلي|بلدية|محافظة)', re.IGNORECASE),
    'دولي': re.compile(r'(عالمي|أمم متحدة|دولي|أجنبي)', re.IGNORECASE)
}

# High urgency patterns
URGENT_PATTERNS = re.compile(r'(عاجل|فوري|طارئ|انفجار|هجوم|اغتيال|قصف|تحرك عسكري)', re.IGNORECASE)

async def fast_triage(message_payload: Dict) -> Dict:
    """
    Perform ultra-fast triage.
    Payload contains: text, channel_id, content_type, message_id, etc.
    Returns: {
        'importance': float,
        'urgency': float,
        'confidence': float,
        'event_type': str,
        'summary': str (short summary)
    }
    """
    start_time = time.time()
    text = message_payload.get('text', '')
    channel_id = message_payload['channel_id']
    content_type = message_payload.get('content_type', 'text')

    # Get source scores
    source_scores = await scoring.get_source_score(channel_id)

    # Base importance: 0.0
    importance = 0.0
    urgency = 0.0
    event_type = "عام"

    # If text is empty, low importance
    if not text:
        importance = 0.1
        urgency = 0.0
    else:
        # Check urgent patterns
        if URGENT_PATTERNS.search(text):
            urgency = 0.8
            importance = 0.7
        # Check event patterns
        max_match = 0
        for etype, pattern in EVENT_PATTERNS.items():
            if pattern.search(text):
                importance += 0.2
                urgency += 0.1
                if pattern.search(text).group(0) in ['انفجار', 'هجوم', 'اغتيال', 'قصف']:
                    importance += 0.3
                    urgency += 0.3
                max_match = max(max_match, 1)
                event_type = etype if max_match > 0 else event_type

        # Normalize importance and urgency
        importance = min(importance, 1.0)
        urgency = min(urgency, 1.0)

        # Boost if content_type is video/photo (often important)
        if content_type in ['video', 'photo']:
            importance = min(importance + 0.2, 1.0)
            urgency = min(urgency + 0.1, 1.0)

        # If text is very short and no matches, low importance
        if len(text.split()) < 3 and importance < 0.3:
            importance = 0.1
            urgency = 0.0

    # Adjust by source scores
    importance = await scoring.adjust_importance_with_source(importance, channel_id)
    urgency = await scoring.adjust_urgency_with_source(urgency, channel_id)

    # Confidence based on content length, patterns, source trust
    confidence = 0.3 + (importance * 0.4) + (urgency * 0.3)
    confidence = min(confidence, 1.0)

    # Generate summary (first sentence)
    summary = text.split('.')[0][:150] if text else ""

    # Add performance metric
    elapsed = time.time() - start_time
    # Record triage latency (optional, but we can log)
    logger.debug(f"Triage took {elapsed:.3f}s for msg {message_payload.get('message_id')}")

    return {
        'importance': importance,
        'urgency': urgency,
        'confidence': confidence,
        'event_type': event_type,
        'summary': summary,
        'latency': elapsed
    }
