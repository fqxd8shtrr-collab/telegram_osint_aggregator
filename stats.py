import datetime
import database as db
from typing import Dict, List, Any

async def get_system_status() -> Dict[str, Any]:
    """جمع جميع بيانات حالة النظام"""
    is_running = await db.get_bot_state("is_running") == "1"
    channels = await db.get_all_channels()
    active_channels = [c for c in channels if c['enabled']]
    total_forwarded = await db.get_bot_state("total_forwarded", "0")
    total_alerts = await db.get_bot_state("total_alerts", "0")
    last_activity = await db.get_bot_state("last_activity", "لا يوجد")
    last_error = await db.get_bot_state("last_error", "لا يوجد")
    start_time = await db.get_bot_state("start_time")
    uptime = ""
    if start_time:
        start = datetime.datetime.fromisoformat(start_time)
        delta = datetime.datetime.utcnow() - start
        uptime = str(delta).split('.')[0]
    forward_mode = await db.get_bot_state("forward_mode", "copy")
    targets = await db.get_all_forward_targets()
    primary = targets.get('primary') or "غير محدد"
    backup = targets.get('backup') or "غير محدد"
    
    # إحصائيات القنوات (آخر 24 ساعة)
    daily_stats = await db.get_daily_stats(days=1)
    today = datetime.date.today().isoformat()
    channel_stats = {}
    if today in daily_stats:
        channel_stats = daily_stats[today]['channels']
    
    # أكثر القنوات نشاطاً
    top_channels = sorted(channel_stats.items(), key=lambda x: x[1], reverse=True)[:5]
    # تحويل المعرفات إلى أسماء إذا أمكن
    top_channels_names = []
    for ch_id, count in top_channels:
        channel = await db.get_channel(int(ch_id))
        name = channel.get('label') or channel.get('title') or str(ch_id) if channel else str(ch_id)
        top_channels_names.append((name, count))
    
    return {
        "is_running": is_running,
        "total_channels": len(channels),
        "active_channels": len(active_channels),
        "total_forwarded": int(total_forwarded),
        "total_alerts": int(total_alerts),
        "last_activity": last_activity,
        "last_error": last_error,
        "uptime": uptime,
        "forward_mode": forward_mode,
        "primary_destination": primary,
        "backup_destination": backup,
        "top_channels": top_channels_names,
        "channel_counts": channel_stats
    }


async def get_queue_stats(queue_manager) -> Dict[str, int]:
    """جمع إحصائيات قوائم الانتظار"""
    return {
        "incoming": queue_manager.incoming_queue.qsize(),
        "alert": queue_manager.alert_queue.qsize(),
        "correlation": queue_manager.correlation_queue.qsize(),
        "analysis": queue_manager.analysis_queue.qsize()
    }


async def get_channel_stats(channel_id: int = None) -> Dict:
    """إحصائيات قناة محددة أو جميع القنوات"""
    daily_stats = await db.get_daily_stats(days=7)
    result = {}
    for date, stats in daily_stats.items():
        if channel_id:
            count = stats['channels'].get(str(channel_id), 0)
            result[date] = count
        else:
            result[date] = stats['total_messages']
    return result
