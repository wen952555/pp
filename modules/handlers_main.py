
import os
import shutil
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes
from .config import check_auth, WEB_PORT, DOWNLOAD_PATH
from .utils import get_base_url, is_rate_limited
from .accounts import account_mgr
from .handlers_file import (
    show_file_list, show_file_options, generate_playlist, 
    deduplicate_folder, initiate_regex_rename, process_regex_rename, calculate_folder_size,
    show_cross_copy_menu, execute_cross_copy
)
from .handlers_task import show_offline_tasks, handle_task_action, add_download_task

logger = logging.getLogger(__name__)

# --- UTILS ---
async def reset_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"[CMD] Reset by {update.effective_user.id}")
    context.user_data.clear()
    await context.bot.send_message(update.effective_chat.id, "✅ 状态已重置，请重新操作。", reply_markup=main_menu_keyboard())

def main_menu_keyboard():
    keyboard = [
        ["📂 文件管理", "☁️ 空间/VIP"],
        ["📉 离线任务", "🔍 搜索文件"],
        ["➕ 添加任务", "👥 账号管理"],
        ["📊 系统状态", "🛠 极客工具箱"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"[CMD] Start by {update.effective_user.id}")
    if not await check_auth(update, context): return
    context.user_data.clear()
    
    # Get Status
    base_url = get_base_url(WEB_PORT)
    is_tunnel = "trycloudflare.com" in base_url
    status_icon = "🟢" if is_tunnel else "🟠"
    net_mode = "Cloudflare 隧道 (公网)" if is_tunnel else "局域网 (内网)"

    # Status message
    text = (
        "👋 **PikPak Termux Bot**\n"
        f"运行状态: 🟢 在线\n"
        f"网络模式: {status_icon} {net_mode}\n"
        f"服务地址: `{base_url}`\n"
    )
    
    if not is_tunnel:
        text += "\n⚠️ **未检测到隧道域名**\n在线播放将仅限局域网访问。若需公网访问，请检查 Cloudflare 进程是否启动 (`pm2 logs cf-tunnel`)。"

    text += "\n👇 点击下方菜单开始使用:"
    
    await context.bot.send_message(update.effective_chat.id, text, reply_markup=main_menu_keyboard(), parse_mode='Markdown')

async def show_system_status(update, context):
    msg = await context.bot.send_message(update.effective_chat.id, "🔍 正在检查系统状态...")
    
    # Check Web URL
    base_url = get_base_url(WEB_PORT)
    is_tunnel = "trycloudflare.com" in base_url
    
    # Check Login
    user_id = update.effective_user.id
    active_user = account_mgr.active_user_map.get(str(user_id), "未登录")
    
    info = (
        "🖥 **系统状态诊断**\n\n"
        f"👤 **当前账号**: `{active_user}`\n"
        f"🌐 **Web 服务**: `{base_url}`\n"
        f"📡 **连接模式**: {'✅ 隧道 (无视VPN)' if is_tunnel else '⚠️ 局域网 (仅限同WiFi)'}\n"
        f"🔌 **端口**: `{WEB_PORT}`\n\n"
    )
    
    if is_tunnel:
        info += "✅ 隧道运行正常，可直接在线播放。"
    else:
        info += "❌ **隧道未就绪**\n可能原因: 启动中、网络受限或进程崩溃。\n尝试: 终端运行 `./start.sh` 重启服务。"
    
    kb = [[InlineKeyboardButton("🔄 刷新状态", callback_data="status_refresh")]]
    await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=info, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def login_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    if len(context.args) < 2:
        await context.bot.send_message(update.effective_chat.id, "❌ 格式: `/login 邮箱 密码`", parse_mode='Markdown')
        return
    
    email = context.args[0]
    pwd = context.args[1]
    
    msg = await context.bot.send_message(update.effective_chat.id, "⏳ 登录中...")
    account_mgr.add_account_credentials(email, pwd)
    
    if await account_mgr.switch_account(update.effective_user.id, email):
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"✅ 登录成功: {email}")
    else:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="❌ 登录失败，请检查密码")

