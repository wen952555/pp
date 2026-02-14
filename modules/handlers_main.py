
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
    context.user_data.clear()
    
    await context.bot.send_message(
        update.effective_chat.id, 
        "👋 **PikPak Ultimate Bot**\n"
        "Termux 专用版 | 状态: 在线\n\n"
        "👇 请从下方菜单选择功能:",
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
        "请在下方直接回复账号和密码 (用空格分开)\n"
        "例如: `example@gmail.com mypassword123`\n\n"
        "💡 提示: Bot 会自动尝试删除您的回复以保护隐私。"
    )
    # Using ForceReply ensures the client focuses input
    await context.bot.send_message(
        update.effective_chat.id, 
        text, 
        reply_markup=ForceReply(selective=True), 
        parse_mode='Markdown'
    )

async def process_add_account(update, context, text):
    logger.info(f"Processing Account Add attempt for user {update.effective_user.id}")
    try:
        # Robust split: handles space, tab, newline automatically
        parts = text.split()
            
        if len(parts) < 2:
            await context.bot.send_message(update.effective_chat.id, "❌ 格式错误\n请回复: `邮箱 密码` (中间要有空格)", parse_mode='Markdown')
            # Keep state True so they can try again immediately
            return
        
        email = parts[0].strip()
        password = parts[1].strip()
        
        # Privacy delete
        try: await update.message.delete()
        except: pass
        
        msg = await context.bot.send_message(update.effective_chat.id, f"⏳ 已识别账号 `{email}`，正在验证登录...", parse_mode='Markdown')
        
        # Add to manager
        account_mgr.add_account_credentials(email, password)
        
        # Try login
        if await account_mgr.switch_account(update.effective_user.id, email):
             await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="🎉 **登录成功！**\n现在可以使用该账号了。")
             # Only clear state on success
             if 'adding_account' in context.user_data: del context.user_data['adding_account']
        else:
             await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="⚠️ **验证失败**\n账号已保存，但登录失败 (密码错误?)。\n您可以尝试重新添加。")
             if 'adding_account' in context.user_data: del context.user_data['adding_account']
             
    except Exception as e:
        logger.error(f"Add account exception: {e}")
        await context.bot.send_message(update.effective_chat.id, f"❌ 程序错误: {e}")
        if 'adding_account' in context.user_data: del context.user_data['adding_account']

async def show_quota_info(update, context):
    user_id = update.effective_user.id
    msg = await context.bot.send_message(update.effective_chat.id, "⏳ 获取数据中...")
    
    try:
        client = await account_mgr.get_client(user_id)
        if not client:
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="❌ 未登录 (请在账号管理中登录)")
            return

        info = await client.get_quota_info()
        limit = int(info.get('quota', 1))
        usage = int(info.get('usage', 0))
        
        if limit == 0: limit = 1
        percent = (usage / limit) * 100
        bars = int(percent / 10)
        if bars > 10: bars = 10
        progress_bar = "🟦" * bars + "⬜" * (10 - bars)
        
        try:
            me = await client.get_user_info()
            vip_status = "👑 VIP" if me.get('vip_status') == 'ok' else "👤 普通"
            expire = me.get('vip_expire', 'N/A')
            nickname = me.get('name', 'Unknown')
        except:
            vip_status, expire, nickname = ("Unknown", "-", "-")

        text = (
            f"📊 **空间状态**\n\n"
            f"用户: `{nickname}`\n"
            f"身份: {vip_status} (到期: {expire})\n\n"
            f"已用: `{format_bytes(usage)}`\n"
            f"总量: `{format_bytes(limit)}`\n"
            f"`[{progress_bar}] {percent:.1f}%`"
        )
        
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=text, parse_mode='Markdown')
        
    except Exception as e:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 获取失败: {e}")

async def show_invite_link(update, context):
    invite_url = "https://mypikpak.com/invite" 
    await update.callback_query.edit_message_text(
        f"🤝 **邀请有礼**\n\n您的专属邀请链接: {invite_url}\n(请在App中查看详情)",
        parse_mode='Markdown'
    )

async def clear_local_cache(update, context):
    try:
        if os.path.exists(DOWNLOAD_PATH):
            shutil.rmtree(DOWNLOAD_PATH)
            os.makedirs(DOWNLOAD_PATH)
        await update.callback_query.answer("✅ 缓存已清理", show_alert=True)
    except Exception as e:
         await update.callback_query.answer(f"❌ 失败: {e}", show_alert=True)

