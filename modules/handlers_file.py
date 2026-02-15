
import re
import io
import zipfile
import time
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from .accounts import account_mgr
from .config import WEB_PORT, DOWNLOAD_PATH
from .utils import get_local_ip, get_base_url, format_bytes

# --- FILE LISTING ---
async def show_file_list(update: Update, context: ContextTypes.DEFAULT_TYPE, parent_id=None, page=0, edit_msg=False, search_query=None):
    user_id = update.effective_user.id
    
    if edit_msg and update.callback_query:
        try: 
            # Temporary loading text to prevent "Button already pressed" feeling
            # But don't do this if we want to be super fast, 
            # though it helps user know something is happening.
            # However, for pagination, direct switch is better.
            pass 
        except: pass

    client = await account_mgr.get_client(user_id)
    if not client:
        text = "⚠️ **未登录**\n请前往 [👥 账号管理] 菜单登录。"
        if edit_msg: 
            try: await update.callback_query.edit_message_text(text, parse_mode='Markdown')
            except: pass
        else: await context.bot.send_message(update.effective_chat.id, text, parse_mode='Markdown')
        return

    if parent_id in ["None", "", "root"]: parent_id = None
    
    if search_query:
        context.user_data['current_search_query'] = search_query
    
    active_search = None
    if parent_id == "SEARCH":
        active_search = context.user_data.get('current_search_query')
        parent_id = None
    elif search_query:
        active_search = search_query

    try:
        try:
            resp = await client.file_list(parent_id=parent_id)
        except Exception as e:
            print(f"API Error (1st try): {e}")
            client = await account_mgr.get_client(user_id, force_refresh=True)
            if client:
                resp = await client.file_list(parent_id=parent_id)
            else:
                raise e

        raw_files = resp.get('files', []) if isinstance(resp, dict) else resp
        if not isinstance(raw_files, list): raw_files = []

        files = []
        if active_search:
            is_regex = active_search.startswith("re:")
            term = active_search[3:] if is_regex else active_search
            for f in raw_files:
                fname = f.get('name', '') or ''
                if is_regex:
                    try: 
                        if re.search(term, fname, re.IGNORECASE): files.append(f)
                    except: pass
                else:
                    if term.lower() in fname.lower(): files.append(f)
        else:
            files = raw_files

        files.sort(key=lambda x: (x.get('kind') != 'drive#folder', x.get('name', '') or ''))

        items_per_page = 10
        total_items = len(files)
        max_page = max(0, (total_items - 1) // items_per_page)
        if page > max_page: page = max_page
        
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        current_files = files[start_idx:end_idx]

        keyboard = []
        
        nav_top = []
        if active_search or parent_id:
             nav_top.append(InlineKeyboardButton("🏠 首页", callback_data="ls:"))
        
        refresh_pid = "SEARCH" if active_search else (parent_id if parent_id else "")
        nav_top.append(InlineKeyboardButton("🔄 刷新", callback_data=f"ls:{refresh_pid}"))
        keyboard.append(nav_top)

        for f in current_files:
            name = f.get('name', 'Unknown')
            fid = f['id']
            dname = name[:20] + ".." if len(name) > 20 else name
            
            if f.get('kind') == 'drive#folder':
                keyboard.append([
                    InlineKeyboardButton(f"📁 {dname}", callback_data=f"ls:{fid}"),
                    InlineKeyboardButton("⚙️", callback_data=f"act_ren:{fid}")
                ])
            else:
                sz = format_bytes(f.get('size', 0))
                keyboard.append([InlineKeyboardButton(f"📄 {dname} ({sz})", callback_data=f"file:{fid}")])

        nav_row = []
        page_pid = "SEARCH" if active_search else (parent_id if parent_id else "")
        
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"page:{page_pid}:{page-1}"))
        
        nav_row.append(InlineKeyboardButton(f"{page+1}/{max_page+1}", callback_data="noop"))
        
        if page < max_page:
            nav_row.append(InlineKeyboardButton("➡️", callback_data=f"page:{page_pid}:{page+1}"))
        
        keyboard.append(nav_row)

        if not active_search:
            tool_pid = parent_id if parent_id else ""
            keyboard.append([
                InlineKeyboardButton("🎬 M3U", callback_data=f"tool_m3u:{tool_pid}"),
                InlineKeyboardButton("📊 统计", callback_data=f"tool_size:{tool_pid}"),
                InlineKeyboardButton("🛠 批量", callback_data=f"tool_regex:{tool_pid}")
            ])

        if 'clipboard' in context.user_data:
            op = "移动" if context.user_data['clipboard']['op'] == 'move' else "复制"
            paste_pid = parent_id if parent_id else ""
            keyboard.append([
                InlineKeyboardButton(f"📋 粘贴{op}", callback_data=f"paste:{paste_pid}"),
                InlineKeyboardButton("❌ 取消", callback_data="paste_cancel")
            ])

        username = account_mgr.active_user_map.get(str(user_id), "Unknown")
        
        if active_search:
            path_str = f"🔍 搜索: `{active_search}`"
        else:
            path_str = f"📂 路径: `{parent_id if parent_id else '根目录'}`"
            
        text = f"👤 **{username}**\n{path_str}\n📦 项目数: {total_items}"

        reply_markup = InlineKeyboardMarkup(keyboard)

        if edit_msg:
            try: 
                await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            except BadRequest as e:
                # Ignore "Message is not modified" errors (Anti-Flood)
                if "not modified" in str(e):
                    pass
                else:
                    await update.callback_query.answer("⚠️ 加载失败", show_alert=False)
            except Exception as e:
                pass
        else:
            await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        err_msg = f"❌ **列表加载出错**\n{str(e)}\n请尝试 `/reset` 重置。"
        if edit_msg:
            try: await update.callback_query.edit_message_text(err_msg, parse_mode='Markdown')
            except: pass
        else:
            await context.bot.send_message(update.effective_chat.id, err_msg, parse_mode='Markdown')

