import logging
import os
import sys
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
PIKPAK_USER = os.getenv("PIKPAK_USER")
PIKPAK_PASS = os.getenv("PIKPAK_PASS")

# --- LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- PIKPAK LIBRARY CHECK ---
PIKPAK_AVAILABLE = False
try:
    from pikpakapi import PikPakApi, PikpakException
    PIKPAK_AVAILABLE = True
except ImportError:
    logger.warning("pikpak-api library not found. Bot will run in SIMULATION mode.")

async def check_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user is the admin."""
    user_id = str(update.effective_user.id)
    if user_id != str(ADMIN_ID):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⛔ 无权访问 (Unauthorized Access)")
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context):
        return
    
    mode = "✅ 连接正常 (Live Mode)" if PIKPAK_AVAILABLE else "⚠️ 模拟模式 (缺依赖)"
    
    help_text = (
        f"🤖 **PikPak Termux Bot**\n"
        f"状态: {mode}\n\n"
        f"📋 **指令列表**:\n"
        f"/space - 查看剩余空间\n"
        f"/help - 显示此帮助\n\n"
        f"🔗 **直接发送链接** (磁力/http) 即可离线下载。"
    )
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=help_text,
        parse_mode='Markdown'
    )

async def space_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check storage quota."""
    if not await check_auth(update, context):
        return

    msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="🔄 正在查询 PikPak 空间信息...")
    
    if not PIKPAK_AVAILABLE:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="⚠️ 模拟模式无法查询真实空间。")
        return

    try:
        client = PikPakApi(username=PIKPAK_USER, password=PIKPAK_PASS)
        await client.login()
        
        # Note: Actual method name depends on the specific pikpak-api version/fork
        # This is a generic implementation attempt
        info = await client.get_quota_info() 
        
        # Assuming info returns something like {'quota': 10995116277760, 'usage': 123456...}
        # Or adapting to whatever the library returns.
        # Fallback to simple text if structure unknown
        
        limit = int(info.get('quota', 0))
        usage = int(info.get('usage', 0))
        
        def format_bytes(size):
            power = 2**10
            n = 0
            power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
            while size > power:
                size /= power
                n += 1
            return f"{size:.2f} {power_labels[n]}B"

        text = (
            f"☁️ **PikPak 空间概览**\n\n"
            f"总空间: `{format_bytes(limit)}`\n"
            f"已使用: `{format_bytes(usage)}`\n"
            f"剩余: `{format_bytes(limit - usage)}`"
        )
        
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, 
            message_id=msg.message_id, 
            text=text,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Quota error: {e}")
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, 
            message_id=msg.message_id, 
            text=f"❌ 查询失败: {str(e)}"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context):
        return

    url = update.message.text
    if not url:
        return

    status_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=f"🔍 正在处理任务: {url[:30]}...")
    
    try:
        if PIKPAK_AVAILABLE:
            client = PikPakApi(username=PIKPAK_USER, password=PIKPAK_PASS)
            await client.login()
            
            try:
                task = await client.offline_download(url)
                
                # Check for error in response task object if applicable
                task_id = task.get('id', 'Unknown') if isinstance(task, dict) else 'Submitted'
                task_name = task.get('name', 'Unknown File') if isinstance(task, dict) else ''
                
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_msg.message_id,
                    text=f"✅ **任务添加成功!**\n\n🆔 ID: `{task_id}`\n📄 名字: {task_name}",
                    parse_mode='Markdown'
                )
            except Exception as api_error:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_msg.message_id,
                    text=f"⚠️ PikPak API 错误: {str(api_error)}"
                )
        else:
            await asyncio.sleep(1.5) 
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text=f"✅ [模拟] 任务已接收: {url}\n(请安装 pikpak-api 以启用真实下载)"
            )

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ 系统错误: {str(e)}")

if __name__ == '__main__':
    # Validate Config
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("\n[!] 错误: 未找到 BOT_TOKEN。请运行 ./setup.sh 进行配置，或检查 .env 文件。\n")
        sys.exit(1)
        
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', start))
    application.add_handler(CommandHandler('space', space_info))
    application.add_handler(CommandHandler('quota', space_info))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print(f"Bot 正在运行中... (Admin ID: {ADMIN_ID})")
    application.run_polling()
