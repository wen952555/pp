
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
        if edit_msg: await update.callback_query.edit_message_text(text)
        else: await context.bot.send_message(update.effective_chat.id, text)
        return

    try:
        # Fetching
        files = []
        
        # Simple client-side regex filter if "re:" prefix used
        is_regex = search_query and search_query.startswith("re:")
        api_search_name = search_query if (search_query and not is_regex) else None
        
        resp = await client.file_list(parent_id=parent_id, name=api_search_name)
        raw_files = resp.get('files', []) if isinstance(resp, dict) else resp
        if not isinstance(raw_files, list): raw_files = []

        # Client side regex filtering
        if is_regex:
            pattern = search_query[3:]
            try:
                files = [f for f in raw_files if re.search(pattern, f.get('name', ''), re.IGNORECASE)]
            except: 
                files = [] # Invalid regex
        else:
            files = raw_files

        # Sort: Folders first
        files.sort(key=lambda x: (x.get('kind') != 'drive#folder', x.get('name')))

        # Pagination
        items_per_page = 10
        total_items = len(files)
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        current_files = files[start_idx:end_idx]

        # Build Keyboard
        keyboard = []
        
        # Top Nav
        nav_top = []
        if parent_id or search_query:
            nav_top.append(InlineKeyboardButton("🏠 根目录", callback_data="ls:"))
            nav_top.append(InlineKeyboardButton("🔙 返回", callback_data="ls:")) # Ideally return to parent
        if nav_top: keyboard.append(nav_top)

        for f in current_files:
            name = f.get('name', 'Unknown')
            fid = f['id']
            if f.get('kind') == 'drive#folder':
                keyboard.append([InlineKeyboardButton(f"📁 {name[:30]}", callback_data=f"ls:{fid}")])
            else:
                sz = format_bytes(f.get('size', 0))
                keyboard.append([InlineKeyboardButton(f"📄 {name[:25]} ({sz})", callback_data=f"file:{fid}")])

        # Pagination Rows
        nav_row = []
        sq = search_query if search_query else ""
        pid = parent_id if parent_id else ""
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f"page:{pid}:{page-1}:{sq}"))
        if end_idx < total_items:
            nav_row.append(InlineKeyboardButton("下一页 ➡️", callback_data=f"page:{pid}:{page+1}:{sq}"))
        if nav_row: keyboard.append(nav_row)

        # Folder Tools (Only show if in a folder or root, not search)
        if not search_query:
            tools_row = [
                InlineKeyboardButton("🎬 M3U", callback_data=f"tool_m3u:{pid}"),
                InlineKeyboardButton("⚡ STRM", callback_data=f"tool_strm:{pid}"),
                InlineKeyboardButton("🧹 去重", callback_data=f"tool_dedupe:{pid}")
            ]
            keyboard.append(tools_row)

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
            # Try catch to avoid "message not modified"
            try: await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            except: pass
        else:
            await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        err = f"❌ 读取列表失败: {e}"
        if edit_msg: await update.callback_query.edit_message_text(err)
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
        
        text = f"📄 **{name}**\n请选择操作:"
        keyboard = [
            [InlineKeyboardButton("🖥️ 网页播放 (局域网)", url=play_link)],
            [InlineKeyboardButton("🔗 获取直链", callback_data=f"act_link:{file_id}"), InlineKeyboardButton("✏️ 重命名", callback_data=f"act_ren:{file_id}")],
            [InlineKeyboardButton("⬇️ TG发送", callback_data=f"act_tg:{file_id}"), InlineKeyboardButton("✂️ 移动", callback_data=f"act_cut:{file_id}")],
            [InlineKeyboardButton("🗑 删除文件", callback_data=f"act_del:{file_id}"), InlineKeyboardButton("🔙 返回列表", callback_data="ls:")]
        ]
        
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        await update.callback_query.answer(f"Error: {e}", show_alert=True)

# --- ADVANCED TOOLS ---

