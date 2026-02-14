
import os
import shutil
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes
from .config import check_auth, WEB_PORT, DOWNLOAD_PATH
from .accounts import account_mgr
from .utils import get_local_ip, format_bytes
from .handlers_file import (
    show_file_list, show_file_options, generate_playlist, 
    deduplicate_folder, initiate_regex_rename, process_regex_rename, calculate_folder_size,
    show_cross_copy_menu, execute_cross_copy
)
from .handlers_task import show_offline_tasks, handle_task_action, add_download_task

logger = logging.getLogger(__name__)

# --- MENUS ---
def main_menu_keyboard():
    keyboard = [
        ["📂 文件管理", "☁️ 空间/VIP"],
        ["📉 离线任务", "🔍 搜索文件"],
        ["➕ 添加任务", "👥 账号管理"],
        ["🛠 极客工具箱", "🧹 垃圾清理"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- START & LOGIN ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    # Clear any stuck states
    context.user_data.clear()
    
    await context.bot.send_message(
        update.effective_chat.id, 
        "👋 **PikPak Ultimate Bot + AList**\n\n"
        "专为 Termux 打造的全能文件管理助手。\n"
        "✅ 支持多账号秒传\n"
        "✅ 支持离线下载管理\n"
        "✅ 支持正则重命名/去重",
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
    try: await update.message.delete()
    except: pass
    
    msg = await context.bot.send_message(update.effective_chat.id, "⏳ 正在登录...")
    if await account_mgr.switch_account(update.effective_user.id, args[0]):
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"✅ 登录成功: {args[0]}")
    else:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="❌ 登录失败，请检查密码")

# --- ACCOUNT UI ---
async def show_accounts_menu(update, context):
    try:
        accounts = account_mgr.get_accounts_list()
        active = account_mgr.active_user_map.get(str(update.effective_user.id))
        
        kb = []
        for u in accounts:
            status = "🟢" if u == active else "⚪️"
            kb.append([
                InlineKeyboardButton(f"{status} {u}", callback_data=f"acc_switch:{u}"),
                InlineKeyboardButton("❌ 删除", callback_data=f"acc_del:{u}")
            ])
        
        kb.append([InlineKeyboardButton("➕ 添加新账号", callback_data="acc_add")])
        kb.append([InlineKeyboardButton("ℹ️ 查看邀请链接", callback_data="acc_invite")])
        kb.append([InlineKeyboardButton("🔙 关闭", callback_data="close_menu")])
        
        msg = f"👥 **多账号管理**\n当前激活: `{active}`\n共 {len(accounts)} 个账号"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        else:
            await context.bot.send_message(update.effective_chat.id, msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Show accounts error: {e}")
        await context.bot.send_message(update.effective_chat.id, f"❌ 加载账号列表失败: {e}")

async def initiate_add_account(update, context):
    context.user_data['adding_account'] = True
    
    text = (
        "👤 **添加新账号**\n\n"
        "请回复: `邮箱 密码` (空格分隔)\n"
        "⚠️ 为保护隐私，Bot 会在读取后尝试删除您的回复。"
    )
    # Using ForceReply is more reliable for user input
    await context.bot.send_message(
        update.effective_chat.id, 
        text, 
        reply_markup=ForceReply(selective=True), 
        parse_mode='Markdown'
    )
    # Answer callback if exists to stop spinner
    if update.callback_query:
        await update.callback_query.answer()

async def process_add_account(update, context, text):
    logger.info("Processing add account...")
    try:
        # Try split by space first, then newline
        parts = text.split()
        if len(parts) < 2:
            parts = text.split('\n')
            
        if len(parts) < 2:
            await context.bot.send_message(update.effective_chat.id, "❌ 格式错误，请重新添加。\n格式: `邮箱 密码`", parse_mode='Markdown')
            # Don't delete state yet, let them try again
            return
        
        email = parts[0].strip()
        password = parts[1].strip()
        
        # Privacy delete
        try: await update.message.delete()
        except: pass
        
        # Save
        account_mgr.add_account_credentials(email, password)
        
        # Clear state
        if 'adding_account' in context.user_data:
            del context.user_data['adding_account']
            
        msg = await context.bot.send_message(update.effective_chat.id, f"✅ 账号 `{email}` 已保存，正在验证登录...", parse_mode='Markdown')
        
        # Try auto login/switch
        if await account_mgr.switch_account(update.effective_user.id, email):
             await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="🎉 登录验证成功！")
        else:
             await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="⚠️ 账号已保存，但登录验证失败 (可能是密码错误或网络问题)。")
             
    except Exception as e:
        logger.error(f"Add account error: {e}")
        await context.bot.send_message(update.effective_chat.id, f"❌ 处理失败: {e}")
        # Clear state on error to avoid getting stuck
        if 'adding_account' in context.user_data:
            del context.user_data['adding_account']

