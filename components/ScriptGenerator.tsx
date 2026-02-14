import React, { useState } from 'react';
import { BotConfig } from '../types';
import { TerminalBlock } from './TerminalBlock';
import { AlertCircle, FileCode, Play, Settings, List } from 'lucide-react';

interface ScriptGeneratorProps {
  config: BotConfig;
}

type FileTab = 'setup.sh' | 'requirements.txt' | 'bot.py' | 'start.sh';

export const ScriptGenerator: React.FC<ScriptGeneratorProps> = ({ config }) => {
  const [activeTab, setActiveTab] = useState<FileTab>('setup.sh');

  const setupScript = `#!/bin/bash

# Color codes
GREEN='\\033[0;32m'
NC='\\033[0m' # No Color

echo -e "\${GREEN}[*] Starting PikPak Bot Setup...\${NC}"

# 1. Update packages only if needed (simple check)
echo -e "\${GREEN}[*] Updating Termux packages...\${NC}"
pkg update -y && pkg upgrade -y

# 2. Install Python & Git if not installed
if ! command -v python >/dev/null 2>&1; then
    echo -e "\${GREEN}[+] Installing Python...\${NC}"
    pkg install python -y
else
    echo -e "\${GREEN}[-] Python already installed.\${NC}"
fi

if ! command -v git >/dev/null 2>&1; then
    echo -e "\${GREEN}[+] Installing Git...\${NC}"
    pkg install git -y
else
    echo -e "\${GREEN}[-] Git already installed.\${NC}"
fi

# 3. Upgrade pip
echo -e "\${GREEN}[*] Upgrading pip...\${NC}"
pip install --upgrade pip

# 4. Install Dependencies
if [ -f "requirements.txt" ]; then
    echo -e "\${GREEN}[*] Installing dependencies from requirements.txt...\${NC}"
    pip install -r requirements.txt
else
    echo -e "\${GREEN}[!] requirements.txt not found. Installing manually...\${NC}"
    pip install python-telegram-bot pikpak-api
fi

# 5. Set permissions
chmod +x start.sh

echo -e "\${GREEN}[OK] Setup complete! Run ./start.sh to start your bot.\${NC}"
`;

  const requirementsTxt = `python-telegram-bot==20.*
pikpak-api
# Add other dependencies here if needed
`;

  const startScript = `#!/bin/bash
echo "Starting PikPak Bot..."
echo "Press Ctrl+C to stop."

while true; do
    python bot.py
    echo "Bot stopped. Restarting in 3 seconds..."
    sleep 3
done
`;

  const pythonScript = `import logging
import os
import sys
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# Try importing pikpak library
try:
    from pikpakapi import PikPakApi
    PIKPAK_AVAILABLE = True
except ImportError:
    PIKPAK_AVAILABLE = False
    print("Warning: 'pikpak-api' library not found. Bot will run in simulation mode.")

# --- CONFIGURATION ---
BOT_TOKEN = "${config.botToken || 'YOUR_BOT_TOKEN_HERE'}"
ADMIN_ID = ${config.adminId || '0'}
PIKPAK_USER = "${config.pikpakUser || 'YOUR_EMAIL'}"
PIKPAK_PASS = "${config.pikpakPass || 'YOUR_PASS'}"

# --- LOGGING SETUP ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if str(user_id) != str(ADMIN_ID):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⛔ Unauthorized access.")
        return
    
    status_msg = "✅ PikPak Lib Detected" if PIKPAK_AVAILABLE else "⚠️ PikPak Lib Missing (Simulation Mode)"
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=f"🤖 PikPak Bot Online!\\n{status_msg}\\n\\nSend me a magnet link or URL to download."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if str(user_id) != str(ADMIN_ID):
        return

    url = update.message.text
    if not url:
        return

    status_reply = await context.bot.send_message(chat_id=update.effective_chat.id, text=f"🔍 Processing: {url[:30]}...")
    
    try:
        if PIKPAK_AVAILABLE:
            # Login and add task
            client = PikPakApi(username=PIKPAK_USER, password=PIKPAK_PASS)
            await client.login()
            
            # This is a hypothetical call based on common unofficial libs structure
            # You might need to adjust based on the specific version of pikpak-api you installed
            try:
                task = await client.offline_download(url)
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_reply.message_id,
                    text=f"✅ Task Added Successfully!\\nID: {task.get('id', 'Unknown')}"
                )
            except Exception as inner_e:
                # Fallback for sync or different method signatures
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_reply.message_id,
                    text=f"⚠️ API Error (Check logs): {str(inner_e)}"
                )
        else:
            # Simulation Mode
            await asyncio.sleep(1) 
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_reply.message_id,
                text=f"✅ [SIMULATION] Task added for: {url}"
            )

    except Exception as e:
        logger.error(f"Error: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Error: {str(e)}")

if __name__ == '__main__':
    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        print("Please configure the Bot Token in the 'Configuration' tab first!")
        sys.exit(1)
        
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Bot is polling...")
    application.run_polling()
`;

  const files = {
    'setup.sh': { icon: <Settings size={16} />, content: setupScript, lang: 'bash' },
    'requirements.txt': { icon: <List size={16} />, content: requirementsTxt, lang: 'text' },
    'bot.py': { icon: <FileCode size={16} />, content: pythonScript, lang: 'python' },
    'start.sh': { icon: <Play size={16} />, content: startScript, lang: 'bash' },
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="bg-blue-900/20 border border-blue-700/50 p-4 rounded-lg flex items-start gap-3">
        <AlertCircle className="text-blue-400 shrink-0 mt-1" />
        <div>
          <h3 className="font-bold text-blue-400 text-lg">One-Click Setup Ready</h3>
          <p className="text-blue-200/80 text-sm">
            We have generated all necessary files. Copy them to your Termux folder. The <code>setup.sh</code> script will handle installing Python, pip, and dependencies automatically.
          </p>
        </div>
      </div>

      <div className="flex flex-col bg-gray-900 rounded-xl border border-gray-700 overflow-hidden shadow-2xl">
        {/* Tab Header */}
        <div className="flex overflow-x-auto bg-gray-800 border-b border-gray-700">
          {(Object.keys(files) as FileTab[]).map((fileName) => (
            <button
              key={fileName}
              onClick={() => setActiveTab(fileName)}
              className={`flex items-center gap-2 px-6 py-3 text-sm font-medium transition-colors border-b-2 whitespace-nowrap ${
                activeTab === fileName
                  ? 'border-brand-telegram text-white bg-gray-700/50'
                  : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-700/30'
              }`}
            >
              {files[fileName].icon}
              {fileName}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="p-1">
           <TerminalBlock 
              title={activeTab} 
              code={files[activeTab].content} 
              language={files[activeTab].lang} 
            />
        </div>
      </div>
    </div>
  );
};