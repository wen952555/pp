
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

async def show_file_list(update: Update, context: ContextTypes.DEFAULT_TYPE, parent_id=None, page=0, edit_msg=False, search_query=None):
    user_id = update.effective_user.id
    
    # 1. Get Client
    client = await account_mgr.get_client(user_id)
    if not client:
        text = "⚠️ **未登录**\n请前往 [👥 账号管理] 进行登录。"
        if edit_msg: 
            try: await update.callback_query.edit_message_text(text, parse_mode='Markdown')
            except: pass
        else: await context.bot.send_message(update.effective_chat.id, text, parse_mode='Markdown')
        return

    # 2. Sanitize Parent ID
    if parent_id in ["None", "", "root"]: parent_id = None

    try:
        # 3. API Call with Auto-Relogin retry
        try:
            resp = await client.file_list(parent_id=parent_id)
        except Exception as e:
            # Simple retry once in case of token expiry
            print(f"First API attempt failed: {e}, retrying login...")
            client = await account_mgr.get_client(user_id, force_refresh=True) # Assuming modified get_client or just retry logic
            if client:
                resp = await client.file_list(parent_id=parent_id)
            else:
                raise e

        raw_files = resp.get('files', []) if isinstance(resp, dict) else resp
        if not isinstance(raw_files, list): raw_files = []

        # 4. Filter
        files = []
        if search_query:
            is_regex = search_query.startswith("re:")
            term = search_query[3:] if is_regex else search_query
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

        # 5. Sort (Folders First)
        files.sort(key=lambda x: (x.get('kind') != 'drive#folder', x.get('name', '') or ''))

        # 6. Pagination
        items_per_page = 10
        total_items = len(files)
        if page * items_per_page >= total_items and page > 0: page = 0
            
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        current_files = files[start_idx:end_idx]

        # 7. Build UI
        keyboard = []
        
        # Navigation
        nav_top = []
        if parent_id or search_query:
            nav_top.append(InlineKeyboardButton("🏠 首页", callback_data="ls:"))
            # Back logic is simplified to root for now as we don't track history stack
            nav_top.append(InlineKeyboardButton("🔙 返回", callback_data="ls:"))
        if nav_top: keyboard.append(nav_top)

        for f in current_files:
            name = f.get('name', 'Unknown')
            fid = f['id']
            if f.get('kind') == 'drive#folder':
                # Folder: LS command
                keyboard.append([
                    InlineKeyboardButton(f"📁 {name[:20]}", callback_data=f"ls:{fid}"),
                    # Add folder edit option
                    InlineKeyboardButton("✏️", callback_data=f"act_ren:{fid}")
                ])
            else:
                # File: FILE options
                sz = format_bytes(f.get('size', 0))
                keyboard.append([InlineKeyboardButton(f"📄 {name[:20]} ({sz})", callback_data=f"file:{fid}")])

        # Pagination Buttons
        nav_row = []
        sq = search_query if search_query else ""
        pid = parent_id if parent_id else ""
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f"page:{pid}:{page-1}:{sq}"))
        if end_idx < total_items:
            nav_row.append(InlineKeyboardButton("下一页 ➡️", callback_data=f"page:{pid}:{page+1}:{sq}"))
        if nav_row: keyboard.append(nav_row)

        # Tools Row
        if not search_query:
            keyboard.append([
                InlineKeyboardButton("🎬 M3U播放单", callback_data=f"tool_m3u:{pid}"),
                InlineKeyboardButton("📊 文件夹大小", callback_data=f"tool_size:{pid}")
            ])
            keyboard.append([
                InlineKeyboardButton("🛠 批量重命名", callback_data=f"tool_regex:{pid}"),
                InlineKeyboardButton("🧹 扫描重复", callback_data=f"tool_dedupe:{pid}")
            ])

        # Paste Actions
        if 'clipboard' in context.user_data:
            clip = context.user_data['clipboard']
            op = "移动" if clip['op'] == 'move' else "复制"
            keyboard.append([
                InlineKeyboardButton(f"📋 粘贴{op}到此处", callback_data=f"paste:{pid}"),
                InlineKeyboardButton("❌ 取消粘贴", callback_data="paste_cancel")
            ])

        username = account_mgr.active_user_map.get(str(user_id), "Unknown")
        loc_str = f"🔍 搜索: `{search_query}`" if search_query else f"📂 路径: `{parent_id or '根目录'}`"
        text = f"👤 **{username}**\n{loc_str}\n共 {total_items} 个项目"

        reply_markup = InlineKeyboardMarkup(keyboard)

        if edit_msg:
            try: await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            except: pass
        else:
            await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        err_text = f"❌ **获取列表失败**\n错误信息: `{str(e)}`\n\n如果频繁出现此错误，请尝试在账号管理中删除账号并重新登录。"
        if edit_msg:
            try: await update.callback_query.edit_message_text(err_text, parse_mode='Markdown')
            except: pass
        else:
            await context.bot.send_message(update.effective_chat.id, err_text, parse_mode='Markdown')