async def show_quota_info(update, context):
    user_id = update.effective_user.id
    msg = await context.bot.send_message(update.effective_chat.id, "⏳ 正在获取云端数据...")
    
    try:
        client = await account_mgr.get_client(user_id)
        if not client:
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="❌ 未登录账号")
            return

        # Fetch Quota
        info = await client.get_quota_info()
        # Ensure values are ints
        limit = int(info.get('quota', 1))
        usage = int(info.get('usage', 0))
        
        # Calculate Percentage
        if limit == 0: limit = 1 # Prevent div by zero
        percent = (usage / limit) * 100
        bars = int(percent / 10)
        if bars > 10: bars = 10
        progress_bar = "▓" * bars + "░" * (10 - bars)
        
        # Fetch VIP status (safely)
        vip_status = "未知"
        expire = "-"
        nickname = "用户"
        try:
            me = await client.get_user_info()
            if me:
                vip_status = "👑 VIP会员" if me.get('vip_status') == 'ok' else "👤 普通用户"
                expire = me.get('vip_expire', 'N/A')
                nickname = me.get('name', 'Unknown')
        except Exception as e:
            logger.warning(f"Failed to get VIP info: {e}")

        text = (
            f"👤 **{nickname}**\n"
            f"{vip_status} (到期: {expire})\n\n"
            f"**空间使用率:**\n"
            f"`[{progress_bar}] {percent:.1f}%`\n\n"
            f"已用: `{format_bytes(usage)}`\n"
            f"总共: `{format_bytes(limit)}`"
        )
        
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Quota error: {e}")
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 获取状态失败: {e}")

async def show_invite_link(update, context):
    user_id = update.effective_user.id
    try:
        # Fallback/Generic link
        invite_url = "https://mypikpak.com/invite" 
        await update.callback_query.edit_message_text(
            f"🤝 **邀请信息**\n\n请前往 App 获取您的专属邀请链接。\n官方地址: {invite_url}",
            parse_mode='Markdown'
        )
    except:
        await update.callback_query.answer("功能暂不可用")

async def clear_local_cache(update, context):
    try:
        if os.path.exists(DOWNLOAD_PATH):
            shutil.rmtree(DOWNLOAD_PATH)
            os.makedirs(DOWNLOAD_PATH)
        await update.callback_query.answer("✅ 本地临时缓存已清理", show_alert=True)
    except Exception as e:
         await update.callback_query.answer(f"❌ 清理失败: {e}", show_alert=True)

