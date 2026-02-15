
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .accounts import alist_mgr
from .config import global_cache, WEB_PORT
from .utils import format_bytes, get_base_url
from .handlers_task import start_stream_process

async def show_alist_files(update: Update, context: ContextTypes.DEFAULT_TYPE, path="/", page=1, edit_msg=False):
    # AList API List
    if path == "": path = "/"
    
    # Cache key
    cache_key = f"alist_list_{path}_{page}"
    cached = global_cache.get(cache_key)
    
    data = None
    if cached:
        data = cached
    else:
        resp = alist_mgr.list_files(path, page=page)
        if resp and resp.get('code') == 200:
            data = resp['data']
            global_cache.set(cache_key, data, ttl=60) # Cache 1 min
    
    if not data:
        msg = "❌ 无法连接 AList 或 Token 过期"
        if edit_msg: await update.callback_query.edit_message_text(msg)
        else: await context.bot.send_message(update.effective_chat.id, msg)
        return

    content = data.get('content', [])
    total = data.get('total', 0)
    
    # Sorting: Folders first
    content.sort(key=lambda x: (not x['is_dir'], x['name']))
    
    # Build Keyboard
    keyboard = []
    
    # Parent Dir
    if path != "/":
        parent = "/" + "/".join(path.strip("/").split("/")[:-1])
        keyboard.append([InlineKeyboardButton("🔙 返回上一级", callback_data=f"ls:{parent}")])

    # Items
    for item in content:
        name = item['name']
        is_dir = item['is_dir']
        full_path = f"{path}/{name}".replace("//", "/")
        
        # Safe callback data (path can be long)
        # We assume paths fit in 64 bytes usually, or we need a map. 
        # For simple use, we send path directly. 
        # If path too long, AList IDs are not stable, so we rely on path.
        
        if len(full_path.encode('utf-8')) > 50:
             # Very basic truncation for UI, but might break logic if deep
             pass 

        if is_dir:
            keyboard.append([InlineKeyboardButton(f"📁 {name}", callback_data=f"ls:{full_path}")])
        else:
            size = format_bytes(item['size'])
            keyboard.append([InlineKeyboardButton(f"📄 {name} ({size})", callback_data=f"file:{full_path}")])

    # Controls
    nav = []
    nav.append(InlineKeyboardButton("🔄 刷新", callback_data=f"ls_force:{path}"))
    keyboard.append(nav)

    text = f"📂 **文件列表**\n路径: `{path}`\n总数: {total}"
    reply_markup = InlineKeyboardMarkup(keyboard)

    if edit_msg:
        try: await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except: pass
    else:
        await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_alist_file_action(update, context, path):
    if update.callback_query: await update.callback_query.answer("获取中...")
    
    resp = alist_mgr.get_file_info(path)
    if not resp or resp.get('code') != 200:
        await update.callback_query.edit_message_text("❌ 获取文件信息失败")
        return

    data = resp['data']
    name = data['name']
    raw_url = data['raw_url']
    sign = data.get('sign', '')
    
    # Construct full URL
    # If raw_url is relative or needs signing
    full_url = raw_url
    if sign and 'sign=' not in full_url:
        full_url += f"?sign={sign}" if '?' not in full_url else f"&sign={sign}"

    # Web Player Link
    # Encode URL
    encoded_url = urllib.parse.quote(full_url)
    encoded_name = urllib.parse.quote(name)
    base_url = get_base_url(WEB_PORT)
    # We can use the generic player endpoint if we adapted it, 
    # but here we can just use the AList raw link for external players
    
    text = f"📄 **{name}**\n📏 大小: {format_bytes(data['size'])}"
    
    keyboard = [
        [InlineKeyboardButton("📺 推流到 Telegram 直播", callback_data=f"do_stream:{path}")],
        [InlineKeyboardButton("▶️ 调用本地播放器", url=f"intent:{full_url}#Intent;type=video/*;S.title={encoded_name};end")],
        [InlineKeyboardButton("🔗 复制直链", callback_data="copy_link")], # Handle in callback
        [InlineKeyboardButton("🔙 返回", callback_data=f"ls:{'/' + '/'.join(path.strip('/').split('/')[:-1])}")]
    ]
    
    # Store URL in context for copy/stream
    context.user_data['temp_file_url'] = full_url
    context.user_data['temp_file_name'] = name
    
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_alist_action(update, context, action, payload):
    if action == "do_stream":
        # Get url from context if matched or fetch again
        path = payload
        resp = alist_mgr.get_file_info(path)
        if resp and resp.get('code') == 200:
            data = resp['data']
            full_url = data['raw_url']
            if data.get('sign'): full_url += f"?sign={data['sign']}"
            await start_stream_process(update, context, full_url, data['name'])
        else:
            await update.callback_query.answer("无法获取链接")
            
    elif action == "copy_link":
        url = context.user_data.get('temp_file_url', 'Error')
        await context.bot.send_message(update.effective_chat.id, f"🔗 `{url}`", parse_mode='Markdown')
