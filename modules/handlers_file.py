
import urllib.parse
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .accounts import alist_mgr
from .utils import format_bytes

# --- Constants ---
VIDEO_EXTS = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.ts', '.m2ts')
AUDIO_EXTS = ('.mp3', '.flac', '.wav', '.m4a', '.aac', '.ogg', '.wma')
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')

def is_target_file(filename, mode):
    lower_name = filename.lower()
    if mode == 'video':
        return lower_name.endswith(VIDEO_EXTS)
    elif mode == 'audio':
        return lower_name.endswith(AUDIO_EXTS) or lower_name.endswith(IMAGE_EXTS)
    return True

# --- File Browser with Multi-Select ---
async def show_alist_files(update: Update, context: ContextTypes.DEFAULT_TYPE, path="/", page=1, edit_msg=False):
    if path == "": path = "/"
    
    # Store current path for refreshing
    context.user_data['current_path'] = path
    
    # Get Browse Mode
    mode = context.user_data.get('browse_mode', 'video') # default video
    playlist = context.user_data.get('playlist', [])
    playlist_count = len(playlist)

    # Fetch Data
    resp = alist_mgr.list_files(path, page=page)
    if not resp or resp.get('code') != 200:
        msg = "❌ 无法连接 AList"
        if edit_msg: await update.callback_query.edit_message_text(msg)
        else: await context.bot.send_message(update.effective_chat.id, msg)
        return

    data = resp['data']
    content = data.get('content', [])
    
    # Filter Content based on Mode
    filtered_content = []
    for item in content:
        if item['is_dir']:
            filtered_content.append(item)
        elif is_target_file(item['name'], mode):
            filtered_content.append(item)

    # Sort: Folders first
    filtered_content.sort(key=lambda x: (not x['is_dir'], x['name']))

    keyboard = []
    
    # 1. Info & Control Row
    mode_icon = "🎬" if mode == 'video' else "🎵"
    info_text = f"{mode_icon} 已选: {playlist_count} 个文件"
    
    control_row = []
    if playlist_count > 0:
        control_row.append(InlineKeyboardButton(f"▶️ 开始推流 ({playlist_count})", callback_data="action_start_stream"))
        control_row.append(InlineKeyboardButton("🗑 清空", callback_data="action_clear_playlist"))
    keyboard.append(control_row)

    # 2. Navigation Row
    nav_row = []
    if path != "/":
        parent = "/" + "/".join(path.strip("/").split("/")[:-1])
        if parent == "": parent = "/"
        nav_row.append(InlineKeyboardButton("🔙 上一级", callback_data=f"ls:{parent}"))
    
    nav_row.append(InlineKeyboardButton("🏠 首页", callback_data="ls:/"))
    keyboard.append(nav_row)

    # 3. File List
    for item in filtered_content:
        name = item['name']
        is_dir = item['is_dir']
        full_path = os.path.join(path, name).replace("\\", "/")
        
        display_name = (name[:25] + '..') if len(name) > 25 else name
        
        if is_dir:
            keyboard.append([
                InlineKeyboardButton(f"📁 {display_name}", callback_data=f"ls:{full_path}")
            ])
        else:
            # Check if selected
            # Store simplified items in playlist: {'path': full_path, 'name': name}
            is_selected = any(p['path'] == full_path for p in playlist)
            check_icon = "✅" if is_selected else "⬜"
            
            # Use a safe way to encode path for callback data
            # Callback data limit is 64 bytes. If path is long, this fails.
            # Strategy: We can't put full path in callback if deep.
            # BUT for this bot, we assume paths aren't crazy deep or we use a cache map.
            # For robustness in "Lite" version, we try direct path if short, otherwise we might have issues.
            # Let's strip the common prefix or use an index if we cached the list.
            # Simpler approach: Just put the index of the item in the current filtered_content list?
            # No, that breaks if list changes.
            # Let's use urllib quote but be wary of length.
            
            # Workaround: Use a temporary index for the current view? 
            # Ideally we need a session-based map.
            # Let's stick to 'sel:<index>' relative to the CURRENT page content.
            # We need to save 'current_view_files' in user_data.
            
            size = format_bytes(item['size'])
            keyboard.append([InlineKeyboardButton(f"{check_icon} {display_name} ({size})", callback_data=f"sel:{full_path}")])

    # Save content map for safer callbacks? 
    # Actually, let's just use the full path. If it fails, user will know.
    # Telegram limit is 64 bytes. This is very small.
    # We MUST use a mapping.
    
    # Mapping Strategy:
    # Key: Hash(path) -> Value: Path. 
    # Or simpler: Just rely on the user clicking and us finding it?
    # No, we need to know what they clicked.
    # Let's try passing the index in the `filtered_content` array.
    # We must save `filtered_content` to user_data.
    context.user_data['current_file_list'] = filtered_content
    
    # Re-generate keyboard using indices
    keyboard = [keyboard[0], keyboard[1]] # Keep control and nav rows
    
    for idx, item in enumerate(filtered_content):
        name = item['name']
        is_dir = item['is_dir']
        display_name = (name[:25] + '..') if len(name) > 25 else name
        
        if is_dir:
            full_path = os.path.join(path, name).replace("\\", "/")
            keyboard.append([InlineKeyboardButton(f"📁 {display_name}", callback_data=f"ls:{full_path}")])
        else:
            full_path = os.path.join(path, name).replace("\\", "/")
            is_selected = any(p['path'] == full_path for p in playlist)
            check_icon = "✅" if is_selected else "⬜"
            # Pass index
            keyboard.append([InlineKeyboardButton(f"{check_icon} {display_name}", callback_data=f"sel:{idx}")])

    text = f"📂 **选择文件** ({mode_icon})\n路径: `{path}`"
    reply_markup = InlineKeyboardMarkup(keyboard)

    if edit_msg:
        try: await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except: pass
    else:
        await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_file_selection(update, context, data):
    # data is "sel:INDEX"
    try:
        idx = int(data.split(":")[1])
        file_list = context.user_data.get('current_file_list', [])
        
        if 0 <= idx < len(file_list):
            item = file_list[idx]
            current_path = context.user_data.get('current_path', '/')
            full_path = os.path.join(current_path, item['name']).replace("\\", "/")
            
            playlist = context.user_data.get('playlist', [])
            
            # Toggle Logic
            # Check if exists
            existing = next((i for i, p in enumerate(playlist) if p['path'] == full_path), None)
            
            if existing is not None:
                # Remove
                playlist.pop(existing)
            else:
                # Add
                playlist.append({'path': full_path, 'name': item['name']})
            
            context.user_data['playlist'] = playlist
            
            # Refresh View (Fast refresh without fetching API if possible, but API fetch ensures consistency)
            # To be safe, we just reload the UI.
            await show_alist_files(update, context, path=current_path, edit_msg=True)
            
    except Exception as e:
        print(f"Selection Error: {e}")
        await update.callback_query.answer("选择出错，请刷新")
