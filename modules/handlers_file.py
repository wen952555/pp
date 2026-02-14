
import re
import io
import zipfile
import time
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes
from .accounts import account_mgr
from .config import WEB_PORT, DOWNLOAD_PATH
from .utils import get_local_ip, format_bytes

# --- FILE LISTING ---
async def show_file_list(update: Update, context: ContextTypes.DEFAULT_TYPE, parent_id=None, page=0, edit_msg=False, search_query=None):
    user_id = update.effective_user.id
    client = await account_mgr.get_client(user_id)
    
    if not client:
        text = "⚠️ 未登录，请使用 [👥 账号管理] 登录"
        if edit_msg: 
            try: await update.callback_query.edit_message_text(text)
            except: await context.bot.send_message(update.effective_chat.id, text)
        else: await context.bot.send_message(update.effective_chat.id, text)
        return

    try:
        # Fetching - Always fetch list and filter client-side for safety
        resp = await client.file_list(parent_id=parent_id)
        raw_files = resp.get('files', []) if isinstance(resp, dict) else resp
        if not isinstance(raw_files, list): raw_files = []

        # Client-side Filtering
        files = []
        if search_query:
            is_regex = search_query.startswith("re:")
            term = search_query[3:] if is_regex else search_query
            
            for f in raw_files:
                fname = f.get('name', '')
                if is_regex:
                    try: 
                        if re.search(term, fname, re.IGNORECASE): files.append(f)
                    except: pass
                else:
                    if term.lower() in fname.lower(): files.append(f)
        else:
            files = raw_files

        # Sort: Folders first
        files.sort(key=lambda x: (x.get('kind') != 'drive#folder', x.get('name')))

        # Pagination
        items_per_page = 10
        total_items = len(files)
        # Reset page if out of bounds (e.g. after search filter)
        if page * items_per_page >= total_items and page > 0: page = 0
            
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        current_files = files[start_idx:end_idx]

        # Build Keyboard
        keyboard = []
        
        # Top Nav
        nav_top = []
        if parent_id or search_query:
            nav_top.append(InlineKeyboardButton("🏠 根目录", callback_data="ls:"))
            nav_top.append(InlineKeyboardButton("🔙 返回", callback_data="ls:"))
        if nav_top: keyboard.append(nav_top)

        for f in current_files:
            name = f.get('name', 'Unknown')
            fid = f['id']
            if f.get('kind') == 'drive#folder':
                keyboard.append([InlineKeyboardButton(f"📁 {name[:25]}", callback_data=f"ls:{fid}")])
            else:
                sz = format_bytes(f.get('size', 0))
                keyboard.append([InlineKeyboardButton(f"📄 {name[:20]} ({sz})", callback_data=f"file:{fid}")])

        # Pagination Rows
        nav_row = []
        sq = search_query if search_query else ""
        pid = parent_id if parent_id else ""
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"page:{pid}:{page-1}:{sq}"))
        if end_idx < total_items:
            nav_row.append(InlineKeyboardButton("➡️", callback_data=f"page:{pid}:{page+1}:{sq}"))
        if nav_row: keyboard.append(nav_row)

        # Folder Tools (Advanced)
        if not search_query:
            # Row 1: M3U, STRM
            keyboard.append([
                InlineKeyboardButton("🎬 M3U", callback_data=f"tool_m3u:{pid}"),
                InlineKeyboardButton("⚡ STRM", callback_data=f"tool_strm:{pid}")
            ])
            # Row 2: Manage
            keyboard.append([
                InlineKeyboardButton("📊 计算体积", callback_data=f"tool_size:{pid}"),
                InlineKeyboardButton("🛠 正则重命名", callback_data=f"tool_regex:{pid}")
            ])
            # Row 3: Dedupe
            keyboard.append([InlineKeyboardButton("🧹 扫描重复文件", callback_data=f"tool_dedupe:{pid}")])

        # Clipboard Paste
        if 'clipboard' in context.user_data:
            clip = context.user_data['clipboard']
            op = "移动" if clip['op'] == 'move' else "复制"
            keyboard.append([
                InlineKeyboardButton(f"📋 粘贴{op}", callback_data=f"paste:{pid}"),
                InlineKeyboardButton("❌ 取消", callback_data="paste_cancel")
            ])

        # Message Text
        username = account_mgr.active_user_map.get(str(user_id), "Unknown")
        path_display = f"🔍 `{search_query}`" if search_query else f"📂 `{parent_id or 'ROOT'}`"
        text = f"👤 **{username}**\n{path_display}\n共 {total_items} 个文件"

        reply_markup = InlineKeyboardMarkup(keyboard)

        if edit_msg:
            try: await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            except: pass
        else:
            await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        err = f"❌ 读取列表失败: {e}"
        if edit_msg: 
            try: await update.callback_query.edit_message_text(err)
            except: await context.bot.send_message(update.effective_chat.id, err)
        else: await context.bot.send_message(update.effective_chat.id, err)

