import logging
import os
import sys
import asyncio
import json
import subprocess
import requests
from pathlib import Path
from dotenv import load_dotenv
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, 
    ReplyKeyboardRemove
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

# Global Client Cache (Simple)
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
        ["➕ 添加任务", "🗑 清空回收站"],
        ["⚙️ 帮助/设置"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def show_file_list(update: Update, context: ContextTypes.DEFAULT_TYPE, parent_id=None, page=0, edit_msg=False):
    client = await get_client()
    if not client:
        text = "⚠️ API 未连接 (模拟模式)"
        if edit_msg: await update.callback_query.edit_message_text(text)
        else: await context.bot.send_message(update.effective_chat.id, text)
        return

    try:
        # Fetch files
        files = await client.file_list(parent_id=parent_id)
        # Sort: Folders first, then Files
        files.sort(key=lambda x: (x.get('kind') != 'drive#folder', x.get('name')))
        
        # Pagination (10 items per page to keep buttons clean)
        items_per_page = 10
        total_items = len(files)
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        current_files = files[start_idx:end_idx]

        keyboard = []
        
        # Back button (if not root)
        if parent_id:
            # We don't easily know grandparent ID without querying file info of parent, 
            # so for simplicity "Back" usually goes to Root or we implement a navigation stack.
            # Here we add a specific "Home" or "Up" button if we can implement 'up' logic later.
            # For now, "Back to Root" is safer if we don't track stack.
            keyboard.append([InlineKeyboardButton("🔙 返回根目录", callback_data="ls:")])

        # File List Buttons
        for f in current_files:
            name = f.get('name', 'Unknown')
            fid = f.get('id')
            kind = f.get('kind')
            size = format_bytes(f.get('size', 0))
            
            # Truncate long names
            display_name = (name[:20] + '..') if len(name) > 20 else name
            
            if kind == 'drive#folder':
                btn_text = f"📁 {display_name}"
                cb_data = f"ls:{fid}"
            else:
                btn_text = f"📄 {display_name} ({size})"
                cb_data = f"file:{fid}"
            
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=cb_data)])

        # Pagination Buttons
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f"page:{parent_id or ''}:{page-1}"))
        if end_idx < total_items:
            nav_row.append(InlineKeyboardButton("下一页 ➡️", callback_data=f"page:{parent_id or ''}:{page+1}"))
        if nav_row:
            keyboard.append(nav_row)

        reply_markup = InlineKeyboardMarkup(keyboard)
        text = f"📂 **文件列表**\n当前目录ID: `{parent_id or 'ROOT'}`\n共 {total_items} 个项目"

        if edit_msg:
            await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        logger.error(e)
        err_text = f"❌ 获取列表失败: {str(e)}"
        if edit_msg: await update.callback_query.edit_message_text(err_text)
        else: await context.bot.send_message(update.effective_chat.id, err_text)

