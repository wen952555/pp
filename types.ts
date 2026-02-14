export interface BotConfig {
  botToken: string;
  adminId: string;
  pikpakUser: string;
  pikpakPass: string;
}

export interface ChatMessage {
  role: 'user' | 'model';
  text: string;
  timestamp: number;
}

export enum AppStep {
  CONFIG = 0,
  SCRIPT_GEN = 1,
  TERMUX_SETUP = 2,
  AI_HELP = 3
}