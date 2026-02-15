
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from .config import check_auth, WEB_PORT, global_cache, ALIST_HOST
from .utils import get_base_url, is_rate_limited
from .handlers_file import show_alist_files, show_alist_file_action, handle_alist_action
from .handlers_task import show_stream_menu, stop_stream, set_rtmp_url

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    
    base_url = get_base_url(WEB_PORT)
    text = (
        "🤖 **AList Termux Bot**\n"
        f"🌐 Web 管理: `{base_url}`\n"
        f"📂 AList 后端: `{ALIST_HOST}`\n\n"
        "👇 请选择功能:"
    )
    
    kb = [
        ["📂 云盘文件", "📺 推流管理"],
        ["⚙️ 系统状态", "🛠 刷新缓存"]
    ]
    await context.bot.send_message(
        update.effective_chat.id, 
        text, 
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
        parse_mode='Markdown'
    )

async def router_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    msg = update.message.text.strip()
    
    # Capture RTMP setting
    if context.user_data.get('setting_rtmp'):
        context.user_data['rtmp_url'] = msg
        del context.user_data['setting_rtmp']
        await context.bot.send_message(update.effective_chat.id, f"✅ RTMP 地址已保存")
        await show_stream_menu(update, context)
        return

    if msg == "📂 云盘文件":
        await show_alist_files(update, context)
    elif msg == "📺 推流管理":
        await show_stream_menu(update, context)
    elif msg == "⚙️ 系统状态":
        base_url = get_base_url(WEB_PORT)
        await context.bot.send_message(update.effective_chat.id, f"💻 **System Info**\nTunnel: {base_url}\nAList: {ALIST_HOST}")
    elif msg == "🛠 刷新缓存":
        global_cache.clear()
        await context.bot.send_message(update.effective_chat.id, "✅ 缓存已清空")

async def router_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data.startswith("ls:"):
        path = data[3:]
        await show_alist_files(update, context, path=path, edit_msg=True)
    elif data.startswith("ls_force:"):
        path = data.split(':', 1)[1]
        global_cache.clear()
        await show_alist_files(update, context, path=path, edit_msg=True)
    elif data.startswith("file:"):
        path = data[5:]
        await show_alist_file_action(update, context, path)
    elif data.startswith("do_stream:"):
        path = data.split(':', 1)[1]
        await handle_alist_action(update, context, "do_stream", path)
    elif data == "copy_link":
        await handle_alist_action(update, context, "copy_link", None)
    
    # Stream Controls
    elif data == "stream_refresh":
        await show_stream_menu(update, context)
    elif data == "stream_stop":
        await stop_stream(update, context)
    elif data == "stream_set_url":
        await set_rtmp_url(update, context)
    
    await query.answer()

async def reset_state(update, context):
    context.user_data.clear()
    await context.bot.send_message(update.effective_chat.id, "已重置")
    await start(update, context)
    
async def login_cmd(update, context):
    await context.bot.send_message(update.effective_chat.id, "无需登录，使用配置文件中的 AList 信息。")
