
import subprocess
import asyncio
import logging
import signal
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes
from .config import logger
from .utils import is_rate_limited

# Global Stream State
# { user_id: { 'process': subprocess, 'file_name': str, 'rtmp': str } }
stream_sessions = {}

async def show_stream_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rtmp_url = context.user_data.get('rtmp_url', '未设置')
    
    session = stream_sessions.get(user_id)
    is_streaming = session is not None and session['process'].poll() is None
    
    status_text = "🟢 推流中" if is_streaming else "⚪️ 空闲"
    file_info = f"\n📄 文件: `{session['file_name']}`" if is_streaming else ""
    
    text = (
        "📺 **直播推流控制台**\n\n"
        f"状态: {status_text}{file_info}\n\n"
        f"🔗 **RTMP 地址**: \n`{rtmp_url}`\n"
        "(请从 Telegram -> 开始直播 -> 获取服务器URL和密钥，拼接在一起)"
    )
    
    kb = []
    if is_streaming:
        kb.append([InlineKeyboardButton("⏹ 停止推流", callback_data="stream_stop")])
    else:
        kb.append([InlineKeyboardButton("✏️ 设置 RTMP 地址", callback_data="stream_set_url")])
    
    kb.append([InlineKeyboardButton("🔄 刷新状态", callback_data="stream_refresh")])
    
    reply_markup = InlineKeyboardMarkup(kb)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode='Markdown')

async def set_rtmp_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['setting_rtmp'] = True
    await context.bot.send_message(
        update.effective_chat.id, 
        "📡 请回复 RTMP 地址 (URL+Key):\n例如: `rtmps://dc4-1.rtmp.t.me/s/1234:AbCdEf`", 
        reply_markup=ForceReply(selective=True)
    )

async def start_stream_process(update, context, file_url, file_name):
    user_id = update.effective_user.id
    rtmp = context.user_data.get('rtmp_url')
    
    if not rtmp:
        await context.bot.send_message(update.effective_chat.id, "⚠️ 请先在 [📺 推流管理] 中设置 RTMP 地址")
        return

    # Stop existing
    if user_id in stream_sessions:
        proc = stream_sessions[user_id]['process']
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=5)
            except: proc.kill()
    
    msg = await context.bot.send_message(update.effective_chat.id, f"🚀 正在启动推流...\n📄 {file_name}")
    
    # FFmpeg Command
    # -re (Read at native frame rate)
    # -i (Input URL)
    # -c copy (Direct stream copy - minimal CPU)
    # -f flv (Format for RTMP)
    cmd = [
        "ffmpeg", 
        "-re", 
        "-i", file_url,
        "-c", "copy",
        "-f", "flv",
        rtmp
    ]
    
    try:
        # Start process
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
        
        stream_sessions[user_id] = {
            'process': process,
            'file_name': file_name,
            'rtmp': rtmp
        }
        
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=msg.message_id,
            text=f"✅ **推流已开始!**\n📄 `{file_name}`\n\n请在直播软件/Telegram中确认画面。",
            parse_mode='Markdown'
        )
    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=msg.message_id,
            text=f"❌ 启动失败: {e}"
        )

async def stop_stream(update, context):
    user_id = update.effective_user.id
    if user_id in stream_sessions:
        proc = stream_sessions[user_id]['process']
        proc.terminate()
        del stream_sessions[user_id]
        if update.callback_query: await update.callback_query.answer("已停止推流")
        await show_stream_menu(update, context)
    else:
        if update.callback_query: await update.callback_query.answer("当前没有正在进行的推流")
