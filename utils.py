import hashlib
import re
import langdetect
from typing import Optional, List

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def generate_content_hash(text: str, media_ids: List[int] = None) -> str:
    combined = normalize_text(text) if text else ""
    if media_ids:
        combined += "".join(str(mid) for mid in media_ids)
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()

def simple_summarize(text: str, max_len: int = 150) -> str:
    if not text:
        return ""
    sentences = re.split(r'[.!?]', text)
    if sentences:
        summary = sentences[0].strip()
        if len(summary) > max_len:
            summary = summary[:max_len] + "..."
        return summary
    return text[:max_len]

def detect_language(text: str) -> Optional[str]:
    try:
        return langdetect.detect(text)
    except:
        return None

def auto_categorize(text: str) -> str:
    text_lower = text.lower()
    categories = {
        "عسكري": ["جيش", "قصف", "عسكري", "صاروخ", "طائرة", "حرب"],
        "سياسي": ["سياسي", "وزير", "حكومة", "انتخابات"],
        "أمني": ["أمن", "شرطة", "انفجار", "هجوم", "تفجير"],
        "اقتصادي": ["اقتصاد", "دولار", "سعر", "نفط"],
        "إعلامي": ["إعلام", "صحيفة", "وكالة"],
        "دبلوماسي": ["دبلوماسي", "سفير", "لقاء"],
        "محلي": ["محلي", "بلدية"],
        "دولي": ["عالمي", "دولي", "أمم متحدة"]
    }
    for cat, keywords in categories.items():
        for kw in keywords:
            if kw in text_lower:
                return cat
    return "عام"

def detect_event(text: str) -> Optional[str]:
    text_lower = text.lower()
    events = {
        "انفجار": ["انفجار", "تفجير"],
        "هجوم": ["هجوم", "اعتداء"],
        "اغتيال": ["اغتيال", "قتل"],
        "قصف": ["قصف", "ضربة"],
        "زلزال": ["زلزال"],
        "فيضان": ["فيضان", "سيول"]
    }
    for event, keywords in events.items():
        for kw in keywords:
            if kw in text_lower:
                return event
    return None