async def show_file_options(update: Update, context: ContextTypes.DEFAULT_TYPE, file_id):
    client = await get_client()
    try:
        # We assume file_id is valid. PikPak API doesn't always have a quick 'get_file_info' 
        # without listing, but let's try to get download url which contains info.
        data = await client.get_download_url(file_id)
        name = data.get('name', 'Unknown')
        size = format_bytes(data.get('size', 0))
        url = data.get('url') # Direct link
        
        text = (
            f"📄 **文件详情**\n\n"
            f"名字: `{name}`\n"
            f"大小: `{size}`\n"
            f"ID: `{file_id}`"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("⬇️ TG发送", callback_data=f"act_tg:{file_id}"),
                InlineKeyboardButton("🔗 获取直链", callback_data=f"act_link:{file_id}")
            ],
            [
                InlineKeyboardButton("🚀 Aria2下载", callback_data=f"act_aria:{file_id}"),
                InlineKeyboardButton("✏️ 重命名", callback_data=f"act_ren:{file_id}")
            ],
            [
                InlineKeyboardButton("🗑 删除文件", callback_data=f"act_del:{file_id}"),
                InlineKeyboardButton("🔙 返回列表", callback_data="ls:")
            ]
        ]
        
        await update.callback_query.edit_message_text(
            text=text, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.callback_query.answer(f"Error: {str(e)}", show_alert=True)

# --- CALLBACK HANDLER ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # Acknowledge interaction
    
    data = query.data
    cmd, *args = data.split(':', 1) # simple parsing
    arg = args[0] if args else None

    if cmd == "ls":
        # Argument is parent_id (or empty for root)
        parent_id = arg if arg else None
        await show_file_list(update, context, parent_id=parent_id, edit_msg=True)
    
    elif cmd == "page":
        # args: parent_id:page_num
        pid, pnum = arg.split(':')
        parent_id = pid if pid else None
        page = int(pnum)
        await show_file_list(update, context, parent_id=parent_id, page=page, edit_msg=True)

    elif cmd == "file":
        await show_file_options(update, context, arg)
    
    elif cmd == "act_link":
        client = await get_client()
        try:
            d = await client.get_download_url(arg)
            await context.bot.send_message(update.effective_chat.id, f"🔗 **直链**:\n`{d.get('url')}`", parse_mode='Markdown')
        except Exception as e:
            await context.bot.send_message(update.effective_chat.id, f"❌ 获取失败: {e}")

    elif cmd == "act_tg":
        # Trigger the existing TG upload logic
        # We construct a mock message command or call function directly
        context.args = [arg]
        await get_file_to_tg(update, context)

    elif cmd == "act_aria":
        context.args = [arg]
        await download_local_aria2(update, context)

    elif cmd == "act_ren":
        # Send a helper message for rename
        await context.bot.send_message(
            update.effective_chat.id, 
            f"✏️ **请复制以下命令并修改名称**:\n\n`/rename {arg} 新文件名.ext`", 
            parse_mode='Markdown'
        )

    elif cmd == "act_del":
        client = await get_client()
        try:
            # Note: library method might be batch_delete or delete_file
            await client.delete_file([arg]) # Assume it takes a list
            await query.edit_message_text("✅ 文件已删除")
        except Exception as e:
            await query.answer(f"删除失败: {e}", show_alert=True)

# --- COMMAND HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="👋 **欢迎使用 PikPak 旗舰版 Bot**\n请使用下方菜单操作。",
        reply_markup=main_menu_keyboard(),
        parse_mode='Markdown'
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    text = update.message.text
    
    # Handle Menu Buttons
    if text == "📂 文件管理":
        await show_file_list(update, context, parent_id=None)
    elif text == "☁️ 空间状态":
        await space_info(update, context)
    elif text == "🗑 清空回收站":
        await empty_trash(update, context)
    elif text == "➕ 添加任务":
        await context.bot.send_message(update.effective_chat.id, "📥 **请直接发送链接** (磁力/HTTP/TikTok/Twitter)...")
    elif text == "⚙️ 帮助/设置":
        help_txt = (
            "🛠 **高级命令**:\n"
            "`/mkdir <名>` - 建文件夹\n"
            "`/mv <文件ID> <目录ID>` - 移动\n"
            "`/rename <ID> <名>` - 重命名\n"
            "`/invite <ID>` - 邀请用户"
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
            # parent_id=None means root
            await client.create_folder(name=name) 
            await context.bot.send_message(update.effective_chat.id, f"✅ 文件夹 `{name}` 创建成功", parse_mode='Markdown')
        except Exception as e:
            await context.bot.send_message(update.effective_chat.id, f"❌ 创建失败: {e}")

# --- REUSED/MODIFIED ACTIONS ---

async def handle_download_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines: return

    status_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=f"📥 处理 {len(lines)} 个任务...")
    
    client = await get_client()
    if not client:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=status_msg.message_id, text="❌ API 未连接")
        return

    success = 0
    for link in lines:
        final = link
        # Optional: yt-dlp parsing
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
        text=f"✅ **任务提交完成**\n成功: {success}/{len(lines)}",
        parse_mode='Markdown'
    )

async def get_file_to_tg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Refactored to handle both Command and Callback context"""
    # Logic is complex because CallbackQuery doesn't have same attrs as Message
    # We use effective_chat.id
    chat_id = update.effective_chat.id
    
    # args comes from context.args set in callback handler, or command args
    if not context.args: return
    file_id = context.args[0]

    msg = await context.bot.send_message(chat_id=chat_id, text="⏳ 正在下载到服务器中转 (限50MB)...")
    
    client = await get_client()
    if not client: return

    try:
        data = await client.get_download_url(file_id)
        url = data.get('url')
        name = data.get('name', 'downloaded_file')
        size = int(data.get('size', 0))

        if size > 50 * 1024 * 1024:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text=f"⚠️ 文件过大 ({format_bytes(size)})，Telegram 限制 50MB。")
            return

        r = requests.get(url, stream=True)
        local_path = f"{DOWNLOAD_PATH}/{name}"
        if not os.path.exists(DOWNLOAD_PATH): os.makedirs(DOWNLOAD_PATH)
        
        with open(local_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text="⬆️ 上传中...")
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
            text=f"🚀 **Aria2 任务已启动**\n文件: `{name}`",
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
    
    # Old text commands for compatibility
    application.add_handler(CommandHandler('ls', lambda u,c: show_file_list(u,c,None)))
    application.add_handler(CommandHandler('space', space_info))
    application.add_handler(CommandHandler('trash', empty_trash))
    
    # Callbacks (Buttons)
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Text Handler (Menu Buttons & Links)
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))
    
    print(f"PikPak Bot Ultimate Started. Admin: {ADMIN_ID}")
    application.run_polling()
