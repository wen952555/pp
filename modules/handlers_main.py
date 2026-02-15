
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from .config import check_auth, global_cache
from .handlers_file import (
    show_alist_files, 
    handle_file_selection
)
from .handlers_task import (
    show_stream_status,
    stop_stream, 
    handle_stream_key_action,
    process_stream_input,
    show_key_manager,
    start_playlist_stream,
    view_stream_log
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    
    # Reset browsing state on start
    context.user_data.pop('playlist', None)
    context.user_data.pop('browse_mode', None)

    text = (
        "🤖 **AList 直播推流助手**\n\n"
        "请选择模式："
    )
    
    kb = [
        ["🎬 视频直播", "🎵 音频直播"],
        ["🔑 密钥管理", "⏹ 停止推流"]
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
    
    # 1. Input Modes (Key Name/URL)
    if 'input_mode' in context.user_data:
        await process_stream_input(update, context)
        return

    # 2. Main Menu Routing
    if msg == "🎬 视频直播":
        context.user_data['browse_mode'] = 'video'
        context.user_data['playlist'] = [] # Initialize empty playlist
        await show_alist_files(update, context, path="/")
        
    elif msg == "🎵 音频直播":
        context.user_data['browse_mode'] = 'audio'
        context.user_data['playlist'] = [] # Initialize empty playlist
        await show_alist_files(update, context, path="/")
        
    elif msg == "🔑 密钥管理":
        await show_key_manager(update, context)
        
    elif msg == "⏹ 停止推流":
        await stop_stream(update, context)

async def router_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    # File Browser Navigation
    if data.startswith("ls:"):
        path = data[3:]
        await show_alist_files(update, context, path=path, edit_msg=True)
        
    # File Selection (Multi-select)
    elif data.startswith("sel:"):
        await handle_file_selection(update, context, data)

    # Start Stream Action
    elif data == "action_start_stream":
        await start_playlist_stream(update, context)
        
    # Clear Playlist
    elif data == "action_clear_playlist":
        context.user_data['playlist'] = []
        path = context.user_data.get('current_path', '/')
        await show_alist_files(update, context, path=path, edit_msg=True)

    # Key Management & Stream Controls
    elif data.startswith("stream_"):
        if data == "stream_stop":
            await stop_stream(update, context)
        elif data == "stream_refresh":
            await show_stream_status(update, context)
        elif data == "stream_log":
            await view_stream_log(update, context)
        else:
            await handle_stream_key_action(update, context)
    
    try: await query.answer()
    except: pass

async def reset_state(update, context):
    context.user_data.clear()
    await context.bot.send_message(update.effective_chat.id, "✅ 状态已重置")
    await start(update, context)
    
async def login_cmd(update, context):
    await context.bot.send_message(update.effective_chat.id, "无需登录。")
