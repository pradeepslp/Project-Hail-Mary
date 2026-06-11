"use client";

import React, { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { 
  Play, 
  Pause, 
  RotateCcw, 
  Activity, 
  Compass, 
  Gauge, 
  Radio, 
  Clock, 
  AlertTriangle,
  Sliders,
  Brain
} from "lucide-react";
import { useWebSocket } from "../hooks/useWebSocket";
import { CircularGauge, ProgressBar, ParamGridItem } from "./Gauges";
import EventDashboard from "./EventDashboard";
import AnalyticsPanel from "./AnalyticsPanel";
import IntelligenceCenter from "./IntelligenceCenter";

// Import 3D spacecraft dynamically with SSR disabled to prevent hydration errors
const Spacecraft3D = dynamic(() => import("./Spacecraft3D"), { ssr: false });

export default function MissionControl() {
  const { 
    telemetry, 
    mission, 
    events, 
    activeEvents,
    status, 
    startMission, 
    pauseMission, 
    resetMission 
  } = useWebSocket("127.0.0.1:8000");

  const [activeTab, setActiveTab] = useState<"telemetry" | "events" | "analytics" | "intelligence" | string>("telemetry");
  const [localFreq, setLocalFreq] = useState<number | null>(null);

  // Sync local frequency state with mission prop when it updates
  useEffect(() => {
    if (mission?.event_frequency) {
      setLocalFreq(mission.event_frequency);
    }
  }, [mission?.event_frequency]);

  const updateConfig = async (difficulty?: string, frequency?: number) => {
    try {
      const payload: any = {};
      if (difficulty) payload.difficulty = difficulty;
      if (frequency) payload.event_frequency = frequency;

      const res = await fetch("http://127.0.0.1:8000/simulation/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        // Backend config updated successfully
      }
    } catch (err) {
      console.error("Failed to update simulation config:", err);
    }
  };

  const logConsoleRef = useRef<HTMLDivElement>(null);

  // Auto-scroll the log console to the bottom when new logs arrive
  useEffect(() => {
    if (logConsoleRef.current) {
      logConsoleRef.current.scrollTop = logConsoleRef.current.scrollHeight;
    }
  }, [events]);

  const formatDuration = (secs: number) => {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = Math.floor(secs % 60);
    return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  const getStatusLightColor = () => {
    if (status === "connected") return "bg-emerald-500 shadow-emerald-500/50 animate-pulse";
    if (status === "connecting") return "bg-amber-500 shadow-amber-500/50 animate-pulse";
    return "bg-rose-600 shadow-rose-600/50";
  };

  const currentMissionState = mission?.state ?? "Idle";

  // Helpers for parameter states
  const getFuelColor = (fuel: number) => (fuel < 15 ? "rose" : fuel < 40 ? "amber" : "cyan");
  const getPowerColor = (power: number) => (power < 20 ? "rose" : power < 50 ? "amber" : "emerald");
  const getOxygenColor = (oxy: number) => (oxy < 20 ? "rose" : oxy < 50 ? "amber" : "cyan");
  const getHealthColor = (health: number) => (health < 30 ? "rose" : health < 75 ? "amber" : "emerald");

  const stateTimeline = ["Idle", "Launch", "Cruise", "Maneuver", "Emergency", "Completed"];

  return (
    <div className="flex flex-col min-h-screen bg-[#020617] text-slate-100 selection:bg-cyan-500/30">
      
      {/* 1. Top Navigation Control Deck */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 px-6 py-4 bg-slate-950/80 border-b border-slate-900 backdrop-blur-md sticky top-0 z-30">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-tr from-cyan-600 to-indigo-600 rounded-lg shadow-lg shadow-cyan-900/30">
            <Compass className="w-6 h-6 text-white animate-spin-slow" />
          </div>
          <div>
            <h1 className="text-lg font-bold font-mono tracking-wider bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
              HAIL MARY MISSION CONTROL
            </h1>
            <p className="text-[10px] font-mono text-slate-500">
              HEURISTIC AUTONOMOUS INTELLIGENCE FOR LEARNING & ADAPTATION
            </p>
          </div>
        </div>

        {/* Action Controls & Signal State */}
        <div className="flex flex-wrap items-center gap-4">
          {/* Signal Indicator */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-slate-800 bg-slate-900/40 text-[10px] font-mono font-medium">
            <span className={`w-2.5 h-2.5 rounded-full ${getStatusLightColor()} shadow-md`} />
            <span className="text-slate-400 uppercase">SYS_LINK: {status}</span>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 bg-slate-900/60 p-1 rounded-lg border border-slate-800">
            <button
              onClick={startMission}
              disabled={currentMissionState === "Completed" || status !== "connected"}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-mono font-bold tracking-wider text-emerald-400 hover:bg-emerald-950/40 hover:text-emerald-300 disabled:text-slate-600 disabled:hover:bg-transparent transition-all"
              title="Start or Resume Mission"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              START
            </button>
            <button
              onClick={pauseMission}
              disabled={status !== "connected" || !["Launch", "Cruise", "Maneuver", "Emergency"].includes(currentMissionState)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-mono font-bold tracking-wider text-amber-400 hover:bg-amber-950/40 hover:text-amber-300 disabled:text-slate-600 disabled:hover:bg-transparent transition-all"
              title="Pause Simulation"
            >
              <Pause className="w-3.5 h-3.5 fill-current" />
              PAUSE
            </button>
            <button
              onClick={resetMission}
              disabled={status !== "connected"}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-mono font-bold tracking-wider text-rose-400 hover:bg-rose-950/40 hover:text-rose-300 disabled:text-slate-600 disabled:hover:bg-transparent transition-all"
              title="Reset Parameters"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              RESET
            </button>
          </div>
        </div>
      </header>

      {/* 1.5. Sub-header Navigation & Controls */}
      <div className="bg-slate-950/40 border-b border-slate-900/60 px-6 py-2.5 flex flex-col xl:flex-row xl:items-center justify-between gap-4 z-20">
        {/* Left Side: Tabs */}
        <div className="flex flex-wrap items-center gap-2">
          {[
            { id: "telemetry", label: "Telemetry Console", icon: <Activity className="w-3.5 h-3.5" /> },
            { id: "events", label: "Event Center", icon: <AlertTriangle className="w-3.5 h-3.5" /> },
            { id: "intelligence", label: "Mission Intelligence", icon: <Brain className="w-3.5 h-3.5 text-cyan-400 animate-pulse" /> },
            { id: "analytics", label: "Analytics Panel", icon: <Sliders className="w-3.5 h-3.5 text-cyan-500" /> }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-xs font-bold transition-all duration-200 ${
                activeTab === tab.id 
                  ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-md shadow-cyan-500/5"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/40 border border-transparent"
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Right Side: Simulation Config Dials */}
        <div className="flex flex-wrap items-center gap-6 font-mono text-xs">
          {/* Difficulty Selector */}
          <div className="flex items-center gap-2">
            <span className="text-slate-500 font-bold uppercase text-[10px] tracking-wider">Engine Stress:</span>
            <div className="flex items-center gap-1 bg-slate-900/80 p-0.5 rounded-lg border border-slate-800/80">
              {["Easy", "Normal", "Hard", "Extreme"].map((level) => {
                const isActive = mission?.difficulty === level;
                const activeColors = {
                  Easy: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
                  Normal: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
                  Hard: "bg-amber-500/10 text-amber-400 border-amber-500/30",
                  Extreme: "bg-rose-500/20 text-rose-400 border-rose-500/40 animate-pulse font-bold"
                }[level];

                return (
                  <button
                    key={level}
                    onClick={() => updateConfig(level, undefined)}
                    className={`px-2.5 py-1 rounded text-[10px] font-bold uppercase transition-all duration-200 border ${
                      isActive 
                        ? activeColors
                        : "text-slate-500 border-transparent hover:text-slate-350"
                    }`}
                  >
                    {level}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Frequency Slider */}
          <div className="flex items-center gap-3">
            <span className="text-slate-500 font-bold uppercase text-[10px] tracking-wider whitespace-nowrap">Check Rate:</span>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min="10"
                max="60"
                step="5"
                value={localFreq ?? mission?.event_frequency ?? 30}
                onChange={(e) => setLocalFreq(parseFloat(e.target.value))}
                onMouseUp={() => localFreq && updateConfig(undefined, localFreq)}
                onTouchEnd={() => localFreq && updateConfig(undefined, localFreq)}
                className="w-24 md:w-32 accent-cyan-500 bg-slate-950 border border-slate-900 rounded h-1 cursor-pointer"
              />
              <span className="text-cyan-400 font-bold text-[10px] w-8 text-right font-mono">
                {localFreq ?? mission?.event_frequency ?? 30}s
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Main Layout Area */}
      <main className="flex-1 p-4 max-w-[1600px] w-full mx-auto">
        {activeTab === "telemetry" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            
            {/* Left Panel: Mission Metadata & Timeline (Col span 3) */}
            <section className="lg:col-span-3 flex flex-col gap-4">
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl">
                <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-850 pb-2 mb-3 uppercase flex items-center gap-2">
                  <Activity className="w-4 h-4" />
                  Mission Parameters
                </h2>
                <div className="space-y-3 font-mono text-[11px]">
                  <div>
                    <span className="text-slate-500 uppercase block">Mission Name</span>
                    <span className="text-slate-200 font-bold text-sm tracking-wide">{mission?.name ?? "INITIALIZING..."}</span>
                  </div>
                  <hr className="border-slate-900" />
                  <div>
                    <span className="text-slate-500 uppercase block">Destination</span>
                    <span className="text-slate-200 font-bold">{mission?.destination ?? "INITIALIZING..."}</span>
                  </div>
                  <hr className="border-slate-900" />
                  <div>
                    <span className="text-slate-500 uppercase block">Launch Epoch</span>
                    <span className="text-slate-300">
                      {mission?.launch_time !== "Not Launched"
                        ? new Date(mission?.launch_time ?? "").toLocaleTimeString()
                        : "WAITING FOR LAUNCH"}
                    </span>
                  </div>
                  <hr className="border-slate-900" />
                  <div>
                    <span className="text-slate-500 uppercase block">Duration</span>
                    <span className="text-slate-200 text-sm font-bold flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-cyan-500" />
                      {formatDuration(mission?.duration ?? 0)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Mission State Timeline */}
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl flex-1">
                <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-850 pb-2 mb-3 uppercase flex items-center gap-2">
                  <Compass className="w-4 h-4" />
                  State Machine
                </h2>
                <div className="relative pl-4 border-l border-slate-800 space-y-4 py-2">
                  {stateTimeline.map((state) => {
                    const isCurrent = currentMissionState === state;
                    const isAlertState = state === "Emergency" && isCurrent;
                    
                    return (
                      <div key={state} className="relative group">
                        {/* Glowing bullet */}
                        <div 
                          className={`absolute -left-[21px] top-1.5 w-2.5 h-2.5 rounded-full transition-all duration-500 ${
                            isCurrent 
                              ? isAlertState 
                                ? "bg-rose-500 shadow-[0_0_12px_#ef4444]" 
                                : "bg-cyan-400 shadow-[0_0_12px_#06b6d4]" 
                              : "bg-slate-800 group-hover:bg-slate-700"
                          }`}
                        />
                        <div className="flex flex-col">
                          <span className={`text-[11px] font-mono font-bold tracking-wider uppercase transition-colors duration-300 ${
                            isCurrent 
                              ? isAlertState 
                                ? "text-rose-400" 
                                : "text-cyan-400 font-extrabold" 
                              : "text-slate-500"
                          }`}>
                            {state}
                          </span>
                          {isCurrent && (
                            <span className="text-[9px] font-mono text-slate-400 mt-0.5 leading-snug">
                              {state === "Idle" && "Systems configured. Awaiting launch authorization."}
                              {state === "Launch" && "Chemical thrusters igniting. Escape trajectory active."}
                              {state === "Cruise" && "Solar panels deployed. Kinetic gliding at speed."}
                              {state === "Maneuver" && "Vector adjustments active. Trajectory aligning."}
                              {state === "Emergency" && "System warnings detected. Core diagnostics failure."}
                              {state === "Completed" && "Orbit attained. Systems operating at steady-state."}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </section>

            {/* Center: 3D Visualization (Col span 6) */}
            <section className="lg:col-span-6 flex flex-col gap-4 rounded-xl border border-slate-800/85 bg-slate-950/70 overflow-hidden shadow-2xl relative">
              <div className="flex items-center justify-between px-4 py-3 bg-slate-900/40 border-b border-slate-900/60 font-mono text-xs z-10">
                <span className="font-bold tracking-widest text-cyan-400 uppercase flex items-center gap-2">
                  <Activity className="w-4 h-4 animate-pulse text-cyan-500" />
                  Digital Twin (3D Render)
                </span>
                <span className="text-[10px] text-slate-500">MODEL_INDEX: HM-DT-01</span>
              </div>
              
              <div className="flex-1 relative bg-[#020617]">
                <Spacecraft3D telemetry={telemetry} state={currentMissionState} activeEvents={activeEvents} />
              </div>
            </section>

            {/* Right Panel: Telemetry Dashboard (Col span 3) */}
            <section className="lg:col-span-3 flex flex-col gap-4">
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl flex flex-col gap-4">
                <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-850 pb-2 uppercase flex items-center gap-2">
                  <Gauge className="w-4 h-4" />
                  Spacecraft Systems
                </h2>
                
                {/* Systems Radial Gauges */}
                <div className="grid grid-cols-2 gap-3">
                  <CircularGauge 
                    value={telemetry?.fuel ?? 100} 
                    label="Propellant" 
                    color={getFuelColor(telemetry?.fuel ?? 100)} 
                  />
                  <CircularGauge 
                    value={telemetry?.power ?? 100} 
                    label="Solar Power" 
                    color={getPowerColor(telemetry?.power ?? 100)} 
                  />
                  <CircularGauge 
                    value={telemetry?.oxygen ?? 100} 
                    label="Life O2" 
                    color={getOxygenColor(telemetry?.oxygen ?? 100)} 
                  />
                  <CircularGauge 
                    value={telemetry?.health ?? 100} 
                    label="Hull Armor" 
                    color={getHealthColor(telemetry?.health ?? 100)} 
                  />
                </div>
                
                {/* Linear Progress Bars */}
                <div className="space-y-3 mt-1">
                  <ProgressBar 
                    value={telemetry?.mission_progress ?? 0} 
                    label="Mission Progress" 
                    unit="%" 
                    color="cyan" 
                  />
                  <ProgressBar 
                    value={telemetry?.temperature ?? 25} 
                    label="Thermal Diagnostics" 
                    unit="°C" 
                    color={telemetry && telemetry.temperature > 80 ? "rose" : telemetry && telemetry.temperature > 40 ? "amber" : "cyan"} 
                    max={150} 
                  />
                </div>
              </div>

              {/* Core Telemetry Numerical Parameters */}
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl flex-1 flex flex-col gap-3">
                <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-850 pb-2 uppercase flex items-center gap-2">
                  <Radio className="w-4 h-4" />
                  Telemetry Grid
                </h2>
                <div className="flex-1 grid grid-cols-1 gap-2.5">
                  <ParamGridItem 
                    title="Velocity" 
                    value={`${(telemetry?.velocity ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })} km/s`} 
                    icon={<Activity className="w-4 h-4" />} 
                  />
                  <ParamGridItem 
                    title="Distance Traveled" 
                    value={`${(telemetry?.distance ?? 0).toLocaleString(undefined, { maximumFractionDigits: 1 })} km`} 
                    icon={<Compass className="w-4 h-4" />} 
                  />
                  <ParamGridItem 
                    title="Comm Link Status" 
                    value={telemetry?.communication ?? "Disconnected"} 
                    accentColor={telemetry?.communication === "Connected" ? "text-emerald-400" : "text-rose-500"}
                    icon={<Radio className="w-4 h-4" />} 
                  />
                </div>
              </div>
            </section>

            {/* Bottom Panel: Event Log (Col span 12) */}
            <section className="lg:col-span-12 flex flex-col rounded-xl border border-slate-800/80 bg-slate-950/70 overflow-hidden shadow-xl">
              <div className="flex items-center justify-between px-4 py-3 bg-slate-900/40 border-b border-slate-900/60 font-mono text-xs">
                <span className="font-bold tracking-widest text-cyan-400 uppercase flex items-center gap-2">
                  <Clock className="w-4 h-4" />
                  Event Console Logs
                </span>
                <span className="text-[9px] text-slate-500">SYS_TICK_RATE: 1Hz</span>
              </div>
              
              <div 
                ref={logConsoleRef}
                className="h-[140px] overflow-y-auto p-4 font-mono text-[11px] leading-relaxed space-y-1.5 scrollbar-thin scrollbar-thumb-slate-850 scrollbar-track-transparent bg-slate-950/90 text-cyan-500/90"
              >
                {events.length === 0 ? (
                  <div className="text-slate-600 italic animate-pulse">
                    [SYSTEM LOG] Listening for telemetry broadcasts...
                  </div>
                ) : (
                  events.map((log, index) => {
                    const isWarn = log.includes("[WARNING]");
                    const isErr = log.includes("[ERROR]");
                    
                    let lineClass = "text-cyan-500/85";
                    if (isWarn) lineClass = "text-amber-400 font-semibold";
                    if (isErr) lineClass = "text-rose-500 font-bold";

                    return (
                      <div key={index} className={`flex items-start gap-1 ${lineClass}`}>
                        <span className="text-slate-600 select-none">&gt;</span>
                        <span>{log}</span>
                      </div>
                    );
                  })
                )}
              </div>
            </section>

          </div>
        )}

        {activeTab === "events" && (
          <EventDashboard telemetry={telemetry} mission={mission} activeEvents={activeEvents} />
        )}

        {activeTab === "intelligence" && (
          <IntelligenceCenter telemetry={telemetry} mission={mission} activeEvents={activeEvents} />
        )}

        {activeTab === "analytics" && (
          <AnalyticsPanel />
        )}
      </main>

      {/* Footer System Integrity Info */}
      <footer className="text-center py-3 border-t border-slate-900 bg-slate-950/40 font-mono text-[9px] text-slate-600">
        PROJECT HAIL MARY SYSTEM // CORE v1.0.0-ALPHA // STABLE ORBITAL SIMULATION ACTIVE
      </footer>
      
    </div>
  );
}
