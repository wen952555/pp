import logging
import os
import sys
import asyncio
import json
import subprocess
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# Try importing yt_dlp for advanced parsing
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

# Load environment variables
load_dotenv()

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
PIKPAK_USER = os.getenv("PIKPAK_USER")
PIKPAK_PASS = os.getenv("PIKPAK_PASS")
DOWNLOAD_PATH = "downloads" # Local download path for Termux

# Whitelist file
WHITELIST_FILE = "whitelist.txt"

# --- LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- PIKPAK LIBRARY CHECK ---
PIKPAK_AVAILABLE = False
try:
    from pikpakapi import PikPakApi
    PIKPAK_AVAILABLE = True
except ImportError:
    logger.warning("pikpak-api library not found. Bot will run in SIMULATION mode.")

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
    """Check if the user is authorized."""
    user_id = str(update.effective_user.id)
    allowed_ids = get_whitelist()
    
    if user_id not in allowed_ids:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"⛔ 无权访问 (ID: {user_id})")
        return False
    return True

def format_bytes(size):
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def extract_direct_url_with_ytdlp(url):
    """Use yt-dlp to extract direct video link for social media."""
    if not YTDLP_AVAILABLE:
        return None
    
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'simulate': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get('url', None)
    except Exception as e:
        logger.error(f"yt-dlp error: {e}")
        return None

# --- COMMAND HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    
    status = "✅ 在线" if PIKPAK_AVAILABLE else "⚠️ 模拟"
    
    help_text = (
        f"🤖 **PikPak 旗舰版 Bot**\n"
        f"状态: {status}\n\n"
        f"📥 **资源交互**:\n"
        f"• 发送链接 -> 离线下载/解析\n"
        f"• `/ls [ID]` - 列出文件 (默认根目录)\n"
        f"• `/rename <ID> <新名>` - 重命名\n"
        f"• `/mv <ID> <目录ID>` - 移动文件\n"
        f"• `/dl <ID>` - 获取直链\n"
        f"• `/get <ID>` - 发送到 TG (限50MB)\n"
        f"• `/down <ID>` - 下载到 Termux (Aria2)\n\n"
        f"🛠 **系统管理**:\n"
        f"• `/space` - 空间使用\n"
        f"• `/trash` - 清空回收站\n"
        f"• `/invite <ID>` - 添加用户"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text, parse_mode='Markdown')

async def list_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    
    parent_id = context.args[0] if context.args else None # None usually implies root in some libs
    msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="📂 读取文件列表...")
    
    if PIKPAK_AVAILABLE:
        try:
            client = PikPakApi(username=PIKPAK_USER, password=PIKPAK_PASS)
            await client.login()
            # Note: Method name might vary by library version. 
            # Trying common `file_list` or `get_file_list`.
            files = await client.file_list(parent_id=parent_id) 
            
            if not files:
                await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="📂 文件夹为空或读取失败")
                return

            # Construct display list
            # Limit to 15 items to avoid message length limits
            display_text = f"📂 **文件列表** (ID: {parent_id or 'Root'})\n\n"
            for f in files[:15]:
                icon = "📁" if f.get('kind') == 'drive#folder' else "📄"
                name = f.get('name', 'Unknown')
                fid = f.get('id', 'N/A')
                size = format_bytes(int(f.get('size', 0))) if f.get('size') else ""
                display_text += f"{icon} `{name}`\n   🆔 `{fid}` {size}\n\n"
            
            if len(files) > 15:
                display_text += f"...还有 {len(files)-15} 个文件"

            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=display_text, parse_mode='Markdown')
        except Exception as e:
             await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 读取失败: {str(e)}")
    else:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="⚠️ 模拟模式: file_1 (ID: 123), folder_A (ID: 456)")

async def rename_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    
    if len(context.args) < 2:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="ℹ️ 用法: `/rename <ID> <新名称>`", parse_mode='Markdown')
        return
    
    file_id = context.args[0]
    new_name = " ".join(context.args[1:])
    
    if PIKPAK_AVAILABLE:
        try:
            client = PikPakApi(username=PIKPAK_USER, password=PIKPAK_PASS)
            await client.login()
            await client.rename_file(file_id=file_id, name=new_name)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"✅ 重命名成功:\n`{new_name}`", parse_mode='Markdown')
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ 失败: {str(e)}")

async def move_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    
    if len(context.args) < 2:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="ℹ️ 用法: `/mv <文件ID> <目标文件夹ID>`", parse_mode='Markdown')
        return

    file_id = context.args[0]
    target_id = context.args[1]

    if PIKPAK_AVAILABLE:
        try:
            client = PikPakApi(username=PIKPAK_USER, password=PIKPAK_PASS)
            await client.login()
            # Usually client.move_file(file_id, target_parent_id)
            await client.move_file(file_ids=[file_id], parent_id=target_id)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"✅ 移动成功!")
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ 移动失败: {str(e)}")

