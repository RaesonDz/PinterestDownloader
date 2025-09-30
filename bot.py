"""
بوت تلجرام احترافي لتحميل فيديوهات Pinterest
مع ميزة الاشتراك الإجباري في القناة
متوافق مع Fly.io و Railway
"""

import os
import logging
import asyncio
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

from database import Database
from downloader import PinterestDownloader

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

REQUIRED_CHANNEL = "@Garren_Store"
REQUIRED_CHANNEL_ID = "-1002353060403"


class PinterestBot:
    """Telegram bot for downloading Pinterest videos with forced channel subscription"""

    def __init__(self, token: str, admin_id: Optional[int] = None, use_webhook: bool = False):
        self.token = token
        self.admin_id = admin_id
        self.db = Database()
        self.downloader = PinterestDownloader()
        self.use_webhook = use_webhook

        self.app = Application.builder().token(token).build()

        self._setup_handlers()
        self._init_settings()
        logger.info("Bot initialized successfully")

    def _init_settings(self):
        if not self.db.get_setting("channel_username"):
            self.db.set_setting("channel_username", REQUIRED_CHANNEL)
        if not self.db.get_setting("channel_id"):
            self.db.set_setting("channel_id", REQUIRED_CHANNEL_ID)

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("admin", self.admin_command))
        self.app.add_handler(CommandHandler("setchannel", self.setchannel_command))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "👋 Welcome to the Pinterest Video Downloader Bot!\n\n"
            "📌 Send me a Pinterest video link and I’ll download it for you."
        )

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        total_users = self.db.get_total_users()
        total_videos = self.db.get_total_videos()
        await update.message.reply_text(
            f"📊 Bot Stats:\n\n👥 Users: {total_users}\n🎬 Videos Downloaded: {total_videos}"
        )

    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("⚙️ Admin Panel coming soon...")

    async def setchannel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🔧 Set channel feature not implemented yet.")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.answer("👌 Button clicked.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        url = update.message.text.strip()
        if not self.downloader.is_pinterest_url(url):
            await update.message.reply_text("❌ Invalid link! Please send a Pinterest video link.")
            return

        await update.message.reply_text("⬇️ Downloading video... (demo mode)")

    def run(self):
        if self.use_webhook:
            port = int(os.environ.get("PORT", "8080"))
            webhook_url = os.environ.get("WEBHOOK_URL")  # ضع رابط موقعك هنا
            logger.info(f"Starting bot in WEBHOOK mode on port {port}")

            self.app.run_webhook(
                listen="0.0.0.0",
                port=port,
                url_path=self.token,
                webhook_url=f"{webhook_url}/{self.token}",
            )
        else:
            logger.info("Starting bot in POLLING mode")
            self.app.run_polling(drop_pending_updates=True)


def main():
    token = os.getenv("BOT_TOKEN")
    admin_id_str = os.getenv("TELEGRAM_ADMIN_ID")

    if not token:
        logger.error("❌ BOT_TOKEN not found in environment variables!")
        return

    admin_id = None
    if admin_id_str:
        try:
            admin_id = int(admin_id_str)
        except ValueError:
            pass

    # اختيار الوضع بناءً على متغير البيئة
    use_webhook = os.getenv("USE_WEBHOOK", "false").lower() == "true"

    bot = PinterestBot(token, admin_id, use_webhook=use_webhook)
    bot.run()


if __name__ == "__main__":
    main()
