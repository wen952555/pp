
import urllib.parse
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes
from .accounts import alist_mgr
from .config import global_cache, WEB_PORT
from .utils import format_bytes, get_base_url
from .handlers_task import start_stream_process

# --- File Browser ---
async def show_alist_files(update: Update, context: ContextTypes.DEFAULT_TYPE, path="/", page=1, edit_msg=False):
    if path == "": path = "/"
    
    data = None
    # No cache for now to ensure freshness
    resp = alist_mgr.list_files(path, page=page)
    if resp and resp.get('code') == 200:
        data = resp['data']
    
    if not data:
        msg = "❌ 无法连接 AList 或 Token 过期"
        if edit_msg: await update.callback_query.edit_message_text(msg)
        else: await context.bot.send_message(update.effective_chat.id, msg)
        return

    content = data.get('content', [])
    total = data.get('total', 0)
    
    # Sorting: Folders first
    content.sort(key=lambda x: (not x['is_dir'], x['name']))
    
    keyboard = []
    
    # 1. Navigation Row
    nav_row = []
    if path != "/":
        parent = "/" + "/".join(path.strip("/").split("/")[:-1])
        if parent == "": parent = "/"
        nav_row.append(InlineKeyboardButton("🔙 上一级", callback_data=f"ls:{parent}"))
    
    nav_row.append(InlineKeyboardButton("🔄 刷新", callback_data=f"ls_force:{path}"))
    nav_row.append(InlineKeyboardButton("🏠 首页", callback_data="ls:/"))
    keyboard.append(nav_row)

    # 2. Clipboard Paste Action
    clipboard = context.user_data.get('clipboard')
    if clipboard and clipboard.get('files'):
        op = "✂️ 移动" if clipboard['op'] == 'move' else "📑 复制"
        count = len(clipboard['files'])
        keyboard.append([
            InlineKeyboardButton(f"{op} {count} 个文件到此", callback_data=f"act_paste:{path}"),
            InlineKeyboardButton("❌ 取消粘贴", callback_data="act_clear_clip")
        ])

    # 3. File List
    for item in content:
        name = item['name']
        is_dir = item['is_dir']
        # Construct full path carefully
        full_path = os.path.join(path, name).replace("\\", "/")
        
        # Truncate for display
        display_name = (name[:20] + '..') if len(name) > 20 else name
        
        if is_dir:
            keyboard.append([
                InlineKeyboardButton(f"📁 {display_name}", callback_data=f"ls:{full_path}"),
                InlineKeyboardButton("⚙️", callback_data=f"opt_dir:{full_path}")
            ])
        else:
            size = format_bytes(item['size'])
            keyboard.append([InlineKeyboardButton(f"📄 {display_name} ({size})", callback_data=f"file:{full_path}")])

    # 4. Folder Actions
    keyboard.append([
        InlineKeyboardButton("➕ 新建文件夹", callback_data=f"act_mkdir:{path}"),
        InlineKeyboardButton("📥 离线下载", callback_data=f"act_offline_dl:{path}")
    ])

    text = f"📂 **文件列表**\n路径: `{path}`\n总数: {total}"
    reply_markup = InlineKeyboardMarkup(keyboard)

    if edit_msg:
        try: await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except: pass
    else:
        await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode='Markdown')