async def get_file_to_tg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Download small file and send to TG."""
    if not await check_auth(update, context): return
    if not context.args:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="ℹ️ 用法: `/get <ID>`")
        return
    
    file_id = context.args[0]
    msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="⏳ 获取链接并下载中 (限50MB)...")

    if PIKPAK_AVAILABLE:
        try:
            client = PikPakApi(username=PIKPAK_USER, password=PIKPAK_PASS)
            await client.login()
            data = await client.get_download_url(file_id)
            url = data.get('url')
            name = data.get('name', 'downloaded_file')
            size = int(data.get('size', 0))

            if size > 50 * 1024 * 1024:
                await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"⚠️ 文件太大 ({format_bytes(size)})，TG 限制 50MB。请使用 `/dl` 获取直链。")
                return

            # Stream download
            r = requests.get(url, stream=True)
            if r.status_code == 200:
                local_path = f"{DOWNLOAD_PATH}/{name}"
                if not os.path.exists(DOWNLOAD_PATH): os.makedirs(DOWNLOAD_PATH)
                
                with open(local_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="⬆️ 正在上传到 Telegram...")
                await context.bot.send_document(chat_id=update.effective_chat.id, document=open(local_path, 'rb'), filename=name)
                
                # Cleanup
                os.remove(local_path)
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg.message_id)
            else:
                await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="❌ 下载失败: HTTP Error")

        except Exception as e:
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 出错: {str(e)}")

async def download_local_aria2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trigger local aria2c download on Termux."""
    if not await check_auth(update, context): return
    if not context.args:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="ℹ️ 用法: `/down <ID>` (下载到 Termux)")
        return
    
    file_id = context.args[0]
    msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="🚀 正在启动 Aria2...")

    if PIKPAK_AVAILABLE:
        try:
            client = PikPakApi(username=PIKPAK_USER, password=PIKPAK_PASS)
            await client.login()
            data = await client.get_download_url(file_id)
            url = data.get('url')
            name = data.get('name', 'download')
            
            # Ensure download dir exists
            if not os.path.exists(DOWNLOAD_PATH): os.makedirs(DOWNLOAD_PATH)
            
            # Spawn aria2c process
            # -d: directory, -o: filename
            cmd = ['aria2c', '-d', DOWNLOAD_PATH, '-o', name, url]
            subprocess.Popen(cmd)
            
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id, 
                message_id=msg.message_id, 
                text=f"✅ **下载已开始**\n\n📄 文件: `{name}`\n📂 位置: `{os.path.abspath(DOWNLOAD_PATH)}`\n\n(请在 Termux 检查进度)"
            )

        except Exception as e:
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 启动失败: {str(e)}")

# ... (Reuse space_info, empty_trash, invite_user from previous version) ...
async def space_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    if PIKPAK_AVAILABLE:
        try:
            client = PikPakApi(username=PIKPAK_USER, password=PIKPAK_PASS)
            await client.login()
            info = await client.get_quota_info()
            limit = int(info.get('quota', 0))
            usage = int(info.get('usage', 0))
            text = f"☁️ **空间详情**\n总: `{format_bytes(limit)}`\n用: `{format_bytes(usage)}`\n余: `{format_bytes(limit - usage)}`"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode='Markdown')
        except:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ 查询失败")

async def empty_trash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    if PIKPAK_AVAILABLE:
        try:
            client = PikPakApi(username=PIKPAK_USER, password=PIKPAK_PASS)
            await client.login()
            # Try different method names for trash
            if hasattr(client, 'trash_empty'): await client.trash_empty()
            elif hasattr(client, 'empty_trash'): await client.empty_trash()
            else: raise Exception("Method not found")
            await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ 回收站已清空")
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ 失败: {str(e)}")

async def invite_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_ID): return
    if not context.args: return
    add_to_whitelist(context.args[0])
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"✅ 用户 {context.args[0]} 已添加")

async def get_direct_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    if not context.args: return
    try:
        client = PikPakApi(username=PIKPAK_USER, password=PIKPAK_PASS)
        await client.login()
        data = await client.get_download_url(context.args[0])
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"🔗 `{data.get('url')}`", parse_mode='Markdown')
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return

    text = update.message.text
    if not text: return

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines: return

    status_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=f"📥 处理 {len(lines)} 个任务...")
    
    success = 0
    if PIKPAK_AVAILABLE:
        try:
            client = PikPakApi(username=PIKPAK_USER, password=PIKPAK_PASS)
            await client.login()
            for link in lines:
                final = link
                if YTDLP_AVAILABLE and any(x in link for x in ['youtube','youtu.be','tiktok','twitter','x.com']):
                    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
                    parsed = extract_direct_url_with_ytdlp(link)
                    if parsed: final = parsed
                try:
                    await client.offline_download(final)
                    success += 1
                except: pass
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=status_msg.message_id, text=f"✅ 成功提交 {success} 个任务")
        except Exception as e:
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=status_msg.message_id, text=f"❌ 错误: {str(e)}")

if __name__ == '__main__':
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN missing.")
        sys.exit(1)
        
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', start))
    application.add_handler(CommandHandler('ls', list_files))
    application.add_handler(CommandHandler('rename', rename_file))
    application.add_handler(CommandHandler('mv', move_file))
    application.add_handler(CommandHandler('space', space_info))
    application.add_handler(CommandHandler('trash', empty_trash))
    application.add_handler(CommandHandler('invite', invite_user))
    application.add_handler(CommandHandler('dl', get_direct_link))
    application.add_handler(CommandHandler('get', get_file_to_tg))
    application.add_handler(CommandHandler('down', download_local_aria2))
    
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print(f"PikPak Bot Ultimate Started. Admin: {ADMIN_ID}")
    application.run_polling()
