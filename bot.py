
import sys
import asyncio
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    filters
)
from modules.config import BOT_TOKEN, logger, ADMIN_ID
from modules.player import start_web_server
from modules.handlers_main import start, login_cmd, router_callback, router_text
from modules.handlers_file import upload_tg_file
from modules.handlers_task import add_download_task
from modules.accounts import account_mgr

# Job: Quota Monitor
async def check_quota_job(context):
    if not ADMIN_ID: return
    client = await account_mgr.get_client(ADMIN_ID)
    if not client: return
    try:
        info = await client.get_quota_info()
        usage = int(info.get('usage', 0))
        limit = int(info.get('quota', 1))
        if (usage / limit) > 0.95:
            await context.bot.send_message(ADMIN_ID, f"⚠️ **空间告警**: 使用量已超过 95%!")
    except: pass

if __name__ == '__main__':
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found in .env")
        sys.exit(1)

    # 1. Build App
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # 2. Register Handlers
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('login', login_cmd))
    app.add_handler(CallbackQueryHandler(router_callback))
    
    # Text & File Handlers
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), router_text))
    app.add_handler(MessageHandler(filters.Document.MimeType("text/plain"), 
                                   lambda u,c: add_download_task(u,c, u.message.document.get_file().download_as_bytearray().decode())))
    app.add_handler(MessageHandler(filters.ATTACHMENT & (~filters.Document.MimeType("text/plain")), upload_tg_file))

    # 3. Register Background Jobs
    if app.job_queue:
        app.job_queue.run_repeating(check_quota_job, interval=3600, first=20) # Check every hour

    # 4. Start Web Server
    loop = asyncio.get_event_loop()
    loop.create_task(start_web_server())

    # 5. Run
    logger.info("🤖 PikPak Ultimate Bot Started")
    app.run_polling()
