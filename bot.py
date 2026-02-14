import logging
import os
import sys
import asyncio
import json
import subprocess
import requests
import re
from pathlib import Path
from dotenv import load_dotenv
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, 
    ReplyKeyboardRemove,
    ForceReply
)
from telegram.ext import (
    ApplicationBuilder, 
    ContextTypes, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    filters
)

# Try importing yt_dlp for advanced parsing
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

# --- LOAD ENVIRONMENT VARIABLES ---
current_dir = Path(__file__).parent.resolve()
parent_env = current_dir.parent / '.env'

if parent_env.exists():
    load_dotenv(dotenv_path=parent_env)
else:
    load_dotenv()

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
PIKPAK_USER = os.getenv("PIKPAK_USER")
PIKPAK_PASS = os.getenv("PIKPAK_PASS")
DOWNLOAD_PATH = "downloads"
WHITELIST_FILE = "whitelist.txt"

# --- LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- PIKPAK API HANDLING ---
PIKPAK_AVAILABLE = False
try:
    from pikpakapi import PikPakApi
    PIKPAK_AVAILABLE = True
except ImportError:
    logger.warning("pikpak-api library not found. Running in SIMULATION mode.")

# Global Client Cache
pikpak_client = None

async def get_client():
    global pikpak_client
    if not PIKPAK_AVAILABLE: return None
    if pikpak_client is None:
        try:
            pikpak_client = PikPakApi(username=PIKPAK_USER, password=PIKPAK_PASS)
            await pikpak_client.login()
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return None
    return pikpak_client

# --- HELPER FUNCTIONS ---

def get_whitelist():
    ids = [str(ADMIN_ID)]
    if os.path.exists(WHITELIST_FILE):
        with open(WHITELIST_FILE, 'r') as f:
            for line in f:
                if line.strip():
                    ids.append(line.strip())
    return ids

def add_to_whitelist(user_id):
    with open(WHITELIST_FILE, 'a') as f:
        f.write(f"\n{user_id}")

async def check_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = str(update.effective_user.id)
    if user_id not in get_whitelist():
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"⛔ 无权访问 (ID: {user_id})")
        return False
    return True

def format_bytes(size):
    if not size: return "0 B"
    size = int(size)
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def extract_direct_url_with_ytdlp(url):
    if not YTDLP_AVAILABLE: return None
    ydl_opts = {'format': 'best', 'quiet': True, 'no_warnings': True, 'simulate': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get('url', None)
    except: return None

# --- MENUS & KEYBOARDS ---

def main_menu_keyboard():
    keyboard = [
        ["📂 文件管理", "☁️ 空间状态"],
        ["📉 离线任务", "🔍 搜索文件"],
        ["➕ 添加任务", "⚙️ 帮助/设置"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def show_file_list(update: Update, context: ContextTypes.DEFAULT_TYPE, parent_id=None, page=0, edit_msg=False, search_query=None):
    client = await get_client()
    if not client:
        text = "⚠️ API 未连接 (模拟模式)"
        if edit_msg: await update.callback_query.edit_message_text(text)
        else: await context.bot.send_message(update.effective_chat.id, text)
        return

    try:
        if search_query:
            # Search mode
            # Note: pikpakapi file_list supports name arg for search
            files = await client.file_list(parent_id=None, name=search_query)
            title = f"🔍 **搜索结果**: `{search_query}`"
        else:
            # Normal list
            files = await client.file_list(parent_id=parent_id)
            title = f"📂 **文件列表**\n目录ID: `{parent_id or 'ROOT'}`"

        # Sort: Folders first
        files.sort(key=lambda x: (x.get('kind') != 'drive#folder', x.get('name')))
        
        items_per_page = 10
        total_items = len(files)
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        current_files = files[start_idx:end_idx]

        keyboard = []
        
        # Navigation Buttons (Home / Back)
        nav_top = []
        if parent_id or search_query:
            nav_top.append(InlineKeyboardButton("🏠 首页", callback_data="ls:"))
        if parent_id:
             # PikPak API doesn't give easy parent ID, so we default to Root for "Back" to be safe
            nav_top.append(InlineKeyboardButton("🔙 返回根目录", callback_data="ls:"))
        if nav_top: keyboard.append(nav_top)

        # File Items
        for f in current_files:
            name = f.get('name', 'Unknown')
            fid = f.get('id')
            kind = f.get('kind')
            size = format_bytes(f.get('size', 0))
            
            display_name = (name[:20] + '..') if len(name) > 20 else name
            
            if kind == 'drive#folder':
                btn_text = f"📁 {display_name}"
                cb_data = f"ls:{fid}"
            else:
                btn_text = f"📄 {display_name} ({size})"
                cb_data = f"file:{fid}"
            
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=cb_data)])

        # Pagination
        nav_row = []
        # Construct callback data properly for pagination
        # Format: page:parent_id:page_num:search_query
        s_q_safe = search_query if search_query else ""
        p_id_safe = parent_id if parent_id else ""
        
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f"page:{p_id_safe}:{page-1}:{s_q_safe}"))
        if end_idx < total_items:
            nav_row.append(InlineKeyboardButton("下一页 ➡️", callback_data=f"page:{p_id_safe}:{page+1}:{s_q_safe}"))
        if nav_row:
            keyboard.append(nav_row)

        text = f"{title}\n共 {total_items} 个项目"
        
        if not current_files and page == 0:
            text += "\n(空文件夹或无结果)"

        reply_markup = InlineKeyboardMarkup(keyboard)

        if edit_msg:
            await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        logger.error(e)
        err_text = f"❌ 读取失败: {str(e)}"
        if edit_msg: await update.callback_query.edit_message_text(err_text)
        else: await context.bot.send_message(update.effective_chat.id, err_text)

