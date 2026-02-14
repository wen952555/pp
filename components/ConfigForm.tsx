import React from 'react';
import { BotConfig } from '../types';
import { Bot, User, Key, Lock } from 'lucide-react';

interface ConfigFormProps {
  config: BotConfig;
  setConfig: React.Dispatch<React.SetStateAction<BotConfig>>;
}

export const ConfigForm: React.FC<ConfigFormProps> = ({ config, setConfig }) => {
  const handleChange = (field: keyof BotConfig, value: string) => {
    setConfig((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <div className="space-y-6 max-w-2xl mx-auto p-6 bg-gray-800 rounded-xl border border-gray-700 shadow-lg">
      <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-2">
        <Bot className="text-brand-telegram" /> 
        Bot Configuration
      </h2>
      <p className="text-gray-400 mb-6">
        Enter your credentials to generate the Python script automatically. 
        Your data remains local in your browser until you generate the script.
      </p>

      <div className="grid gap-6">
        {/* Telegram Config */}
        <div className="space-y-4">
          <h3 className="text-sm uppercase tracking-wider text-gray-500 font-semibold border-b border-gray-700 pb-2">Telegram Details</h3>
          
          <div className="relative">
            <label className="block text-sm font-medium text-gray-300 mb-1">Telegram Bot Token</label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Key size={16} className="text-gray-500" />
              </div>
              <input
                type="text"
                value={config.botToken}
                onChange={(e) => handleChange('botToken', e.target.value)}
                placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
                className="w-full bg-gray-900 border border-gray-600 rounded-lg py-2 pl-10 pr-3 text-white placeholder-gray-600 focus:ring-2 focus:ring-brand-telegram focus:border-transparent outline-none transition-all"
              />
            </div>
            <p className="text-xs text-gray-500 mt-1">Get this from <a href="https://t.me/BotFather" target="_blank" rel="noreferrer" className="text-brand-telegram hover:underline">@BotFather</a></p>
          </div>

          <div className="relative">
            <label className="block text-sm font-medium text-gray-300 mb-1">Your Telegram Admin ID</label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <User size={16} className="text-gray-500" />
              </div>
              <input
                type="text"
                value={config.adminId}
                onChange={(e) => handleChange('adminId', e.target.value)}
                placeholder="123456789"
                className="w-full bg-gray-900 border border-gray-600 rounded-lg py-2 pl-10 pr-3 text-white placeholder-gray-600 focus:ring-2 focus:ring-brand-telegram focus:border-transparent outline-none transition-all"
              />
            </div>
            <p className="text-xs text-gray-500 mt-1">Check <a href="https://t.me/userinfobot" target="_blank" rel="noreferrer" className="text-brand-telegram hover:underline">@userinfobot</a> to find your ID.</p>
          </div>
        </div>

        {/* PikPak Config */}
        <div className="space-y-4 pt-4">
          <h3 className="text-sm uppercase tracking-wider text-gray-500 font-semibold border-b border-gray-700 pb-2">PikPak Credentials</h3>
          
          <div className="relative">
            <label className="block text-sm font-medium text-gray-300 mb-1">PikPak Username/Email</label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <User size={16} className="text-gray-500" />
              </div>
              <input
                type="text"
                value={config.pikpakUser}
                onChange={(e) => handleChange('pikpakUser', e.target.value)}
                placeholder="email@example.com"
                className="w-full bg-gray-900 border border-gray-600 rounded-lg py-2 pl-10 pr-3 text-white placeholder-gray-600 focus:ring-2 focus:ring-brand-pikpak focus:border-transparent outline-none transition-all"
              />
            </div>
          </div>

          <div className="relative">
            <label className="block text-sm font-medium text-gray-300 mb-1">PikPak Password</label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Lock size={16} className="text-gray-500" />
              </div>
              <input
                type="password"
                value={config.pikpakPass}
                onChange={(e) => handleChange('pikpakPass', e.target.value)}
                placeholder="********"
                className="w-full bg-gray-900 border border-gray-600 rounded-lg py-2 pl-10 pr-3 text-white placeholder-gray-600 focus:ring-2 focus:ring-brand-pikpak focus:border-transparent outline-none transition-all"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};