# --- MENUS ---
async def show_accounts_menu(update, context):
    try:
        accounts = account_mgr.get_accounts_list()
        active = account_mgr.active_user_map.get(str(update.effective_user.id))
        kb = []
        for u in accounts:
            icn = "🟢" if u == active else "⚪️"
            kb.append([InlineKeyboardButton(f"{icn} {u}", callback_data=f"acc_switch:{u}"), InlineKeyboardButton("❌ 删除", callback_data=f"acc_del:{u}")])
        kb.append([InlineKeyboardButton("➕ 添加账号", callback_data="acc_add")])
        kb.append([InlineKeyboardButton("🔙 关闭", callback_data="close_menu")])
        msg = f"👥 **账号管理** (当前: `{active}`)"
        
        if update.callback_query: await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        else: await context.bot.send_message(update.effective_chat.id, msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    except Exception as e:
        print(f"[ERR] Show Accounts: {e}")
        await context.bot.send_message(update.effective_chat.id, "❌ 菜单加载失败")

async def initiate_add_account(update, context):
    context.user_data['adding_account'] = True
    await context.bot.send_message(update.effective_chat.id, "👤 请直接回复: `邮箱 密码`\n(用空格分隔)", reply_markup=ForceReply(selective=True), parse_mode='Markdown')
    if update.callback_query: await update.callback_query.answer()

async def process_add_account(update, context, text):
    if text.lower() in ['cancel', '取消']:
        del context.user_data['adding_account']
        await context.bot.send_message(update.effective_chat.id, "🚫 已取消")
        return
        
    parts = text.replace("：", " ").replace(":", " ").split()
    if len(parts) < 2:
        await context.bot.send_message(update.effective_chat.id, "❌ 格式错误，请回复: `邮箱 密码`")
        return
    
    try: await update.message.delete()
    except: pass
    
    email, pwd = parts[0].strip(), parts[1].strip()
    msg = await context.bot.send_message(update.effective_chat.id, f"⏳ 正在验证 `{email}`...")
    
    account_mgr.add_account_credentials(email, pwd)
    
    if await account_mgr.switch_account(update.effective_user.id, email):
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"✅ **登录成功**\n欢迎回来，{email}")
        if 'adding_account' in context.user_data: del context.user_data['adding_account']
    else:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="❌ 登录失败 (密码错误?)")

async def show_quota_info(update, context):
    msg = await context.bot.send_message(update.effective_chat.id, "⏳ 查询中...")
    client = await account_mgr.get_client(update.effective_user.id)
    if not client: 
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="⚠️ 未登录")
        return
    try:
        info = await client.get_quota_info()
        limit, usage = int(info.get('quota', 1)), int(info.get('usage', 0))
        pct = (usage/limit)*100
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"☁️ **空间状态**\n已用: {format_bytes(usage)}\n总计: {format_bytes(limit)}\n占比: `{pct:.1f}%`", parse_mode='Markdown')
    except Exception as e: 
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 失败: {e}")