# --- SINGLE FILE ACTIONS ---
async def show_file_options(update: Update, context: ContextTypes.DEFAULT_TYPE, file_id: str):
    user_id = update.effective_user.id
    client = await account_mgr.get_client(user_id)
    try:
        data = await client.get_download_url(file_id)
        name = data.get('name', 'Unknown')
        
        # Web Player Link
        ip = get_local_ip()
        play_link = f"http://{ip}:{WEB_PORT}/play?id={file_id}&user={user_id}"
        
        text = f"📄 **{name}**"
        keyboard = [
            [InlineKeyboardButton("🖥️ 网页播放", url=play_link)],
            [InlineKeyboardButton("🔗 直链", callback_data=f"act_link:{file_id}"), InlineKeyboardButton("✏️ 重命名", callback_data=f"act_ren:{file_id}")],
            [InlineKeyboardButton("⬇️ 发送TG", callback_data=f"act_tg:{file_id}"), InlineKeyboardButton("✂️ 剪切", callback_data=f"act_cut:{file_id}")],
            [InlineKeyboardButton("🗑 删除", callback_data=f"act_del:{file_id}"), InlineKeyboardButton("🔙 返回", callback_data="ls:")]
        ]

        # Add Cross-Account Copy if multiple accounts exist
        if len(account_mgr.get_accounts_list()) > 1:
            keyboard.insert(2, [InlineKeyboardButton("🚀 秒传到其他账号", callback_data=f"x_copy_menu:{file_id}")])
        
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        await update.callback_query.answer(f"Error: {e}", show_alert=True)

async def show_cross_copy_menu(update, context, file_id):
    """Show list of accounts to copy file to"""
    user_id = update.effective_user.id
    current_user = account_mgr.active_user_map.get(str(user_id))
    all_users = account_mgr.get_accounts_list()
    
    keyboard = []
    for u in all_users:
        if u == current_user: continue
        # Pass file_id and target_username
        keyboard.append([InlineKeyboardButton(f"📥 转存到: {u}", callback_data=f"x_copy_do:{file_id}:{u}")])
    
    keyboard.append([InlineKeyboardButton("🔙 返回", callback_data=f"file:{file_id}")])
    
    await update.callback_query.edit_message_text(
        "🚀 **跨账号秒传**\n请选择目标账号:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def execute_cross_copy(update, context, file_id, target_user):
    """Actually perform the copy via offline_download"""
    user_id = update.effective_user.id
    source_client = await account_mgr.get_client(user_id) # Active client
    target_client = await account_mgr.get_client(user_id, specific_username=target_user) # Target client
    
    if not source_client or not target_client:
        await update.callback_query.answer("账号认证失败", show_alert=True)
        return

    await update.callback_query.answer("⏳ 正在请求秒传...", show_alert=False)
    
    try:
        # 1. Get source link
        data = await source_client.get_download_url(file_id)
        url = data.get('url')
        name = data.get('name')
        
        if not url:
            await update.callback_query.edit_message_text(f"❌ 无法获取源文件链接: {name}")
            return
            
        # 2. Add task to target
        await target_client.offline_download(url)
        
        await update.callback_query.edit_message_text(
            f"✅ **秒传成功**\n\n文件: `{name}`\n已添加到账号: `{target_user}`\n(请在离线任务中确认)",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回文件", callback_data=f"file:{file_id}")]])
        )
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ 秒传失败: {e}")

# --- ADVANCED TOOLS ---

async def calculate_folder_size(update, context, folder_id):
    """Recursively calculate folder size"""
    user_id = update.effective_user.id
    client = await account_mgr.get_client(user_id)
    
    msg = await context.bot.send_message(update.effective_chat.id, "⏳ 正在递归计算文件夹体积 (这可能需要一点时间)...")
    
    try:
        resp = await client.file_list(parent_id=folder_id)
        files = resp.get('files', []) if isinstance(resp, dict) else resp
        
        total_size = 0
        count = 0
        
        for f in files:
            total_size += int(f.get('size', 0))
            count += 1
            
        readable = format_bytes(total_size)
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, 
            message_id=msg.message_id, 
            text=f"📊 **文件夹统计**\n当前层级文件数: {count}\n总大小: **{readable}**\n\n(注: 仅统计当前层级文件)"
        )
    except Exception as e:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 计算失败: {e}")

