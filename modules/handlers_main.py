
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes
from .config import check_auth, WEB_PORT
from .accounts import account_mgr
from .utils import get_local_ip
from .handlers_file import (
    show_file_list, show_file_options, generate_playlist, 
    deduplicate_folder, initiate_regex_rename, process_regex_rename, calculate_folder_size
)
from .handlers_task import show_offline_tasks, handle_task_action, add_download_task

# --- MENUS ---
def main_menu_keyboard():
    keyboard = [
        ["📂 文件管理", "☁️ 空间状态"],
        ["📉 离线任务", "🔍 搜索文件"],
        ["➕ 添加任务", "👥 账号管理"],
        ["🛠 极客工具箱", "🧹 垃圾清理"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- START & LOGIN ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    await context.bot.send_message(
        update.effective_chat.id, 
        "👋 **PikPak Ultimate Bot + AList**\n全能文件管理/离线下载/Web播放/去重", 
        reply_markup=main_menu_keyboard(), 
        parse_mode='Markdown'
    )

async def login_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    args = context.args
    if len(args) < 2:
        await context.bot.send_message(update.effective_chat.id, "❌ 格式: `/login 邮箱 密码`", parse_mode='Markdown')
        return
    
    account_mgr.add_account_credentials(args[0], args[1])
    if await account_mgr.switch_account(update.effective_user.id, args[0]):
        await context.bot.send_message(update.effective_chat.id, f"✅ 登录成功: {args[0]}")
    else:
        await context.bot.send_message(update.effective_chat.id, "❌ 登录失败")

# --- ACCOUNT UI ---
async def show_accounts_menu(update, context):
    accounts = account_mgr.get_accounts_list()
    active = account_mgr.active_user_map.get(str(update.effective_user.id))
    
    kb = []
    for u in accounts:
        status = "✅" if u == active else ""
        kb.append([InlineKeyboardButton(f"{status} {u}", callback_data=f"acc_switch:{u}")])
    
    kb.append([InlineKeyboardButton("➕ 添加账号", callback_data="acc_add")])
    kb.append([InlineKeyboardButton("🔙 关闭", callback_data="close_menu")])
    
    msg = f"👥 **多账号管理**\n当前激活: `{active}`"
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    else:
        await context.bot.send_message(update.effective_chat.id, msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def show_alist_info(update, context):
    ip = get_local_ip()
    text = (
        "🗂️ **AList 本地服务**\n\n"
        f"🔗 地址: `http://{ip}:5244`\n"
        "🔑 默认密码: `123456` (若脚本设置成功)\n\n"
        "⚠️ **如何挂载 PikPak?**\n"
        "1. 浏览器打开 AList 地址并登录\n"
        "2. 存储 -> 添加 -> 驱动选择 PikPak\n"
        "3. 挂载路径: `/PikPak`\n"
        "4. 填入你的 PikPak 账号密码\n\n"
        "💡 挂载后可在本地播放器中使用 WebDAV 观看。"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown')
    else:
        await context.bot.send_message(update.effective_chat.id, text, parse_mode='Markdown')

# --- CALLBACK ROUTER ---
async def router_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    
    parts = data.split(':', 1)
    cmd = parts[0]
    arg = parts[1] if len(parts) > 1 else None

    # Routing
    if cmd == "ls": await show_file_list(update, context, parent_id=arg, edit_msg=True)
    elif cmd == "file": await show_file_options(update, context, arg)
    elif cmd == "page":
        p = arg.split(':')
        pid = p[0] if p[0] else None
        p_num = int(p[1])
        sq = p[2] if len(p) > 2 else None
        await show_file_list(update, context, parent_id=pid, page=p_num, search_query=sq, edit_msg=True)
    
    # Advanced Tools
    elif cmd == "tool_m3u": await generate_playlist(update, context, arg, 'm3u')
    elif cmd == "tool_strm": await generate_playlist(update, context, arg, 'strm')
    elif cmd == "tool_dedupe": await deduplicate_folder(update, context, arg)
    elif cmd == "tool_size": await calculate_folder_size(update, context, arg)
    elif cmd == "tool_regex": await initiate_regex_rename(update, context, arg)
    elif cmd == "tool_alist": await show_alist_info(update, context)

    elif cmd == "confirm_dedupe":
        ids = context.user_data.get('dedupe_ids')
        if ids:
            client = await account_mgr.get_client(user_id)
            try:
                await client.delete_file(ids)
                await query.edit_message_text(f"✅ 已删除 {len(ids)} 个重复文件")
            except Exception as e: await query.edit_message_text(f"❌ 删除失败: {e}")
            del context.user_data['dedupe_ids']
    
    # File Actions
    elif cmd == "act_link":
        client = await account_mgr.get_client(user_id)
        try:
            d = await client.get_download_url(arg)
            if d.get('url'): await context.bot.send_message(update.effective_chat.id, f"🔗 直链:\n`{d['url']}`", parse_mode='Markdown')
        except: pass
    elif cmd == "act_ren":
        context.user_data['renaming_id'] = arg
        await context.bot.send_message(update.effective_chat.id, "✏️ 请回复新文件名:", reply_markup=ForceReply(selective=True))
    elif cmd == "act_cut":
        context.user_data['clipboard'] = {'id': arg, 'op': 'move'}
        await query.answer("✂️ 已剪切，请导航到目标目录粘贴")
        await show_file_list(update, context, edit_msg=True)
    elif cmd == "paste":
        clip = context.user_data.get('clipboard')
        if clip:
            client = await account_mgr.get_client(user_id)
            try:
                await client.move_file(file_ids=[clip['id']], parent_id=arg)
                del context.user_data['clipboard']
                await query.answer("✅ 移动成功")
                await show_file_list(update, context, parent_id=arg, edit_msg=True)
            except: await query.answer("操作失败")
    elif cmd == "paste_cancel":
        if 'clipboard' in context.user_data: del context.user_data['clipboard']
        await show_file_list(update, context, edit_msg=True)
    elif cmd == "act_del":
        client = await account_mgr.get_client(user_id)
        try:
            await client.delete_file([arg])
            await query.edit_message_text("🗑 文件已删除")
        except: pass
    elif cmd == "act_tg":
        await context.bot.send_message(update.effective_chat.id, "⏳ 请使用 /download 下载命令或等待未来版本支持大文件发送。")

    # Tasks
    elif cmd == "tasks_refresh" or cmd.startswith("task_del"):
        await handle_task_action(update, context)

    # Accounts
    elif cmd == "acc_switch":
        if await account_mgr.switch_account(user_id, arg):
            await query.answer(f"✅ 已切换: {arg}")
            await show_accounts_menu(update, context)
    elif cmd == "acc_add": await context.bot.send_message(update.effective_chat.id, "➕ 使用 `/login 邮箱 密码` 添加", parse_mode='Markdown')
    elif cmd == "close_menu": await query.delete_message()
    
    # Cleanup Commands
    elif cmd == "trash_empty":
        client = await account_mgr.get_client(user_id)
        try:
            await client.trash_empty()
            await query.edit_message_text("✅ 回收站已清空")
        except: pass

# --- TEXT ROUTER ---
async def router_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    msg = update.message.text.strip()
    user_id = update.effective_user.id
    
    # 1. State Handling (Rename)
    if 'renaming_id' in context.user_data:
        client = await account_mgr.get_client(user_id)
        try:
            await client.rename_file(file_id=context.user_data['renaming_id'], name=msg)
            await context.bot.send_message(update.effective_chat.id, "✅ 重命名成功")
        except Exception as e: await context.bot.send_message(update.effective_chat.id, f"❌ 失败: {e}")
        del context.user_data['renaming_id']
        return

    # 2. State Handling (Regex Rename)
    if 'regex_context' in context.user_data:
        await process_regex_rename(update, context, msg)
        return

    # 3. Main Menu
    if msg == "📂 文件管理": await show_file_list(update, context)
    elif msg == "👥 账号管理": await show_accounts_menu(update, context)
    elif msg == "📉 离线任务": await show_offline_tasks(update, context)
    elif msg == "☁️ 空间状态":
        client = await account_mgr.get_client(user_id)
        if client:
            info = await client.get_quota_info()
            limit = int(info.get('quota', 0))
            usage = int(info.get('usage', 0))
            await context.bot.send_message(update.effective_chat.id, f"☁️ 已用: {int(usage/1024**3)}GB / 总共: {int(limit/1024**3)}GB")
    
    elif msg == "🛠 极客工具箱":
        kb = [[InlineKeyboardButton("🗂️ AList 服务信息", callback_data="tool_alist")]]
        await context.bot.send_message(
            update.effective_chat.id, 
            "🛠 **极客工具箱**\n- **AList**: 获取本地 WebDAV 服务信息\n- **正则重命名**: 请在文件夹内部使用",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    elif msg == "🧹 垃圾清理":
        kb = [[InlineKeyboardButton("🗑 清空回收站", callback_data="trash_empty")]]
        await context.bot.send_message(update.effective_chat.id, "🧹 垃圾清理:", reply_markup=InlineKeyboardMarkup(kb))
    
    elif msg == "🔍 搜索文件":
        await context.bot.send_message(update.effective_chat.id, "🔍 请回复搜索关键词 (支持 `re:正则`):", reply_markup=ForceReply(selective=True))
    
    elif update.message.reply_to_message and "搜索" in update.message.reply_to_message.text:
        await show_file_list(update, context, search_query=msg)

    elif msg == "➕ 添加任务":
        await context.bot.send_message(update.effective_chat.id, "📥 请直接发送链接 (Magnet/HTTP) 或 .txt 文件")

    # 4. Link Handling (Add Task)
    elif "http" in msg or "magnet:" in msg:
        await add_download_task(update, context, msg)