async def show_file_options(update: Update, context: ContextTypes.DEFAULT_TYPE, file_id: str):
    if update.callback_query:
        try: await update.callback_query.edit_message_text("⏳ 获取详情...")
        except: pass
        
    user_id = update.effective_user.id
    client = await account_mgr.get_client(user_id)
    try:
        # Get base url (refresh log check)
        base_url = get_base_url(WEB_PORT)
        
        data = await client.get_download_url(file_id)
        name = data.get('name', 'Unknown')
        
        play_link = f"{base_url}/play?id={file_id}&user={user_id}"
        
        text = f"📄 **{name}**"
        if "trycloudflare.com" in base_url:
            text += f"\n🌐 隧道在线 (无视VPN)"
        else:
            text += f"\n🏠 局域网模式"
        
        keyboard = [
            [InlineKeyboardButton("🖥️ 在线播放 / 调用 APP", url=play_link)],
            [InlineKeyboardButton("🔗 直链", callback_data=f"act_link:{file_id}"), InlineKeyboardButton("✏️ 重命名", callback_data=f"act_ren:{file_id}")],
            [InlineKeyboardButton("✂️ 剪切", callback_data=f"act_cut:{file_id}"), InlineKeyboardButton("🗑 删除", callback_data=f"act_del:{file_id}")]
        ]
        
        if len(account_mgr.get_accounts_list()) > 1:
            keyboard.append([InlineKeyboardButton("🚀 跨号秒传", callback_data=f"x_copy_menu:{file_id}")])
            
        keyboard.append([InlineKeyboardButton("🔙 返回", callback_data="ls:")])
        
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ 失败: {e}")

async def calculate_folder_size(update, context, folder_id):
    if update.callback_query: await update.callback_query.answer("计算中...")
    user_id = update.effective_user.id
    client = await account_mgr.get_client(user_id)
    msg = await context.bot.send_message(update.effective_chat.id, "⏳ 正在计算...")
    try:
        resp = await client.file_list(parent_id=folder_id)
        files = resp.get('files', []) if isinstance(resp, dict) else resp
        total = sum(int(f.get('size', 0)) for f in files)
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"📊 大小: {format_bytes(total)}")
    except: pass

async def initiate_regex_rename(update, context, folder_id):
    context.user_data['regex_context'] = folder_id
    await context.bot.send_message(update.effective_chat.id, "🛠 回复: `正则 替换`", reply_markup=ForceReply(selective=True))

async def process_regex_rename(update, context, text):
    folder_id = context.user_data.get('regex_context')
    del context.user_data['regex_context']
    try:
        parts = text.split()
        if len(parts) < 1: return
        pat, repl = parts[0], parts[1] if len(parts)>1 else ""
        client = await account_mgr.get_client(update.effective_user.id)
        msg = await context.bot.send_message(update.effective_chat.id, "Processing...")
        resp = await client.file_list(parent_id=folder_id)
        count = 0
        for f in resp.get('files', []):
            new_n = re.sub(pat, repl, f.get('name',''))
            if new_n != f.get('name'):
                await client.rename_file(file_id=f['id'], name=new_n)
                count+=1
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"✅ Updated {count}")
    except Exception as e:
        await context.bot.send_message(update.effective_chat.id, f"Error: {e}")

