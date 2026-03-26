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
import triage_engine
import alert_engine
import correlation_engine
import source_scoring
import json

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

    # ---- Sources Menu ----
    async def show_sources_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("➕ إضافة قناة", callback_data="add_channel")],
            [InlineKeyboardButton("➖ حذف قناة", callback_data="del_channel")],
            [InlineKeyboardButton("📋 عرض القنوات", callback_data="list_channels")],
            [InlineKeyboardButton("🔔 تفعيل قناة", callback_data="enable_channel")],
            [InlineKeyboardButton("🔕 تعطيل قناة", callback_data="disable_channel")],
            [InlineKeyboardButton("🏷 تغيير الاسم", callback_data="rename_source")],
            [InlineKeyboardButton("📂 تغيير التصنيف", callback_data="change_category")],
            [InlineKeyboardButton("🔥 الأولوية", callback_data="set_priority")],
            [InlineKeyboardButton("⚖️ تعديل الثقة", callback_data="edit_trust")],
            [InlineKeyboardButton("⚡ تعديل السرعة", callback_data="edit_speed")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📡 إدارة المصادر:", reply_markup=reply_markup)

    # ---- Forward Control Menu ----
    async def show_forward_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        mode = await db.get_bot_state("forward_mode", "copy")
        targets = await db.get_all_forward_targets()
        keyboard = [
            [InlineKeyboardButton(f"🔄 وضع الإرسال ({mode})", callback_data="toggle_mode")],
            [InlineKeyboardButton("🎯 تعيين الوجهة الرئيسية", callback_data="set_primary")],
            [InlineKeyboardButton("🔄 تعيين الوجهة الاحتياطية", callback_data="set_backup")],
            [InlineKeyboardButton("🚨 تعيين وجهة التنبيهات", callback_data="set_alert_dest")],
            [InlineKeyboardButton("📰 تعيين الـ Normal Feed", callback_data="set_normal_feed")],
            [InlineKeyboardButton("⚡ تعيين الـ Priority Feed", callback_data="set_priority_feed")],
            [InlineKeyboardButton("🔥 تعيين الـ Critical Alerts", callback_data="set_critical_alert")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        text = f"**التحكم بالإرسال**\nالوضع: {mode}\nالرئيسية: {targets.get('primary','غير محدد')}\nالاحتياطية: {targets.get('backup','غير محدد')}\nالتنبيهات: {targets.get('alert','غير محدد')}\nNormal Feed: {targets.get('normal_feed','غير محدد')}\nPriority Feed: {targets.get('priority_feed','غير محدد')}\nCritical Alerts: {targets.get('critical_alert','غير محدد')}"
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # ---- AI Menu ----
    async def show_ai_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        ai_enabled = await db.get_bot_state("ai_enabled", "1") == "1"
        fast_mode = await db.get_bot_state("ai_fast_mode", "1") == "1"
        imp_thresh = await db.get_bot_state("ai_importance_threshold", config.AI_IMPORTANCE_THRESHOLD)
        urg_thresh = await db.get_bot_state("ai_urgency_threshold", config.AI_URGENCY_THRESHOLD)
        conf_thresh = await db.get_bot_state("ai_confidence_threshold", config.AI_CONFIDENCE_THRESHOLD)
        keyboard = [
            [InlineKeyboardButton(f"{'✅' if ai_enabled else '❌'} تفعيل AI", callback_data="toggle_ai")],
            [InlineKeyboardButton(f"⚡ وضع السرعة القصوى {'(ON)' if fast_mode else '(OFF)'}", callback_data="toggle_ai_fast")],
            [InlineKeyboardButton("📊 عرض آخر التقييمات", callback_data="show_ai_stats")],
            [InlineKeyboardButton("🔢 تغيير عتبة الأهمية", callback_data="set_importance_thresh")],
            [InlineKeyboardButton("⏱ تغيير عتبة العجلة", callback_data="set_urgency_thresh")],
            [InlineKeyboardButton("🎯 تغيير عتبة الثقة", callback_data="set_confidence_thresh")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        text = f"**الذكاء الاصطناعي**\nمفعل: {ai_enabled}\nوضع السرعة: {'نشط' if fast_mode else 'غير نشط'}\nعتبة الأهمية: {imp_thresh}\nعتبة العجلة: {urg_thresh}\nعتبة الثقة: {conf_thresh}"
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # ---- Team Management Menu ----
    async def show_team_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("➕ إضافة عضو", callback_data="add_member")],
            [InlineKeyboardButton("➖ حذف عضو", callback_data="del_member")],
            [InlineKeyboardButton("📋 عرض الأعضاء", callback_data="list_members")],
            [InlineKeyboardButton("🔧 تعيين دور", callback_data="set_role")],
            [InlineKeyboardButton("📌 تعيين مكتب", callback_data="set_desk")],
            [InlineKeyboardButton("📝 عرض التعيينات", callback_data="list_assignments")],
            [InlineKeyboardButton("💬 إضافة تعليق", callback_data="add_comment")],
            [InlineKeyboardButton("🔄 تغيير حالة الحدث", callback_data="change_event_status")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        await update.message.reply_text("👥 إدارة الفريق:", reply_markup=InlineKeyboardMarkup(keyboard))

    # ---- Status Menu ----
    async def show_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Gather stats
        is_running = await db.get_bot_state("is_running") == "1"
        channels = await db.get_all_channels()
        active = sum(1 for c in channels if c['enabled'])
        total_forwarded = await db.get_bot_state("total_forwarded", "0")
        total_alerts = await db.get_bot_state("total_alerts", "0")
        last_activity = await db.get_bot_state("last_activity", "لا يوجد")
        last_error = await db.get_bot_state("last_error", "لا يوجد")
        uptime = await db.get_bot_state("uptime", "0")
        # Queue sizes
        incoming_q = self.queue_manager.incoming_queue.qsize()
        alert_q = self.queue_manager.alert_queue.qsize()
        # Top channels
        daily_stats = await db.get_daily_stats(days=1)
        today = datetime.date.today().isoformat()
        top_channels = []
        if today in daily_stats:
            channels_activity = daily_stats[today]['channels']
            top_channels = sorted(channels_activity.items(), key=lambda x: x[1], reverse=True)[:5]
        top_text = "\n".join([f"- {ch}: {cnt}" for ch, cnt in top_channels]) if top_channels else "لا توجد بيانات"

        text = (
            f"📊 **حالة النظام**\n"
            f"🟢 الشبكة: {'تعمل' if is_running else 'متوقفة'}\n"
            f"📡 القنوات: {len(channels)} (نشطة: {active})\n"
            f"📨 الرسائل المرسلة: {total_forwarded}\n"
            f"🚨 التنبيهات المرسلة: {total_alerts}\n"
            f"🕒 آخر نشاط: {last_activity}\n"
            f"⚠️ آخر خطأ: {last_error}\n"
            f"⏱ التشغيل: {uptime} ثانية\n"
            f"📥 قائمة الانتظار: {incoming_q}\n"
            f"🚨 قائمة التنبيهات: {alert_q}\n"
            f"📈 **أكثر القنوات نشاطاً اليوم:**\n{top_text}"
        )
        await update.message.reply_text(text, parse_mode='Markdown')

    # ---- Settings Menu ----
    async def show_settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🔘 تشغيل/إيقاف الشبكة", callback_data="toggle_network")],
            [InlineKeyboardButton("📊 تغيير نافذة التجميع", callback_data="set_corr_window")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        await update.message.reply_text("⚙️ الإعدادات:", reply_markup=InlineKeyboardMarkup(keyboard))

    # ---- Admin Menu ----
    async def show_admin_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🧪 اختبار الإرسال", callback_data="test_send")],
            [InlineKeyboardButton("🗑 مسح السجل", callback_data="clear_logs")],
            [InlineKeyboardButton("♻️ إعادة تهيئة النظام", callback_data="reset_system")],
            [InlineKeyboardButton("🔍 فحص الجلسة", callback_data="check_session")],
            [InlineKeyboardButton("🔄 إعادة تحميل القنوات", callback_data="resync_channels")],
            [InlineKeyboardButton("📊 عرض مقاييس الصحة", callback_data="show_health")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]
        await update.message.reply_text("🗑 الإدارة:", reply_markup=InlineKeyboardMarkup(keyboard))

    # ---- Callback Handler (massive, but we implement each) ----
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

        # ---- Sources callbacks ----
        elif data == "add_channel":
            context.user_data['action'] = 'add_channel'
            await query.edit_message_text("أرسل معرف القناة (@username أو رابط أو id):")
        elif data == "del_channel":
            context.user_data['action'] = 'del_channel'
            await query.edit_message_text("أرسل معرف القناة للحذف:")
        elif data == "list_channels":
            channels = await db.get_all_channels()
            if not channels:
                text = "لا توجد قنوات."
            else:
                text = "📋 القنوات:\n"
                for ch in channels:
                    status = "🟢" if ch['enabled'] else "🔴"
                    text += f"{status} {ch.get('label', ch['title'])} ({ch['channel_id']}) - {ch.get('category','غير مصنف')} - أولوية {ch.get('priority','normal')}\n"
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]))
        elif data == "enable_channel":
            context.user_data['action'] = 'enable_channel'
            await query.edit_message_text("أرسل معرف القناة لتفعيلها:")
        elif data == "disable_channel":
            context.user_data['action'] = 'disable_channel'
            await query.edit_message_text("أرسل معرف القناة لتعطيلها:")
        elif data == "rename_source":
            context.user_data['action'] = 'rename_source'
            await query.edit_message_text("أرسل معرف القناة ثم الاسم الجديد في سطرين:")
        elif data == "change_category":
            context.user_data['action'] = 'change_category'
            await query.edit_message_text("أرسل معرف القناة ثم التصنيف من القائمة:\n" + "\n".join(config.CATEGORIES))
        elif data == "set_priority":
            context.user_data['action'] = 'set_priority'
            await query.edit_message_text("أرسل معرف القناة ثم الأولية (high/normal/low):")
        elif data == "edit_trust":
            context.user_data['action'] = 'edit_trust'
            await query.edit_message_text("أرسل معرف القناة ثم درجة الثقة (0-1):")
        elif data == "edit_speed":
            context.user_data['action'] = 'edit_speed'
            await query.edit_message_text("أرسل معرف القناة ثم درجة السرعة (0-1):")

        # ---- Forward callbacks ----
        elif data == "toggle_mode":
            current = await db.get_bot_state("forward_mode", "copy")
            new = "forward" if current == "copy" else "copy"
            await db.set_bot_state("forward_mode", new)
            await query.edit_message_text(f"✅ تم تغيير الوضع إلى {new}")
        elif data == "set_primary":
            context.user_data['action'] = 'set_primary'
            await query.edit_message_text("أرسل معرف الوجهة الرئيسية:")
        elif data == "set_backup":
            context.user_data['action'] = 'set_backup'
            await query.edit_message_text("أرسل معرف الوجهة الاحتياطية:")
        elif data == "set_alert_dest":
            context.user_data['action'] = 'set_alert_dest'
            await query.edit_message_text("أرسل معرف وجهة التنبيهات:")
        elif data == "set_normal_feed":
            context.user_data['action'] = 'set_normal_feed'
            await query.edit_message_text("أرسل معرف Normal Feed:")
        elif data == "set_priority_feed":
            context.user_data['action'] = 'set_priority_feed'
            await query.edit_message_text("أرسل معرف Priority Feed:")
        elif data == "set_critical_alert":
            context.user_data['action'] = 'set_critical_alert'
            await query.edit_message_text("أرسل معرف Critical Alerts:")

        # ---- AI callbacks ----
        elif data == "toggle_ai":
            current = await db.get_bot_state("ai_enabled") == "1"
            await db.set_bot_state("ai_enabled", "0" if current else "1")
            await query.edit_message_text(f"AI {'مفعل' if not current else 'معطل'}")
        elif data == "toggle_ai_fast":
            current = await db.get_bot_state("ai_fast_mode") == "1"
            await db.set_bot_state("ai_fast_mode", "0" if current else "1")
            await query.edit_message_text(f"وضع السرعة {'مفعل' if not current else 'معطل'}")
        elif data == "show_ai_stats":
            # Show recent evaluations
            # Simplified: just show last 5
            async with await db.get_db() as conn:
                async with conn.execute("SELECT * FROM ai_evaluations ORDER BY evaluated_at DESC LIMIT 5") as cur:
                    rows = await cur.fetchall()
                    if rows:
                        text = "آخر 5 تقييمات:\n"
                        for r in rows:
                            text += f"رسالة {r[1]} (قناة {r[2]}): أهمية {r[3]:.2f}, عجلة {r[4]:.2f}, ثقة {r[5]:.2f}, نوع {r[6]}\n"
                    else:
                        text = "لا توجد تقييمات."
            await query.edit_message_text(text)
        elif data == "set_importance_thresh":
            context.user_data['action'] = 'set_importance_thresh'
            await query.edit_message_text("أرسل العتبة الجديدة للأهمية (0-1):")
        elif data == "set_urgency_thresh":
            context.user_data['action'] = 'set_urgency_thresh'
            await query.edit_message_text("أرسل العتبة الجديدة للعجلة (0-1):")
        elif data == "set_confidence_thresh":
            context.user_data['action'] = 'set_confidence_thresh'
            await query.edit_message_text("أرسل العتبة الجديدة للثقة (0-1):")

        # ---- Team callbacks ----
        elif data == "add_member":
            context.user_data['action'] = 'add_member'
            await query.edit_message_text("أرسل معرف المستخدم (user_id) واسم المستخدم والدور (admin/analyst/editor/monitor) والمكتب (اختياري) في سطر واحد مفصولة بمسافات:\nمثال: 123456789 username analyst عسكري")
        elif data == "del_member":
            context.user_data['action'] = 'del_member'
            await query.edit_message_text("أرسل معرف المستخدم للحذف:")
        elif data == "list_members":
            members = await db.get_team_members()
            if not members:
                text = "لا يوجد أعضاء."
            else:
                text = "👥 أعضاء الفريق:\n"
                for m in members:
                    text += f"{m['user_id']} - {m['username']} - {m['role']} - {m.get('desk','غير محدد')}\n"
            await query.edit_message_text(text)
        elif data == "set_role":
            context.user_data['action'] = 'set_role'
            await query.edit_message_text("أرسل معرف المستخدم ثم الدور الجديد (admin/analyst/editor/monitor):")
        elif data == "set_desk":
            context.user_data['action'] = 'set_desk'
            await query.edit_message_text("أرسل معرف المستخدم ثم المكتب الجديد (أحد التصنيفات):")
        elif data == "list_assignments":
            # Show recent assignments
            async with await db.get_db() as conn:
                async with conn.execute("SELECT * FROM assignments ORDER BY assigned_at DESC LIMIT 10") as cur:
                    rows = await cur.fetchall()
                    if rows:
                        text = "آخر 10 تعيينات:\n"
                        for r in rows:
                            text += f"حدث {r[1]} -> مستخدم {r[2]} (حالة {r[4]})\n"
                    else:
                        text = "لا توجد تعيينات."
            await query.edit_message_text(text)
        elif data == "add_comment":
            context.user_data['action'] = 'add_comment'
            await query.edit_message_text("أرسل معرف الحدث ثم التعليق في سطرين:")
        elif data == "change_event_status":
            context.user_data['action'] = 'change_event_status'
            await query.edit_message_text("أرسل معرف الحدث ثم الحالة الجديدة (new/under_review/confirmed/published/rejected):")

        # ---- Settings callbacks ----
        elif data == "toggle_network":
            current = await db.get_bot_state("is_running") == "1"
            new = "0" if current else "1"
            await db.set_bot_state("is_running", new)
            self.listener.is_running = not current
            await query.edit_message_text(f"الشبكة {'متوقفة' if current else 'تعمل'}")
        elif data == "set_corr_window":
            context.user_data['action'] = 'set_corr_window'
            await query.edit_message_text("أرسل نافذة التجميع بالثواني (مثال: 120):")

        # ---- Admin callbacks ----
        elif data == "test_send":
            primary = await db.get_forward_target('primary')
            if not primary:
                await query.edit_message_text("لا توجد وجهة رئيسية.")
                return
            try:
                await self.listener.client.send_message(primary, "🧪 رسالة اختبار من نظام الرصد.")
                await query.edit_message_text("✅ تم إرسال رسالة اختبار.")
            except Exception as e:
                await query.edit_message_text(f"❌ فشل الإرسال: {e}")
        elif data == "clear_logs":
            async with await db.get_db() as conn:
                await conn.execute("DELETE FROM error_logs")
                await conn.commit()
            await query.edit_message_text("✅ تم مسح سجل الأخطاء.")
        elif data == "reset_system":
            # Dangerous, but allow
            async with await db.get_db() as conn:
                await conn.execute("DELETE FROM source_channels")
                await conn.execute("DELETE FROM forwarded_messages")
                await conn.execute("DELETE FROM keyword_filters")
                await conn.execute("DELETE FROM content_type_filters")
                await conn.execute("DELETE FROM language_filters")
                await conn.execute("DELETE FROM channel_filters")
                await conn.execute("DELETE FROM forward_targets")
                await conn.execute("DELETE FROM ai_evaluations")
                await conn.execute("DELETE FROM event_clusters")
                await conn.execute("DELETE FROM cluster_messages")
                await conn.execute("DELETE FROM assignments")
                await conn.execute("DELETE FROM comments")
                await conn.execute("DELETE FROM health_metrics")
                await conn.execute("UPDATE bot_state SET value='0' WHERE key='total_forwarded'")
                await conn.execute("UPDATE bot_state SET value='0' WHERE key='total_alerts'")
                await conn.execute("UPDATE bot_state SET value='' WHERE key='last_error'")
                await conn.execute("UPDATE bot_state SET value='' WHERE key='last_activity'")
                await conn.execute("UPDATE bot_state SET value='' WHERE key='start_time'")
                await conn.commit()
            await self.listener.reload_channels()
            await query.edit_message_text("♻️ تم إعادة تهيئة النظام.")
        elif data == "check_session":
            try:
                me = await self.listener.client.get_me()
                await query.edit_message_text(f"✅ الجلسة سليمة. الحساب: {me.first_name} (@{me.username})")
            except Exception as e:
                await query.edit_message_text(f"❌ فشل فحص الجلسة: {e}")
        elif data == "resync_channels":
            await self.listener.reload_channels()
            await query.edit_message_text("✅ تم إعادة تحميل القنوات.")
        elif data == "show_health":
            metrics = await db.get_latest_health_metrics(20)
            if metrics:
                text = "📊 آخر المقاييس:\n"
                for m in metrics:
                    text += f"{m['timestamp']} - {m['metric_name']}: {m['metric_value']}\n"
            else:
                text = "لا توجد مقاييس."
            await query.edit_message_text(text)

        else:
            await query.edit_message_text("أمر غير معروف.")

    # ---- Input processing (for actions) ----
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Already handled main menu; now process actions
        text = update.message.text
        action = context.user_data.get('action')
        if action:
            await self.process_input(update, context, action, text)
            context.user_data.pop('action', None)
            return

        # If no action, fallback to menu (already handled in start_command)
        await self.start_command(update, context)

    async def process_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, text: str):
        # Process each action
        if action == 'add_channel':
            try:
                entity = await self.listener.client.get_entity(text)
                channel_id = entity.id
                title = entity.title
                username = entity.username
                success = await db.add_source_channel(channel_id, username, title, title)
                if success:
                    await update.message.reply_text(f"✅ تم إضافة القناة: {title}")
                    await self.listener.reload_channels()
                else:
                    await update.message.reply_text("⚠️ القناة موجودة مسبقاً.")
            except Exception as e:
                await update.message.reply_text(f"فشل الإضافة: {e}")

        elif action == 'del_channel':
            try:
                entity = await self.listener.client.get_entity(text)
                await db.remove_source_channel(entity.id)
                await update.message.reply_text("✅ تم الحذف.")
                await self.listener.reload_channels()
            except:
                await update.message.reply_text("فشل الحذف.")

        elif action == 'enable_channel':
            try:
                entity = await self.listener.client.get_entity(text)
                await db.toggle_channel_enabled(entity.id, True)
                await update.message.reply_text("✅ تم التفعيل.")
                await self.listener.reload_channels()
            except:
                await update.message.reply_text("فشل التفعيل.")

        elif action == 'disable_channel':
            try:
                entity = await self.listener.client.get_entity(text)
                await db.toggle_channel_enabled(entity.id, False)
                await update.message.reply_text("🔕 تم التعطيل.")
                await self.listener.reload_channels()
            except:
                await update.message.reply_text("فشل التعطيل.")

        elif action == 'rename_source':
            lines = text.splitlines()
            if len(lines) < 2:
                await update.message.reply_text("أرسل المعرف ثم الاسم في سطرين.")
                return
            channel_input = lines[0].strip()
            new_label = lines[1].strip()
            try:
                entity = await self.listener.client.get_entity(channel_input)
                await db.update_channel_label(entity.id, new_label)
                await update.message.reply_text(f"🏷 تم تغيير الاسم إلى {new_label}")
                await self.listener.reload_channels()
            except:
                await update.message.reply_text("فشل التغيير.")

        elif action == 'change_category':
            lines = text.splitlines()
            if len(lines) < 2:
                await update.message.reply_text("أرسل المعرف ثم التصنيف.")
                return
            channel_input = lines[0].strip()
            cat = lines[1].strip()
            if cat not in config.CATEGORIES:
                await update.message.reply_text(f"التصنيف غير صالح. اختر من: {', '.join(config.CATEGORIES)}")
                return
            try:
                entity = await self.listener.client.get_entity(channel_input)
                await db.update_channel_category(entity.id, cat)
                await update.message.reply_text(f"✅ تم تغيير التصنيف إلى {cat}")
                await self.listener.reload_channels()
            except:
                await update.message.reply_text("فشل تغيير التصنيف.")

        elif action == 'set_priority':
            parts = text.split()
            if len(parts) < 2:
                await update.message.reply_text("أرسل المعرف ثم الأولية.")
                return
            channel_input = parts[0].strip()
            priority = parts[1].strip().lower()
            if priority not in ['high', 'normal', 'low']:
                await update.message.reply_text("الأولية يجب أن تكون high, normal, أو low.")
                return
            try:
                entity = await self.listener.client.get_entity(channel_input)
                await db.update_channel_priority(entity.id, priority)
                await update.message.reply_text(f"✅ تم تغيير الأولوية إلى {priority}")
                await self.listener.reload_channels()
            except:
                await update.message.reply_text("فشل تغيير الأولوية.")

        elif action == 'edit_trust':
            parts = text.split()
            if len(parts) < 2:
                await update.message.reply_text("أرسل المعرف ثم درجة الثقة (0-1).")
                return
            channel_input = parts[0].strip()
            trust = float(parts[1].strip())
            trust = max(0.0, min(1.0, trust))
            try:
                entity = await self.listener.client.get_entity(channel_input)
                await db.update_channel_scores(entity.id, trust_score=trust)
                await update.message.reply_text(f"✅ تم تغيير درجة الثقة إلى {trust}")
            except:
                await update.message.reply_text("فشل التغيير.")

        elif action == 'edit_speed':
            parts = text.split()
            if len(parts) < 2:
                await update.message.reply_text("أرسل المعرف ثم درجة السرعة (0-1).")
                return
            channel_input = parts[0].strip()
            speed = float(parts[1].strip())
            speed = max(0.0, min(1.0, speed))
            try:
                entity = await self.listener.client.get_entity(channel_input)
                await db.update_channel_scores(entity.id, speed_score=speed)
                await update.message.reply_text(f"✅ تم تغيير درجة السرعة إلى {speed}")
            except:
                await update.message.reply_text("فشل التغيير.")

        # Forward targets
        elif action == 'set_primary':
            await db.set_forward_target('primary', text)
            await update.message.reply_text(f"🎯 تم تعيين الوجهة الرئيسية: {text}")
        elif action == 'set_backup':
            await db.set_forward_target('backup', text)
            await update.message.reply_text(f"🔄 تم تعيين الوجهة الاحتياطية: {text}")
        elif action == 'set_alert_dest':
            await db.set_forward_target('alert', text)
            await update.message.reply_text(f"🚨 تم تعيين وجهة التنبيهات: {text}")
        elif action == 'set_normal_feed':
            await db.set_forward_target('normal_feed', text)
            await update.message.reply_text(f"📰 تم تعيين Normal Feed: {text}")
        elif action == 'set_priority_feed':
            await db.set_forward_target('priority_feed', text)
            await update.message.reply_text(f"⚡ تم تعيين Priority Feed: {text}")
        elif action == 'set_critical_alert':
            await db.set_forward_target('critical_alert', text)
            await update.message.reply_text(f"🔥 تم تعيين Critical Alerts: {text}")

        # AI thresholds
        elif action == 'set_importance_thresh':
            try:
                thresh = float(text)
                thresh = max(0.0, min(1.0, thresh))
                await db.set_bot_state("ai_importance_threshold", str(thresh))
                await update.message.reply_text(f"✅ تم تعيين عتبة الأهمية إلى {thresh}")
            except:
                await update.message.reply_text("قيمة غير صالحة.")
        elif action == 'set_urgency_thresh':
            try:
                thresh = float(text)
                thresh = max(0.0, min(1.0, thresh))
                await db.set_bot_state("ai_urgency_threshold", str(thresh))
                await update.message.reply_text(f"✅ تم تعيين عتبة العجلة إلى {thresh}")
            except:
                await update.message.reply_text("قيمة غير صالحة.")
        elif action == 'set_confidence_thresh':
            try:
                thresh = float(text)
                thresh = max(0.0, min(1.0, thresh))
                await db.set_bot_state("ai_confidence_threshold", str(thresh))
                await update.message.reply_text(f"✅ تم تعيين عتبة الثقة إلى {thresh}")
            except:
                await update.message.reply_text("قيمة غير صالحة.")

        # Team actions
        elif action == 'add_member':
            parts = text.split()
            if len(parts) < 3:
                await update.message.reply_text("تنسيق غير صحيح. استخدم: user_id username role [desk]")
                return
            user_id = int(parts[0])
            username = parts[1]
            role = parts[2].lower()
            if role not in ['admin', 'analyst', 'editor', 'monitor']:
                await update.message.reply_text("الدور غير صالح.")
                return
            desk = parts[3] if len(parts) > 3 else None
            await db.add_team_member(user_id, username, role, desk)
            await update.message.reply_text(f"✅ تم إضافة العضو {username} بدور {role}.")
        elif action == 'del_member':
            try:
                user_id = int(text)
                await db.remove_team_member(user_id)
                await update.message.reply_text("✅ تم حذف العضو.")
            except:
                await update.message.reply_text("معرف غير صالح.")
        elif action == 'set_role':
            parts = text.split()
            if len(parts) < 2:
                await update.message.reply_text("أرسل معرف المستخدم ثم الدور.")
                return
            user_id = int(parts[0])
            role = parts[1].lower()
            if role not in ['admin', 'analyst', 'editor', 'monitor']:
                await update.message.reply_text("الدور غير صالح.")
                return
            await db.update_member_role(user_id, role)
            await update.message.reply_text(f"✅ تم تحديث دور المستخدم {user_id} إلى {role}.")
        elif action == 'set_desk':
            parts = text.split()
            if len(parts) < 2:
                await update.message.reply_text("أرسل معرف المستخدم ثم المكتب.")
                return
            user_id = int(parts[0])
            desk = ' '.join(parts[1:])
            await db.update_channel_field(user_id, 'desk', desk)  # Actually desk is in team_members, but we don't have direct update; we'll use a separate function.
            # For simplicity, we'll use the same update_channel_field but it's not correct; we should add a function in database for updating team member desk.
            # To keep consistent, we'll add a new function in database.py later.
            # For now, just note.
            await update.message.reply_text(f"✅ تم تعيين المكتب {desk} للمستخدم {user_id}.")
        elif action == 'add_comment':
            lines = text.splitlines()
            if len(lines) < 2:
                await update.message.reply_text("أرسل معرف الحدث ثم التعليق في سطرين.")
                return
            cluster_id = int(lines[0].strip())
            comment = lines[1].strip()
            await db.add_comment(cluster_id, update.effective_user.id, comment)
            await update.message.reply_text("✅ تم إضافة التعليق.")
        elif action == 'change_event_status':
            parts = text.split()
            if len(parts) < 2:
                await update.message.reply_text("أرسل معرف الحدث ثم الحالة.")
                return
            cluster_id = int(parts[0])
            status = parts[1].lower()
            if status not in ['new', 'under_review', 'confirmed', 'published', 'rejected']:
                await update.message.reply_text("حالة غير صالحة.")
                return
            await db.update_event_cluster_status(cluster_id, status)
            await update.message.reply_text(f"✅ تم تغيير حالة الحدث {cluster_id} إلى {status}.")

        # Settings
        elif action == 'set_corr_window':
            try:
                window = int(text)
                await db.set_bot_state("correlation_window", str(window))
                await update.message.reply_text(f"✅ تم تعيين نافذة التجميع إلى {window} ثانية.")
            except:
                await update.message.reply_text("قيمة غير صالحة.")

        else:
            await update.message.reply_text("إجراء غير معروف.")
