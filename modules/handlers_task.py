
import subprocess
import asyncio
import logging
import os
import json
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes
from .config import logger
from .accounts import alist_mgr

# Global Stream State
stream_sessions = {}
KEYS_FILE = "stream_keys.json"
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
        # Combine Base URL + Key
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
            # Sign logic
            if resp['data'].get('sign'):
                raw_url += f"?sign={resp['data']['sign']}"
            
            # Simple encoding for spaces in URL if necessary, but requests usually handles it.
            # However, ffmpeg concat list needs spaces handled or quoted.
            resolved_files.append(raw_url)
    
    if not resolved_files:
        await context.bot.send_message(update.effective_chat.id, "❌ 无法获取文件链接")
        return

    # 4. Generate Playlist File (concat.txt)
    # Format: file 'url'
    playlist_content = ""
    for url in resolved_files:
        # Escape single quotes in URL for ffmpeg protocol
        safe_url = url.replace("'", "'\\''") 
        playlist_content += f"file '{safe_url}'\n"
    
    playlist_path = f"playlist_{user_id}.txt"
    with open(playlist_path, "w", encoding='utf-8') as f:
        f.write(playlist_content)

    # 5. Stop Previous Stream
    await stop_stream(update, context, silent=True)

    # 6. Build FFmpeg Command
    # -safe 0: Allow unsafe file paths/URLs in concat list
    # -protocol_whitelist: Allow remote http/https urls in list
    cmd = [
        "ffmpeg",
        "-re", # Realtime reading
        "-f", "concat",
        "-safe", "0",
        "-protocol_whitelist", "file,http,https,tcp,tls",
        "-i", playlist_path,
        "-c", "copy", # Copy codec (Fastest)
        "-f", "flv",
        rtmp_url
    ]

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        stream_sessions[user_id] = {
            'process': process,
            'playlist_file': playlist_path,
            'count': len(resolved_files)
        }
        
        await context.bot.send_message(
            update.effective_chat.id,
            f"🚀 **推流已启动!**\n\n"
            f"📄 文件数: {len(resolved_files)}\n"
            f"🔑 目标: {context.user_data.get('selected_key_name')}\n"
            f"💡 模式: 列表顺序播放\n\n"
            f"点击 [⏹ 停止推流] 可结束。",
            parse_mode='Markdown'
        )
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
        
        # Cleanup playlist file
        if os.path.exists(session['playlist_file']):
            os.remove(session['playlist_file'])
            
        del stream_sessions[user_id]
        if not silent:
            await context.bot.send_message(update.effective_chat.id, "✅ 推流已停止")
    else:
        if not silent:
            await context.bot.send_message(update.effective_chat.id, "⚪️ 当前没有推流任务")

async def show_stream_status(update, context):
    user_id = update.effective_user.id
    is_streaming = user_id in stream_sessions and stream_sessions[user_id]['process'].poll() is None
    
    status = "🟢 正在直播" if is_streaming else "⚪️ 空闲"
    count = stream_sessions[user_id]['count'] if is_streaming else 0
    
    text = f"📺 **推流状态**: {status}\n正在播放: {count} 个文件"
    kb = [[InlineKeyboardButton("刷新", callback_data="stream_refresh")]]
    if is_streaming:
        kb.append([InlineKeyboardButton("⏹ 停止", callback_data="stream_stop")])
        
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