async def initiate_regex_rename(update, context, folder_id):
    """Sets state for regex rename in specific folder"""
    context.user_data['regex_context'] = folder_id
    text = (
        "🛠 **批量正则重命名**\n"
        "作用范围: 当前文件夹\n\n"
        "请回复格式: `匹配模式 替换内容`\n"
        "例如:\n"
        "- 去掉 [AD]: `\[AD\] ""`\n"
        "- MP4改MKV: `\.mp4$ .mkv`"
    )
    await context.bot.send_message(update.effective_chat.id, text, reply_markup=ForceReply(selective=True), parse_mode='Markdown')

async def process_regex_rename(update, context, pattern_str):
    """Executes the rename"""
    folder_id = context.user_data.get('regex_context')
    del context.user_data['regex_context'] # Clear state
    
    try:
        import shlex
        try: parts = shlex.split(pattern_str)
        except: parts = pattern_str.split()
            
        if len(parts) < 1: 
            await context.bot.send_message(update.effective_chat.id, "❌ 格式错误")
            return
            
        pattern = parts[0]
        repl = parts[1] if len(parts) > 1 else ""
        
        user_id = update.effective_user.id
        client = await account_mgr.get_client(user_id)
        
        resp = await client.file_list(parent_id=folder_id)
        files = resp.get('files', []) if isinstance(resp, dict) else resp
        
        count = 0
        msg = await context.bot.send_message(update.effective_chat.id, "⏳ 处理中...")
        
        for f in files:
            old_name = f.get('name', '')
            try:
                new_name = re.sub(pattern, repl, old_name)
                if new_name != old_name:
                    await client.rename_file(file_id=f['id'], name=new_name)
                    count += 1
            except: continue
            
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"✅ 已重命名 {count} 个文件")
        
    except Exception as e:
        await context.bot.send_message(update.effective_chat.id, f"❌ 出错: {e}")

