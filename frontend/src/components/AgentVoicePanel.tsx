"use client";

import React, { useEffect, useState } from "react";
import { 
  Volume2, 
  VolumeX, 
  Settings, 
  Play, 
  Compass, 
  Droplet, 
  ShieldAlert, 
  Atom, 
  Brain,
  Sliders,
  CheckCircle,
  HelpCircle
} from "lucide-react";
import { useStore } from "../hooks/useStore";
import { voiceSettingsStore, agentVoiceService, VoiceSettings } from "../hooks/useAgentVoice";

export default function AgentVoicePanel() {
  const settings = useStore(voiceSettingsStore);

  // Sync state helpers
  const updateSettings = (updated: Partial<VoiceSettings>) => {
    voiceSettingsStore.setState((prev) => ({
      ...prev,
      ...updated,
    }));
  };

  const handleMuteChange = (agent: string, isMuted: boolean) => {
    updateSettings({
      mutedAgents: {
        ...settings.mutedAgents,
        [agent]: isMuted,
      },
    });
  };

  const agentIcons: Record<string, React.ReactNode> = {
    "Navigation Agent": <Compass className="w-3.5 h-3.5 text-cyan-400" />,
    "Resource Agent": <Droplet className="w-3.5 h-3.5 text-orange-400" />,
    "Safety Agent": <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />,
    "Science Agent": <Atom className="w-3.5 h-3.5 text-indigo-400" />,
    "Mission Commander Agent": <Brain className="w-3.5 h-3.5 text-emerald-400" />,
  };

  const agentColorClasses: Record<string, string> = {
    "Navigation Agent": "text-cyan-400",
    "Resource Agent": "text-orange-400",
    "Safety Agent": "text-rose-400",
    "Science Agent": "text-indigo-400",
    "Mission Commander Agent": "text-emerald-400",
  };

  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md flex flex-col gap-3 font-mono text-xs text-slate-200">
      
      {/* Header */}
      <h2 className="text-xs font-bold tracking-widest text-cyan-400 border-b border-slate-800 pb-2 mb-1 uppercase flex items-center justify-between">
        <span className="flex items-center gap-2">
          <Volume2 className="w-4 h-4 text-cyan-400" />
          Agent Voice System
        </span>
        <span className="text-[9px] text-slate-500 font-bold uppercase">v2.1</span>
      </h2>

      {/* Main Enable/Disable Toggle */}
      <div className="flex items-center justify-between bg-slate-900/30 p-2.5 rounded-lg border border-slate-900/60">
        <div className="flex items-center gap-2">
          {settings.enabled ? (
            <Volume2 className="w-4 h-4 text-cyan-400 animate-pulse" />
          ) : (
            <VolumeX className="w-4 h-4 text-slate-600" />
          )}
          <div>
            <span className="font-bold text-[10px] tracking-wide block uppercase">
              SPEECH SYNTHESIS ENGINE
            </span>
            <span className="text-[9px] text-slate-500 uppercase">
              {settings.enabled ? "Online & Ready" : "System Deactivated"}
            </span>
          </div>
        </div>

        <button
          onClick={() => {
            updateSettings({ enabled: !settings.enabled });
            if (settings.enabled) {
              agentVoiceService.cancelAll();
            }
          }}
          className={`px-3 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all duration-300 border ${
            settings.enabled
              ? "bg-cyan-950/30 border-cyan-500/40 text-cyan-400 hover:bg-cyan-500/20"
              : "bg-slate-900 border-slate-800 text-slate-500 hover:bg-slate-800/50"
          }`}
        >
          {settings.enabled ? "ACTIVE" : "MUTED"}
        </button>
      </div>

      {/* Speed & Volume Controls */}
      <div className="space-y-3 bg-slate-900/10 p-2.5 rounded-lg border border-slate-900/40">
        
        {/* Volume Slider */}
        <div className="space-y-1.5">
          <div className="flex justify-between items-center text-[9px] text-slate-400 font-bold uppercase">
            <span className="flex items-center gap-1">
              <Volume2 className="w-3 h-3" /> Master Volume
            </span>
            <span className="text-cyan-400 font-mono">
              {Math.round(settings.volume * 100)}%
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={settings.volume}
            disabled={!settings.enabled}
            onChange={(e) => updateSettings({ volume: parseFloat(e.target.value) })}
            className="w-full accent-cyan-500 h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
          />
        </div>

        {/* Speed (Rate) Slider */}
        <div className="space-y-1.5">
          <div className="flex justify-between items-center text-[9px] text-slate-400 font-bold uppercase">
            <span className="flex items-center gap-1">
              <Sliders className="w-3 h-3" /> Playback Speed
            </span>
            <span className="text-cyan-400 font-mono">
              {settings.rate.toFixed(1)}x
            </span>
          </div>
          <input
            type="range"
            min="0.5"
            max="2.0"
            step="0.1"
            value={settings.rate}
            disabled={!settings.enabled}
            onChange={(e) => updateSettings({ rate: parseFloat(e.target.value) })}
            className="w-full accent-cyan-500 h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
          />
        </div>

      </div>

      {/* Individual Agent Mutes */}
      <div className="space-y-2">
        <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest block pl-0.5">
          INDIVIDUAL AGENT CHANNELS
        </span>

        <div className="grid grid-cols-1 gap-1.5">
          {Object.entries(settings.mutedAgents)
            .filter(([agent]) => agent === "Mission Commander Agent")
            .map(([agent, isMuted]) => (
              <div
                key={agent}
                className={`flex items-center justify-between p-2 rounded border transition-all duration-200 ${
                  isMuted 
                    ? "bg-slate-950/20 border-slate-900 text-slate-500" 
                    : "bg-slate-900/20 border-slate-900/60 text-slate-300"
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  {agentIcons[agent] || <Brain className="w-3.5 h-3.5" />}
                  <span className={`text-[10px] truncate ${!isMuted ? "font-bold text-slate-200" : "text-slate-500"}`}>
                    {agent.split(" ")[0]} Agent
                  </span>
                </div>

                <button
                  onClick={() => handleMuteChange(agent, !isMuted)}
                  disabled={!settings.enabled}
                  className={`px-2 py-0.5 rounded text-[8px] font-bold tracking-wider uppercase border disabled:opacity-20 transition-all ${
                    isMuted
                      ? "bg-slate-950/40 border-slate-900 text-slate-500 hover:bg-slate-900"
                      : `bg-${agentColorClasses[agent]?.split("-")[1]}-950/10 border-${agentColorClasses[agent]?.split("-")[1]}-500/20 ${agentColorClasses[agent]} hover:bg-${agentColorClasses[agent]?.split("-")[1]}-500/10`
                  }`}
                >
                  {isMuted ? "MUTED" : "ON AIR"}
                </button>
              </div>
            ))}
        </div>
      </div>

    </div>
  );
}
