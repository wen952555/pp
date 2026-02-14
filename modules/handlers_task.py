
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .accounts import account_mgr
from .utils import extract_direct_url_with_ytdlp

async def show_offline_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    client = await account_mgr.get_client(user_id)
    if not client: return

    try:
        resp = await client.offline_list()
        tasks = resp.get('tasks', []) if isinstance(resp, dict) else (resp if isinstance(resp, list) else [])
        
        text = "📉 **离线任务列表**\n"
        keyboard = []
        
        if not tasks:
            text += "(暂无任务)"
        
        for t in tasks[:10]: # Show max 10 to avoid limit
            status_icon = "✅" if t.get('phase') == 'PHASE_TYPE_COMPLETE' else "🚀"
            if t.get('phase') == 'PHASE_TYPE_ERROR': status_icon = "❌"
            
            name = t.get('name', 'Unknown')[:15]
            progress = t.get('progress', 0)
            
            btn_text = f"{status_icon} {name} {progress}%"
            # Delete button
            keyboard.append([
                InlineKeyboardButton(btn_text, callback_data="noop"),
                InlineKeyboardButton("🗑", callback_data=f"task_del:{t.get('id')}")
            ])
        
        keyboard.append([InlineKeyboardButton("🔄 刷新任务", callback_data="tasks_refresh")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode='Markdown')
            
    except Exception as e:
        if update.callback_query: await update.callback_query.answer(f"Error: {e}")

async def handle_task_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    
    if data == "tasks_refresh":
        await show_offline_tasks(update, context)
    elif data.startswith("task_del:"):
        task_id = data.split(':')[1]
        client = await account_mgr.get_client(user_id)
        try:
            # Compat for different api versions
            if hasattr(client, 'delete_offline_task'): await client.delete_offline_task([task_id])
            elif hasattr(client, 'offline_delete'): await client.offline_delete([task_id])
            await query.answer("任务已删除")
            await show_offline_tasks(update, context)
        except Exception as e:
            await query.answer(f"删除失败: {e}", show_alert=True)

async def add_download_task(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text: str):
    """Add tasks from text (supports multiline)"""
    user_id = update.effective_user.id
    client = await account_mgr.get_client(user_id)
    if not client: 
        await context.bot.send_message(update.effective_chat.id, "⚠️ 请先登录账号")
        return

    urls = raw_text.split('\n')
    count = 0
    msg = await context.bot.send_message(update.effective_chat.id, "⏳ 正在解析链接...")
    
    for url in urls:
        url = url.strip()
        if not url: continue
        
        final_url = url
        # Social Media Pre-processing
        if any(x in url for x in ['tiktok.com', 'twitter.com', 'x.com', 'youtube.com', 'instagram.com']):
            direct = extract_direct_url_with_ytdlp(url)
            if direct: final_url = direct
            
        try:
            await client.offline_download(final_url)
            count += 1
        except Exception as e:
            pass # Ignore errors for individual links in batch
            
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id, 
        message_id=msg.message_id, 
        text=f"✅ 已成功添加 {count} 个离线任务"
    )
