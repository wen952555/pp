import React from 'react';
import { TerminalBlock } from './TerminalBlock';
import { Terminal, Shield, Play } from 'lucide-react';

export const TermuxGuide: React.FC = () => {
  return (
    <div className="space-y-8 max-w-3xl mx-auto">
      <div className="text-center mb-8">
        <h2 className="text-3xl font-bold text-white flex items-center justify-center gap-3">
          <Terminal className="text-green-500" />
          Termux Deployment
        </h2>
        <p className="text-gray-400 mt-2">Run these commands in your Termux app on Android.</p>
      </div>

      <div className="relative pl-8 border-l border-gray-700 space-y-12">
        {/* Step 1 */}
        <div className="relative">
          <div className="absolute -left-[41px] bg-gray-800 border border-gray-600 rounded-full w-8 h-8 flex items-center justify-center text-white font-bold">1</div>
          <h3 className="text-xl font-semibold text-white mb-2">Update & Install Dependencies</h3>
          <p className="text-gray-400 mb-4">First, ensure your package lists are up to date and install Python.</p>
          <TerminalBlock 
            code={`pkg update && pkg upgrade -y
pkg install python git -y
pip install --upgrade pip`} 
          />
        </div>

        {/* Step 2 */}
        <div className="relative">
          <div className="absolute -left-[41px] bg-gray-800 border border-gray-600 rounded-full w-8 h-8 flex items-center justify-center text-white font-bold">2</div>
          <h3 className="text-xl font-semibold text-white mb-2">Install Python Libraries</h3>
          <p className="text-gray-400 mb-4">Install the Telegram Bot library. You may also need to find a working PikPak wrapper from GitHub (e.g., via git clone) or PyPI.</p>
          <TerminalBlock 
            code={`pip install python-telegram-bot
# Example for a pikpak wrapper (verify the package name first)
pip install pikpak-api`} 
          />
        </div>

        {/* Step 3 */}
        <div className="relative">
          <div className="absolute -left-[41px] bg-gray-800 border border-gray-600 rounded-full w-8 h-8 flex items-center justify-center text-white font-bold">3</div>
          <h3 className="text-xl font-semibold text-white mb-2">Create the Bot File</h3>
          <p className="text-gray-400 mb-4">
            You can use `nano` to paste the code you generated in the previous step.
          </p>
          <TerminalBlock 
            code={`pkg install nano
nano bot.py
# (Paste the code from the generator, then Press Ctrl+X, Y, Enter)`} 
          />
        </div>

        {/* Step 4 */}
        <div className="relative">
          <div className="absolute -left-[41px] bg-brand-pikpak border border-yellow-600 rounded-full w-8 h-8 flex items-center justify-center text-black font-bold shadow-lg shadow-yellow-500/50">
            <Play size={14} fill="currentColor" />
          </div>
          <h3 className="text-xl font-semibold text-white mb-2">Run the Bot</h3>
          <p className="text-gray-400 mb-4">Start your bot. It should print "Bot is polling...".</p>
          <TerminalBlock 
            code={`python bot.py`} 
          />
          <div className="bg-gray-800 p-4 rounded-lg border border-gray-700 mt-4 flex gap-3">
             <Shield className="text-green-400 shrink-0" />
             <p className="text-sm text-gray-300">
                <strong>Tip:</strong> To keep the bot running in the background even when you close Termux, consider using <code>nohup python bot.py &</code> or installing a process manager like <code>pm2</code> (requires nodejs).
             </p>
          </div>
        </div>
      </div>
    </div>
  );
};