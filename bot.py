import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import config
import database as db
import stats as stats_mod
import utils
from listener import Listener
from queue_manager import QueueManager

logger = logging.getLogger(__name__)

class ControlBot:
    def __init__(self, listener: Listener, queue_manager: QueueManager):
        self.listener = listener
        self.queue_manager = queue_manager
        self.app = None

    async def start(self):
        self.app = Application.builder().token(config.BOT_TOKEN).build()
        # Handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        logger.info("Bot started.")

    async def stop(self):
        await self.app.updater.stop()
        await self.app.stop()

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in config.ALLOWED_USER_IDS:
            await update.message.reply_text("⛔ غير مصرح.")
            return
        keyboard = [
            [KeyboardButton("📡 إدارة المصادر"), KeyboardButton("🎯 التحكم بالإرسال")],
            [KeyboardButton("🧠 الذكاء الاصطناعي"), KeyboardButton("👥 إدارة الفريق")],
            [KeyboardButton("📊 الحالة والإحصائيات"), KeyboardButton("⚙️ الإعدادات")],
            [KeyboardButton("🗑 الإدارة")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "🌐 **Telegram OSINT Aggregator - Team Edition**\nاختر أحد الأزرار:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in config.ALLOWED_USER_IDS:
            await update.message.reply_text("⛔ غير مصرح.")
            return
        text = update.message.text
        if text == "📡 إدارة المصادر":
            await self.show_sources_menu(update, context)
        elif text == "🎯 التحكم بالإرسال":
            await self.show_forward_menu(update, context)
        elif text == "🧠 الذكاء الاصطناعي":
            await self.show_ai_menu(update, context)
        elif text == "👥 إدارة الفريق":
            await self.show_team_menu(update, context)
        elif text == "📊 الحالة والإحصائيات":
            await self.show_status(update, context)
        elif text == "⚙️ الإعدادات":
            await self.show_settings_menu(update, context)
        elif text == "🗑 الإدارة":
            await self.show_admin_menu(update, context)
        else:
            await update.message.reply_text("استخدم الأزرار من القائمة.")

    async def show_sources_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("➕ إضافة قناة", callback_data="add_channel")],
            [InlineKeyboardButton("📋 عرض القنوات", callback_data="list_channels")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📡 إدارة المصادر:", reply_markup=reply_markup)

    async def show_forward_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🎯 تعيين الوجهة الرئيسية", callback_data="set_primary")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🎯 التحكم بالإرسال:", reply_markup=reply_markup)

    async def show_ai_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🧠 الذكاء الاصطناعي:", reply_markup=reply_markup)

    async def show_team_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("👥 إدارة الفريق:", reply_markup=reply_markup)

    async def show_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        status = await stats_mod.get_system_status()
        text = (
            f"📊 **حالة النظام**\n"
            f"🟢 الشبكة: {'تعمل' if status['is_running'] else 'متوقفة'}\n"
            f"📡 القنوات: {status['total_channels']} (نشطة: {status['active_channels']})\n"
            f"📨 الرسائل المرسلة: {status['total_forwarded']}\n"
            f"🚨 التنبيهات المرسلة: {status['total_alerts']}\n"
            f"🕒 آخر نشاط: {status['last_activity']}\n"
            f"⚠️ آخر خطأ: {status['last_error']}\n"
            f"⏱ التشغيل: {status['uptime']}\n"
        )
        await update.message.reply_text(text, parse_mode='Markdown')

    async def show_settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🔘 تشغيل/إيقاف الشبكة", callback_data="toggle_network")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("⚙️ الإعدادات:", reply_markup=reply_markup)

    async def show_admin_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🧪 اختبار الإرسال", callback_data="test_send")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🗑 الإدارة:", reply_markup=reply_markup)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data
        user_id = update.effective_user.id
        if user_id not in config.ALLOWED_USER_IDS:
            await query.edit_message_text("⛔ غير مصرح.")
            return

        if data == "main_menu":
            await self.start_command(update, context)
            return

        elif data == "add_channel":
            context.user_data['action'] = 'add_channel'
            await query.edit_message_text("أرسل معرف القناة (@username أو رابط):")
        elif data == "list_channels":
            channels = await db.get_all_channels()
            if not channels:
                text = "لا توجد قنوات مضافة."
            else:
                text = "📋 القنوات:\n"
                for ch in channels:
                    status = "🟢" if ch['enabled'] else "🔴"
                    text += f"{status} {ch.get('label', ch['title'])} ({ch['channel_id']})\n"
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]))
        elif data == "set_primary":
            context.user_data['action'] = 'set_primary'
            await query.edit_message_text("أرسل معرف الوجهة الرئيسية:")
        elif data == "toggle_network":
            current = await db.get_bot_state("is_running") == "1"
            new = "0" if current else "1"
            await db.set_bot_state("is_running", new)
            self.listener.is_running = not current
            await query.edit_message_text(f"الشبكة {'متوقفة' if current else 'تعمل'}")
        elif data == "test_send":
            primary = await db.get_forward_target('primary')
            if not primary:
                await query.edit_message_text("لا توجد وجهة رئيسية.")
                return
            try:
                await self.listener.send_message(primary, "🧪 رسالة اختبار", {})
                await query.edit_message_text("✅ تم إرسال رسالة اختبار.")
            except Exception as e:
                await query.edit_message_text(f"❌ فشل الإرسال: {e}")
        else:
            await query.edit_message_text("أمر غير معروف.")

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # This is already defined above; we need to merge actions
        text = update.message.text
        action = context.user_data.get('action')
        if action:
            await self.process_input(update, context, action, text)
            context.user_data.pop('action', None)
            return

    async def process_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str):
        if action == 'add_channel':
            try:
                entity = await self.listener.client.get_entity(text)
                channel_id = entity.id
                title = entity.title
                success = await db.add_source_channel(channel_id, entity.username, title, title)
                if success:
                    await update.message.reply_text(f"✅ تم إضافة القناة: {title}")
                    await self.listener.reload_channels()
                else:
                    await update.message.reply_text("⚠️ القناة موجودة مسبقاً.")
            except Exception as e:
                await update.message.reply_text(f"فشل الإضافة: {e}")
        elif action == 'set_primary':
            await db.set_forward_target('primary', text)
            await update.message.reply_text(f"🎯 تم تعيين الوجهة الرئيسية: {text}")
        else:
            await update.message.reply_text("إجراء غير معروف.")
