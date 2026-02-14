import React from 'react';
import { BotConfig } from '../types';
import { TerminalBlock } from './TerminalBlock';
import { AlertCircle } from 'lucide-react';

interface ScriptGeneratorProps {
  config: BotConfig;
}

export const ScriptGenerator: React.FC<ScriptGeneratorProps> = ({ config }) => {
  const pythonScript = `
import logging
import os
import sys
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
# Note: You need a pikpak library. Usually 'pikpak-api' or similar. 
# Since official SDKs vary, this is a conceptual implementation pattern.
# We will assume a 'pikpakpy' wrapper exists or you implement the login request manually.

# CONFIGURATION
BOT_TOKEN = "${config.botToken || 'YOUR_BOT_TOKEN_HERE'}"
ADMIN_ID = ${config.adminId || 'YOUR_ADMIN_ID_HERE'}
PIKPAK_USER = "${config.pikpakUser || 'YOUR_EMAIL'}"
PIKPAK_PASS = "${config.pikpakPass || 'YOUR_PASS'}"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Unauthorized.")
        return
    await context.bot.send_message(chat_id=update.effective_chat.id, text="PikPak Bot Active! Send me a magnet link or URL.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID):
        return

    url = update.message.text
    if not url:
        return

    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Processing link: {url}...")
    
    try:
        # --- PIKPAK LOGIC PLACEHOLDER ---
        # Here you would call: pikpak_client.offline_download(url)
        # For this template, we simulate success.
        # import pikpakapi
        # client = pikpakapi.PikPakApi(username=PIKPAK_USER, password=PIKPAK_PASS)
        # client.login()
        # task = client.offline_download(url)
        
        await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ Task added to PikPak successfully!")
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Error: {str(e)}")

if __name__ == '__main__':
    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        print("Please configure the Bot Token first!")
        sys.exit(1)
        
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    msg_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    
    application.add_handler(start_handler)
    application.add_handler(msg_handler)
    
    print("Bot is polling...")
    application.run_polling()
`;

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="bg-yellow-900/30 border border-yellow-700/50 p-4 rounded-lg flex items-start gap-3">
        <AlertCircle className="text-yellow-500 shrink-0 mt-1" />
        <div>
          <h3 className="font-bold text-yellow-500 text-lg">Important Note</h3>
          <p className="text-yellow-200/80 text-sm">
            This script uses the <code>python-telegram-bot</code> library. For PikPak interaction, you normally need a specific unofficial API wrapper (like <code>pikpak-api</code> or <code>pikpakpy</code>) from GitHub, as there is no single standard public SDK on PyPI.
            <br/><br/>
            The script below provides the <strong>Telegram Interface structure</strong>. You will need to install a PikPak library on Termux and uncomment the connection logic.
          </p>
        </div>
      </div>

      <div>
        <h3 className="text-xl font-bold text-white mb-2">1. Save this as <code className="text-green-400">bot.py</code></h3>
        <TerminalBlock title="bot.py" code={pythonScript} language="python" />
      </div>
    </div>
  );
};