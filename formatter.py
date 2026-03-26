import html
from datetime import datetime

def format_alert_message(db_message, triage_result):
    """
    Format a message for sending to output channels.
    """
    urgency_emoji = "🚨" if triage_result.get("urgency", 0) > 0.8 else "⚠️"
    importance_stars = "★" * int(triage_result.get("importance", 0) * 5) or "☆"
    event_type = triage_result.get("event_type", "عام").capitalize()

    text = f"""
{urgency_emoji} <b>تنبيه {event_type}</b>
<b>الخطورة:</b> {importance_stars}
<b>الثقة:</b> {int(triage_result.get('confidence', 0)*100)}%
<b>التصنيف:</b> {event_type}
<b>الخلاصة:</b> {html.escape(triage_result.get('summary', ''))[:500]}
<b>المصدر:</b> {db_message.source_channel_id}
<b>الوقت:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
    # Add translated text if available
    if triage_result.get("translated_text"):
        text += f"\n<b>الترجمة:</b>\n{html.escape(triage_result['translated_text'])}"

    return text.strip()
