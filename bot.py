import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import config
import database as db
import utils
from listener import Listener
from queue_manager import QueueManager

logger = logging.getLogger(__name__)

class ControlBot:
    def __init__(self, listener: Listener, queue_manager: QueueManager):
        self.listener = listener
        self.qm = queue_manager
        self.app = None

    async def start(self):
        self.app = Application.builder().token(config.BOT_TOKEN).build()
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
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
            [InlineKeyboardButton("➕ إضافة قناة يدويًا", callback_data="add_channel_manual")],
            [InlineKeyboardButton("📋 عرض القنوات المشترك بها", callback_data="list_subscribed")],
            [InlineKeyboardButton("📋 عرض القنوات المُضافة", callback_data="list_channels")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📡 إدارة المصادر:", reply_markup=reply_markup)

    async def show_forward_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🎯 تعيين الوجهة الرئيسية", callback_data="set_primary")],
            [InlineKeyboardButton("🚨 تعيين وجهة التنبيهات", callback_data="set_alert")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🎯 التحكم بالإرسال:", reply_markup=reply_markup)

    async def show_ai_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("⚡ وضع السرعة القصوى", callback_data="toggle_fast_mode")],
            [InlineKeyboardButton("📊 عرض آخر التقييمات", callback_data="show_ai_stats")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🧠 الذكاء الاصطناعي:", reply_markup=reply_markup)

    async def show_team_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("👥 عرض الأعضاء", callback_data="list_team")],
            [InlineKeyboardButton("➕ إضافة عضو", callback_data="add_member")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("👥 إدارة الفريق:", reply_markup=reply_markup)

    async def show_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        is_running = await db.get_state("is_running") == "1"
        channels = await db.get_all_channels()
        active = sum(1 for c in channels if c["enabled"])
        total_forwarded = await db.get_state("total_forwarded", "0")
        total_alerts = await db.get_state("total_alerts", "0")
        last_activity = await db.get_state("last_activity", "لا يوجد")
        uptime = await db.get_state("uptime", "0")
        text = (
            f"📊 **حالة النظام**\n"
            f"🟢 الشبكة: {'تعمل' if is_running else 'متوقفة'}\n"
            f"📡 القنوات: {len(channels)} (نشطة: {active})\n"
            f"📨 الرسائل المرسلة: {total_forwarded}\n"
            f"🚨 التنبيهات المرسلة: {total_alerts}\n"
            f"🕒 آخر نشاط: {last_activity}\n"
            f"⏱ التشغيل: {uptime} ثانية\n"
            f"📥 قائمة الانتظار: {self.qm.incoming_queue.qsize()}"
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
            [InlineKeyboardButton("🗑 مسح السجل", callback_data="clear_logs")],
            [InlineKeyboardButton("♻️ إعادة تهيئة النظام", callback_data="reset_system")],
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

        # Sources
        elif data == "add_channel_manual":
            context.user_data["action"] = "add_channel"
            await query.edit_message_text("أرسل معرف القناة (@username أو رابط أو id):")
        elif data == "list_subscribed":
            # Fetch user's channels from Telethon
            try:
                channels = await self.listener.get_my_channels()
                if not channels:
                    await query.edit_message_text("لا توجد قنوات مشترك فيها.")
                    return
                # Build a list with checkboxes
                keyboard = []
                for ch in channels:
                    # Check if already added
                    existing = await db.get_channel(ch["id"])
                    checked = "✅ " if existing else "⬜ "
                    keyboard.append([InlineKeyboardButton(f"{checked}{ch['title']} ({ch.get('username', '')})", callback_data=f"toggle_channel_{ch['id']}")])
                keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
                await query.edit_message_text("اختر القنوات لإضافتها:", reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception as e:
                await query.edit_message_text(f"خطأ في جلب القنوات: {e}")
        elif data.startswith("toggle_channel_"):
            ch_id = int(data.split("_")[2])
            existing = await db.get_channel(ch_id)
            if existing:
                await db.remove_source_channel(ch_id)
                await query.edit_message_text(f"❌ تم إزالة القناة {ch_id} من القائمة.")
            else:
                # Fetch channel details from Telethon
                try:
                    entity = await self.listener.client.get_entity(ch_id)
                    await db.add_channel(ch_id, entity.username, entity.title, entity.title)
                    await query.edit_message_text(f"✅ تم إضافة القناة {entity.title}")
                except Exception as e:
                    await query.edit_message_text(f"فشل إضافة القناة: {e}")
            # Reload listener channels
            await self.listener.reload_channels()
        elif data == "list_channels":
            channels = await db.get_all_channels()
            if not channels:
                text = "لا توجد قنوات مضافة."
            else:
                text = "📋 القنوات:\n"
                for ch in channels:
                    status = "🟢" if ch["enabled"] else "🔴"
                    text += f"{status} {ch.get('label', ch['title'])} ({ch['channel_id']})\n"
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]))

        # Forward
        elif data == "set_primary":
            context.user_data["action"] = "set_primary"
            await query.edit_message_text("أرسل معرف الوجهة الرئيسية:")
        elif data == "set_alert":
            context.user_data["action"] = "set_alert"
            await query.edit_message_text("أرسل معرف وجهة التنبيهات:")

        # AI
        elif data == "toggle_fast_mode":
            current = await db.get_state("ai_fast_mode", "1")
            new = "0" if current == "1" else "1"
            await db.set_state("ai_fast_mode", new)
            await query.edit_message_text(f"وضع السرعة {'مفعل' if new == '1' else 'معطل'}")
        elif data == "show_ai_stats":
            # Show last 5 evaluations
            rows = await db.fetch_all("SELECT * FROM evaluations ORDER BY evaluated_at DESC LIMIT 5")
            if rows:
                text = "آخر 5 تقييمات:\n"
                for r in rows:
                    text += f"رسالة {r['message_id']}: أهمية {r['importance']:.2f}, عجلة {r['urgency']:.2f}, ثقة {r['confidence']:.2f}, نوع {r['event_type']}\n"
            else:
                text = "لا توجد تقييمات."
            await query.edit_message_text(text)

        # Team
        elif data == "list_team":
            users = await db.get_users()
            if not users:
                text = "لا يوجد أعضاء."
            else:
                text = "👥 أعضاء الفريق:\n"
                for u in users:
                    text += f"{u['user_id']} - {u['username']} - {u['role']}\n"
            await query.edit_message_text(text)
        elif data == "add_member":
            context.user_data["action"] = "add_member"
            await query.edit_message_text("أرسل معرف المستخدم واسم المستخدم والدور (admin/analyst/editor/monitor) في سطر واحد:\nمثال: 123456789 username analyst")

        # Settings
        elif data == "toggle_network":
            current = await db.get_state("is_running") == "1"
            new = "0" if current else "1"
            await db.set_state("is_running", new)
            self.listener.is_running = not current
            await query.edit_message_text(f"الشبكة {'متوقفة' if current else 'تعمل'}")

        # Admin
        elif data == "test_send":
            primary = await db.get_forward_target("primary")
            if not primary:
                await query.edit_message_text("لا توجد وجهة رئيسية.")
                return
            try:
                await self.listener.send_message(primary, "🧪 رسالة اختبار من نظام الرصد.")
                await query.edit_message_text("✅ تم إرسال رسالة اختبار.")
            except Exception as e:
                await query.edit_message_text(f"❌ فشل الإرسال: {e}")
        elif data == "clear_logs":
            await db.execute("DELETE FROM health_metrics")
            await query.edit_message_text("✅ تم مسح السجل.")
        elif data == "reset_system":
            # Dangerous: delete all data
            await db.execute("DELETE FROM channels")
            await db.execute("DELETE FROM messages")
            await db.execute("DELETE FROM evaluations")
            await db.execute("DELETE FROM clusters")
            await db.execute("DELETE FROM cluster_messages")
            await db.execute("DELETE FROM assignments")
            await db.execute("DELETE FROM comments")
            await db.execute("DELETE FROM users")
            await db.execute("DELETE FROM health_metrics")
            await db.set_state("total_forwarded", "0")
            await db.set_state("total_alerts", "0")
            await db.set_state("last_error", "")
            await db.set_state("last_activity", "")
            await self.listener.reload_channels()
            await query.edit_message_text("♻️ تم إعادة تهيئة النظام.")
        else:
            await query.edit_message_text("أمر غير معروف.")

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # This is called after start_command's handle_text; we already have actions in context.user_data
        text = update.message.text
        action = context.user_data.get("action")
        if action:
            await self.process_input(update, context, action, text)
            context.user_data.pop("action", None)
            return
        # Otherwise, this text is already handled by the main text handler above

    async def process_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str):
        if action == "add_channel":
            try:
                entity = await self.listener.client.get_entity(text)
                ch_id = entity.id
                title = entity.title
                username = entity.username
                success = await db.add_channel(ch_id, username, title, title)
                if success:
                    await update.message.reply_text(f"✅ تم إضافة القناة: {title}")
                    await self.listener.reload_channels()
                else:
                    await update.message.reply_text("⚠️ القناة موجودة مسبقاً.")
            except Exception as e:
                await update.message.reply_text(f"فشل الإضافة: {e}")
        elif action == "set_primary":
            await db.set_forward_target("primary", text)
            await update.message.reply_text(f"🎯 تم تعيين الوجهة الرئيسية: {text}")
        elif action == "set_alert":
            await db.set_forward_target("critical_alert", text)
            await update.message.reply_text(f"🚨 تم تعيين وجهة التنبيهات: {text}")
        elif action == "add_member":
            parts = text.split()
            if len(parts) < 3:
                await update.message.reply_text("تنسيق غير صحيح. استخدم: user_id username role")
                return
            user_id = int(parts[0])
            username = parts[1]
            role = parts[2].lower()
            if role not in ["admin", "analyst", "editor", "monitor"]:
                await update.message.reply_text("الدور غير صالح.")
                return
            await db.add_user(user_id, username, role)
            await update.message.reply_text(f"✅ تم إضافة العضو {username} بدور {role}.")
        else:
            await update.message.reply_text("إجراء غير معروف.")
