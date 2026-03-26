import hashlib
import re
import langdetect
from typing import Optional, List, Tuple

# ---------- Text Normalization ----------
def normalize_text(text: str) -> str:
    """Remove extra spaces, lower case, remove punctuation."""
    if not text:
        return ""
    # Lowercase
    text = text.lower()
    # Remove punctuation except spaces
    text = re.sub(r'[^\w\s]', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# ---------- Content Hash ----------
def generate_content_hash(text: str, media_ids: List[int] = None) -> str:
    """Generate a hash for deduplication."""
    combined = normalize_text(text) if text else ""
    if media_ids:
        combined += "".join(str(mid) for mid in media_ids)
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()

# ---------- Simple Summarization ----------
def simple_summarize(text: str, max_len: int = 150) -> str:
    """Extract first sentence or truncate."""
    if not text:
        return ""
    # Try to split by sentence delimiters
    sentences = re.split(r'[.!?]', text)
    if sentences:
        summary = sentences[0].strip()
        if len(summary) > max_len:
            summary = summary[:max_len] + "..."
        return summary
    return text[:max_len]

# ---------- Language Detection (with fallback) ----------
def detect_language(text: str) -> Optional[str]:
    """Detect language code, return None if fails."""
    try:
        return langdetect.detect(text)
    except:
        return None

# ---------- Auto Categorization (simple keyword-based) ----------
def auto_categorize(text: str) -> str:
    """Return category based on keywords."""
    text_lower = text.lower()
    categories = {
        "عسكري": ["جيش", "قصف", "عسكري", "صاروخ", "طائرة", "حرب", "معركة"],
        "أمني": ["أمن", "شرطة", "انفجار", "تفجير", "هجوم", "اشتباك"],
        "سياسي": ["سياسي", "وزير", "حكومة", "انتخابات", "برلمان"],
        "اقتصادي": ["اقتصاد", "دولار", "سعر", "نفط", "بترول", "مالي"],
        "دبلوماسي": ["دبلوماسي", "سفير", "لقاء", "اتفاق", "علاقات"],
        "محلي": ["محلي", "بلدية", "محافظة"],
        "دولي": ["عالمي", "أمم متحدة", "دولي", "أجنبي"]
    }
    for cat, keywords in categories.items():
        for kw in keywords:
            if kw in text_lower:
                return cat
    return "عام"

# ---------- Event Detection (important events) ----------
def detect_important_event(text: str) -> Optional[str]:
    """Return event type if important, else None."""
    text_lower = text.lower()
    events = {
        "انفجار": ["انفجار", "تفجير", "انفجار"],
        "هجوم": ["هجوم", "هاجم", "اعتداء"],
        "تحرك عسكري": ["تحرك عسكري", "حشد", "نقل قوات"],
        "قصف": ["قصف", "ضربة", "غارة"],
        "اغتيال": ["اغتيال", "قتل"],
        "زلزال": ["زلزال", "هزة أرضية"],
        "فيضان": ["فيضان", "سيول"]
    }
    for event, keywords in events.items():
        for kw in keywords:
            if kw in text_lower:
                return event
    return None

# ---------- Similarity (simple Jaccard) ----------
def jaccard_similarity(text1: str, text2: str) -> float:
    """Jaccard similarity of word sets."""
    if not text1 or not text2:
        return 0.0
    words1 = set(normalize_text(text1).split())
    words2 = set(normalize_text(text2).split())
    if not words1 or not words2:
        return 0.0
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    return intersection / union
