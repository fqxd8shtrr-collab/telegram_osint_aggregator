import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import config
from database import AsyncSessionLocal, SourceChannel, OutputTarget, User, RoutingRule, BotState
from sqlalchemy import select
from listener import listener
import asyncio
from health_monitor import health_monitor
from stats import get_stats

logger = logging.getLogger(__name__)

# Helper to check if user is allowed
def authorized(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in config.ALLOWED_USERS:
            await update.message.reply_text("غير مصرح لك باستخدام هذا البوت.")
            return
        return await func(update, context)
    return wrapper

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Add user to database if not exists
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            user = User(telegram_id=user_id, username=update.effective_user.username, role="admin")
            session.add(user)
            await session.commit()
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📡 إدارة المصادر", callback_data="manage_sources")],
        [InlineKeyboardButton("🎯 التحكم بالإرسال", callback_data="manage_outputs")],
        [InlineKeyboardButton("🤖 الذكاء الاصطناعي", callback_data="ai_settings")],
        [InlineKeyboardButton("🌍 إدارة الواجهات", callback_data="manage_outputs")],
        [InlineKeyboardButton("🧠 الفلاتر", callback_data="filters")],
        [InlineKeyboardButton("👥 إدارة الفريق", callback_data="team_management")],
        [InlineKeyboardButton("📊 الحالة والإحصائيات", callback_data="stats")],
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
        [InlineKeyboardButton("🗑 الإدارة", callback_data="admin")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("قائمة التحكم الرئيسية:", reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "manage_sources":
        await list_sources(query)
    elif data == "manage_outputs":
        await list_outputs(query)
    elif data == "stats":
        await show_stats(query)
    # ... other handlers

async def list_sources(query):
    # Fetch all source channels from DB
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(SourceChannel))
        sources = result.scalars().all()
        if not sources:
            await query.edit_message_text("لا توجد مصادر. استخدم /add_source لإضافة مصدر.")
            return
        text = "📡 المصادر:\n"
        buttons = []
        for src in sources:
            text += f"\n• {src.title or src.username} - {'نشط' if src.enabled else 'معطل'}"
            buttons.append([InlineKeyboardButton(f"{src.title or src.username}", callback_data=f"source_{src.id}")])
        buttons.append([InlineKeyboardButton("رجوع", callback_data="main_menu")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_stats(query):
    stats = await get_stats()
    text = f"📊 الإحصائيات:\n"
    text += f"• رسائل في الدقيقة: {stats.get('messages_per_minute', 0)}\n"
    text += f"• التنبيهات: {stats.get('alerts_sent', 0)}\n"
    text += f"• حجم الطابور: {stats.get('queue_size', 0)}\n"
    text += f"• وقت التشغيل: {stats.get('uptime', '')}\n"
    text += f"• آخر خطأ: {stats.get('last_error', 'لا يوجد')}\n"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="main_menu")]]))

# Command to add source channel (manual)
@authorized
async def add_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Expects /add_source @channelusername
    if len(context.args) == 0:
        await update.message.reply_text("الاستخدام: /add_source @channelusername")
        return
    username = context.args[0]
    # Fetch entity via listener client
    try:
        entity = await listener.client.get_entity(username)
        async with AsyncSessionLocal() as session:
            # Check if exists
            existing = await session.execute(select(SourceChannel).where(SourceChannel.telegram_id == entity.id))
            if existing.scalar_one_or_none():
                await update.message.reply_text("المصدر موجود بالفعل.")
                return
            src = SourceChannel(
                telegram_id=entity.id,
                username=entity.username,
                title=entity.title,
                enabled=True,
                label="",
                category="",
                trust_score=1.0,
                priority_score=1.0,
                target_outputs=[],
                video_only=False
            )
            session.add(src)
            await session.commit()
            await update.message.reply_text(f"تمت إضافة المصدر {entity.title} بنجاح.")
    except Exception as e:
        await update.message.reply_text(f"خطأ: {e}")

# Command to list all subscribed channels from the personal account and add them in bulk
@authorized
async def sync_subscribed_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Get all dialogs from listener client
    dialogs = await listener.client.get_dialogs()
    channels = [d for d in dialogs if d.is_channel]
    text = "القنوات المشترك بها:\n"
    buttons = []
    for ch in channels:
        text += f"\n• {ch.title}"
        buttons.append([InlineKeyboardButton(ch.title, callback_data=f"select_channel_{ch.entity.id}")])
    buttons.append([InlineKeyboardButton("تحديد الكل", callback_data="select_all")])
    buttons.append([InlineKeyboardButton("إلغاء التحديد", callback_data="clear_all")])
    buttons.append([InlineKeyboardButton("إضافة المحدد كمصادر", callback_data="add_selected_sources")])
    buttons.append([InlineKeyboardButton("رجوع", callback_data="main_menu")])
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# Similar handlers for outputs, routing, etc.

def main():
    app = Application.builder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add_source", add_source))
    app.add_handler(CommandHandler("sync", sync_subscribed_channels))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()

if __name__ == "__main__":
    main()
