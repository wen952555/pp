
import os
import logging
import time
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
    level=logging.WARNING # Changed to WARNING to reduce I/O lag on Termux
)
logger = logging.getLogger("PikPakBot")
logger.setLevel(logging.INFO)

# --- Simple Memory Cache ---
class SimpleCache:
    def __init__(self):
        self._cache = {}

    def get(self, key):
        if key in self._cache:
            data, expiry = self._cache[key]
            if time.time() < expiry:
                return data
            else:
                del self._cache[key]
        return None

    def set(self, key, value, ttl=300): # Default 5 mins
        self._cache[key] = (value, time.time() + ttl)

    def clear(self):
        self._cache.clear()

# Global Cache Instance
global_cache = SimpleCache()

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
    
    if not allowed_ids:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⛔ **配置错误**: 管理员 ID 未设置，无法使用。")
        return False

    if user_id not in allowed_ids:
        # Silent reject to save resources, or verify strict mode
        # await context.bot.send_message(chat_id=update.effective_chat.id, text=f"⛔ 无权访问 (ID: `{user_id}`)")
        return False
        
    return True
