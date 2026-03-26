import hashlib
import langdetect
from database import AsyncSessionLocal, ForwardedMessage

def compute_content_hash(message):
    # Create hash based on message content and media
    content = f"{message.id}_{message.chat_id}_{message.text or ''}_{message.media and message.media.__class__.__name__}"
    return hashlib.sha256(content.encode()).hexdigest()

def detect_language(text):
    try:
        return langdetect.detect(text)
    except:
        return "unknown"

async def save_message_to_db(channel_id, message_id, content_hash, normalized_text_hash, text, has_media, media_type):
    async with AsyncSessionLocal() as session:
        # Check duplicates
        existing = await session.execute(
            select(ForwardedMessage).where(
                (ForwardedMessage.content_hash == content_hash) |
                (ForwardedMessage.normalized_text_hash == normalized_text_hash)
            )
        )
        if existing.scalar_one_or_none():
            return None
        # Get source channel ID from DB
        source = await session.execute(
            select(SourceChannel).where(SourceChannel.telegram_id == channel_id)
        )
        source_id = source.scalar_one().id if source else None
        msg = ForwardedMessage(
            message_id=message_id,
            source_channel_id=source_id,
            content_hash=content_hash,
            normalized_text_hash=normalized_text_hash,
            text=text,
            has_media=has_media,
            media_type=media_type
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return msg