# --- CALLBACK ROUTER ---
async def router_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # Don't auto answer here, let individual handlers answer or edit, 
    # but to be safe against timeout, we can answer empty.
    try: await query.answer()
    except: pass
    
    data = query.data
    user_id = update.effective_user.id
    print(f"[Callback] {data}") # Debug log

    parts = data.split(':', 1)
    cmd = parts[0]
    arg = parts[1] if len(parts) > 1 else None

    # Global Cancel
    if cmd == "cancel_state":
        context.user_data.clear()
        await query.edit_message_text("🚫 操作已取消")
        return
    
    # Menus
    if cmd == "close_menu": await query.delete_message()

    # File System
    elif cmd in ["ls", "file", "page"]:
        # Relay to handlers_file
        if cmd == "ls": await show_file_list(update, context, parent_id=arg, edit_msg=True)
        elif cmd == "file": await show_file_options(update, context, arg)
        elif cmd == "page":
            p = arg.split(':')
            await show_file_list(update, context, parent_id=p[0] or None, page=int(p[1]), search_query=p[2] if len(p)>2 else None, edit_msg=True)

    # File Tools
    elif cmd.startswith("tool_"):
        if cmd == "tool_m3u": await generate_playlist(update, context, arg, 'm3u')
        elif cmd == "tool_strm": await generate_playlist(update, context, arg, 'strm')
        elif cmd == "tool_dedupe": await deduplicate_folder(update, context, arg)
        elif cmd == "tool_size": await calculate_folder_size(update, context, arg)
        elif cmd == "tool_regex": await initiate_regex_rename(update, context, arg)
        elif cmd == "tool_alist": await show_alist_info(update, context)
        elif cmd == "tool_clearcache": await clear_local_cache(update, context)

    # File Actions
    elif cmd.startswith("act_"):
        if cmd == "act_link":
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
            try: await query.answer("✂️ 已剪切，请导航到目标目录粘贴")
            except: pass
            await show_file_list(update, context, edit_msg=True)
        elif cmd == "act_del":
            client = await account_mgr.get_client(user_id)
            try:
                await client.delete_file([arg])
                await query.edit_message_text("🗑 文件已删除")
            except: pass
        elif cmd == "act_tg":
            await context.bot.send_message(update.effective_chat.id, "⏳ 仅支持通过 /download 下载，TG大文件上传受限。")

    # Paste
    elif cmd == "paste":
        clip = context.user_data.get('clipboard')
        if clip:
            client = await account_mgr.get_client(user_id)
            try:
                await client.move_file(file_ids=[clip['id']], parent_id=arg)
                del context.user_data['clipboard']
                try: await query.answer("✅ 移动成功")
                except: pass
                await show_file_list(update, context, parent_id=arg, edit_msg=True)
            except Exception as e: 
                try: await query.answer(f"操作失败: {e}", show_alert=True)
                except: pass
    elif cmd == "paste_cancel":
        if 'clipboard' in context.user_data: del context.user_data['clipboard']
        await show_file_list(update, context, edit_msg=True)

    # Tasks
    elif cmd == "tasks_refresh" or cmd.startswith("task_del"):
        await handle_task_action(update, context)

    # Accounts
    elif cmd == "acc_switch":
        msg = await context.bot.send_message(update.effective_chat.id, f"⏳ 正在切换至 {arg}...")
        if await account_mgr.switch_account(user_id, arg):
            try: await context.bot.delete_message(update.effective_chat.id, msg.message_id)
            except: pass
            await show_accounts_menu(update, context)
        else:
             await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 切换失败，登录错误。")

    elif cmd == "acc_add": await initiate_add_account(update, context)
    elif cmd == "acc_del":
        if account_mgr.remove_account(arg):
            try: await query.answer(f"🗑 已删除账号: {arg}")
            except: pass
            await show_accounts_menu(update, context)
    elif cmd == "acc_invite": await show_invite_link(update, context)

    # Cross Copy
    elif cmd.startswith("x_copy"):
        if cmd == "x_copy_menu": await show_cross_copy_menu(update, context, arg)
        elif cmd == "x_copy_do":
            sub = arg.split(':', 1)
            await execute_cross_copy(update, context, sub[0], sub[1])

    # Dedupe Confirm
    elif cmd == "confirm_dedupe":
        ids = context.user_data.get('dedupe_ids')
        if ids:
            client = await account_mgr.get_client(user_id)
            try:
                await client.delete_file(ids)
                await query.edit_message_text(f"✅ 已删除 {len(ids)} 个重复文件")
            except: await query.edit_message_text("❌ 删除失败")
            del context.user_data['dedupe_ids']

    # Trash
    elif cmd == "trash_empty":
        client = await account_mgr.get_client(user_id)
        try:
            # Try multiple known methods for compatibility
            if hasattr(client, 'empty_trash'): await client.empty_trash()
            elif hasattr(client, 'trash_empty'): await client.trash_empty()
            else: raise Exception("API Method not found")
            await query.edit_message_text("✅ 回收站已清空")
        except Exception as e:
            try: await query.answer(f"❌ 失败: {e}", show_alert=True)
            except: await context.bot.send_message(update.effective_chat.id, f"❌ 清空失败: {e}")

