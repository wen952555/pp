
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ContextTypes

# Load Env
current_dir = Path(__file__).parent.parent.resolve()
parent_env = current_dir.parent / '.env'
if parent_env.exists(): load_dotenv(dotenv_path=parent_env)
else: load_dotenv()

# Constants
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
DOWNLOAD_PATH = "downloads"
WHITELIST_FILE = "whitelist.txt"
ACCOUNTS_FILE = "accounts.json"
USER_PREFS_FILE = "user_prefs.json"
WEB_PORT = 8080

# Proxy Support
HTTP_PROXY = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
HTTPS_PROXY = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("PikPakBot")

# Auth Helper
def get_whitelist():
    ids = []
    if ADMIN_ID:
        ids.append(str(ADMIN_ID).strip())
    
    if os.path.exists(WHITELIST_FILE):
        with open(WHITELIST_FILE, 'r') as f:
            for line in f:
                if line.strip(): ids.append(line.strip())
    return ids

async def check_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_user:
        return False
        
    user_id = str(update.effective_user.id)
    allowed_ids = get_whitelist()
    
    # DEBUG PRINT
    print(f"[DEBUG] Msg from {user_id}. Whitelist: {allowed_ids}")

    if not allowed_ids:
        print("[WARN] Whitelist is empty! Please check ADMIN_ID in .env")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⛔ **配置错误**: 管理员 ID 未设置，无法使用。")
        return False

    if user_id not in allowed_ids:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"⛔ 无权访问 (ID: `{user_id}`)")
        return False
        
    return True
