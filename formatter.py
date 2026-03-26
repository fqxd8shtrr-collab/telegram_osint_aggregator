import datetime
from typing import Optional, Dict
import config

async def format_normal_feed(message_text: str, channel_info: Dict, content_type: str) -> str:
    """Format for normal feed."""
    source_name = channel_info.get('label') or channel_info.get('title') or str(channel_info['channel_id'])
    header = (
        f"📡 **{source_name}**\n"
        f"🕒 {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        f"─────────────────\n"
    )
    return header + (message_text or "")

async def format_priority_feed(message_text: str, channel_info: Dict, content_type: str, eval_result: Dict) -> str:
    """Format for priority feed."""
    source_name = channel_info.get('label') or channel_info.get('title') or str(channel_info['channel_id'])
    urgency_icon = "⚠️" if eval_result.get('urgency', 0) > 0.7 else "📌"
    header = (
        f"{urgency_icon} **أولوية**\n"
        f"📡 **{source_name}**\n"
        f"🧭 **التصنيف:** {eval_result.get('event_type', 'عام')}\n"
        f"⚡ **الأهمية:** {eval_result.get('importance', 0)*100:.0f}%\n"
        f"🕒 {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        f"─────────────────\n"
    )
    return header + (message_text or "")

async def format_critical_alert(message_text: str, channel_info: Dict, eval_result: Dict, cluster_info: Dict = None) -> str:
    """Format for critical alert."""
    source_name = channel_info.get('label') or channel_info.get('title') or str(channel_info['channel_id'])
    urgency_icon = "🚨" if eval_result.get('urgency', 0) > 0.8 else "⚠️"
    confidence_pct = eval_result.get('confidence', 0) * 100
    source_count = cluster_info.get('message_count', 1) if cluster_info else 1
    channels_list = cluster_info.get('channels', []) if cluster_info else []
    sources_text = f"عدد المصادر: {source_count}" if source_count > 1 else f"المصدر: {source_name}"
    if source_count > 1:
        sources_text = f"عدد المصادر: {source_count}\nالمصادر: {', '.join(str(c) for c in channels_list)}"
    header = (
        f"{urgency_icon} **تنبيه عاجل جدًا**\n"
        f"**النوع:** {eval_result.get('event_type', 'غير معروف')}\n"
        f"**الخطورة:** {'عالية جدًا' if eval_result.get('urgency',0)>0.8 else 'عالية'}\n"
        f"**الثقة:** {confidence_pct:.0f}%\n"
        f"{sources_text}\n"
        f"**الخلاصة:** {eval_result.get('summary', message_text[:150])}\n"
        f"🕒 {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
    )
    return header

async def format_team_notification(event_cluster: Dict, assignment: Dict, comment: str = None) -> str:
    """Format notification for team."""
    status_icons = {
        'new': '🆕',
        'under_review': '🔍',
        'confirmed': '✅',
        'published': '📢',
        'rejected': '❌'
    }
    icon = status_icons.get(event_cluster.get('status', 'new'), '📌')
    header = f"{icon} **تحديث الحدث #{event_cluster['id']}**\n"
    header += f"**النوع:** {event_cluster['event_type']}\n"
    header += f"**الحالة:** {event_cluster['status']}\n"
    if assignment:
        header += f"**مسند إلى:** {assignment.get('assigned_to')}\n"
    if comment:
        header += f"**تعليق:** {comment}\n"
    return header
