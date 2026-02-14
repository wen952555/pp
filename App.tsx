import React, { useState } from 'react';
import { BotConfig, AppStep } from './types';
import { ConfigForm } from './components/ConfigForm';
import { ScriptGenerator } from './components/ScriptGenerator';
import { TermuxGuide } from './components/TermuxGuide';
import { AiChat } from './components/AiChat';
import { Terminal, Settings, Code2, Bot, HelpCircle, HardDrive } from 'lucide-react';

const App: React.FC = () => {
  const [step, setStep] = useState<AppStep>(AppStep.CONFIG);
  const [config, setConfig] = useState<BotConfig>({
    botToken: '',
    adminId: '',
    pikpakUser: '',
    pikpakPass: ''
  });

  const renderStep = () => {
    switch (step) {
      case AppStep.CONFIG:
        return <ConfigForm config={config} setConfig={setConfig} />;
      case AppStep.SCRIPT_GEN:
        return <ScriptGenerator config={config} />;
      case AppStep.TERMUX_SETUP:
        return <TermuxGuide />;
      case AppStep.AI_HELP:
        return <AiChat />;
      default:
        return <ConfigForm config={config} setConfig={setConfig} />;
    }
  };

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-200 font-sans selection:bg-brand-telegram selection:text-white pb-20">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 backdrop-blur-md bg-[#0f172a]/80 border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="bg-gradient-to-br from-brand-pikpak to-orange-500 p-2 rounded-lg shadow-lg shadow-orange-500/20">
                <HardDrive className="text-gray-900" size={24} />
              </div>
              <h1 className="text-xl font-bold tracking-tight text-white hidden sm:block">
                PikPak <span className="text-gray-500">x</span> Termux
              </h1>
            </div>
            <div className="flex items-center gap-4">
              <a 
                href="https://termux.com" 
                target="_blank" 
                rel="noreferrer" 
                className="text-xs font-mono text-gray-500 hover:text-white transition-colors"
              >
                v1.0.0
              </a>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content Layout */}
      <div className="max-w-7xl mx-auto mt-8 px-4 sm:px-6 lg:px-8 flex flex-col lg:flex-row gap-8">
        
        {/* Sidebar Navigation */}
        <aside className="lg:w-64 shrink-0">
          <div className="sticky top-24 space-y-2">
            <button
              onClick={() => setStep(AppStep.CONFIG)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                step === AppStep.CONFIG 
                  ? 'bg-brand-telegram text-white shadow-lg shadow-blue-500/20' 
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              }`}
            >
              <Settings size={20} />
              <span className="font-medium">Configuration</span>
            </button>
            
            <button
              onClick={() => setStep(AppStep.SCRIPT_GEN)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                step === AppStep.SCRIPT_GEN 
                  ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-500/20' 
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              }`}
            >
              <Code2 size={20} />
              <span className="font-medium">Generate Script</span>
            </button>
            
            <button
              onClick={() => setStep(AppStep.TERMUX_SETUP)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                step === AppStep.TERMUX_SETUP 
                  ? 'bg-gray-700 text-white shadow-lg border border-gray-600' 
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              }`}
            >
              <Terminal size={20} />
              <span className="font-medium">Termux Setup</span>
            </button>

             <button
              onClick={() => setStep(AppStep.AI_HELP)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                step === AppStep.AI_HELP 
                  ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/20' 
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              }`}
            >
              <Bot size={20} />
              <span className="font-medium">AI Troubleshooting</span>
            </button>
          </div>
        </aside>

        {/* Main View Area */}
        <main className="flex-1 min-w-0">
          <div className="bg-gray-900/50 rounded-2xl p-1 min-h-[600px] border border-gray-800/50 backdrop-blur-sm">
             <div className="p-6 md:p-8">
               {renderStep()}
             </div>
          </div>
        </main>
      </div>
      
      {/* Footer hint */}
      {step === AppStep.CONFIG && (
        <div className="fixed bottom-6 right-6 lg:hidden z-50">
          <button 
            onClick={() => setStep(AppStep.SCRIPT_GEN)}
            className="bg-brand-telegram text-white p-4 rounded-full shadow-xl shadow-blue-500/40 flex items-center justify-center"
          >
            <Code2 size={24} />
          </button>
        </div>
      )}
    </div>
  );
};

export default App;