async def deduplicate_folder(update, context, folder_id):
    if update.callback_query: await update.callback_query.answer("Scanning...")
    client = await account_mgr.get_client(update.effective_user.id)
    msg = await context.bot.send_message(update.effective_chat.id, "🔍 Scanning...")
    try:
        resp = await client.file_list(parent_id=folder_id)
        seen, dupes = {}, []
        for f in resp.get('files', []):
            if f.get('hash') in seen: dupes.append(f)
            else: seen[f.get('hash')] = f
        if not dupes: await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="✅ No duplicates")
        else:
            context.user_data['dedupe_ids'] = [x['id'] for x in dupes]
            kb = [[InlineKeyboardButton("Delete Dupes", callback_data="confirm_dedupe")], [InlineKeyboardButton("Cancel", callback_data="close_menu")]]
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"Found {len(dupes)} dupes", reply_markup=InlineKeyboardMarkup(kb))
    except: pass

async def generate_playlist(update, context, folder_id, mode='m3u'):
    if update.callback_query: await update.callback_query.answer("Generating...")
    client = await account_mgr.get_client(update.effective_user.id)
    msg = await context.bot.send_message(update.effective_chat.id, "⏳ Generating...")
    try:
        resp = await client.file_list(parent_id=folder_id)
        vids = [f for f in resp.get('files', []) if f.get('name','').endswith(('.mp4','.mkv'))]
        out = io.BytesIO()
        out.write("#EXTM3U\n".encode('utf-8'))
        
        # Use tunnel URL for M3U as well
        base_url = get_base_url(WEB_PORT)
        
        for f in vids:
             # We use the local player proxy link for M3U so it works externally via tunnel
             # Original direct link expires, but local proxy refreshes it? 
             # Actually, best to use the proxy link: http://domain/play?id=...
             # But M3U players expect media. The /play endpoint returns HTML.
             # We need a stream endpoint or use the direct link.
             # Direct links from API have expiry. 
             # For now, let's use direct link from API as per original code, but maybe consider proxying later.
             d = await client.get_download_url(f['id'])
             if d.get('url'): out.write(f"#EXTINF:-1,{f['name']}\n{d['url']}\n".encode('utf-8'))
        
        out.seek(0)
        await context.bot.send_document(update.effective_chat.id, out, filename="list.m3u")
        await context.bot.delete_message(update.effective_chat.id, msg.message_id)
    except Exception as e:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"Error: {e}")

async def show_cross_copy_menu(update, context, file_id):
    users = account_mgr.get_accounts_list()
    kb = [[InlineKeyboardButton(f"To {u}", callback_data=f"x_copy_do:{file_id}:{u}")] for u in users if u != account_mgr.active_user_map.get(str(update.effective_user.id))]
    kb.append([InlineKeyboardButton("Cancel", callback_data="close_menu")])
    await update.callback_query.edit_message_text("Select Target:", reply_markup=InlineKeyboardMarkup(kb))

async def execute_cross_copy(update, context, file_id, target):
    client = await account_mgr.get_client(update.effective_user.id)
    tgt = await account_mgr.get_client(update.effective_user.id, specific_username=target)
    try:
        d = await client.get_download_url(file_id)
        await tgt.offline_download(d['url'])
        await update.callback_query.edit_message_text(f"✅ Sent to {target}")
    except Exception as e: await update.callback_query.edit_message_text(f"Error: {e}")

async def upload_tg_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    client = await account_mgr.get_client(user_id)
    if not client: 
        await context.bot.send_message(update.effective_chat.id, "⚠️ 请先登录")
        return

    # Check for document, video, or photo
    attachment = None
    filename = "file_" + str(int(time.time()))

    if update.message.document:
        attachment = update.message.document
        filename = attachment.file_name or filename
    elif update.message.video:
        attachment = update.message.video
        filename = f"video_{int(time.time())}.mp4"
    elif update.message.photo:
        # Photo is a list, get last
        attachment = update.message.photo[-1]
        filename = f"photo_{int(time.time())}.jpg"
    
    if not attachment:
        await context.bot.send_message(update.effective_chat.id, "⚠️ 无法获取文件")
        return

    f_size = attachment.file_size
    if f_size > 50 * 1024 * 1024:
        await context.bot.send_message(update.effective_chat.id, "⚠️ Telegram Bot API 限制上传 50MB 以下文件。")
        return

    msg = await context.bot.send_message(update.effective_chat.id, "⬇️ 正在下载到 Termux...")
    try:
        file_obj = await attachment.get_file()
        
        if not os.path.exists(DOWNLOAD_PATH): os.makedirs(DOWNLOAD_PATH)
        local_path = os.path.join(DOWNLOAD_PATH, filename)
        
        await file_obj.download_to_drive(local_path)
        
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="⬆️ 正在上传到 PikPak...")
        
        # Upload
        try:
            # Assuming pikpakapi uses upload_file(path)
            await client.upload_file(local_path)
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"✅ 上传成功: `{filename}`", parse_mode='Markdown')
        except Exception as e:
             await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 上传失败: {e}")

        # Cleanup
        if os.path.exists(local_path): os.remove(local_path)

    except Exception as e:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 处理出错: {e}")