async def show_file_options(update: Update, context: ContextTypes.DEFAULT_TYPE, file_id):
    client = await get_client()
    try:
        data = await client.get_download_url(file_id)
        name = data.get('name', 'Unknown')
        size = format_bytes(data.get('size', 0))
        url = data.get('url') # Direct link
        mime = data.get('mime_type', '')
        
        text = (
            f"📄 **文件操作**\n"
            f"📝 `{name}`\n"
            f"📦 `{size}` | `{mime}`"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("⬇️ TG发送", callback_data=f"act_tg:{file_id}"),
                InlineKeyboardButton("▶️ 在线播放", callback_data=f"act_play:{file_id}")
            ],
            [
                InlineKeyboardButton("🔗 获取直链", callback_data=f"act_link:{file_id}"),
                InlineKeyboardButton("🚀 Aria2", callback_data=f"act_aria:{file_id}")
            ],
            [
                InlineKeyboardButton("✏️ 重命名", callback_data=f"act_ren:{file_id}"),
                InlineKeyboardButton("🗑 删除", callback_data=f"act_del:{file_id}")
            ],
            [InlineKeyboardButton("🔙 返回文件列表", callback_data="ls:")]
        ]
        
        await update.callback_query.edit_message_text(
            text=text, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.callback_query.answer(f"Error: {str(e)}", show_alert=True)

async def show_offline_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client = await get_client()
    if not client: return
    
    try:
        # Fetch tasks (limit 20)
        tasks = await client.offline_list(limit=20)
        
        if not tasks:
            await context.bot.send_message(update.effective_chat.id, "📉 **当前没有离线任务**", parse_mode='Markdown')
            return
            
        text = "📉 **离线下载任务**\n\n"
        for task in tasks:
            name = task.get('name', 'Unknown')
            # Phase: PHASE_TYPE_RUNNING, PHASE_TYPE_COMPLETE, PHASE_TYPE_ERROR
            phase = task.get('phase')
            progress = task.get('progress', 0)
            status_icon = "⏳"
            
            if phase == 'PHASE_TYPE_COMPLETE': status_icon = "✅"
            elif phase == 'PHASE_TYPE_ERROR': status_icon = "❌"
            elif phase == 'PHASE_TYPE_RUNNING': status_icon = "🚀"
            
            text += f"{status_icon} `{name[:25]}...`\n   └ 进度: {progress}%\n\n"
            
        await context.bot.send_message(update.effective_chat.id, text, parse_mode='Markdown')
        
    except Exception as e:
        await context.bot.send_message(update.effective_chat.id, f"❌ 获取任务失败: {e}")

# --- CALLBACK HANDLER ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    # Use split with maxsplit to safely get arguments
    parts = data.split(':', 1)
    cmd = parts[0]
    arg = parts[1] if len(parts) > 1 else None

    if cmd == "ls":
        parent_id = arg if arg else None
        await show_file_list(update, context, parent_id=parent_id, edit_msg=True)
    
    elif cmd == "page":
        # Format: page:parent_id:page_num:search_query
        # We need to split manually based on knowledge of structure
        # arg string is: "parent_id:page_num:search_query"
        # Since parent_id or search_query might be empty or None strings
        p_args = arg.split(':')
        # p_args[0] = parent_id
        # p_args[1] = page_num
        # p_args[2] = search_query (optional)
        
        pid = p_args[0] if p_args[0] else None
        page = int(p_args[1])
        sq = p_args[2] if len(p_args) > 2 and p_args[2] else None
        
        await show_file_list(update, context, parent_id=pid, page=page, edit_msg=True, search_query=sq)

    elif cmd == "file":
        await show_file_options(update, context, arg)
    
    elif cmd == "act_link":
        client = await get_client()
        try:
            d = await client.get_download_url(arg)
            url = d.get('url')
            await context.bot.send_message(update.effective_chat.id, f"🔗 **直链 (有时效)**:\n\n`{url}`", parse_mode='Markdown')
        except Exception as e:
            await context.bot.send_message(update.effective_chat.id, f"❌ 获取失败: {e}")

    elif cmd == "act_play":
        client = await get_client()
        try:
            d = await client.get_download_url(arg)
            url = d.get('url')
            name = d.get('name', 'video')
            # Create player links
            # PotPlayer: potplayer://link
            # VLC: vlc://link
            # nPlayer: nplayer-http://link (iOS)
            
            kb = [
                [InlineKeyboardButton("VLC 播放", url=f"vlc://{url}")],
                [InlineKeyboardButton("nPlayer 播放", url=f"nplayer-{url}")],
                [InlineKeyboardButton("PotPlayer 播放", url=f"potplayer://{url}")]
            ]
            await context.bot.send_message(
                update.effective_chat.id, 
                f"▶️ **播放: {name}**\n请选择播放器 (需已安装App):", 
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode='Markdown'
            )
        except Exception as e:
            await context.bot.send_message(update.effective_chat.id, f"❌ 获取失败: {e}")

    elif cmd == "act_tg":
        context.args = [arg]
        await get_file_to_tg(update, context)

    elif cmd == "act_aria":
        context.args = [arg]
        await download_local_aria2(update, context)

    elif cmd == "act_ren":
        await context.bot.send_message(
            update.effective_chat.id, 
            f"✏️ **请复制并修改**:\n\n`/rename {arg} 新文件名`", 
            parse_mode='Markdown'
        )

    elif cmd == "act_del":
        client = await get_client()
        try:
            await client.delete_file([arg])
            # Go back to list
            await query.edit_message_text("✅ 文件已删除")
        except Exception as e:
            await query.answer(f"删除失败: {e}", show_alert=True)

# --- COMMAND HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="👋 **欢迎使用 PikPak 旗舰版 Bot**\n\n📁 管理文件 | ☁️ 查看空间 | 📉 离线任务\n⬇️ 远程下载 | 🚀 本地下载 | ▶️ 在线播放",
        reply_markup=main_menu_keyboard(),
        parse_mode='Markdown'
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    text = update.message.text
    
    # Handle Reply for Search
    if update.message.reply_to_message and "请输入搜索关键词" in update.message.reply_to_message.text:
        await show_file_list(update, context, search_query=text)
        return

    # Handle Menu Buttons
    if text == "📂 文件管理":
        await show_file_list(update, context, parent_id=None)
    elif text == "☁️ 空间状态":
        await space_info(update, context)
    elif text == "🗑 清空回收站":
        await empty_trash(update, context)
    elif text == "📉 离线任务":
        await show_offline_tasks(update, context)
    elif text == "🔍 搜索文件":
        await context.bot.send_message(
            update.effective_chat.id, 
            "🔍 **请输入搜索关键词**:", 
            reply_markup=ForceReply(selective=True),
            parse_mode='Markdown'
        )
    elif text == "➕ 添加任务":
        await context.bot.send_message(update.effective_chat.id, "📥 **请发送链接** (磁力/HTTP/TikTok)...")
    elif text == "⚙️ 帮助/设置":
        help_txt = (
            "🛠 **命令列表**:\n"
            "`/mkdir <名>` - 新建文件夹\n"
            "`/mv <文件ID> <目录ID>` - 移动\n"
            "`/rename <ID> <名>` - 重命名\n"
            "`/invite <ID>` - 授权新用户"
        )
        await context.bot.send_message(update.effective_chat.id, help_txt, parse_mode='Markdown')
    else:
        # Treat as download links
        await handle_download_links(update, context)

async def mkdir_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    if not context.args:
        await context.bot.send_message(update.effective_chat.id, "用法: `/mkdir <文件夹名称>`", parse_mode='Markdown')
        return
    
    name = " ".join(context.args)
    client = await get_client()
    if client:
        try:
            await client.create_folder(name=name) 
            await context.bot.send_message(update.effective_chat.id, f"✅ 文件夹 `{name}` 创建成功", parse_mode='Markdown')
        except Exception as e:
            await context.bot.send_message(update.effective_chat.id, f"❌ 创建失败: {e}")

# --- ACTION LOGIC ---

async def handle_download_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines: return

    status_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=f"📥 正在解析 {len(lines)} 个链接...")
    
    client = await get_client()
    if not client:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=status_msg.message_id, text="❌ API 未连接")
        return

    success = 0
    for link in lines:
        final = link
        if YTDLP_AVAILABLE and any(x in link for x in ['youtube','tiktok','twitter','x.com']):
            parsed = extract_direct_url_with_ytdlp(link)
            if parsed: final = parsed
        try:
            await client.offline_download(final)
            success += 1
        except: pass
    
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id, 
        message_id=status_msg.message_id, 
        text=f"✅ **已提交 {success}/{len(lines)} 个任务**\n请点击 [📉 离线任务] 查看进度。",
        parse_mode='Markdown'
    )

