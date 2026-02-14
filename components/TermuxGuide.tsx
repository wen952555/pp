import React from 'react';
import { TerminalBlock } from './TerminalBlock';
import { Terminal, Shield, Play, FolderPlus } from 'lucide-react';

export const TermuxGuide: React.FC = () => {
  return (
    <div className="space-y-8 max-w-3xl mx-auto">
      <div className="text-center mb-8">
        <h2 className="text-3xl font-bold text-white flex items-center justify-center gap-3">
          <Terminal className="text-green-500" />
          Termux 部署指南 (Pro版)
        </h2>
        <p className="text-gray-400 mt-2">只需4步，在 Android 上部署你的私人 PikPak 助手。</p>
      </div>

      <div className="relative pl-8 border-l border-gray-700 space-y-12">
        {/* Step 1 */}
        <div className="relative">
          <div className="absolute -left-[41px] bg-gray-800 border border-gray-600 rounded-full w-8 h-8 flex items-center justify-center text-white font-bold">1</div>
          <h3 className="text-xl font-semibold text-white mb-2">创建项目文件夹</h3>
          <p className="text-gray-400 mb-4">打开 Termux，输入以下命令创建一个干净的文件夹。</p>
          <TerminalBlock 
            code={`mkdir pikpak-bot
cd pikpak-bot`} 
          />
        </div>

        {/* Step 2 */}
        <div className="relative">
          <div className="absolute -left-[41px] bg-gray-800 border border-gray-600 rounded-full w-8 h-8 flex items-center justify-center text-white font-bold">2</div>
          <h3 className="text-xl font-semibold text-white mb-2">创建文件</h3>
          <p className="text-gray-400 mb-4">
            将 "Generate Script" 选项卡中生成的 4 个文件内容复制进去。
            <br/>你可以使用 <code>nano 文件名</code> 来创建和编辑。
          </p>
          <TerminalBlock 
            code={`# 示例:
nano setup.sh 
# (粘贴 setup.sh 内容 -> Ctrl+X 保存 -> Y -> 回车)

nano requirements.txt
# (粘贴 requirements.txt 内容...)

nano bot.py
# (粘贴 bot.py 内容...)

nano start.sh
# (粘贴 start.sh 内容...)`} 
          />
        </div>

        {/* Step 3 */}
        <div className="relative">
          <div className="absolute -left-[41px] bg-gray-800 border border-gray-600 rounded-full w-8 h-8 flex items-center justify-center text-white font-bold">3</div>
          <h3 className="text-xl font-semibold text-white mb-2">一键安装环境</h3>
          <p className="text-gray-400 mb-4">
            运行 setup 脚本。它会自动安装 Python、Git、FFmpeg (用于媒体处理) 和所有依赖库。
            <br/><span className="text-yellow-400">注意：脚本运行过程中会要求你输入 Token 和账号密码。</span>
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
          <h3 className="text-xl font-semibold text-white mb-2">启动机器人</h3>
          <p className="text-gray-400 mb-4">一切就绪，运行启动脚本！</p>
          <TerminalBlock 
            code={`./start.sh`} 
          />
          <div className="bg-gray-800 p-4 rounded-lg border border-gray-700 mt-4 flex gap-3">
             <Shield className="text-green-400 shrink-0" />
             <p className="text-sm text-gray-300">
                <strong>后台运行技巧：</strong> 建议安装 Screen (<code>pkg install screen</code>)，然后使用 <code>screen -S bot</code> 创建新窗口运行机器人，这样关闭 Termux 后它依然会在后台运行。
             </p>
          </div>
        </div>
      </div>
    </div>
  );
};