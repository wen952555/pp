
import sys
import asyncio
import logging
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
from modules.config import BOT_TOKEN, ADMIN_ID, HTTPS_PROXY, check_auth
from modules.handlers_main import start, router_callback, router_text, reset_state, login_cmd

# Configure Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("BotMain")

# Global Error Handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    print(f"❌ [ERROR] {context.error}")

async def on_startup(context: ContextTypes.DEFAULT_TYPE):
    # Notify Admin
    if ADMIN_ID:
        try:
            msg = f"🤖 **AList Bot 已启动 (Live Mode)**\n服务已就绪。"
            await context.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode='Markdown')
        except: pass

if __name__ == '__main__':
    if not BOT_TOKEN:
        print("❌ Error: BOT_TOKEN is missing in .env")
        sys.exit(1)

    print("🚀 Starting Bot (Streamer Mode)...")
    
    # Network Config
    req = None
    if HTTPS_PROXY:
        print(f"🌐 Using Proxy: {HTTPS_PROXY}")
        req = HTTPXRequest(
            proxy_url=HTTPS_PROXY, 
            connection_pool_size=10, 
            connect_timeout=10.0, 
            read_timeout=45.0,
            write_timeout=45.0
        )
    else:
        req = HTTPXRequest(
            connection_pool_size=10, 
            connect_timeout=10.0, 
            read_timeout=45.0,
            write_timeout=45.0
        )

    # Build App
    try:
        app = ApplicationBuilder().token(BOT_TOKEN).request(req).post_init(on_startup).build()
    except Exception as e:
        print(f"❌ Failed to initialize Bot: {e}")
        sys.exit(1)
    
    # Handlers
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('reset', reset_state))
    app.add_handler(CommandHandler('login', login_cmd))
    
    app.add_handler(CallbackQueryHandler(router_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), router_text))
    
    app.add_error_handler(error_handler)

    print("✅ Bot is running! Waiting for updates...")
    try:
        app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES, timeout=40)
    except Exception as e:
        print(f"❌ Polling Error: {e}")