# --- SINGLE FILE OPTIONS ---
async def show_file_options(update: Update, context: ContextTypes.DEFAULT_TYPE, file_id: str):
    user_id = update.effective_user.id
    client = await account_mgr.get_client(user_id)
    try:
        data = await client.get_download_url(file_id)
        name = data.get('name', 'Unknown')
        
        # Player
        ip = get_local_ip()
        play_link = f"http://{ip}:{WEB_PORT}/play?id={file_id}&user={user_id}"
        
        text = f"📄 **文件操作**\n`{name}`"
        keyboard = [
            [InlineKeyboardButton("🖥️ 在线播放 (Web)", url=play_link)],
            [InlineKeyboardButton("🔗 获取直链", callback_data=f"act_link:{file_id}"), InlineKeyboardButton("✏️ 重命名", callback_data=f"act_ren:{file_id}")],
            [InlineKeyboardButton("✂️ 剪切移动", callback_data=f"act_cut:{file_id}"), InlineKeyboardButton("🗑 删除", callback_data=f"act_del:{file_id}")],
        ]
        
        # Cross Copy
        if len(account_mgr.get_accounts_list()) > 1:
            keyboard.append([InlineKeyboardButton("🚀 秒传到其他账号", callback_data=f"x_copy_menu:{file_id}")])
            
        keyboard.append([InlineKeyboardButton("🔙 返回列表", callback_data="ls:")])
        
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ 操作失败: {e}")

# ... (Rest of existing tool functions like calculate_folder_size, initiate_regex_rename, etc. remain mostly the same but ensure they handle exceptions gracefully) ...

async def calculate_folder_size(update, context, folder_id):
    user_id = update.effective_user.id
    client = await account_mgr.get_client(user_id)
    if not client: return
    
    msg = await context.bot.send_message(update.effective_chat.id, "⏳ 计算中 (这可能需要几秒钟)...")
    try:
        resp = await client.file_list(parent_id=folder_id)
        files = resp.get('files', []) if isinstance(resp, dict) else resp
        
        total_size = 0
        count = 0
        for f in files:
            total_size += int(f.get('size', 0))
            count += 1
            
        readable = format_bytes(total_size)
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"📊 **统计结果**\n文件数: {count}\n总大小: **{readable}**")
    except Exception as e:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 失败: {e}")

async def initiate_regex_rename(update, context, folder_id):
    context.user_data['regex_context'] = folder_id
    text = "🛠 **正则重命名**\n请回复: `正则表达式 替换内容`\n示例: `\.mp4$ .mkv`"
    await context.bot.send_message(update.effective_chat.id, text, reply_markup=ForceReply(selective=True), parse_mode='Markdown')

async def process_regex_rename(update, context, pattern_str):
    folder_id = context.user_data.get('regex_context')
    del context.user_data['regex_context']
    
    try:
        parts = pattern_str.split()
        if len(parts) < 1: return
        pattern = parts[0]
        repl = parts[1] if len(parts) > 1 else ""
        
        user_id = update.effective_user.id
        client = await account_mgr.get_client(user_id)
        
        msg = await context.bot.send_message(update.effective_chat.id, "⏳ 正在批量处理...")
        
        resp = await client.file_list(parent_id=folder_id)
        files = resp.get('files', []) if isinstance(resp, dict) else resp
        
        count = 0
        for f in files:
            try:
                new_name = re.sub(pattern, repl, f.get('name',''))
                if new_name != f.get('name'):
                    await client.rename_file(file_id=f['id'], name=new_name)
                    count += 1
            except: continue
        
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"✅ 已重命名 {count} 个文件")
    except Exception as e:
        await context.bot.send_message(update.effective_chat.id, f"❌ 错误: {e}")

