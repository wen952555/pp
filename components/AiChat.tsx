import React, { useState, useRef, useEffect } from 'react';
import { generateHelpResponse } from '../services/geminiService';
import { ChatMessage } from '../types';
import { Send, Bot, User, Sparkles, Loader2 } from 'lucide-react';

export const AiChat: React.FC = () => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: 'model', text: 'Hello! I am your Termux & PikPak deployment assistant. Ask me if you get stuck with installation errors or Python scripts!', timestamp: Date.now() }
  ]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userText = input;
    setInput('');
    setLoading(true);

    const newMessages = [
      ...messages,
      { role: 'user', text: userText, timestamp: Date.now() } as ChatMessage
    ];
    setMessages(newMessages);

    // Context for AI: Last few messages
    const history = messages.slice(-5).map(m => m.text);

    const responseText = await generateHelpResponse(userText, history);

    setMessages([
      ...newMessages,
      { role: 'model', text: responseText, timestamp: Date.now() }
    ]);
    setLoading(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-[600px] bg-gray-900 rounded-xl border border-gray-700 shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-900 to-gray-900 p-4 border-b border-gray-700 flex items-center gap-2">
        <Sparkles className="text-purple-400" />
        <h3 className="font-bold text-white">Gemini Deployment Assistant</h3>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`flex gap-3 max-w-[85%] ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${msg.role === 'user' ? 'bg-blue-600' : 'bg-purple-600'}`}>
                {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
              </div>
              <div className={`p-3 rounded-lg text-sm leading-relaxed ${
                msg.role === 'user' 
                  ? 'bg-blue-600/20 border border-blue-500/30 text-blue-100' 
                  : 'bg-gray-800 border border-gray-700 text-gray-200'
              }`}>
                 {/* Simple formatting for code blocks in response */}
                 {msg.text.split('```').map((part, i) => 
                    i % 2 === 1 ? (
                      <pre key={i} className="bg-black/50 p-2 rounded my-2 overflow-x-auto font-mono text-xs text-green-400">
                        {part}
                      </pre>
                    ) : (
                      <p key={i} className="whitespace-pre-wrap">{part}</p>
                    )
                 )}
              </div>
            </div>
          </div>
        ))}
        {loading && (
           <div className="flex justify-start">
             <div className="flex gap-3 max-w-[85%]">
               <div className="w-8 h-8 rounded-full bg-purple-600 flex items-center justify-center shrink-0 animate-pulse">
                 <Bot size={16} />
               </div>
               <div className="p-3 rounded-lg bg-gray-800 border border-gray-700 flex items-center gap-2 text-gray-400 text-sm">
                 <Loader2 size={16} className="animate-spin" />
                 Thinking...
               </div>
             </div>
           </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 bg-gray-900 border-t border-gray-800">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your error or question here..."
            className="flex-1 bg-gray-950 border border-gray-700 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="bg-purple-600 hover:bg-purple-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg transition-colors flex items-center justify-center"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
};