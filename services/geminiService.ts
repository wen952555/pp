import { GoogleGenAI } from "@google/genai";

const getClient = () => {
  const apiKey = process.env.API_KEY;
  if (!apiKey) {
    throw new Error("API Key is missing. Please check your environment configuration.");
  }
  return new GoogleGenAI({ apiKey });
};

export const generateHelpResponse = async (userPrompt: string, history: string[]): Promise<string> => {
  try {
    const ai = getClient();
    
    // Construct a context-aware prompt
    const systemInstruction = `
      You are an expert DevOps engineer specializing in Android Termux environments, Python scripting, the Telegram Bot API, and the PikPak cloud storage API.
      
      Your goal is to assist a user who is trying to deploy a Python-based Telegram bot on Termux to manage their PikPak account.
      
      Common issues you might solve:
      - 'pkg install' errors in Termux.
      - Python 'pip install' dependency issues.
      - How to get a Telegram Bot Token from BotFather.
      - How to find a Telegram User ID (Admin ID).
      - PikPak login issues or API limits.
      
      Provide concise, command-line friendly answers. Use Markdown for code blocks.
    `;

    const chat = ai.chats.create({
      model: 'gemini-3-flash-preview',
      config: {
        systemInstruction,
      },
      history: history.map(msg => ({
        role: 'user', 
        parts: [{ text: msg }] // Simplified history mapping for this demo
      })),
    });

    const result = await chat.sendMessage({ message: userPrompt });
    return result.text || "I couldn't generate a response. Please check your connection.";
  } catch (error) {
    console.error("Gemini API Error:", error);
    return "Error communicating with the AI assistant. Please try again later.";
  }
};