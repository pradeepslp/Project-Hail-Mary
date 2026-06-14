import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X, Mic, MicOff, Send, Volume2, Sparkles,
  VolumeX, RotateCcw
} from "lucide-react";
import type { CMIOrbState, CMIVoiceMode, CMIMessage } from "../types/cmi";

interface ConversationalPanelProps {
  messages: CMIMessage[];
  orbState: CMIOrbState;
  voiceMode: CMIVoiceMode;
  currentTranscript: string;
  micVolume: number;
  sendMessage: (text: string) => void;
  toggleVoiceMode: () => void;
  startPTTListening: () => void;
  stopPTTListening: () => void;
  clearChatHistory: () => void;
  onClose: () => void;
  isOpen: boolean;
}

const QUICK_SUGGESTIONS = [
  { label: "📊 Mission Status", query: "What is our current mission status?" },
  { label: "🔬 Explain Survival", query: "HAIL MARY, explain why we survived the solar storm." },
  { label: "🛡️ What are our risks?", query: "What are our biggest risks right now?" }
];

export const ConversationalPanel: React.FC<ConversationalPanelProps> = ({
  messages,
  orbState,
  voiceMode,
  currentTranscript,
  micVolume,
  sendMessage,
  toggleVoiceMode,
  startPTTListening,
  stopPTTListening,
  clearChatHistory,
  onClose,
  isOpen
}) => {
  const [inputText, setInputText] = useState("");
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  // Scroll guard: only auto-scroll when a new message is appended and panel is open
  const prevMessagesLengthRef = useRef<number>(0);

  // Auto-scroll to latest message only when the panel is open and a new message arrives
  useEffect(() => {
    if (
      isOpen &&
      messagesContainerRef.current &&
      messages.length > prevMessagesLengthRef.current
    ) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
    }
    prevMessagesLengthRef.current = messages.length;
  }, [messages, isOpen]);

  if (!isOpen) return null;

  const handleSubmitText = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    sendMessage(inputText.trim());
    setInputText("");
  };

  // Build the pulsing scale for the orb based on microphone intensity or current state
  const getOrbAnimation = () => {
    switch (orbState) {
      case "listening":
        return {
          scale: 1 + micVolume * 0.4,
          borderRadius: ["42% 58% 70% 30% / 45% 45% 55% 55%", "70% 30% 52% 48% / 60% 40% 60% 40%", "42% 58% 70% 30% / 45% 45% 55% 55%"],
          rotate: 360,
          transition: {
            scale: { duration: 0.1 },
            borderRadius: { repeat: Infinity, duration: 2, ease: "linear" },
            rotate: { repeat: Infinity, duration: 4, ease: "linear" }
          }
        };
      case "thinking":
        return {
          scale: [1, 1.15, 1],
          borderRadius: ["50%", "30% 70% 70% 30% / 50% 30% 70% 50%", "50%"],
          rotate: 360,
          transition: {
            scale: { repeat: Infinity, duration: 1.5, ease: "easeInOut" },
            borderRadius: { repeat: Infinity, duration: 1.5, ease: "easeInOut" },
            rotate: { repeat: Infinity, duration: 2, ease: "linear" }
          }
        };
      case "speaking":
        return {
          scale: [1, 1.1, 0.95, 1.05, 1],
          borderRadius: ["45% 55% 50% 50% / 50% 50% 50% 50%", "50% 50% 45% 55% / 55% 45% 55% 45%", "45% 55% 50% 50% / 50% 50% 50% 50%"],
          rotate: -360,
          transition: {
            scale: { repeat: Infinity, duration: 1.2, ease: "easeInOut" },
            borderRadius: { repeat: Infinity, duration: 2, ease: "easeInOut" },
            rotate: { repeat: Infinity, duration: 5, ease: "linear" }
          }
        };
      case "muted":
        return {
          scale: 0.85,
          borderRadius: "50%",
          rotate: 0,
          transition: { duration: 0.4 }
        };
      case "idle":
      default:
        return {
          scale: [0.95, 1.02, 0.95],
          borderRadius: ["50% 50% 50% 50%", "48% 52% 48% 52%", "50% 50% 50% 50%"],
          rotate: 0,
          transition: {
            scale: { repeat: Infinity, duration: 3, ease: "easeInOut" },
            borderRadius: { repeat: Infinity, duration: 3, ease: "easeInOut" }
          }
        };
    }
  };

  const getOrbGradient = () => {
    switch (orbState) {
      case "listening":
        return "bg-gradient-to-tr from-cyan-500 via-emerald-400 to-teal-500 shadow-[0_0_30px_rgba(6,182,212,0.6)]";
      case "thinking":
        return "bg-gradient-to-tr from-fuchsia-500 via-purple-500 to-indigo-600 shadow-[0_0_30px_rgba(168,85,247,0.6)]";
      case "speaking":
        return "bg-gradient-to-tr from-cyan-400 via-indigo-500 to-purple-500 shadow-[0_0_30px_rgba(99,102,241,0.6)]";
      case "muted":
        return "bg-gradient-to-tr from-slate-700 via-slate-600 to-slate-800 shadow-[none]";
      case "idle":
      default:
        return "bg-gradient-to-tr from-tau-teal/40 via-cyan-500/50 to-indigo-500/40 shadow-[0_0_20px_rgba(6,182,212,0.3)]";
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-40 w-96 max-h-[640px] h-[85vh] flex flex-col glass-panel border border-tau-teal/25 rounded-xl overflow-hidden shadow-2xl bg-slate-950/85 backdrop-blur-md">
      {/* Visual top decor */}
      <div className="absolute top-0 left-0 w-4 h-4 border-t-2 border-l-2 border-tau-teal/60" />
      <div className="absolute top-0 right-0 w-4 h-4 border-t-2 border-r-2 border-tau-teal/60" />

      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-tau-teal/15 bg-slate-900/40 select-none">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-cyan-400 animate-pulse" />
          <div>
            <h2 className="text-xs font-orbitron font-extrabold tracking-widest text-white uppercase">
              Conversational AI
            </h2>
            <span className="text-[9px] font-mono text-slate-500 uppercase tracking-wider block">
              Commander Mode // CMI-v1.0
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={clearChatHistory}
            className="p-1.5 rounded text-slate-500 hover:text-white hover:bg-slate-800 transition-colors"
            title="Purge logs & memory"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded text-slate-500 hover:text-rose-400 hover:bg-slate-800 transition-colors"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Main chat history & logs */}
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-4 space-y-4 font-mono text-[10px] leading-relaxed scrollbar-thin">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col gap-1 max-w-[85%] ${
              msg.role === "user" ? "ml-auto items-end" : "mr-auto items-start"
            }`}
          >
            <div className="flex items-center gap-1.5 text-[8px] text-slate-500">
              <span className="font-bold uppercase tracking-wider">
                {msg.role === "user" ? "Human Operator" : "HAIL MARY CMI"}
              </span>
              <span>•</span>
              <span>{new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
            </div>

            <div
              className={`px-3 py-2 rounded-lg border leading-relaxed select-text ${
                msg.role === "user"
                  ? "bg-slate-900/40 border-slate-700/60 text-slate-200"
                  : "bg-cyan-950/20 border-cyan-500/25 text-cyan-200"
              }`}
            >
              {/* Output parsing highlights or action strings cleanly without raw syntax */}
              {msg.content
                .replace(/\[ACTION:\s*\w+\]/g, "")
                .replace(/\[HIGHLIGHT:\s*\w+\]/g, "")
                .trim()}

              {/* Action tags badge visual display */}
              {msg.role === "assistant" && (msg.content.includes("[ACTION:") || msg.content.includes("[HIGHLIGHT:")) && (
                <div className="mt-1.5 pt-1.5 border-t border-cyan-500/10 flex flex-wrap gap-1">
                  {msg.content.match(/\[ACTION:\s*(\w+)\]/g)?.map((actToken, idx) => {
                    const match = actToken.match(/\[ACTION:\s*(\w+)\]/);
                    const actName = match ? match[1] : "";
                    return (
                      <span key={idx} className="px-1.5 py-0.5 rounded bg-cyan-950/60 text-cyan-400 border border-cyan-500/30 text-[7.5px] font-bold uppercase tracking-widest">
                        ⚙️ {actName.replace("_", " ")}
                      </span>
                    );
                  })}
                  {msg.content.match(/\[HIGHLIGHT:\s*(\w+)\]/g)?.map((hlToken, idx) => {
                    const match = hlToken.match(/\[HIGHLIGHT:\s*(\w+)\]/);
                    const sectionName = match ? match[1] : "";
                    return (
                      <span key={idx} className="px-1.5 py-0.5 rounded bg-indigo-950/60 text-indigo-400 border border-indigo-500/30 text-[7.5px] font-bold uppercase tracking-widest">
                        👁️ Highlight {sectionName}
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Real-time speech-to-text preview */}
        {currentTranscript && (
          <div className="flex items-center gap-2 max-w-[85%] ml-auto text-emerald-400 font-bold bg-emerald-950/20 border border-emerald-500/30 px-3 py-2 rounded-lg select-none">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="animate-pulse">{currentTranscript}...</span>
          </div>
        )}
      </div>

      {/* Suggestion list */}
      <div className="px-4 py-2 border-t border-tau-teal/10 flex flex-wrap gap-1.5 bg-slate-900/20 select-none">
        {QUICK_SUGGESTIONS.map((sug, idx) => (
          <button
            key={idx}
            onClick={() => sendMessage(sug.query)}
            className="px-2 py-1 bg-slate-900/60 hover:bg-slate-800 text-slate-400 hover:text-white border border-slate-800 hover:border-slate-700 rounded-md text-[9px] font-mono transition-all"
          >
            {sug.label}
          </button>
        ))}
      </div>

      {/* Animated Orb & Mic status container */}
      <div className="flex flex-col items-center justify-center py-4 px-6 border-t border-tau-teal/15 bg-slate-900/30 select-none relative overflow-hidden">
        {/* Radar concentric viz background waves on speech detection */}
        <AnimatePresence>
          {orbState === "listening" && (
            <>
              <motion.div
                initial={{ scale: 0.8, opacity: 0.5 }}
                animate={{ scale: 2.2, opacity: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut" }}
                className="absolute w-24 h-24 border border-cyan-500/30 rounded-full"
              />
              <motion.div
                initial={{ scale: 0.8, opacity: 0.4 }}
                animate={{ scale: 3.0, opacity: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut", delay: 0.5 }}
                className="absolute w-24 h-24 border border-teal-500/20 rounded-full"
              />
            </>
          )}
        </AnimatePresence>

        {/* Dynamic morphing orb */}
        <motion.div
          animate={getOrbAnimation()}
          className={`w-14 h-14 rounded-full flex items-center justify-center cursor-pointer transition-all ${getOrbGradient()}`}
          onClick={toggleVoiceMode}
          title={`Click to switch mode. Current: ${voiceMode.toUpperCase()}`}
        >
          {voiceMode === "muted" ? (
            <MicOff className="h-5 w-5 text-slate-300" />
          ) : (
            <Mic className={`h-5 w-5 text-black ${orbState === "listening" ? "animate-pulse" : ""}`} />
          )}
        </motion.div>

        {/* Subtitle status tag */}
        <div className="text-[9px] font-mono text-slate-500 uppercase mt-2.5 flex items-center gap-1.5">
          <span>Mode:</span>
          <span className="font-extrabold text-white bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">
            {voiceMode === "ptt" ? "Push-To-Talk" : voiceMode === "hands-free" ? "Hands-Free" : "Muted"}
          </span>
          <span>// State:</span>
          <span className={`font-bold uppercase ${orbState === "listening" ? "text-cyan-400" : orbState === "thinking" ? "text-purple-400 animate-pulse" : orbState === "speaking" ? "text-indigo-400" : "text-slate-400"}`}>
            {orbState}
          </span>
        </div>
      </div>

      {/* Manual text query controls */}
      <form onSubmit={handleSubmitText} className="p-3 border-t border-tau-teal/15 flex items-center gap-2 bg-slate-900/60">
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder={
            voiceMode === "ptt"
              ? "Type query, or hold/use mic button..."
              : voiceMode === "hands-free"
              ? "Listening continuously..."
              : "Microphone muted. Type query..."
          }
          className="flex-1 min-w-0 bg-slate-950/60 border border-slate-800 focus:border-tau-teal/50 rounded-lg px-3 py-2 font-mono text-[10px] text-white focus:outline-none placeholder-slate-600"
        />

        {/* Dynamic mic capture buttons based on PTT / Hands-free modes */}
        {voiceMode === "ptt" ? (
          <button
            type="button"
            onMouseDown={startPTTListening}
            onMouseUp={stopPTTListening}
            onMouseLeave={stopPTTListening}
            onTouchStart={startPTTListening}
            onTouchEnd={stopPTTListening}
            className={`p-2 rounded-lg border transition-all ${
              orbState === "listening"
                ? "bg-cyan-500/20 border-cyan-500 text-cyan-400 shadow-[0_0_10px_rgba(6,182,212,0.3)] cursor-grabbing"
                : "bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-white cursor-pointer"
            }`}
            title="Hold to speak (Push-To-Talk)"
          >
            <Mic className="h-4 w-4" />
          </button>
        ) : (
          <button
            type="button"
            onClick={toggleVoiceMode}
            className={`p-2 rounded-lg border transition-all ${
              voiceMode === "hands-free"
                ? "bg-emerald-500/20 border-emerald-500 text-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.3)]"
                : "bg-slate-900 border-slate-800 text-slate-400"
            }`}
            title="Toggle Hands-Free (always listening)"
          >
            {voiceMode === "hands-free" ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
          </button>
        )}

        <button
          type="submit"
          disabled={!inputText.trim()}
          className="p-2 bg-tau-teal/10 hover:bg-tau-teal/20 disabled:opacity-40 text-tau-teal border border-tau-teal/30 hover:border-tau-teal/50 rounded-lg transition-all"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
};