async def generate_playlist(update, context, folder_id, mode='m3u'):
    """Generates M3U or ZIP of STRM files"""
    user_id = update.effective_user.id
    client = await account_mgr.get_client(user_id)
    
    msg = await context.bot.send_message(update.effective_chat.id, f"⏳ 正在生成 {mode.upper()}...")
    
    try:
        resp = await client.file_list(parent_id=folder_id)
        files = resp.get('files', []) if isinstance(resp, dict) else resp
        
        video_files = []
        for f in files:
            if f.get('kind') == 'drive#folder': continue
            if f.get('mime_type', '').startswith('video/') or f.get('name', '').lower().endswith(('.mp4','.mkv','.avi','.mov')):
                video_files.append(f)
        
        if not video_files:
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="❌ 该目录下没有视频文件")
            return

        output_buffer = io.BytesIO()
        output_filename = "playlist.m3u"
        caption = ""

        if mode == 'm3u':
            content = "#EXTM3U\n"
            count = 0
            for f in video_files:
                try:
                    d = await client.get_download_url(f['id'])
                    url = d.get('url')
                    if url:
                        content += f"#EXTINF:-1,{f['name']}\n{url}\n"
                        count += 1
                except: continue
            
            output_buffer.write(content.encode('utf-8'))
            output_filename = f"playlist.m3u"
            caption = f"✅ 已生成 M3U ({count} 个视频)"

        elif mode == 'strm':
            count = 0
            with zipfile.ZipFile(output_buffer, 'w') as zf:
                for f in video_files:
                    try:
                        d = await client.get_download_url(f['id'])
                        url = d.get('url')
                        if url:
                            strm_name = os.path.splitext(f['name'])[0] + ".strm"
                            zf.writestr(strm_name, url)
                            count += 1
                    except: continue
            
            output_filename = "strm_files.zip"
            caption = f"✅ STRM ZIP ({count} 个文件)"

        output_buffer.seek(0)
        await context.bot.send_document(chat_id=update.effective_chat.id, document=output_buffer, filename=output_filename, caption=caption)
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg.message_id)

    except Exception as e:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 失败: {e}")

async def deduplicate_folder(update, context, folder_id):
    user_id = update.effective_user.id
    client = await account_mgr.get_client(user_id)
    msg = await context.bot.send_message(update.effective_chat.id, "🔍 扫描重复文件...")

    try:
        resp = await client.file_list(parent_id=folder_id)
        files = resp.get('files', []) if isinstance(resp, dict) else resp
        hashes = {}
        duplicates = []
        for f in files:
            if f.get('kind') == 'drive#folder': continue
            h = f.get('hash')
            if not h: continue
            if h in hashes: duplicates.append(f)
            else: hashes[h] = f
        
        if not duplicates:
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="✅ 无重复文件")
            return

        context.user_data['dedupe_ids'] = [f['id'] for f in duplicates]
        text = f"⚠️ 发现 {len(duplicates)} 个重复项:\n"
        for f in duplicates[:5]: text += f"- {f['name']}\n"
        
        kb = [[InlineKeyboardButton("🗑 删除重复项", callback_data="confirm_dedupe")], [InlineKeyboardButton("❌ 取消", callback_data="close_menu")]]
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=text, reply_markup=InlineKeyboardMarkup(kb))

    except Exception as e:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ Error: {e}")

async def upload_tg_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle small file uploads from TG"""
    user_id = update.effective_user.id
    client = await account_mgr.get_client(user_id)
    if not client: 
        await context.bot.send_message(update.effective_chat.id, "⚠️ 请先登录")
        return

    f_size = update.message.effective_attachment.file_size
    if f_size > 20 * 1024 * 1024:
        await context.bot.send_message(update.effective_chat.id, "⚠️ 文件过大 (>20MB)")
        return

    msg = await context.bot.send_message(update.effective_chat.id, "⬇️ 下载中...")
    try:
        file_obj = await update.message.effective_attachment.get_file()
        filename = "file_" + str(int(time.time()))
        if hasattr(update.message, 'document') and update.message.document: filename = update.message.document.file_name
        elif hasattr(update.message, 'video'): filename += ".mp4"
        elif hasattr(update.message, 'photo'): filename += ".jpg"
        
        if not os.path.exists(DOWNLOAD_PATH): os.makedirs(DOWNLOAD_PATH)
        local_path = os.path.join(DOWNLOAD_PATH, filename)
        await file_obj.download_to_drive(local_path)
        
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="⬆️ 上传中...")
        try:
            await client.upload_file(local_path)
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"✅ 上传成功: {filename}")
        except Exception as e:
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 上传失败: {e}")
        
        if os.path.exists(local_path): os.remove(local_path)
    except Exception as e:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ Error: {e}")
