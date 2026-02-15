
import sys
import asyncio
import logging
import io
import traceback
import os
import nest_asyncio

# Apply nest_asyncio to solve event loop issues in Termux
nest_asyncio.apply()

from telegram import Update
from telegram.request import HTTPXRequest
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    ContextTypes,
    filters
)
from modules.config import BOT_TOKEN, ADMIN_ID, HTTPS_PROXY, check_auth, WEB_PORT, global_cache
from modules.player import start_web_server
from modules.handlers_main import start, login_cmd, router_callback, router_text, reset_state
from modules.handlers_file import upload_tg_file
from modules.handlers_task import add_download_task
from modules.accounts import account_mgr
from modules.utils import get_base_url

# Configure Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING # Less verbose for performance
)
logger = logging.getLogger("BotMain")
logger.setLevel(logging.INFO)

# Silence httpx logger to reduce noise and IO
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

# Global Error Handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    print(f"❌ [ERROR] {context.error}")
    
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text=f"🚫 **系统错误**\n请使用 /reset 重置。\n错误: `{context.error}`",
                parse_mode='Markdown'
            )
        except: pass

# Helper: Async File Wrapper
async def handle_document_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    doc = update.message.document
    try:
        msg = await context.bot.send_message(update.effective_chat.id, "📄 正在读取文件...")
        f = await doc.get_file()
        byte_stream = io.BytesIO()
        await f.download_to_memory(out=byte_stream)
        byte_stream.seek(0)
        content = byte_stream.read().decode('utf-8', errors='ignore')
        
        if doc.mime_type == "application/x-bittorrent" or doc.file_name.endswith(".torrent"):
             await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="⚠️ 暂不支持直接上传 .torrent 文件，请将磁力链接 (magnet) 粘贴发送。")
        else:
             await add_download_task(update, context, content)
             await context.bot.delete_message(update.effective_chat.id, msg.message_id)
    except Exception as e:
        await context.bot.send_message(update.effective_chat.id, f"❌ 文件解析失败: {e}")

# Job: Quota Monitor
async def check_quota_job(context):
    if not ADMIN_ID: return
    try:
        client = await account_mgr.get_client(ADMIN_ID)
        if client:
            info = await client.get_quota_info()
            usage = int(info.get('usage', 0))
            limit = int(info.get('quota', 1))
            if limit > 0 and (usage / limit) > 0.95:
                await context.bot.send_message(ADMIN_ID, f"⚠️ **空间告警**: 使用量已超过 95%!")
    except: pass

async def on_startup(context: ContextTypes.DEFAULT_TYPE):
    # 1. Start Web Server (inside the same loop)
    try:
        await start_web_server()
        logger.info("✅ Web Server started via on_startup")
    except Exception as e:
        logger.error(f"❌ Web Server failed to start: {e}")

    # 2. Notify Admin
    if ADMIN_ID:
        try:
            # Try to get public URL
            base_url = get_base_url(WEB_PORT)
            msg = (
                "🤖 **PikPak Bot 已启动**\n"
                "Termux 服务已就绪。\n\n"
                f"🌐 **Web 服务地址**:\n`{base_url}`"
            )
            await context.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode='Markdown')
        except Exception as e:
            print(f"Failed to send startup message: {e}")

if __name__ == '__main__':
    if not BOT_TOKEN:
        print("❌ Error: BOT_TOKEN is missing in .env")
        sys.exit(1)

    print("🚀 Starting Bot...")
    
    # 1. Network Configuration (Proxy Support)
    # Optimized for Mobile/Termux:
    # - Connect Timeout: 10s (fail fast if network dead)
    # - Read Timeout: 45s (allow slow data)
    # - Write Timeout: 45s (allow slow upload)
    # - Keepalive: 60s
    req = None
    if HTTPS_PROXY:
        print(f"🌐 Using Proxy: {HTTPS_PROXY}")
        req = HTTPXRequest(
            proxy_url=HTTPS_PROXY, 
            connection_pool_size=10, 
            connect_timeout=10.0, 
            read_timeout=45.0,
            write_timeout=45.0,
            http2=True 
        )
    else:
        print("🌐 No Proxy detected (Direct Connection)")
        req = HTTPXRequest(
            connection_pool_size=10, 
            connect_timeout=10.0, 
            read_timeout=45.0,
            write_timeout=45.0,
            http2=True
        )

    # 2. Build App
    try:
        app = ApplicationBuilder().token(BOT_TOKEN).request(req).post_init(on_startup).build()
    except Exception as e:
        print(f"❌ Failed to initialize Bot: {e}")
        sys.exit(1)
    
    # 3. Register Handlers
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('reset', reset_state))
    app.add_handler(CommandHandler('login', login_cmd))
    
    app.add_handler(CallbackQueryHandler(router_callback))
    
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), router_text))
    
    # Document Handler (for .txt lists)
    app.add_handler(MessageHandler(filters.Document.MimeType("text/plain") | filters.Document.FileExtension("txt"), handle_document_upload))
    
    # Generic File Handler (Upload to PikPak)
    app.add_handler(MessageHandler(filters.ATTACHMENT & (~filters.Document.MimeType("text/plain")), upload_tg_file))

    app.add_error_handler(error_handler)

    if app.job_queue:
        app.job_queue.run_repeating(check_quota_job, interval=3600, first=60)

    # 4. Run
    print("✅ Bot is running! Waiting for updates...")
    try:
        # Note: start_web_server is now called in on_startup to ensure correct Event Loop
        app.run_polling(
            drop_pending_updates=True, 
            allowed_updates=Update.ALL_TYPES,
            timeout=40 # Polling timeout
        )
    except Exception as e:
        print(f"❌ Polling Error: {e}")