# --- CALLBACK ROUTER ---
async def router_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    
    # 1. Rate Limit Check
    if is_rate_limited(context.user_data):
        try: await query.answer("✋ 操作太快，请稍候", show_alert=False)
        except: pass
        return

    print(f"[CB] {data} (User: {user_id})") # Debug log
    
    parts = data.split(':', 1)
    cmd = parts[0]
    arg = parts[1] if len(parts) > 1 and parts[1] not in ["", "None"] else None

    # Handle Errors gracefully
    try:
        if cmd == "noop": await query.answer()
        elif cmd == "close_menu": await query.delete_message()
        
        # System
        elif cmd == "status_refresh": await show_system_status(update, context)

        # File System
        elif cmd == "ls": await show_file_list(update, context, parent_id=arg, edit_msg=True)
        elif cmd == "file": await show_file_options(update, context, arg)
        elif cmd == "page":
            try:
                sub = arg.split(':')
                pid = sub[0] if sub[0] != "" else None
                page = int(sub[1])
                await show_file_list(update, context, parent_id=pid, page=page, edit_msg=True)
            except: await show_file_list(update, context, edit_msg=True)

        # Actions
        elif cmd == "act_link":
            # Direct Link Logic with Retry
            try:
                # Indicate loading via chat action
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
                
                client = await account_mgr.get_client(user_id)
                d = await client.get_download_url(arg)
                
                # Retry once if url is missing (maybe token expired)
                if not d or not d.get('url'):
                    client = await account_mgr.get_client(user_id, force_refresh=True)
                    d = await client.get_download_url(arg)
                
                if d and d.get('url'):
                    url = d['url']
                    await context.bot.send_message(
                        update.effective_chat.id, 
                        f"🔗 **直链获取成功**:\n\n`{url}`", 
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                    await query.answer()
                else: 
                    await query.answer("❌ 无法获取 (文件处理中?)", show_alert=True)
            except Exception as e:
                logger.error(f"Link Error: {e}")
                await query.answer("获取失败，请重试", show_alert=True)

        elif cmd == "act_ren":
            context.user_data['renaming_id'] = arg
            await context.bot.send_message(update.effective_chat.id, "✏️ 请回复新文件名:", reply_markup=ForceReply(selective=True))
            await query.answer()
        elif cmd == "act_del":
            client = await account_mgr.get_client(user_id)
            await client.delete_file([arg])
            await query.answer("已删除")
            # Try to refresh list? We don't know parent, so show root/current list if possible or just say deleted
            # Ideally we reload previous list, but we don't have state.
            await context.bot.send_message(update.effective_chat.id, "✅ 文件已删除")

        elif cmd == "act_cut":
            context.user_data['clipboard'] = {'id': arg, 'op': 'move'}
            await query.answer("已剪切")
            await context.bot.send_message(update.effective_chat.id, "✂️ 已剪切。请进入目标目录点击『粘贴』")

        elif cmd == "paste":
            cl = context.user_data.get('clipboard')
            if cl:
                await query.answer("移动中...")
                client = await account_mgr.get_client(user_id)
                await client.move_file([cl['id']], arg)
                del context.user_data['clipboard']
                await query.answer("成功")
                await show_file_list(update, context, parent_id=arg, edit_msg=True)
        elif cmd == "paste_cancel":
            if 'clipboard' in context.user_data: del context.user_data['clipboard']
            await show_file_list(update, context, edit_msg=True)

        # Accounts
        elif cmd == "acc_switch":
            await query.answer("切换中...")
            if await account_mgr.switch_account(user_id, arg):
                await show_accounts_menu(update, context)
            else: await query.answer("切换失败")
        elif cmd == "acc_add": await initiate_add_account(update, context)
        elif cmd == "acc_del":
            account_mgr.remove_account(arg)
            await show_accounts_menu(update, context)

        # Tools
        elif cmd.startswith("tool_"):
            if "m3u" in cmd: await generate_playlist(update, context, arg, 'm3u')
            elif "size" in cmd: await calculate_folder_size(update, context, arg)
            elif "regex" in cmd: await initiate_regex_rename(update, context, arg)
            elif "dedupe" in cmd: await deduplicate_folder(update, context, arg)
            elif "alist" in cmd: await context.bot.send_message(update.effective_chat.id, f"🗂 AList: http://{WEB_PORT}:5244 (Local IP)")
            elif "clearcache" in cmd: 
                if os.path.exists(DOWNLOAD_PATH): shutil.rmtree(DOWNLOAD_PATH)
                await query.answer("缓存已清空")

        # Tasks
        elif cmd == "tasks_refresh": await show_offline_tasks(update, context)
        elif cmd.startswith("task_del"): await handle_task_action(update, context)

        # Cross Copy
        elif cmd == "x_copy_menu": await show_cross_copy_menu(update, context, arg)
        elif cmd.startswith("x_copy_do"):
            sub = arg.split(':', 1)
            await execute_cross_copy(update, context, sub[0], sub[1])
        elif cmd == "confirm_dedupe":
            ids = context.user_data.get('dedupe_ids')
            if ids:
                client = await account_mgr.get_client(user_id)
                await client.delete_file(ids)
            del context.user_data['dedupe_ids']
            await query.answer("清理完成")
        
        elif cmd == "trash_empty":
            await query.answer("执行中...")
            client = await account_mgr.get_client(user_id)
            try: await client.empty_trash()
            except: await client.trash_empty()
            await query.answer("回收站已清空")
            
    except Exception as e:
        print(f"[ERR] CB Error: {e}")
        try: await query.answer("操作失败 (查看日志)", show_alert=True)
        except: pass

# --- TEXT ROUTER ---
async def router_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    msg = update.message.text.strip()
    print(f"[TXT] {msg} (User: {update.effective_user.id})")
    
    # 1. Add Account State
    if context.user_data.get('adding_account'):
        await process_add_account(update, context, msg)
        return
    
    # 2. Rename State
    if context.user_data.get('renaming_id'):
        client = await account_mgr.get_client(update.effective_user.id)
        try: await client.rename_file(context.user_data['renaming_id'], msg)
        except: pass
        del context.user_data['renaming_id']
        await context.bot.send_message(update.effective_chat.id, "✅ 重命名成功")
        return

    # 3. Regex State
    if context.user_data.get('regex_context'):
        await process_regex_rename(update, context, msg)
        return
        
    # 4. Search State
    if context.user_data.get('searching'):
        del context.user_data['searching']
        await show_file_list(update, context, search_query=msg)
        return

    # 5. Commands
    if msg == "📂 文件管理": await show_file_list(update, context)
    elif msg == "👥 账号管理": await show_accounts_menu(update, context)
    elif msg == "📉 离线任务": await show_offline_tasks(update, context)
    elif msg == "☁️ 空间/VIP": await show_quota_info(update, context)
    elif msg == "📊 系统状态": await show_system_status(update, context)
    elif msg == "🔍 搜索文件":
        context.user_data['searching'] = True
        await context.bot.send_message(update.effective_chat.id, "🔍 请输入关键词:", reply_markup=ForceReply(selective=True))
    elif msg == "➕ 添加任务": await context.bot.send_message(update.effective_chat.id, "📥 请直接发送磁力链接或 URL")
    elif msg == "🛠 极客工具箱":
        kb = [[InlineKeyboardButton("AList 信息", callback_data="tool_alist"), InlineKeyboardButton("清理缓存", callback_data="tool_clearcache")]]
        await context.bot.send_message(update.effective_chat.id, "🛠 工具箱", reply_markup=InlineKeyboardMarkup(kb))
    elif msg == "🧹 垃圾清理":
         kb = [[InlineKeyboardButton("🗑 确认清空回收站", callback_data="trash_empty")]]
         await context.bot.send_message(update.effective_chat.id, "⚠️ 确认清空?", reply_markup=InlineKeyboardMarkup(kb))
    
    # 6. Auto Add Task
    elif "http" in msg or "magnet" in msg:
        await add_download_task(update, context, msg)