# --- File Details & Actions ---
async def show_alist_file_action(update, context, path):
    if update.callback_query: await update.callback_query.answer("加载菜单...")
    
    resp = alist_mgr.get_file_info(path)
    if not resp or resp.get('code') != 200:
        await update.callback_query.edit_message_text("❌ 获取文件信息失败")
        return

    data = resp['data']
    name = data['name']
    raw_url = data['raw_url']
    if data.get('sign'): raw_url += f"?sign={data['sign']}"
    
    # Links
    base_url = get_base_url(WEB_PORT)
    encoded_path = urllib.parse.quote(path)
    web_play_link = f"{base_url}/play?id={encoded_path}"
    encoded_name = urllib.parse.quote(name)

    text = f"📄 **{name}**\n📏 大小: {format_bytes(data['size'])}"
    
    # Store for actions
    context.user_data['target_path'] = path
    context.user_data['target_name'] = name
    context.user_data['temp_file_url'] = raw_url

    kb = [
        [InlineKeyboardButton("📺 推流直播", callback_data=f"do_stream:{path}"), InlineKeyboardButton("🖥️ 网页播放", url=web_play_link)],
        [InlineKeyboardButton("▶️ 本地播放", url=f"intent:{raw_url}#Intent;type=video/*;S.title={encoded_name};end"), InlineKeyboardButton("🔗 复制链接", callback_data="copy_link")],
        [InlineKeyboardButton("✏️ 重命名", callback_data="req_rename"), InlineKeyboardButton("🗑 删除", callback_data="req_delete")],
        [InlineKeyboardButton("✂️ 剪切", callback_data="req_cut"), InlineKeyboardButton("📑 复制", callback_data="req_copy")],
        [InlineKeyboardButton("🔙 返回列表", callback_data=f"ls:{os.path.dirname(path)}")]
    ]
    
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def show_dir_options(update, context, path):
    context.user_data['target_path'] = path
    context.user_data['target_name'] = os.path.basename(path)
    
    text = f"📁 **文件夹管理**\n路径: `{path}`"
    kb = [
        [InlineKeyboardButton("✏️ 重命名", callback_data="req_rename"), InlineKeyboardButton("🗑 删除", callback_data="req_delete")],
        [InlineKeyboardButton("✂️ 剪切", callback_data="req_cut"), InlineKeyboardButton("📑 复制", callback_data="req_copy")],
        [InlineKeyboardButton("🔙 返回", callback_data=f"ls:{os.path.dirname(path)}")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

# --- Action Logic ---

async def handle_fs_action_request(update, context, action):
    query = update.callback_query
    path = context.user_data.get('target_path')
    name = context.user_data.get('target_name')
    parent = os.path.dirname(path)
    
    if action == "req_rename":
        context.user_data['input_mode'] = 'rename'
        await query.message.reply_text(
            f"✏️ 请输入 `{name}` 的新名称:", 
            reply_markup=ForceReply(selective=True), 
            parse_mode='Markdown'
        )
        
    elif action == "req_delete":
        kb = [
            [InlineKeyboardButton("🗑 确认删除", callback_data="confirm_delete")],
            [InlineKeyboardButton("❌ 取消", callback_data="cancel_action")]
        ]
        await query.edit_message_text(f"⚠️ **确认删除** `{name}` ?", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif action in ["req_cut", "req_copy"]:
        op = 'move' if action == "req_cut" else 'copy'
        context.user_data['clipboard'] = {
            'op': op,
            'source_dir': parent,
            'files': [name] # Currently single file
        }
        await query.answer(f"✅ 已{'剪切' if op=='move' else '复制'}，请前往目标文件夹粘贴")
        await show_alist_files(update, context, path=parent, edit_msg=True)

    elif action == "act_mkdir":
        # path passed in payload is the current directory
        current_dir = path # Payload from callback
        context.user_data['input_mode'] = 'mkdir'
        context.user_data['target_path'] = current_dir
        await query.message.reply_text(
            "➕ 请输入新文件夹名称:", 
            reply_markup=ForceReply(selective=True)
        )

    elif action == "act_offline_dl":
        current_dir = path # Payload from callback
        context.user_data['input_mode'] = 'offline_dl'
        context.user_data['target_path'] = current_dir
        await query.message.reply_text(
            "📥 请回复下载链接 (HTTP/Magnet):",
            reply_markup=ForceReply(selective=True)
        )

    elif action == "act_paste":
        current_dir = path # Payload from callback
        clipboard = context.user_data.get('clipboard')
        if not clipboard: return
        
        await query.edit_message_text("⏳ 处理中...")
        res = alist_mgr.fs_move_copy(
            src_dir=clipboard['source_dir'],
            dst_dir=current_dir,
            names=clipboard['files'],
            action=clipboard['op']
        )
        
        if res.get('code') == 200:
            del context.user_data['clipboard']
            await query.answer("✅ 操作成功")
            await show_alist_files(update, context, path=current_dir, edit_msg=True)
        else:
            await query.message.reply_text(f"❌ 失败: {res.get('message')}")
            await show_alist_files(update, context, path=current_dir, edit_msg=True)

    elif action == "confirm_delete":
        res = alist_mgr.fs_remove(names=[name], dir_path=parent)
        if res.get('code') == 200:
            await query.answer("✅ 已删除")
            await show_alist_files(update, context, path=parent, edit_msg=True)
        else:
            await query.edit_message_text(f"❌ 删除失败: {res.get('message')}")
            
    elif action == "cancel_action":
        await show_alist_files(update, context, path=parent, edit_msg=True)

    elif action == "act_clear_clip":
        if 'clipboard' in context.user_data: del context.user_data['clipboard']
        await query.answer("已清空剪贴板")

# --- Specific AList Actions ---
async def handle_alist_action(update, context, action, payload):
    if action == "do_stream":
        path = payload
        resp = alist_mgr.get_file_info(path)
        if resp and resp.get('code') == 200:
            data = resp['data']
            full_url = data['raw_url']
            if data.get('sign'): full_url += f"?sign={data['sign']}"
            await start_stream_process(update, context, full_url, data['name'])
        else:
            if update.callback_query:
                await update.callback_query.answer("无法获取链接")
            
    elif action == "copy_link":
        url = context.user_data.get('temp_file_url', 'Error')
        await context.bot.send_message(update.effective_chat.id, f"🔗 `{url}`", parse_mode='Markdown')
        if update.callback_query:
            await update.callback_query.answer("已发送")

# --- Input Processor ---
async def process_fs_input(update, context):
    mode = context.user_data.get('input_mode')
    text = update.message.text.strip()
    
    if mode == 'rename':
        old_path = context.user_data.get('target_path')
        res = alist_mgr.fs_rename(old_path, text)
        if res.get('code') == 200:
            await update.message.reply_text(f"✅ 重命名成功: `{text}`", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ 重命名失败: {res.get('message')}")
            
    elif mode == 'mkdir':
        parent = context.user_data.get('target_path')
        full_path = os.path.join(parent, text).replace("\\", "/")
        res = alist_mgr.fs_mkdir(full_path)
        if res.get('code') == 200:
            await update.message.reply_text(f"✅ 文件夹已创建: `{text}`", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ 创建失败: {res.get('message')}")
            
    elif mode == 'offline_dl':
        path = context.user_data.get('target_path', '/')
        res = alist_mgr.add_offline_download(text, path)
        if res.get('code') == 200:
             await update.message.reply_text(f"✅ 离线任务已添加: `{text}`", parse_mode='Markdown')
        else:
             await update.message.reply_text(f"❌ 添加失败: {res.get('message')}")

    # Clear state
    if 'input_mode' in context.user_data: del context.user_data['input_mode']