async def generate_playlist(update, context, folder_id, mode='m3u'):
    """Generates M3U or ZIP of STRM files"""
    user_id = update.effective_user.id
    client = await account_mgr.get_client(user_id)
    
    msg = await context.bot.send_message(update.effective_chat.id, f"⏳ 正在生成 {mode.upper()} (扫描中)...")
    
    try:
        resp = await client.file_list(parent_id=folder_id)
        files = resp.get('files', []) if isinstance(resp, dict) else resp
        
        video_files = []
        for f in files:
            if f.get('kind') == 'drive#folder': continue
            # Basic video detection
            if f.get('mime_type', '').startswith('video/') or f.get('name', '').lower().endswith(('.mp4','.mkv','.avi','.mov')):
                video_files.append(f)
        
        if not video_files:
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="❌ 该目录下没有视频文件")
            return

        # Prepare Buffer
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
            output_filename = f"playlist_{folder_id or 'root'}.m3u"
            caption = f"✅ 已生成 M3U 列表 ({count} 个视频)"

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
            
            output_filename = f"strm_files_{folder_id or 'root'}.zip"
            caption = f"✅ 已生成 STRM 压缩包 ({count} 个文件)\n解压到 Emby 媒体库即可播放。"

        output_buffer.seek(0)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=output_buffer,
            filename=output_filename,
            caption=caption
        )
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg.message_id)

    except Exception as e:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 生成失败: {e}")

async def deduplicate_folder(update, context, folder_id):
    user_id = update.effective_user.id
    client = await account_mgr.get_client(user_id)
    msg = await context.bot.send_message(update.effective_chat.id, "🔍 正在扫描重复文件 (Hash比对)...")

    try:
        resp = await client.file_list(parent_id=folder_id)
        files = resp.get('files', []) if isinstance(resp, dict) else resp
        
        hashes = {}
        duplicates = [] # List of file objects
        
        for f in files:
            if f.get('kind') == 'drive#folder': continue
            h = f.get('hash')
            if not h: continue
            
            if h in hashes:
                duplicates.append(f)
            else:
                hashes[h] = f
        
        if not duplicates:
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="✅ 未发现重复文件")
            return

        # Prepare deletion confirmation
        context.user_data['dedupe_ids'] = [f['id'] for f in duplicates]
        
        text = f"⚠️ 发现 {len(duplicates)} 个重复文件 (保留最早上传的):\n"
        for f in duplicates[:8]:
            text += f"🗑 {f['name']}\n"
        if len(duplicates) > 8: text += "...等"
        
        kb = [
            [InlineKeyboardButton("🗑 确认删除全部重复项", callback_data="confirm_dedupe")],
            [InlineKeyboardButton("❌ 取消", callback_data="close_menu")]
        ]
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=text, reply_markup=InlineKeyboardMarkup(kb))

    except Exception as e:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 错误: {e}")

async def upload_tg_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle small file uploads from TG"""
    user_id = update.effective_user.id
    client = await account_mgr.get_client(user_id)
    if not client: 
        await context.bot.send_message(update.effective_chat.id, "⚠️ 请先登录")
        return

    # Check size (Max 20MB for bot api)
    f_size = update.message.effective_attachment.file_size
    if f_size > 20 * 1024 * 1024:
        await context.bot.send_message(update.effective_chat.id, "⚠️ 文件过大，Bot 无法直接转存(限制20MB)。请发送下载链接。")
        return

    msg = await context.bot.send_message(update.effective_chat.id, "⬇️ 正在从 Telegram 下载...")
    
    try:
        file_obj = await update.message.effective_attachment.get_file()
        
        # Determine filename
        filename = "file_" + str(int(time.time()))
        if hasattr(update.message, 'document') and update.message.document: filename = update.message.document.file_name
        elif hasattr(update.message, 'video'): filename += ".mp4"
        elif hasattr(update.message, 'photo'): filename += ".jpg"
        
        # Download locally
        if not os.path.exists(DOWNLOAD_PATH): os.makedirs(DOWNLOAD_PATH)
        local_path = os.path.join(DOWNLOAD_PATH, filename)
        await file_obj.download_to_drive(local_path)
        
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="⬆️ 正在上传到 PikPak...")
        
        # Upload
        try:
            await client.upload_file(local_path)
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"✅ 上传成功: {filename}")
        except Exception as e:
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 上传失败: {e}")
        
        if os.path.exists(local_path): os.remove(local_path)
        
    except Exception as e:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 错误: {e}")