async def get_file_to_tg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args: return
    file_id = context.args[0]

    msg = await context.bot.send_message(chat_id=chat_id, text="⏳ 下载中 (中转)...")
    
    client = await get_client()
    if not client: return

    try:
        data = await client.get_download_url(file_id)
        url = data.get('url')
        name = data.get('name', 'downloaded_file')
        size = int(data.get('size', 0))

        if size > 50 * 1024 * 1024:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text=f"⚠️ 文件 > 50MB ({format_bytes(size)})，无法通过 Bot 发送。\n请使用 [🔗 获取直链] 或 [🚀 Aria2]。")
            return

        r = requests.get(url, stream=True)
        local_path = f"{DOWNLOAD_PATH}/{name}"
        if not os.path.exists(DOWNLOAD_PATH): os.makedirs(DOWNLOAD_PATH)
        
        with open(local_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text="⬆️ 上传到 Telegram...")
        await context.bot.send_document(chat_id=chat_id, document=open(local_path, 'rb'), filename=name)
        
        os.remove(local_path)
        await context.bot.delete_message(chat_id=chat_id, message_id=msg.message_id)

    except Exception as e:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text=f"❌ 错误: {e}")

async def download_local_aria2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args: return
    file_id = context.args[0]
    
    client = await get_client()
    if not client: return

    try:
        data = await client.get_download_url(file_id)
        url = data.get('url')
        name = data.get('name', 'download')
        
        if not os.path.exists(DOWNLOAD_PATH): os.makedirs(DOWNLOAD_PATH)
        
        cmd = ['aria2c', '-d', DOWNLOAD_PATH, '-o', name, url]
        subprocess.Popen(cmd)
        
        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"🚀 **Aria2 已启动**\n文件: `{name}`\n位置: `{os.path.abspath(DOWNLOAD_PATH)}`",
            parse_mode='Markdown'
        )
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ 失败: {e}")

