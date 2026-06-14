"use client";

import { Store } from "./useStore";

export interface VoiceSettings {
  enabled: boolean;
  volume: number;
  rate: number;
  mutedAgents: Record<string, boolean>;
}

const DEFAULT_SETTINGS: VoiceSettings = {
  enabled: true,
  volume: 1.0,
  rate: 1.0,
  mutedAgents: {
    "Mission Commander Agent": false,
  },
};

// Helper to load settings from localStorage
const loadSettings = (): VoiceSettings => {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  try {
    const saved = localStorage.getItem("hail_mary:voice:settings");
    if (saved) {
      const parsed = JSON.parse(saved);
      // Ensure all keys are populated
      return {
        enabled: parsed.enabled ?? DEFAULT_SETTINGS.enabled,
        volume: parsed.volume ?? DEFAULT_SETTINGS.volume,
        rate: parsed.rate ?? DEFAULT_SETTINGS.rate,
        mutedAgents: {
          ...DEFAULT_SETTINGS.mutedAgents,
          ...(parsed.mutedAgents || {}),
        },
      };
    }
  } catch (e) {
    console.error("Failed to load voice settings", e);
  }
  return DEFAULT_SETTINGS;
};

// Initialize reactive store
export const voiceSettingsStore = new Store<VoiceSettings>(loadSettings());

// Save settings to localStorage on change
voiceSettingsStore.subscribe((state) => {
  if (typeof window !== "undefined") {
    localStorage.setItem("hail_mary:voice:settings", JSON.stringify(state));
  }
});

class AgentVoiceService {
  private queue: { agentName: string; text: string }[] = [];
  private isSpeaking = false;
  private currentUtterance: SpeechSynthesisUtterance | null = null;

  constructor() {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      // Chrome/Firefox occasionally require triggering voiceschanged
      window.speechSynthesis.onvoiceschanged = () => {};
    }
  }

  /**
   * Enqueues a text string for a specific agent to be spoken aloud.
   */
  speak(agentName: string, text: string) {
    if (typeof window === "undefined" || !window.speechSynthesis) return;

    this.queue.push({ agentName, text });
    this.processQueue();
  }

  /**
   * Processes the next item in the speech queue sequentially.
   */
  private processQueue() {
    if (this.isSpeaking || this.queue.length === 0) return;

    const settings = voiceSettingsStore.getState();
    if (!settings.enabled) {
      // If disabled, clear the queue and cancel any active speech
      this.cancelAll();
      return;
    }

    const nextItem = this.queue.shift();
    if (!nextItem) return;

    const { agentName, text } = nextItem;

    // Skip if agent is muted
    if (settings.mutedAgents[agentName]) {
      setTimeout(() => this.processQueue(), 50);
      return;
    }

    this.isSpeaking = true;

    // Clean up text formatting and underscores for cleaner speech
    const cleanedText = text
      .replace(/_/g, " ")
      .replace(/[\u2600-\u27BF]/g, ""); // remove common emojis

    const utterance = new SpeechSynthesisUtterance(cleanedText);
    this.currentUtterance = utterance;

    // Apply global volume/speed adjustments
    utterance.volume = settings.volume;
    
    // Default rate/pitch properties
    let agentRate = settings.rate;
    let agentPitch = 1.0;

    const voices = window.speechSynthesis.getVoices();
    let selectedVoice: SpeechSynthesisVoice | null = null;

    // Apply voice personality adjustments
    if (agentName.includes("Navigation")) {
      agentPitch = 0.85; // calm, deep
      agentRate = settings.rate * 0.9; // measured/slow
      // Look for male voice
      selectedVoice =
        voices.find(
          (v) =>
            v.lang.startsWith("en-") &&
            (v.name.toLowerCase().includes("david") ||
              v.name.toLowerCase().includes("male") ||
              v.name.toLowerCase().includes("premium"))
        ) || null;
    } else if (agentName.includes("Resource") || agentName.includes("Fuel")) {
      agentPitch = 1.05; // technical, focused
      agentRate = settings.rate * 1.0;
      // Look for female voice
      selectedVoice =
        voices.find(
          (v) =>
            v.lang.startsWith("en-") &&
            (v.name.toLowerCase().includes("zira") ||
              v.name.toLowerCase().includes("female") ||
              v.name.toLowerCase().includes("hazel"))
        ) || null;
    } else if (agentName.includes("Safety")) {
      agentPitch = 0.75; // deep, serious, authoritative
      agentRate = settings.rate * 0.85;
      // Look for authoritative voice
      selectedVoice =
        voices.find(
          (v) =>
            v.lang.startsWith("en-") &&
            (v.name.toLowerCase().includes("hazel") ||
              v.name.toLowerCase().includes("google") ||
              v.name.toLowerCase().includes("male"))
        ) || null;
    } else if (agentName.includes("Science")) {
      agentPitch = 1.2; // curious, slightly higher
      agentRate = settings.rate * 1.05; // faster
      selectedVoice =
        voices.find(
          (v) =>
            v.lang.startsWith("en-") &&
            (v.name.toLowerCase().includes("mark") ||
              v.name.toLowerCase().includes("natural"))
        ) || null;
    } else if (agentName.includes("Commander")) {
      agentPitch = 0.95; // confident leadership
      agentRate = settings.rate * 0.95;
      selectedVoice =
        voices.find(
          (v) =>
            v.lang.startsWith("en-") &&
            (v.name.toLowerCase().includes("google") ||
              v.name.toLowerCase().includes("natural") ||
              v.name.toLowerCase().includes("david"))
        ) || null;
    }

    if (selectedVoice) {
      utterance.voice = selectedVoice;
    }

    utterance.pitch = agentPitch;
    utterance.rate = agentRate;

    utterance.onend = () => {
      this.isSpeaking = false;
      this.currentUtterance = null;
      // Pause slightly between turns for realism
      setTimeout(() => this.processQueue(), 500);
    };

    utterance.onerror = (e) => {
      console.error("[SpeechSynthesis] Error during playback:", e);
      this.isSpeaking = false;
      this.currentUtterance = null;
      setTimeout(() => this.processQueue(), 100);
    };

    window.speechSynthesis.speak(utterance);
  }

  /**
   * Cancels any active speaking and flushes the queue.
   */
  cancelAll() {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
      this.queue = [];
      this.isSpeaking = false;
      this.currentUtterance = null;
    }
  }

  /**
   * Clear queue items only, leaving the currently speaking item.
   */
  clearQueue() {
    this.queue = [];
  }
}

export const agentVoiceService = new AgentVoiceService();
