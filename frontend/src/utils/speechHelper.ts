type SpeechProvider = "browser" | "openai" | "elevenlabs";

export class SpeechHelper {
  private queue: { text: string; provider: SpeechProvider; apiKey?: string; voiceId?: string }[] = [];
  private isPlaying: boolean = false;
  private currentAudio: HTMLAudioElement | null = null;
  private onSpeakingStateChange: (speaking: boolean) => void;

  constructor(onSpeakingStateChange: (speaking: boolean) => void) {
    this.onSpeakingStateChange = onSpeakingStateChange;
  }

  /**
   * Queue a sentence for playback.
   */
  queueSentence(text: string, provider: SpeechProvider, apiKey?: string, voiceId?: string) {
    const cleanText = text.trim();
    if (!cleanText) return;

    this.queue.push({ text: cleanText, provider, apiKey, voiceId });
    if (!this.isPlaying) {
      this.playNext();
    }
  }

  /**
   * Interrupt current playback immediately and clear the queue.
   */
  cancel() {
    this.queue = [];
    this.isPlaying = false;

    // Interrupt native speech
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }

    // Stop current HTML5 audio
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio.src = "";
      this.currentAudio = null;
    }

    this.onSpeakingStateChange(false);
  }

  private async playNext() {
    if (this.queue.length === 0) {
      this.isPlaying = false;
      this.onSpeakingStateChange(false);
      return;
    }

    this.isPlaying = true;
    this.onSpeakingStateChange(true);

    const item = this.queue.shift()!;

    try {
      if (item.provider === "openai" && item.apiKey) {
        await this.playOpenAITTS(item.text, item.apiKey, item.voiceId || "alloy");
      } else if (item.provider === "elevenlabs" && item.apiKey) {
        await this.playElevenLabsTTS(item.text, item.apiKey, item.voiceId || "21m00Tcm4TlvDq8ikWAM");
      } else {
        await this.playBrowserSpeech(item.text);
      }
    } catch (err) {
      console.warn(`[SpeechHelper] Premium TTS failed, falling back to browser synthesis:`, err);
      try {
        await this.playBrowserSpeech(item.text);
      } catch (fallbackErr) {
        console.error(`[SpeechHelper] Fallback speech synthesis failed:`, fallbackErr);
      }
    }

    // Call next item recursively
    this.playNext();
  }

  private playBrowserSpeech(text: string): Promise<void> {
    return new Promise((resolve) => {
      if (typeof window === "undefined" || !window.speechSynthesis) {
        resolve();
        return;
      }

      window.speechSynthesis.cancel(); // clear stuck utterances

      const utterance = new SpeechSynthesisUtterance(text);
      
      // Select a nice native English voice if available
      const voices = window.speechSynthesis.getVoices();
      const preferredVoice = voices.find(
        (v) =>
          v.lang.startsWith("en") &&
          (v.name.includes("Google") || v.name.includes("Natural") || v.name.includes("Microsoft"))
      );
      if (preferredVoice) utterance.voice = preferredVoice;

      utterance.rate = 0.88; // Slightly slower than normal speech for clear friendly companion voice
      utterance.pitch = 1.20// Friendly, warm, slightly higher pitch

      utterance.onend = () => resolve();
      utterance.onerror = () => resolve();

      window.speechSynthesis.speak(utterance);
    });
  }

  private playOpenAITTS(text: string, apiKey: string, voice: string): Promise<void> {
    return new Promise(async (resolve, reject) => {
      try {
        const response = await fetch("https://api.openai.com/v1/audio/speech", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${apiKey}`,
          },
          body: JSON.stringify({
            model: "tts-1",
            input: text,
            voice: voice, // onyx, alloy, nova, echo, fable, shimmer
            response_format: "mp3",
          }),
        });

        if (!response.ok) {
          throw new Error(`OpenAI TTS responded with ${response.status}`);
        }

        const audioBlob = await response.blob();
        const audioURL = URL.createObjectURL(audioBlob);

        const audio = new Audio(audioURL);
        this.currentAudio = audio;

        audio.onended = () => {
          URL.revokeObjectURL(audioURL);
          if (this.currentAudio === audio) this.currentAudio = null;
          resolve();
        };

        audio.onerror = () => {
          URL.revokeObjectURL(audioURL);
          if (this.currentAudio === audio) this.currentAudio = null;
          reject(new Error("Audio playback error"));
        };

        audio.play().catch(reject);
      } catch (err) {
        reject(err);
      }
    });
  }

  private playElevenLabsTTS(text: string, apiKey: string, voiceId: string): Promise<void> {
    return new Promise(async (resolve, reject) => {
      try {
        const response = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "xi-api-key": apiKey,
          },
          body: JSON.stringify({
            text: text,
            model_id: "eleven_monolingual_v1",
            voice_settings: {
              stability: 0.75,
              similarity_boost: 0.75,
            },
          }),
        });

        if (!response.ok) {
          throw new Error(`ElevenLabs responded with ${response.status}`);
        }

        const audioBlob = await response.blob();
        const audioURL = URL.createObjectURL(audioBlob);

        const audio = new Audio(audioURL);
        this.currentAudio = audio;

        audio.onended = () => {
          URL.revokeObjectURL(audioURL);
          if (this.currentAudio === audio) this.currentAudio = null;
          resolve();
        };

        audio.onerror = () => {
          URL.revokeObjectURL(audioURL);
          if (this.currentAudio === audio) this.currentAudio = null;
          reject(new Error("Audio playback error"));
        };

        audio.play().catch(reject);
      } catch (err) {
        reject(err);
      }
    });
  }
}
