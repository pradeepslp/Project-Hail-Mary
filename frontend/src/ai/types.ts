export interface AIConfiguration {
  provider: "mock" | "openai" | "gemini";
  openaiApiKey?: string;
  geminiApiKey?: string;
}