async def generate_playlist(update, context, folder_id, mode='m3u'):
    user_id = update.effective_user.id
    client = await account_mgr.get_client(user_id)
    msg = await context.bot.send_message(update.effective_chat.id, "⏳ 生成中...")
    
    try:
        resp = await client.file_list(parent_id=folder_id)
        files = resp.get('files', []) if isinstance(resp, dict) else resp
        video_files = [f for f in files if f.get('kind') != 'drive#folder' and f.get('name','').lower().endswith(('.mp4','.mkv','.avi','.mov'))]
        
        if not video_files:
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="❌ 此文件夹无视频")
            return

        out = io.BytesIO()
        fname = "playlist.m3u"
        
        if mode == 'm3u':
            content = "#EXTM3U\n"
            for f in video_files:
                try:
                    d = await client.get_download_url(f['id'])
                    if d.get('url'): content += f"#EXTINF:-1,{f['name']}\n{d['url']}\n"
                except: pass
            out.write(content.encode('utf-8'))
        elif mode == 'strm':
            fname = "strm.zip"
            with zipfile.ZipFile(out, 'w') as zf:
                for f in video_files:
                    try:
                        d = await client.get_download_url(f['id'])
                        if d.get('url'): zf.writestr(f"{os.path.splitext(f['name'])[0]}.strm", d['url'])
                    except: pass
        
        out.seek(0)
        await context.bot.send_document(update.effective_chat.id, document=out, filename=fname, caption=f"✅ {len(video_files)} 个视频")
        await context.bot.delete_message(update.effective_chat.id, msg.message_id)
    except Exception as e:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ Error: {e}")

async def deduplicate_folder(update, context, folder_id):
    user_id = update.effective_user.id
    client = await account_mgr.get_client(user_id)
    msg = await context.bot.send_message(update.effective_chat.id, "🔍 正在比对文件 Hash...")
    
    try:
        resp = await client.file_list(parent_id=folder_id)
        files = resp.get('files', []) if isinstance(resp, dict) else resp
        
        seen = {}
        dupes = []
        for f in files:
            if f.get('kind') == 'drive#folder': continue
            h = f.get('hash')
            if not h: continue
            if h in seen: dupes.append(f)
            else: seen[h] = f
            
        if not dupes:
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="✅ 没有发现重复文件")
            return
            
        context.user_data['dedupe_ids'] = [f['id'] for f in dupes]
        kb = [[InlineKeyboardButton(f"🗑 删除 {len(dupes)} 个重复文件", callback_data="confirm_dedupe")], [InlineKeyboardButton("取消", callback_data="close_menu")]]
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"⚠️ 发现 {len(dupes)} 个重复文件!", reply_markup=InlineKeyboardMarkup(kb))
    except Exception as e:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ 错误: {e}")

# ... (show_cross_copy_menu and execute_cross_copy can remain similar to previous iteration) ...
async def show_cross_copy_menu(update, context, file_id):
    accounts = account_mgr.get_accounts_list()
    kb = []
    for u in accounts:
        if u != account_mgr.active_user_map.get(str(update.effective_user.id)):
            kb.append([InlineKeyboardButton(f"➡️ 转存至 {u}", callback_data=f"x_copy_do:{file_id}:{u}")])
    kb.append([InlineKeyboardButton("取消", callback_data="close_menu")])
    await update.callback_query.edit_message_text("🚀 选择目标账号:", reply_markup=InlineKeyboardMarkup(kb))

async def execute_cross_copy(update, context, file_id, target):
    user_id = update.effective_user.id
    src = await account_mgr.get_client(user_id)
    dst = await account_mgr.get_client(user_id, specific_username=target)
    
    try:
        d = await src.get_download_url(file_id)
        if not d.get('url'): raise Exception("No Link")
        await dst.offline_download(d['url'])
        await update.callback_query.edit_message_text(f"✅ 已发送任务至 {target}")
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ 失败: {e}")

