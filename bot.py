"""
بوت تلجرام احترافي لتحميل فيديوهات Pinterest
مع ميزة الاشتراك الإجباري في القناة
"""
import os
import logging
import asyncio
from typing import Optional
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode, ChatAction

from database import Database
from downloader import PinterestDownloader

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

REQUIRED_CHANNEL = "@Garren_Store"
REQUIRED_CHANNEL_ID = "-1002353060403"


class PinterestBot:
    """بوت تلجرام لتحميل فيديوهات Pinterest"""
    
    def __init__(self, token: str, admin_id: Optional[int] = None):
        """
        تهيئة البوت
        
        Args:
            token: توكن البوت من BotFather
            admin_id: معرف المسؤول في تلجرام
        """
        self.token = token
        self.admin_id = admin_id
        self.db = Database()
        self.downloader = PinterestDownloader()
        self.app = Application.builder().token(token).build()
        self._setup_handlers()
        self._init_settings()
        logger.info("تم تهيئة البوت بنجاح")
    
    def _init_settings(self) -> None:
        """تهيئة الإعدادات الافتراضية"""
        if not self.db.get_setting("channel_username"):
            self.db.set_setting("channel_username", REQUIRED_CHANNEL)
        if not self.db.get_setting("channel_id"):
            self.db.set_setting("channel_id", REQUIRED_CHANNEL_ID)
    
    def _setup_handlers(self) -> None:
        """تسجيل معالجات الأوامر والرسائل"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("admin", self.admin_command))
        self.app.add_handler(CommandHandler("setchannel", self.setchannel_command))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
    
    def is_admin(self, user_id: int) -> bool:
        """
        التحقق من أن المستخدم هو المسؤول
        
        Args:
            user_id: معرف المستخدم
            
        Returns:
            True إذا كان المستخدم مسؤولاً
        """
        return self.admin_id is not None and user_id == self.admin_id
    
    async def check_subscription(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """
        التحقق من اشتراك المستخدم في القناة المطلوبة
        
        Args:
            update: كائن التحديث من تلجرام
            context: سياق المحادثة
            
        Returns:
            True إذا كان المستخدم مشتركاً
        """
        user = None
        if update.callback_query:
            user = update.callback_query.from_user
        elif update.effective_user:
            user = update.effective_user
        
        if not user:
            logger.error("لم يتم العثور على معلومات المستخدم في التحديث")
            return False
        
        user_id = user.id
        
        if self.is_admin(user_id):
            logger.info(f"المسؤول {user_id} معفى من التحقق من الاشتراك")
            return True
        
        channel_id = self.db.get_setting("channel_id", REQUIRED_CHANNEL_ID)
        
        try:
            member = await context.bot.get_chat_member(
                chat_id=channel_id,
                user_id=user_id
            )
            
            is_subscribed = member.status in ['member', 'administrator', 'creator']
            
            self.db.update_subscription_status(user_id, is_subscribed)
            
            return is_subscribed
            
        except Exception as e:
            logger.error(f"خطأ في التحقق من الاشتراك: {str(e)}")
            return False
    
    async def send_subscription_message(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        إرسال رسالة طلب الاشتراك في القناة
        
        Args:
            update: كائن التحديث
            context: سياق المحادثة
        """
        channel_username = self.db.get_setting("channel_username", REQUIRED_CHANNEL)
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔗 إنضم للقناة", 
                    url=f"https://t.me/{channel_username[1:]}"
                )
            ],
            [
                InlineKeyboardButton(
                    "✅ تحققت من الاشتراك", 
                    callback_data="check_subscription"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            "مرحباً بك! 👋\n\n"
            "للاستفادة من البوت، يجب عليك الاشتراك في قناتنا أولاً:\n\n"
            f"📢 القناة: {channel_username}\n\n"
            "بعد الاشتراك، اضغط على زر \"تحققت من الاشتراك\" أدناه ✅"
        )
        
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    
    async def start_command(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        معالج أمر /start
        
        Args:
            update: كائن التحديث
            context: سياق المحادثة
        """
        user = update.effective_user
        
        self.db.add_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name
        )
        
        is_subscribed = await self.check_subscription(update, context)
        
        if not is_subscribed:
            await self.send_subscription_message(update, context)
            return
        
        welcome_message = (
            f"مرحباً {user.first_name}! 👋\n\n"
            "🎬 <b>بوت تحميل فيديوهات Pinterest</b>\n\n"
            "📝 <b>طريقة الاستخدام:</b>\n"
            "• أرسل رابط فيديو من Pinterest\n"
            "• سيقوم البوت بتحميل الفيديو وإرساله لك\n\n"
            "⚡️ <b>مميزات البوت:</b>\n"
            "✅ سريع وموثوق\n"
            "✅ جودة عالية\n"
            "✅ سهل الاستخدام\n\n"
            "📊 للإحصائيات: /stats\n\n"
            "💡 فقط أرسل رابط الفيديو وسأقوم بتحميله لك!"
        )
        
        await update.message.reply_text(
            welcome_message,
            parse_mode=ParseMode.HTML
        )
    
    async def stats_command(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        معالج أمر /stats لعرض إحصائيات البوت
        
        Args:
            update: كائن التحديث
            context: سياق المحادثة
        """
        is_subscribed = await self.check_subscription(update, context)
        
        if not is_subscribed:
            await self.send_subscription_message(update, context)
            return
        
        total_users = self.db.get_total_users()
        total_videos = self.db.get_total_videos()
        
        stats_message = (
            "📊 <b>إحصائيات البوت</b>\n\n"
            f"👥 عدد المستخدمين: <code>{total_users}</code>\n"
            f"🎬 عدد الفيديوهات المحملة: <code>{total_videos}</code>\n\n"
            "شكراً لاستخدامك البوت! 💙"
        )
        
        await update.message.reply_text(
            stats_message,
            parse_mode=ParseMode.HTML
        )
    
    async def setchannel_command(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        معالج أمر /setchannel لتغيير إعدادات القناة
        
        Args:
            update: كائن التحديث
            context: سياق المحادثة
        """
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text(
                "⛔️ عذراً، هذا الأمر متاح للمسؤول فقط!"
            )
            return
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "❌ صيغة الأمر غير صحيحة!\n\n"
                "الصيغة الصحيحة:\n"
                "<code>/setchannel معرف_القناة اسم_القناة</code>\n\n"
                "مثال:\n"
                "<code>/setchannel -1002353060403 @Garren_Store</code>",
                parse_mode=ParseMode.HTML
            )
            return
        
        channel_id = context.args[0]
        channel_username = context.args[1]
        
        if not channel_username.startswith("@"):
            channel_username = f"@{channel_username}"
        
        self.db.set_setting("channel_id", channel_id)
        self.db.set_setting("channel_username", channel_username)
        
        await update.message.reply_text(
            "✅ <b>تم تحديث إعدادات القناة بنجاح!</b>\n\n"
            f"🆔 معرف القناة: <code>{channel_id}</code>\n"
            f"📢 اسم القناة: <code>{channel_username}</code>\n\n"
            "سيتم استخدام هذه الإعدادات الجديدة من الآن فصاعداً.",
            parse_mode=ParseMode.HTML
        )
        
        logger.info(f"المسؤول {user_id} قام بتحديث إعدادات القناة: {channel_id} - {channel_username}")
    
    async def admin_command(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        معالج أمر /admin - لوحة التحكم للمسؤول فقط
        
        Args:
            update: كائن التحديث
            context: سياق المحادثة
        """
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text(
                "⛔️ عذراً، هذا الأمر متاح للمسؤول فقط!"
            )
            return
        
        total_users = self.db.get_total_users()
        total_videos = self.db.get_total_videos()
        channel_username = self.db.get_setting("channel_username", REQUIRED_CHANNEL)
        channel_id = self.db.get_setting("channel_id", REQUIRED_CHANNEL_ID)
        
        keyboard = [
            [InlineKeyboardButton("📊 الإحصائيات المفصلة", callback_data="admin_detailed_stats")],
            [
                InlineKeyboardButton("📢 تغيير اسم القناة", callback_data="admin_set_channel_username"),
                InlineKeyboardButton("🆔 تغيير معرف القناة", callback_data="admin_set_channel_id")
            ],
            [InlineKeyboardButton("🔄 تحديث", callback_data="admin_refresh")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        admin_message = (
            "👨‍💼 <b>لوحة التحكم</b>\n\n"
            "📊 <b>إحصائيات سريعة:</b>\n"
            f"👥 المستخدمون: <code>{total_users}</code>\n"
            f"🎬 الفيديوهات: <code>{total_videos}</code>\n\n"
            "⚙️ <b>إعدادات القناة الحالية:</b>\n"
            f"📢 اسم القناة: <code>{channel_username}</code>\n"
            f"🆔 معرف القناة: <code>{channel_id}</code>\n\n"
            "استخدم الأزرار أدناه للتحكم في البوت 👇"
        )
        
        await update.message.reply_text(
            admin_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    
    async def button_callback(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        معالج الأزرار التفاعلية
        
        Args:
            update: كائن التحديث
            context: سياق المحادثة
        """
        query = update.callback_query
        await query.answer()
        
        if query.data == "check_subscription":
            is_subscribed = await self.check_subscription(update, context)
            
            if is_subscribed:
                await query.edit_message_text(
                    "تم التحقق بنجاح! ✅\n\n"
                    "يمكنك الآن استخدام البوت بحرية 🎉\n\n"
                    "أرسل رابط فيديو Pinterest لتحميله!",
                    parse_mode=ParseMode.HTML
                )
            else:
                channel_username = self.db.get_setting("channel_username", REQUIRED_CHANNEL)
                try:
                    await query.edit_message_text(
                        "❌ لم يتم العثور على اشتراكك!\n\n"
                        f"يرجى الاشتراك في القناة {channel_username} أولاً\n"
                        "ثم اضغط على الزر مرة أخرى.",
                        reply_markup=query.message.reply_markup
                    )
                except:
                    pass
        
        elif query.data == "admin_refresh":
            if not self.is_admin(query.from_user.id):
                await query.answer("⛔️ غير مصرح لك!")
                return
            
            total_users = self.db.get_total_users()
            total_videos = self.db.get_total_videos()
            channel_username = self.db.get_setting("channel_username", REQUIRED_CHANNEL)
            channel_id = self.db.get_setting("channel_id", REQUIRED_CHANNEL_ID)
            
            keyboard = [
                [InlineKeyboardButton("📊 الإحصائيات المفصلة", callback_data="admin_detailed_stats")],
                [InlineKeyboardButton("⚙️ تغيير معرف القناة", callback_data="admin_change_channel")],
                [InlineKeyboardButton("🔄 تحديث", callback_data="admin_refresh")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            admin_message = (
                "👨‍💼 <b>لوحة التحكم</b>\n\n"
                "📊 <b>إحصائيات سريعة:</b>\n"
                f"👥 المستخدمون: <code>{total_users}</code>\n"
                f"🎬 الفيديوهات: <code>{total_videos}</code>\n\n"
                "⚙️ <b>إعدادات القناة:</b>\n"
                f"📢 اسم القناة: <code>{channel_username}</code>\n"
                f"🆔 معرف القناة: <code>{channel_id}</code>\n\n"
                "استخدم الأزرار أدناه للتحكم في البوت 👇"
            )
            
            try:
                await query.edit_message_text(
                    admin_message,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
                await query.answer("✅ تم التحديث!")
            except:
                await query.answer("تم التحديث")
        
        elif query.data == "admin_detailed_stats":
            if not self.is_admin(query.from_user.id):
                await query.answer("⛔️ غير مصرح لك!")
                return
            
            total_users = self.db.get_total_users()
            total_videos = self.db.get_total_videos()
            
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            stats_message = (
                "📊 <b>الإحصائيات المفصلة</b>\n\n"
                f"👥 إجمالي المستخدمين: <code>{total_users}</code>\n"
                f"🎬 إجمالي الفيديوهات: <code>{total_videos}</code>\n\n"
                "📈 <b>معلومات إضافية:</b>\n"
                f"💾 قاعدة البيانات: <code>SQLite</code>\n"
                f"🤖 إصدار البوت: <code>1.0</code>\n"
            )
            
            try:
                await query.edit_message_text(
                    stats_message,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            except:
                pass
        
        elif query.data == "admin_set_channel_username":
            if not self.is_admin(query.from_user.id):
                await query.answer("⛔️ غير مصرح لك!")
                return
            
            # حفظ حالة انتظار اسم القناة
            context.user_data['waiting_for'] = 'channel_username'
            context.user_data['admin_message_id'] = query.message.message_id
            
            keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            current_username = self.db.get_setting("channel_username", REQUIRED_CHANNEL)
            
            instructions = (
                "📢 <b>تغيير اسم القناة</b>\n\n"
                f"الاسم الحالي: <code>{current_username}</code>\n\n"
                "أرسل اسم القناة الجديد الآن:\n\n"
                "📝 <b>أمثلة صالحة:</b>\n"
                "• <code>@Garren_Store</code>\n"
                "• <code>Garren_Store</code> (سيتم إضافة @ تلقائياً)\n\n"
                "⚠️ تأكد من صحة اسم القناة!"
            )
            
            try:
                await query.edit_message_text(
                    instructions,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
                await query.answer("انتظار اسم القناة الجديد...")
            except:
                await query.answer("حدث خطأ")
        
        elif query.data == "admin_set_channel_id":
            if not self.is_admin(query.from_user.id):
                await query.answer("⛔️ غير مصرح لك!")
                return
            
            # حفظ حالة انتظار معرف القناة
            context.user_data['waiting_for'] = 'channel_id'
            context.user_data['admin_message_id'] = query.message.message_id
            
            keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            current_id = self.db.get_setting("channel_id", REQUIRED_CHANNEL_ID)
            
            instructions = (
                "🆔 <b>تغيير معرف القناة</b>\n\n"
                f"المعرف الحالي: <code>{current_id}</code>\n\n"
                "أرسل معرف القناة الجديد الآن:\n\n"
                "📝 <b>أمثلة صالحة:</b>\n"
                "• <code>-1002353060403</code>\n"
                "• <code>-100xxxxxxxxx</code>\n\n"
                "💡 <b>للحصول على معرف القناة:</b>\n"
                "1. أضف البوت كمسؤول في القناة\n"
                "2. استخدم @userinfobot في القناة\n\n"
                "⚠️ تأكد من صحة المعرف!"
            )
            
            try:
                await query.edit_message_text(
                    instructions,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
                await query.answer("انتظار معرف القناة الجديد...")
            except:
                await query.answer("حدث خطأ")
    
    async def handle_message(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        معالج الرسائل النصية (الروابط والإعدادات التفاعلية) - محدث للنظام المتقدم
        
        Args:
            update: كائن التحديث
            context: سياق المحادثة
        """
        if not update.effective_user or not update.message:
            return
        
        user_id = update.effective_user.id
        message_text = update.message.text.strip()
        
        # التحقق من حالات الانتظار للمسؤول
        if self.is_admin(user_id) and context.user_data.get('waiting_for'):
            await self._handle_admin_input(update, context, message_text)
            return
        
        is_subscribed = await self.check_subscription(update, context)
        
        if not is_subscribed:
            await self.send_subscription_message(update, context)
            return
        
        url = message_text
        
        if not self.downloader.is_pinterest_url(url):
            await update.message.reply_text(
                "❌ الرابط غير صالح!\n\n"
                "يرجى إرسال رابط فيديو من Pinterest فقط.\n\n"
                "الأشكال المدعومة:\n"
                "• https://pin.it/xxxxx\n"
                "• https://pinterest.com/pin/xxxxx\n"
                "• https://www.pinterest.com/pin/xxxxx\n\n"
                "💡 تأكد من أن الرابط يحتوي على فيديو وليس صورة فقط!"
            )
            return
        
        # فحص الكاش أولاً
        cached_video = self.db.get_downloaded_video(url)
        
        if cached_video:
            logger.info(f"إرسال فيديو من الكاش: {url}")
            
            try:
                await context.bot.send_chat_action(
                    chat_id=update.effective_chat.id,
                    action=ChatAction.UPLOAD_VIDEO
                )
                
                caption = (
                    f"🎬 {cached_video.title or 'Pinterest Video'}\n\n"
                    f"⚡️ تم الإرسال من الكاش (أسرع)\n"
                    f"📊 تم تحميله {cached_video.download_count} مرة"
                )
                
                await update.message.reply_video(
                    video=cached_video.file_id,
                    caption=caption
                )
                
                # تحديث عداد التحميل
                self.db.add_downloaded_video(
                    url=url,
                    file_id=cached_video.file_id,
                    title=cached_video.title,
                    duration=cached_video.duration
                )
                
                return
                
            except Exception as e:
                logger.error(f"خطأ في إرسال الفيديو من الكاش: {str(e)}")
                # المتابعة للتحميل الجديد في حالة فشل الكاش
        
        # رسائل التقدم المحدثة
        status_messages = [
            "🔍 فحص الرابط...",
            "📡 الاتصال بـ Pinterest...", 
            "🎬 استخراج بيانات الفيديو...",
            "⬇️ تحميل الفيديو...",
            "⬆️ رفع الفيديو..."
        ]
        
        status_message = await update.message.reply_text(status_messages[0])
        
        try:
            # فحص أولي للرابط
            await asyncio.sleep(1)
            await status_message.edit_text(status_messages[1])
            
            # التحقق من وجود فيديو في الرابط
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.TYPING
            )
            
            video_info_preview = await self.downloader.get_video_info(url)
            
            if video_info_preview and not video_info_preview.get('has_video', True):
                await status_message.edit_text(
                    "❌ هذا الرابط لا يحتوي على فيديو!\n\n"
                    "يبدو أن هذا Pin يحتوي على صورة فقط.\n"
                    "يرجى إرسال رابط Pin يحتوي على فيديو."
                )
                return
            
            await status_message.edit_text(status_messages[2])
            await asyncio.sleep(1)
            
            await status_message.edit_text(status_messages[3])
            
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.UPLOAD_VIDEO
            )
            
            # تحميل الفيديو بالنظام المتقدم
            video_info = await self.downloader.download_video(url)
            
            if not video_info:
                error_message = (
                    "❌ فشل في تحميل الفيديو!\n\n"
                    "الأسباب المحتملة:\n"
                    "• الفيديو محمي أو خاص\n"
                    "• مشكلة مؤقتة في Pinterest\n"
                    "• الرابط لا يحتوي على فيديو\n"
                    "• مشكلة في الاتصال\n\n"
                    "💡 نصائح:\n"
                    "• تأكد من أن الرابط صحيح\n"
                    "• جرب رابط آخر\n"
                    "• أعد المحاولة بعد قليل"
                )
                await status_message.edit_text(error_message)
                return
            
            filepath = video_info['filepath']
            title = video_info.get('title', 'Pinterest Video')
            description = video_info.get('description', '')
            filesize = video_info.get('filesize', 0)
            
            await status_message.edit_text(status_messages[4])
            
            # تحضير الوصف المحدث
            file_size_mb = filesize / (1024 * 1024) if filesize > 0 else 0
            
            caption = (
                f"🎬 {title}\n\n"
                f"📝 {description[:100]}{'...' if len(description) > 100 else ''}\n\n" if description else "\n"
                f"📊 الحجم: {file_size_mb:.2f} MB\n"
                f"✅ تم التحميل بالنظام المتقدم"
            )
            
            # رفع الفيديو
            with open(filepath, 'rb') as video_file:
                sent_message = await update.message.reply_video(
                    video=video_file,
                    caption=caption,
                    supports_streaming=True,
                    protect_content=False
                )
            
            # حفظ في قاعدة البيانات
            file_id = sent_message.video.file_id
            
            self.db.add_downloaded_video(
                url=url,
                file_id=file_id,
                title=title,
                duration=sent_message.video.duration
            )
            
            # تنظيف الملف
            self.downloader.cleanup_file(filepath)
            
            # حذف رسالة التقدم
            await status_message.delete()
            
            logger.info(f"تم تحميل وإرسال الفيديو بنجاح: {url}")
            
        except Exception as e:
            logger.error(f"خطأ في معالجة الفيديو: {str(e)}")
            
            try:
                error_details = str(e)
                if "timeout" in error_details.lower():
                    error_msg = "⏰ انتهت مهلة الاتصال!\n\nيرجى المحاولة مرة أخرى."
                elif "connection" in error_details.lower():
                    error_msg = "🌐 مشكلة في الاتصال!\n\nتحقق من الإنترنت وأعد المحاولة."
                elif "not found" in error_details.lower():
                    error_msg = "❌ الفيديو غير موجود!\n\nتأكد من أن الرابط صحيح."
                else:
                    error_msg = (
                        f"❌ حدث خطأ غير متوقع!\n\n"
                        f"الخطأ: {error_details[:150]}{'...' if len(error_details) > 150 else ''}\n\n"
                        "يرجى المحاولة مرة أخرى أو التواصل مع المطور."
                    )
                
                await status_message.edit_text(error_msg)
            except:
                # في حالة فشل تحديث الرسالة
                try:
                    await update.message.reply_text(
                        "❌ حدث خطأ في النظام!\n\nيرجى المحاولة مرة أخرى."
                    )
                except:
                    pass
    
    async def _handle_admin_input(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE,
        input_text: str
    ) -> None:
        """
        معالج الإدخال التفاعلي للمسؤول
        
        Args:
            update: كائن التحديث
            context: سياق المحادثة
            input_text: النص المدخل
        """
        waiting_for = context.user_data.get('waiting_for')
        admin_message_id = context.user_data.get('admin_message_id')
        
        try:
            if waiting_for == 'channel_username':
                # تنظيف اسم القناة
                new_username = input_text.strip()
                if not new_username.startswith('@'):
                    new_username = f"@{new_username}"
                
                # التحقق من صحة اسم القناة
                if len(new_username) < 6 or not new_username[1:].replace('_', '').isalnum():
                    await update.message.reply_text(
                        "❌ اسم القناة غير صالح!\n\n"
                        "يجب أن يكون اسم القناة:\n"
                        "• يبدأ بـ @\n"
                        "• يحتوي على أحرف وأرقام و _ فقط\n"
                        "• بطول 5 أحرف على الأقل\n\n"
                        "أرسل اسم القناة مرة أخرى:"
                    )
                    return
                
                # حفظ الإعداد الجديد
                old_username = self.db.get_setting("channel_username", REQUIRED_CHANNEL)
                self.db.set_setting("channel_username", new_username)
                
                # تحديث الرسالة
                success_message = (
                    "✅ <b>تم تحديث اسم القناة بنجاح!</b>\n\n"
                    f"📢 الاسم السابق: <code>{old_username}</code>\n"
                    f"📢 الاسم الجديد: <code>{new_username}</code>\n\n"
                    "سيتم استخدام الاسم الجديد من الآن فصاعداً."
                )
                
                keyboard = [[InlineKeyboardButton("🔙 العودة للوحة التحكم", callback_data="admin_refresh")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # محاولة تحديث الرسالة الأصلية
                try:
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=admin_message_id,
                        text=success_message,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
                except:
                    await update.message.reply_text(
                        success_message,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
                
                logger.info(f"المسؤول {update.effective_user.id} قام بتحديث اسم القناة إلى: {new_username}")
            
            elif waiting_for == 'channel_id':
                # تنظيف معرف القناة
                new_channel_id = input_text.strip()
                
                # التحقق من صحة معرف القناة
                if not new_channel_id.startswith('-100') or not new_channel_id[1:].isdigit():
                    await update.message.reply_text(
                        "❌ معرف القناة غير صالح!\n\n"
                        "يجب أن يكون معرف القناة:\n"
                        "• يبدأ بـ -100\n"
                        "• يحتوي على أرقام فقط بعد -100\n"
                        "• مثال: -1002353060403\n\n"
                        "أرسل معرف القناة مرة أخرى:"
                    )
                    return
                
                # حفظ الإعداد الجديد
                old_channel_id = self.db.get_setting("channel_id", REQUIRED_CHANNEL_ID)
                self.db.set_setting("channel_id", new_channel_id)
                
                # تحديث الرسالة
                success_message = (
                    "✅ <b>تم تحديث معرف القناة بنجاح!</b>\n\n"
                    f"🆔 المعرف السابق: <code>{old_channel_id}</code>\n"
                    f"🆔 المعرف الجديد: <code>{new_channel_id}</code>\n\n"
                    "سيتم استخدام المعرف الجديد من الآن فصاعداً."
                )
                
                keyboard = [[InlineKeyboardButton("🔙 العودة للوحة التحكم", callback_data="admin_refresh")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # محاولة تحديث الرسالة الأصلية
                try:
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=admin_message_id,
                        text=success_message,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
                except:
                    await update.message.reply_text(
                        success_message,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.HTML
                    )
                
                logger.info(f"المسؤول {update.effective_user.id} قام بتحديث معرف القناة إلى: {new_channel_id}")
            
            # مسح حالة الانتظار
            context.user_data.pop('waiting_for', None)
            context.user_data.pop('admin_message_id', None)
            
        except Exception as e:
            logger.error(f"خطأ في معالجة إدخال المسؤول: {str(e)}")
            await update.message.reply_text(
                "❌ حدث خطأ أثناء معالجة الطلب!\n"
                "يرجى المحاولة مرة أخرى."
            )
            
            # مسح حالة الانتظار في حالة الخطأ
            context.user_data.pop('waiting_for', None)
            context.user_data.pop('admin_message_id', None)

    def run(self) -> None:
        """تشغيل البوت"""
        logger.info("بدء تشغيل البوت...")
        
        self.downloader.cleanup_old_files(max_age_hours=1)
        
        self.app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )


def main() -> None:
    """نقطة البداية الرئيسية للبرنامج"""
    token = os.getenv("BOT_TOKEN")
    admin_id_str = os.getenv("TELEGRAM_ADMIN_ID")
    
    if not token:
        logger.error("❌ لم يتم العثور على BOT_TOKEN في المتغيرات البيئية!")
        logger.error("يرجى إضافة توكن البوت من BotFather إلى المتغيرات البيئية")
        return
    
    admin_id = None
    if admin_id_str:
        try:
            admin_id = int(admin_id_str)
            logger.info(f"تم تحميل معرف المسؤول: {admin_id}")
        except ValueError:
            logger.warning("معرف المسؤول غير صالح، سيتم تجاهله")
    else:
        logger.warning("لم يتم تعيين معرف المسؤول TELEGRAM_ADMIN_ID")
    
    bot = PinterestBot(token, admin_id)
    bot.run()


if __name__ == "__main__":
    main()
