import logging
import asyncio
from transformers import pipeline
import config
from database import AsyncSessionLocal, AIEvaluation
from translation_engine import translate_text
import traceback

logger = logging.getLogger(__name__)

# Load a lightweight model for fast triage (can be done once at startup)
fast_classifier = None
try:
    fast_classifier = pipeline("text-classification", model="distilbert-base-uncased-finetuned-sst-2-english", device=-1)
except:
    logger.warning("Fast classifier not loaded, will use fallback")

class TriageEngine:
    def __init__(self):
        self.fast_model = fast_classifier

    def fast_triage(self, text, media):
        """
        Fast scoring using simple heuristics + optional model.
        Returns dict with importance, urgency, confidence, event_type, summary.
        """
        # If no text, use media presence to infer importance
        if not text:
            text = ""

        # Simple keyword scoring
        importance_keywords = ["عاجل", "حادث", "هجوم", "قتل", "انفجار", "إطلاق نار", "حرب", "اجتياح"]
        urgency_keywords = ["فوري", "الآن", "طارئ", "عاجل جداً"]
        event_keywords = {
            "military": ["جيش", "قصف", "طيران", "دبابة", "معركة"],
            "security": ["أمن", "شرطة", "اعتقال", "مداهمة", "إرهاب"],
            "political": ["سياسي", "وزير", "رئيس", "حكومة", "برلمان"],
            "economic": ["اقتصاد", "سعر", "دولار", "ذهب", "نفط"],
            "diplomatic": ["سفير", "دبلوماسي", "سفارة", "اتفاقية"],
            "local": ["محلي", "مدينة", "حي"],
            "international": ["دولي", "أمم", "أمريكا", "روسيا"]
        }

        # Basic scoring
        importance = 0.0
        urgency = 0.0
        for kw in importance_keywords:
            if kw in text:
                importance += 0.2
        for kw in urgency_keywords:
            if kw in text:
                urgency += 0.2

        # Cap at 1.0
        importance = min(1.0, importance)
        urgency = min(1.0, urgency)

        # If media is video, increase importance
        if media and hasattr(media, "video"):
            importance = min(1.0, importance + 0.2)

        # Use model if available (for confidence and event type)
        confidence = 0.5
        event_type = "unknown"
        if self.fast_model and text:
            try:
                # For demonstration, we use a simple sentiment classifier as a proxy
                # In practice, you'd have a fine-tuned model for event classification
                result = self.fast_model(text[:512])[0]
                # Map label to event types (dummy)
                if result['label'] == 'POSITIVE':
                    event_type = "general"
                else:
                    event_type = "negative"
                confidence = result['score']
            except:
                pass

        # For event type, if keywords match strongly
        max_count = 0
        for etype, kwlist in event_keywords.items():
            count = sum(1 for kw in kwlist if kw in text)
            if count > max_count:
                max_count = count
                event_type = etype

        # Summary: just first few words for fast triage
        summary = text[:200] + "..." if len(text) > 200 else text

        return {
            "importance": importance,
            "urgency": urgency,
            "confidence": confidence,
            "event_type": event_type,
            "summary": summary,
            "language": "ar"  # would detect later
        }

    async def deep_analysis(self, message_id, text, media):
        """
        Perform translation, detailed summarization, and advanced classification.
        This runs in background and updates the database.
        """
        # Language detection
        from utils import detect_language
        lang = detect_language(text) if text else "unknown"

        translated_text = None
        if lang != "ar" and text:
            translated_text = await translate_text(text, target_lang="ar")

        # Use a more advanced model for summarization (e.g., using OpenAI)
        # For now, just use the same text
        summary = text[:500] if text else ""

        # Update AIEvaluation record
        async with AsyncSessionLocal() as session:
            ai_eval = await session.get(AIEvaluation, message_id)
            if ai_eval:
                ai_eval.language = lang
                ai_eval.translated_text = translated_text
                ai_eval.summary = summary
                ai_eval.deep_analysis = {"translated": translated_text, "language": lang}
                await session.commit()

        logger.info(f"Deep analysis completed for message {message_id}")

triage_engine = TriageEngine()
