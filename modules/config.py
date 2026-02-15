
import os
import logging
import time
from pathlib import Path
from dotenv import load_dotenv

# Load Env
current_dir = Path(__file__).parent.parent.resolve()
parent_env = current_dir.parent / '.env'
if parent_env.exists(): load_dotenv(dotenv_path=parent_env)
else: load_dotenv()

# Constants
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
WEB_PORT = 8080

# AList Config
ALIST_HOST = os.getenv("ALIST_HOST", "http://127.0.0.1:5244")
ALIST_USER = os.getenv("ALIST_USER", "admin")
ALIST_PASS = os.getenv("ALIST_PASS", "123456")

# Proxy Support
HTTP_PROXY = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
HTTPS_PROXY = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("Bot")

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
async def check_auth(update, context) -> bool:
    if not update.effective_user: return False
    user_id = str(update.effective_user.id)
    # Simple Admin Check
    if not ADMIN_ID:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⛔ **配置错误**: 管理员 ID (ADMIN_ID) 未设置。")
        return False
    
    if user_id != str(ADMIN_ID).strip():
        # Optional: Silent fail for unauthorized users or generic message
        return False
    return True
