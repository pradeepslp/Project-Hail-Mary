export interface CMIMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
}

export type CMIOrbState = "idle" | "listening" | "thinking" | "speaking" | "muted";
export type CMIVoiceMode = "ptt" | "hands-free" | "muted";

export interface CMIState {
  orbState: CMIOrbState;
  voiceMode: CMIVoiceMode;
  isListening: boolean;
  isSpeaking: boolean;
  currentTranscript: string;
}

export interface CMIMemoryEntry {
  id: string;
  text: string;
  type: "conversation" | "event" | "decision";
  timestamp: string;
  metadata?: Record<string, any>;
  vector?: number[]; // Dynamic OpenAI Embeddings vector
}
