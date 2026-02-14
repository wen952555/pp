import React from 'react';
import { TerminalBlock } from './TerminalBlock';
import { Terminal, Shield, Play, FolderPlus } from 'lucide-react';

export const TermuxGuide: React.FC = () => {
  return (
    <div className="space-y-8 max-w-3xl mx-auto">
      <div className="text-center mb-8">
        <h2 className="text-3xl font-bold text-white flex items-center justify-center gap-3">
          <Terminal className="text-green-500" />
          Termux Deployment
        </h2>
        <p className="text-gray-400 mt-2">Follow these simple steps to get your bot running.</p>
      </div>

      <div className="relative pl-8 border-l border-gray-700 space-y-12">
        {/* Step 1 */}
        <div className="relative">
          <div className="absolute -left-[41px] bg-gray-800 border border-gray-600 rounded-full w-8 h-8 flex items-center justify-center text-white font-bold">1</div>
          <h3 className="text-xl font-semibold text-white mb-2">Create Project Folder</h3>
          <p className="text-gray-400 mb-4">Open Termux and create a directory for your bot.</p>
          <TerminalBlock 
            code={`mkdir pikpak-bot
cd pikpak-bot`} 
          />
        </div>

        {/* Step 2 */}
        <div className="relative">
          <div className="absolute -left-[41px] bg-gray-800 border border-gray-600 rounded-full w-8 h-8 flex items-center justify-center text-white font-bold">2</div>
          <h3 className="text-xl font-semibold text-white mb-2">Create Files</h3>
          <p className="text-gray-400 mb-4">
            Create the 4 files generated in the <strong>"Generate Script"</strong> tab (<code>setup.sh</code>, <code>requirements.txt</code>, <code>bot.py</code>, <code>start.sh</code>).
            <br/>You can use <code>nano filename</code> to create/edit files.
          </p>
          <TerminalBlock 
            code={`# Example:
nano setup.sh 
# (Paste setup.sh content, Save with Ctrl+X -> Y -> Enter)

nano requirements.txt
# (Paste requirements.txt content...)

nano bot.py
# (Paste bot.py content...)

nano start.sh
# (Paste start.sh content...)`} 
          />
        </div>

        {/* Step 3 */}
        <div className="relative">
          <div className="absolute -left-[41px] bg-gray-800 border border-gray-600 rounded-full w-8 h-8 flex items-center justify-center text-white font-bold">3</div>
          <h3 className="text-xl font-semibold text-white mb-2">Run One-Click Setup</h3>
          <p className="text-gray-400 mb-4">
            Give execution permissions and run the setup script. This will automatically install Python, pip, and all required libraries.
          </p>
          <TerminalBlock 
            code={`chmod +x setup.sh start.sh
./setup.sh`} 
          />
        </div>

        {/* Step 4 */}
        <div className="relative">
          <div className="absolute -left-[41px] bg-brand-pikpak border border-yellow-600 rounded-full w-8 h-8 flex items-center justify-center text-black font-bold shadow-lg shadow-yellow-500/50">
            <Play size={14} fill="currentColor" />
          </div>
          <h3 className="text-xl font-semibold text-white mb-2">Start the Bot</h3>
          <p className="text-gray-400 mb-4">Run the start script. It includes a restart loop to keep your bot alive if it crashes.</p>
          <TerminalBlock 
            code={`./start.sh`} 
          />
          <div className="bg-gray-800 p-4 rounded-lg border border-gray-700 mt-4 flex gap-3">
             <Shield className="text-green-400 shrink-0" />
             <p className="text-sm text-gray-300">
                <strong>Tip:</strong> The <code>start.sh</code> script keeps the bot running in the foreground. To run it in the background, you can use a session manager like <code>tmux</code> (run <code>pkg install tmux</code>).
             </p>
          </div>
        </div>
      </div>
    </div>
  );
};