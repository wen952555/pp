
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
WEB_PORT = 8080

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("PikPakBot")

# Auth Helper
def get_whitelist():
    ids = [str(ADMIN_ID)] if ADMIN_ID else []
    if os.path.exists(WHITELIST_FILE):
        with open(WHITELIST_FILE, 'r') as f:
            for line in f:
                if line.strip(): ids.append(line.strip())
    return ids

async def check_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = str(update.effective_user.id)
    if user_id not in get_whitelist():
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"⛔ 无权访问 (ID: {user_id})")
        return False
    return True
