
import subprocess
import asyncio
import logging
import os
import json
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes
from .config import logger, HTTP_PROXY, HTTPS_PROXY
from .accounts import alist_mgr

# Global Stream State
stream_sessions = {}
KEYS_FILE = "stream_keys.json"
STREAM_LOG_FILE = "stream.log"
TG_RTMP_BASE = "rtmps://dc5-1.rtmp.t.me/s/"

# --- Key Management ---
def load_keys():
    if not os.path.exists(KEYS_FILE): return {}
    try:
        with open(KEYS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def save_key(name, url):
    keys = load_keys()
    keys[name] = url
    with open(KEYS_FILE, 'w', encoding='utf-8') as f: json.dump(keys, f, ensure_ascii=False)

def delete_key_by_name(name):
    keys = load_keys()
    if name in keys:
        del keys[name]
        with open(KEYS_FILE, 'w', encoding='utf-8') as f: json.dump(keys, f, ensure_ascii=False)

# --- Key Manager UI ---
async def show_key_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keys = load_keys()
    current_key_name = context.user_data.get('selected_key_name')
    
    text = f"🔑 **推流密钥管理**\n当前选中: **{current_key_name or '未选择'}**\n请点击选择要使用的密钥:"
    
    kb = []
    for name, url in keys.items():
        icon = "✅" if current_key_name == name else "▪️"
        kb.append([InlineKeyboardButton(f"{icon} {name}", callback_data=f"stream_key_sel:{name}")])
    
    kb.append([InlineKeyboardButton("➕ 添加新密钥", callback_data="stream_key_add")])
    if keys:
        kb.append([InlineKeyboardButton("🗑 删除密钥", callback_data="stream_key_del_menu")])
        
    reply_markup = InlineKeyboardMarkup(kb)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_key_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keys = load_keys()
    text = "🗑 **点击删除密钥:**"
    kb = []
    for name in keys:
        kb.append([InlineKeyboardButton(f"❌ {name}", callback_data=f"stream_key_del:{name}")])
    kb.append([InlineKeyboardButton("🔙 返回", callback_data="stream_manage_keys")])
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def handle_stream_key_action(update, context):
    query = update.callback_query
    data = query.data
    
    if data == "stream_manage_keys":
        await show_key_manager(update, context)
    elif data == "stream_key_add":
        context.user_data['input_mode'] = 'stream_key_name'
        await query.message.reply_text("📝 请输入密钥名称 (例如: 我的频道):", reply_markup=ForceReply(selective=True))
    elif data == "stream_key_del_menu":
        await show_key_delete_menu(update, context)
    elif data.startswith("stream_key_sel:"):
        name = data.split(":", 1)[1]
        keys = load_keys()
        if name in keys:
            context.user_data['selected_key_name'] = name
            context.user_data['selected_key_url'] = keys[name]
            await query.answer(f"✅ 已选中: {name}")
            await show_key_manager(update, context)
    elif data.startswith("stream_key_del:"):
        name = data.split(":", 1)[1]
        delete_key_by_name(name)
        if context.user_data.get('selected_key_name') == name:
            context.user_data.pop('selected_key_name', None)
            context.user_data.pop('selected_key_url', None)
        await show_key_manager(update, context)

async def process_stream_input(update, context):
    mode = context.user_data.get('input_mode')
    text = update.message.text.strip()
    
    if mode == 'stream_key_name':
        context.user_data['temp_key_name'] = text
        context.user_data['input_mode'] = 'stream_key_value'
        await update.message.reply_text(
            f"🔗 名称: **{text}**\n\n请粘贴 **Telegram 直播密钥**:\n(只需输入密钥部分，无需 rtmp 前缀)\n例如: `123456:AbCdEfG...`", 
            parse_mode='Markdown', 
            reply_markup=ForceReply(selective=True)
        )
    elif mode == 'stream_key_value':
        name = context.user_data.get('temp_key_name')
        full_url = f"{TG_RTMP_BASE}{text}"
        save_key(name, full_url)
        context.user_data['selected_key_name'] = name
        context.user_data['selected_key_url'] = full_url
        
        del context.user_data['input_mode']
        del context.user_data['temp_key_name']
        await update.message.reply_text(f"✅ 密钥已保存并选中！\n地址: `{TG_RTMP_BASE}...`", parse_mode='Markdown')
        await show_key_manager(update, context)

# --- Streaming Logic ---

async def start_playlist_stream(update, context):
    query = update.callback_query
    user_id = update.effective_user.id
    
    # 1. Check Key
    rtmp_url = context.user_data.get('selected_key_url')
    if not rtmp_url:
        await query.answer("❌ 未选择推流密钥，请先去[密钥管理]设置", show_alert=True)
        return

    # 2. Check Playlist
    playlist = context.user_data.get('playlist', [])
    if not playlist:
        await query.answer("❌ 播放列表为空", show_alert=True)
        return

    # 3. Resolve Direct URLs
    await query.edit_message_text(f"⏳ 正在解析 {len(playlist)} 个文件的下载地址...")
    
    resolved_files = []
    for item in playlist:
        resp = alist_mgr.get_file_info(item['path'])
        if resp and resp.get('code') == 200:
            raw_url = resp['data']['raw_url']
            # Fix URL appending logic: Check if ? exists
            if resp['data'].get('sign'):
                separator = "&" if "?" in raw_url else "?"
                raw_url += f"{separator}sign={resp['data']['sign']}"
            resolved_files.append(raw_url)
    
    if not resolved_files:
        await context.bot.send_message(update.effective_chat.id, "❌ 无法获取文件链接")
        return

    # 4. Generate Playlist File (concat.txt)
    playlist_content = ""
    for url in resolved_files:
        safe_url = url.replace("'", "'\\''") 
        playlist_content += f"file '{safe_url}'\n"
    
    playlist_path = f"playlist_{user_id}.txt"
    with open(playlist_path, "w", encoding='utf-8') as f:
        f.write(playlist_content)

    # 5. Stop Previous Stream
    await stop_stream(update, context, silent=True)

    # 6. Build FFmpeg Command
    # Removed -reconnect options to fix 'Option not found' crash. 
    # The proxy environment variables are still injected below to help with speed.
    cmd = [
        "ffmpeg",
        "-re", 
        "-f", "concat",
        "-safe", "0",
        "-protocol_whitelist", "file,http,https,tcp,tls",
        "-i", playlist_path,
        "-c", "copy",
        "-f", "flv",
        "-loglevel", "info", 
        rtmp_url
    ]

    # Prepare Environment with Proxy
    env = os.environ.copy()
    if HTTP_PROXY: env["http_proxy"] = HTTP_PROXY
    if HTTPS_PROXY: env["https_proxy"] = HTTPS_PROXY

    try:
        # Open log file
        log_file = open(STREAM_LOG_FILE, "w")
        
        # Start process with stderr redirected to log file
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.DEVNULL, 
            stderr=log_file,
            env=env  # Inject proxy env
        )
        
        stream_sessions[user_id] = {
            'process': process,
            'playlist_file': playlist_path,
            'log_handle': log_file,
            'count': len(resolved_files)
        }
        
        await context.bot.send_message(
            update.effective_chat.id,
            f"🚀 **推流已启动!**\n\n"
            f"📄 文件数: {len(resolved_files)}\n"
            f"🔑 目标: {context.user_data.get('selected_key_name')}\n"
            f"📝 日志: 已记录到 `{STREAM_LOG_FILE}`\n"
            f"🌐 代理: {'✅ 启用' if HTTPS_PROXY else '❌ 未配置'}\n\n"
            f"若画面黑屏，请点击【查看日志】下载完整日志进行排查。",
            parse_mode='Markdown'
        )
        # Immediately show status panel
        await show_stream_status(update, context, new_msg=True)
        
    except Exception as e:
        await context.bot.send_message(update.effective_chat.id, f"❌ 启动失败: {e}")