# --- CALLBACK ROUTER ---
async def router_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer() 
    except: pass
    
    data = query.data
    user_id = update.effective_user.id
    
    # Debug logging
    logger.info(f"Callback: {data} from {user_id}")

    parts = data.split(':', 1)
    cmd = parts[0]
    
    # Safe Argument Parsing
    arg = None
    if len(parts) > 1:
        arg = parts[1]
        if arg == "" or arg == "None": arg = None

    # Global Cancel
    if cmd == "cancel_state":
        context.user_data.clear()
        await query.edit_message_text("🚫 操作已取消")
        return
    
    if cmd == "close_menu": await query.delete_message()

    # --- File System ---
    elif cmd == "ls": await show_file_list(update, context, parent_id=arg, edit_msg=True)
    elif cmd == "file": await show_file_options(update, context, arg)
    elif cmd == "page":
        # Format: page:parent_id:page_num:search_query
        try:
            p = arg.split(':') if arg else []
            pid = p[0] if len(p) > 0 and p[0] not in ["None", ""] else None
            pnum = int(p[1]) if len(p) > 1 else 0
            sq = p[2] if len(p) > 2 else None
            await show_file_list(update, context, parent_id=pid, page=pnum, search_query=sq, edit_msg=True)
        except Exception as e:
            logger.error(f"Page error: {e}")
            await show_file_list(update, context, edit_msg=True)

    # --- File Actions ---
    elif cmd.startswith("act_"):
        if cmd == "act_link":
            client = await account_mgr.get_client(user_id)
            try:
                d = await client.get_download_url(arg)
                if d.get('url'): await context.bot.send_message(update.effective_chat.id, f"🔗 **直链地址**:\n`{d['url']}`", parse_mode='Markdown')
            except: pass
        elif cmd == "act_ren":
            context.user_data['renaming_id'] = arg
            await context.bot.send_message(update.effective_chat.id, "✏️ 请输入新的名称:", reply_markup=ForceReply(selective=True))
        elif cmd == "act_cut":
            context.user_data['clipboard'] = {'id': arg, 'op': 'move'}
            await show_file_list(update, context, edit_msg=True)
            await context.bot.send_message(update.effective_chat.id, "✂️ 文件已剪切，请进入目标文件夹点击“粘贴”")
        elif cmd == "act_del":
            client = await account_mgr.get_client(user_id)
            try:
                await client.delete_file([arg])
                await query.edit_message_text("🗑 文件已删除")
            except Exception as e: 
                await query.edit_message_text(f"❌ 删除失败: {e}")
        elif cmd == "act_tg":
            await context.bot.send_message(update.effective_chat.id, "⏳ 抱歉，Bot直接上传文件受Telegram API限制较大，建议使用直链或AList下载。")

    # --- Paste ---
    elif cmd == "paste":
        clip = context.user_data.get('clipboard')
        if clip:
            client = await account_mgr.get_client(user_id)
            try:
                await client.move_file(file_ids=[clip['id']], parent_id=arg)
                del context.user_data['clipboard']
                await query.answer("✅ 移动完成")
                await show_file_list(update, context, parent_id=arg, edit_msg=True)
            except Exception as e: 
                await query.answer(f"❌ 移动失败: {e}", show_alert=True)
    elif cmd == "paste_cancel":
        if 'clipboard' in context.user_data: del context.user_data['clipboard']
        await show_file_list(update, context, edit_msg=True)

    # --- Tools ---
    elif cmd == "tool_m3u": await generate_playlist(update, context, arg, 'm3u')
    elif cmd == "tool_strm": await generate_playlist(update, context, arg, 'strm')
    elif cmd == "tool_dedupe": await deduplicate_folder(update, context, arg)
    elif cmd == "tool_size": await calculate_folder_size(update, context, arg)
    elif cmd == "tool_regex": await initiate_regex_rename(update, context, arg)
    elif cmd == "tool_alist": await show_alist_info(update, context)
    elif cmd == "tool_clearcache": await clear_local_cache(update, context)

    # --- Tasks ---
    elif cmd == "tasks_refresh": await show_offline_tasks(update, context)
    elif cmd.startswith("task_del"): await handle_task_action(update, context)

    # --- Accounts ---
    elif cmd == "acc_switch":
        msg = await context.bot.send_message(update.effective_chat.id, f"⏳ 切换中: {arg}...")
        if await account_mgr.switch_account(user_id, arg):
            try: await context.bot.delete_message(update.effective_chat.id, msg.message_id)
            except: pass
            await show_accounts_menu(update, context)
        else:
             await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 切换失败")
    elif cmd == "acc_add": await initiate_add_account(update, context)
    elif cmd == "acc_del":
        if account_mgr.remove_account(arg):
            await show_accounts_menu(update, context)
    elif cmd == "acc_invite": await show_invite_link(update, context)

    # --- Cross Copy & Dedupe ---
    elif cmd == "x_copy_menu": await show_cross_copy_menu(update, context, arg)
    elif cmd.startswith("x_copy_do"):
        sub = arg.split(':', 1)
        await execute_cross_copy(update, context, sub[0], sub[1])
    elif cmd == "confirm_dedupe":
        ids = context.user_data.get('dedupe_ids')
        if ids:
            client = await account_mgr.get_client(user_id)
            try:
                await client.delete_file(ids)
                await query.edit_message_text(f"✅ 已清理 {len(ids)} 个重复项")
            except: await query.edit_message_text("❌ 清理失败")
            del context.user_data['dedupe_ids']
    elif cmd == "trash_empty":
        client = await account_mgr.get_client(user_id)
        try:
            if hasattr(client, 'empty_trash'): await client.empty_trash()
            else: await client.trash_empty() # Try alternate method
            await query.edit_message_text("✅ 回收站已清空")
        except: await query.edit_message_text("❌ 清空失败")