async def rename_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    if len(context.args) < 2:
        await context.bot.send_message(update.effective_chat.id, "用法: `/rename <ID> <新名>`", parse_mode='Markdown')
        return
    file_id = context.args[0]
    new_name = " ".join(context.args[1:])
    
    client = await get_client()
    try:
        await client.rename_file(file_id=file_id, name=new_name)
        await context.bot.send_message(update.effective_chat.id, f"✅ 重命名为: `{new_name}`", parse_mode='Markdown')
    except Exception as e:
        await context.bot.send_message(update.effective_chat.id, f"❌ 失败: {e}")

async def move_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    if len(context.args) < 2: return
    client = await get_client()
    try:
        await client.move_file(file_ids=[context.args[0]], parent_id=context.args[1])
        await context.bot.send_message(update.effective_chat.id, "✅ 移动成功")
    except Exception as e:
        await context.bot.send_message(update.effective_chat.id, f"❌ 失败: {e}")

async def space_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client = await get_client()
    if not client: return
    try:
        info = await client.get_quota_info()
        limit = int(info.get('quota', 0))
        usage = int(info.get('usage', 0))
        text = f"☁️ **PikPak 空间**\n总计: `{format_bytes(limit)}`\n已用: `{format_bytes(usage)}`\n剩余: `{format_bytes(limit - usage)}`"
        await context.bot.send_message(update.effective_chat.id, text, parse_mode='Markdown')
    except: pass

async def empty_trash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client = await get_client()
    if not client: return
    try:
        await client.trash_empty()
        await context.bot.send_message(update.effective_chat.id, "✅ 回收站已清空")
    except: pass

async def invite_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_ID): return
    if context.args:
        add_to_whitelist(context.args[0])
        await context.bot.send_message(update.effective_chat.id, f"✅ 已添加 ID: {context.args[0]}")

# --- MAIN EXECUTION ---

if __name__ == '__main__':
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN missing. Check your .env file in parent directory.")
        sys.exit(1)
        
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Commands
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('mkdir', mkdir_command))
    application.add_handler(CommandHandler('rename', rename_file))
    application.add_handler(CommandHandler('mv', move_file))
    application.add_handler(CommandHandler('invite', invite_user))
    
    # Compatibility Commands
    application.add_handler(CommandHandler('ls', lambda u,c: show_file_list(u,c,None)))
    application.add_handler(CommandHandler('search', lambda u,c: show_file_list(u,c,search_query=" ".join(c.args) if c.args else None)))
    application.add_handler(CommandHandler('tasks', show_offline_tasks))
    
    # Callbacks & Text
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))
    
    print(f"PikPak Bot Ultimate Started. Admin: {ADMIN_ID}")
    application.run_polling()
