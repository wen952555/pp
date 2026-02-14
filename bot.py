
import sys
import asyncio
import logging
import io
import traceback
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    ContextTypes,
    filters
)
from modules.config import BOT_TOKEN, ADMIN_ID
from modules.player import start_web_server
from modules.handlers_main import start, login_cmd, router_callback, router_text, reset_state
from modules.handlers_file import upload_tg_file
from modules.handlers_task import add_download_task
from modules.accounts import account_mgr

# Configure Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("BotMain")

# Global Error Handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    
    # Print short error to console
    print(f"❌ BOT ERROR: {context.error}")

    # Notify user if possible
    if isinstance(update, Update) and update.effective_chat:
        try:
            message = (
                f"🚫 **系统错误**\n"
                f"Bot 遇到了一些问题，请尝试输入 `/reset` 重置状态。\n\n"
                f"错误信息: `{str(context.error)[:100]}`"
            )
            await context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode='Markdown')
        except:
            pass

# Helper: Async File Wrapper for Torrent/Text
async def handle_document_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    try:
        f = await doc.get_file()
        byte_stream = io.BytesIO()
        await f.download_to_memory(out=byte_stream)
        byte_stream.seek(0)
        content = byte_stream.read().decode('utf-8', errors='ignore')
        
        if doc.mime_type == "application/x-bittorrent" or doc.file_name.endswith(".torrent"):
             # TODO: Torrent binary handling needs PikPak specific API support for raw bytes or upload
             # Currently we treat it as text/magnet list as fallback or notify user
             await context.bot.send_message(update.effective_chat.id, "⚠️ 暂不支持直接上传 .torrent 文件，请将磁力链接 (magnet) 粘贴发送。")
        else:
             # Assume text file with links
             await add_download_task(update, context, content)
    except Exception as e:
        await context.bot.send_message(update.effective_chat.id, f"❌ 文件解析失败: {e}")

# Job: Quota Monitor
async def check_quota_job(context):
    if not ADMIN_ID: return
    client = await account_mgr.get_client(ADMIN_ID)
    if not client: return
    try:
        info = await client.get_quota_info()
        usage = int(info.get('usage', 0))
        limit = int(info.get('quota', 1))
        if limit > 0 and (usage / limit) > 0.95:
            await context.bot.send_message(ADMIN_ID, f"⚠️ **空间告警**: 使用量已超过 95%!")
    except: pass

if __name__ == '__main__':
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found in .env")
        print("❌ Error: BOT_TOKEN is missing. Please run setup.sh again.")
        sys.exit(1)

    print("🚀 Starting Bot...")

    # 1. Build App (Connection settings for stability)
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # 2. Register Handlers
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('reset', reset_state)) # New Reset Command
    app.add_handler(CommandHandler('login', login_cmd))
    app.add_handler(CallbackQueryHandler(router_callback))
    
    # Text & File Handlers
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), router_text))
    
    # Specific Document Handlers (Fixed logic)
    app.add_handler(MessageHandler(
        filters.Document.MimeType("text/plain") | filters.Document.FileExtension("txt"), 
        handle_document_upload
    ))
    
    # Catch-all other files
    app.add_handler(MessageHandler(filters.ATTACHMENT & (~filters.Document.MimeType("text/plain")), upload_tg_file))

    # Error Handler
    app.add_error_handler(error_handler)

    # 3. Register Background Jobs
    if app.job_queue:
        app.job_queue.run_repeating(check_quota_job, interval=3600, first=60)

    # 4. Start Web Server
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(start_web_server())
    except Exception as e:
        logger.warning(f"Web server start warning: {e}")

    # 5. Run
    logger.info("🤖 PikPak Ultimate Bot Started")
    print("✅ Bot is running! Go to Telegram and verify.")
    
    # Drop pending updates to avoid flooding on startup
    app.run_polling(drop_pending_updates=True)
