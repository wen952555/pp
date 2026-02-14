
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes
from .config import check_auth
from .accounts import account_mgr
from .handlers_file import (
    show_file_list, show_file_options, generate_playlist, 
    deduplicate_folder
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
        "👋 **PikPak Ultimate Bot**\n全能文件管理/离线下载/Web播放/去重", 
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

# --- CALLBACK ROUTER ---
async def router_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    
    # Split Command
    parts = data.split(':', 1)
    cmd = parts[0]
    arg = parts[1] if len(parts) > 1 else None

    # Routing
    if cmd == "ls": await show_file_list(update, context, parent_id=arg, edit_msg=True)
    elif cmd == "file": await show_file_options(update, context, arg)
    elif cmd == "page":
        # Format: page:parent_id:page_num:search_query
        p = arg.split(':')
        pid = p[0] if p[0] else None
        p_num = int(p[1])
        sq = p[2] if len(p) > 2 else None
        await show_file_list(update, context, parent_id=pid, page=p_num, search_query=sq, edit_msg=True)
    
    # File Tools
    elif cmd == "tool_m3u": await generate_playlist(update, context, arg, 'm3u')
    elif cmd == "tool_strm": await generate_playlist(update, context, arg, 'strm')
    elif cmd == "tool_dedupe": await deduplicate_folder(update, context, arg)
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

    # 2. Main Menu
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
        kb = [[InlineKeyboardButton("📋 AList 配置", callback_data="noop")]] # Just placeholder
        await context.bot.send_message(
            update.effective_chat.id, 
            "🛠 **极客工具箱**\n- **正则重命名**: 发送 `re:pattern replacement`\n- **AList**: 参见账号信息",
            parse_mode='Markdown'
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

    # 3. Regex Rename Command
    elif msg.startswith("re:"):
        # Format: re:pattern replacement
        try:
            parts = msg[3:].split(' ', 1)
            if len(parts) == 2:
                # Logic to apply regex on current folder?
                # This requires context of "current folder", usually difficult in stateless chat.
                # We will skip implementation or limit to Root for safety in this demo.
                await context.bot.send_message(update.effective_chat.id, "⚠️ 批量正则重命名需在特定目录下操作，请等待后续更新。")
        except: pass

    # 4. Link Handling (Add Task)
    elif "http" in msg or "magnet:" in msg:
        await add_download_task(update, context, msg)