async def show_alist_info(update, context):
    ip = get_local_ip()
    text = (
        "🗂️ **AList 连接信息**\n"
        f"地址: `http://{ip}:5244`\n"
        "默认密码: `123456`\n\n"
        "💡 **挂载教程**:\n"
        "1. 登录 AList 后台\n"
        "2. 点击『存储』->『添加』\n"
        "3. 驱动选择 **PikPak**\n"
        "4. 挂载路径填 `/`\n"
        "5. 输入你的 PikPak 账号密码"
    )
    if update.callback_query: await update.callback_query.edit_message_text(text, parse_mode='Markdown')
    else: await context.bot.send_message(update.effective_chat.id, text, parse_mode='Markdown')

# --- TEXT ROUTER ---
async def router_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update, context): return
    
    msg = update.message.text.strip()
    logger.info(f"Text Input: {msg}")

    # 1. State: Adding Account
    if context.user_data.get('adding_account'):
        await process_add_account(update, context, msg)
        return

    # 2. State: Renaming
    if context.user_data.get('renaming_id'):
        client = await account_mgr.get_client(update.effective_user.id)
        try:
            await client.rename_file(file_id=context.user_data['renaming_id'], name=msg)
            await context.bot.send_message(update.effective_chat.id, "✅ 重命名成功")
        except Exception as e:
            await context.bot.send_message(update.effective_chat.id, f"❌ 重命名失败: {e}")
        del context.user_data['renaming_id']
        return

    # 3. State: Regex
    if context.user_data.get('regex_context'):
        await process_regex_rename(update, context, msg)
        return
        
    # 4. State: Searching
    if context.user_data.get('searching'):
        del context.user_data['searching']
        await show_file_list(update, context, search_query=msg)
        return

    # 5. Commands
    if msg == "📂 文件管理": await show_file_list(update, context)
    elif msg == "👥 账号管理": await show_accounts_menu(update, context)
    elif msg == "📉 离线任务": await show_offline_tasks(update, context)
    elif msg == "☁️ 空间/VIP": await show_quota_info(update, context)
    elif msg == "🛠 极客工具箱":
        kb = [[InlineKeyboardButton("🗂️ AList 信息", callback_data="tool_alist"), InlineKeyboardButton("🧹 清理缓存", callback_data="tool_clearcache")]]
        await context.bot.send_message(update.effective_chat.id, "🛠 **工具箱**", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    elif msg == "🧹 垃圾清理":
        kb = [[InlineKeyboardButton("🗑 确认清空回收站", callback_data="trash_empty")]]
        await context.bot.send_message(update.effective_chat.id, "⚠️ **警告**: 确认清空回收站？此操作不可逆。", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    elif msg == "🔍 搜索文件":
        context.user_data['searching'] = True
        await context.bot.send_message(update.effective_chat.id, "🔍 请输入关键词:", reply_markup=ForceReply(selective=True))
    elif msg == "➕ 添加任务":
        await context.bot.send_message(update.effective_chat.id, "📥 请发送下载链接 (Http/Magnet) 或上传种子文件。")

    # 6. Auto-Link
    elif "http" in msg or "magnet:" in msg:
        await add_download_task(update, context, msg)
    else:
        # Check replies
        if update.message.reply_to_message:
            txt = update.message.reply_to_message.text
            if "关键词" in txt: await show_file_list(update, context, search_query=msg)
            elif "回复账号" in txt: await process_add_account(update, context, msg)