async def stop_stream(update, context, silent=False):
    user_id = update.effective_user.id
    if user_id in stream_sessions:
        session = stream_sessions[user_id]
        proc = session['process']
        proc.terminate()
        try: proc.wait(timeout=5)
        except: proc.kill()
        
        # Cleanup
        if os.path.exists(session['playlist_file']):
            os.remove(session['playlist_file'])
        
        # Close log file handle
        try: session['log_handle'].close()
        except: pass
            
        del stream_sessions[user_id]
        if not silent:
            await context.bot.send_message(update.effective_chat.id, "✅ 推流已停止")
    else:
        if not silent:
            await context.bot.send_message(update.effective_chat.id, "⚪️ 当前没有推流任务")

async def show_stream_status(update, context, new_msg=False):
    user_id = update.effective_user.id
    is_streaming = user_id in stream_sessions and stream_sessions[user_id]['process'].poll() is None
    
    status = "🟢 正在直播" if is_streaming else "⚪️ 空闲 (或已退出)"
    count = stream_sessions.get(user_id, {}).get('count', 0)
    
    text = f"📺 **推流状态**: {status}\n正在播放: {count} 个文件"
    
    kb = []
    row1 = [InlineKeyboardButton("🔄 刷新状态", callback_data="stream_refresh")]
    if is_streaming:
        row1.append(InlineKeyboardButton("⏹ 停止", callback_data="stream_stop"))
    kb.append(row1)
    
    # Add Log View Button
    kb.append([InlineKeyboardButton("📝 查看/下载日志", callback_data="stream_log")])
        
    reply_markup = InlineKeyboardMarkup(kb)
    
    if new_msg:
         await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode='Markdown')
    elif update.callback_query:
        try: await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except: pass

async def view_stream_log(update, context):
    if not os.path.exists(STREAM_LOG_FILE):
        await update.callback_query.answer("❌ 暂无日志文件", show_alert=True)
        return
    
    chat_id = update.effective_chat.id
    
    # 1. Send Full Log File (This ensures "All" logs are seen)
    try:
        with open(STREAM_LOG_FILE, 'rb') as f:
             await context.bot.send_document(
                chat_id=chat_id,
                document=f,
                filename="stream_debug.log",
                caption="📄 **完整推流日志文件**",
                parse_mode='Markdown'
            )
    except Exception as e:
        await context.bot.send_message(chat_id, f"❌ 发送日志文件失败: {e}")

    # 2. Show Preview (Text)
    try:
        # Read last 3000 chars for preview
        with open(STREAM_LOG_FILE, "rb") as f:
            try: f.seek(-3000, os.SEEK_END) # Go to end approx
            except: f.seek(0) # File too small
            content = f.read().decode('utf-8', errors='ignore')
            
        if content:
            lines = [l for l in content.splitlines() if l.strip()]
            preview = "\n".join(lines[-30:]) # Show last 30 lines
            
            msg = f"📝 **日志预览 (最后部分):**\n```\n{preview}\n```"
            await context.bot.send_message(chat_id, msg, parse_mode='Markdown')
    except Exception as e:
        pass
        
    await update.callback_query.answer()