async def show_alist_info(update, context):
    try:
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
    except Exception as e:
        err_text = f"❌ 获取信息失败: {e}"
        if update.callback_query: await update.callback_query.edit_message_text(err_text)
        else: await context.bot.send_message(update.effective_chat.id, err_text)

# --- TEXT ROUTER ---
async def router_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    msg = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Print debug info
    print(f"[Router Text] User: {user_id}, Msg: {msg}")

    # --- 1. STATE HANDLING (Higher Priority) ---
    
    if context.user_data.get('adding_account'):
        await process_add_account(update, context, msg)
        return

    if context.user_data.get('renaming_id'):
        client = await account_mgr.get_client(user_id)
        try:
            await client.rename_file(file_id=context.user_data['renaming_id'], name=msg)
            await context.bot.send_message(update.effective_chat.id, "✅ 重命名成功")
        except Exception as e: await context.bot.send_message(update.effective_chat.id, f"❌ 失败: {e}")
        del context.user_data['renaming_id']
        return

    if context.user_data.get('regex_context'):
        await process_regex_rename(update, context, msg)
        return
        
    if context.user_data.get('searching'):
        del context.user_data['searching'] # One-time flag
        await show_file_list(update, context, search_query=msg)
        return

    # --- 2. MENU COMMANDS ---
    
    if msg == "📂 文件管理": await show_file_list(update, context)
    
    elif msg == "👥 账号管理": await show_accounts_menu(update, context)
    
    elif msg == "📉 离线任务": await show_offline_tasks(update, context)
    
    elif msg == "☁️ 空间/VIP": await show_quota_info(update, context)
    
    elif msg == "🛠 极客工具箱":
        kb = [
            [InlineKeyboardButton("🗂️ AList 服务信息", callback_data="tool_alist")],
            [InlineKeyboardButton("🧹 清理本地下载缓存", callback_data="tool_clearcache")]
        ]
        await context.bot.send_message(
            update.effective_chat.id, 
            "🛠 **极客工具箱**",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    elif msg == "🧹 垃圾清理":
        kb = [[InlineKeyboardButton("🗑 确认清空回收站", callback_data="trash_empty")]]
        await context.bot.send_message(update.effective_chat.id, "⚠️ 确认要清空回收站吗？操作不可恢复。", reply_markup=InlineKeyboardMarkup(kb))
    
    elif msg == "🔍 搜索文件":
        context.user_data['searching'] = True
        await context.bot.send_message(update.effective_chat.id, "🔍 请发送搜索关键词 (支持 `re:` 正则表达式):", reply_markup=ForceReply(selective=True))
    
    elif msg == "➕ 添加任务":
        await context.bot.send_message(update.effective_chat.id, "📥 请直接发送链接 (Magnet/HTTP) 或上传 .txt 文件")

    # --- 3. AUTO-DETECT LINKS ---
    elif "http" in msg or "magnet:" in msg:
        await add_download_task(update, context, msg)
        
    # --- 4. FALLBACK ---
    else:
        # Check reply to search
        if update.message.reply_to_message and "搜索" in update.message.reply_to_message.text:
             await show_file_list(update, context, search_query=msg)
