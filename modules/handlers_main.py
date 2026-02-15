
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes
from .config import check_auth, WEB_PORT, global_cache, ALIST_HOST
from .utils import get_base_url, is_rate_limited
from .accounts import alist_mgr
from .handlers_file import (
    show_alist_files, 
    show_alist_file_action, 
    handle_alist_action, 
    show_dir_options, 
    handle_fs_action_request, 
    process_fs_input
)
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
        ["📂 文件浏览", "📺 直播推流"],
        ["☁️ 存储管理", "📥 离线下载"],
        ["⚙️ 系统状态", "🛠 刷新缓存"]
    ]
    await context.bot.send_message(
        update.effective_chat.id, 
        text, 
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
        parse_mode='Markdown'
    )

async def show_storage_list(update, context):
    resp = alist_mgr.admin_storage_list()
    if not resp or resp.get('code') != 200:
        await context.bot.send_message(update.effective_chat.id, "❌ 无法获取存储列表 (需要 Admin 权限)")
        return
    
    data = resp.get('data', {}).get('content', [])
    text = "☁️ **存储挂载列表**\n\n"
    
    for item in data:
        status = "🟢" if not item.get('disabled') else "🔴"
        driver = item.get('driver', 'Unknown')
        mount_path = item.get('mount_path')
        text += f"{status} `{mount_path}` ({driver})\n"
        
    await context.bot.send_message(update.effective_chat.id, text, parse_mode='Markdown')

async def start_offline_download(update, context):
    context.user_data['input_mode'] = 'offline_dl'
    # Default to root for main menu action
    context.user_data['target_path'] = "/" 
    await context.bot.send_message(
        update.effective_chat.id, 
        "📥 **离线下载 (保存到 / )**\n请回复下载链接 (HTTP/Magnet):",
        reply_markup=ForceReply(selective=True)
    )

async def router_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    msg = update.message.text.strip()
    
    # 1. Check for specific input modes (Rename, Mkdir, Offline DL)
    if 'input_mode' in context.user_data:
        await process_fs_input(update, context)
        return

    # 2. Check for RTMP setting
    if context.user_data.get('setting_rtmp'):
        context.user_data['rtmp_url'] = msg
        del context.user_data['setting_rtmp']
        await context.bot.send_message(update.effective_chat.id, f"✅ RTMP 地址已保存")
        await show_stream_menu(update, context)
        return

    # 3. Main Menu Routing
    if msg == "📂 文件浏览":
        await show_alist_files(update, context)
    elif msg == "📺 直播推流":
        await show_stream_menu(update, context)
    elif msg == "☁️ 存储管理":
        await show_storage_list(update, context)
    elif msg == "📥 离线下载":
        await start_offline_download(update, context)
    elif msg == "⚙️ 系统状态":
        base_url = get_base_url(WEB_PORT)
        await context.bot.send_message(update.effective_chat.id, f"💻 **System Info**\nTunnel: {base_url}\nAList: {ALIST_HOST}")
    elif msg == "🛠 刷新缓存":
        global_cache.clear()
        await context.bot.send_message(update.effective_chat.id, "✅ 缓存已清空")

async def router_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    # Navigation
    if data.startswith("ls:"):
        path = data[3:]
        await show_alist_files(update, context, path=path, edit_msg=True)
    elif data.startswith("ls_force:"):
        path = data.split(':', 1)[1]
        global_cache.clear()
        await show_alist_files(update, context, path=path, edit_msg=True)
    
    # File/Dir Options
    elif data.startswith("file:"):
        path = data[5:]
        await show_alist_file_action(update, context, path)
    elif data.startswith("opt_dir:"):
        path = data[8:]
        await show_dir_options(update, context, path)
        
    # FS Actions (Rename, Delete, Copy, Paste, Mkdir, OfflineDL)
    elif data.startswith("req_") or data.startswith("act_") or data == "confirm_delete" or data == "cancel_action":
        payload = None
        action = data
        if ":" in data:
            action, payload = data.split(":", 1)
            # actions with payload: act_mkdir, act_paste, act_offline_dl
            if action in ["act_mkdir", "act_paste", "act_offline_dl"]:
                 # Manually inject payload into user_data['target_path'] for the handler
                 context.user_data['target_path'] = payload
                 
        await handle_fs_action_request(update, context, action)

    # Legacy AList Actions
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
    
    try: await query.answer()
    except: pass

async def reset_state(update, context):
    context.user_data.clear()
    await context.bot.send_message(update.effective_chat.id, "已重置")
    await start(update, context)
    
async def login_cmd(update, context):
    await context.bot.send_message(update.effective_chat.id, "无需登录，使用配置文件中的 AList 信息。")
