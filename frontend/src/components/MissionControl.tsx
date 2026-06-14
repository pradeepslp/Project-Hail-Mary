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
  Brain,
  Layers,
  Sparkles
} from "lucide-react";
import { useWebSocket } from "../hooks/useWebSocket";
import {
  useStore,
  telemetryStore,
  missionStore,
  eventsStore,
  activeEventsStore,
  statusStore,
  missionSuccessStore,
  missionFailureStore
} from "../hooks/useStore";
import { CircularGauge, ProgressBar, ParamGridItem } from "./Gauges";
import EventDashboard from "./EventDashboard";
import AnalyticsPanel from "./AnalyticsPanel";
import IntelligenceCenter from "./IntelligenceCenter";

import AgentActivity from "./AgentActivity";
import AutonomousOpsCenter from "./AutonomousOpsCenter";

import TestingCenterPanel from "./TestingCenterPanel";
import AgentVoicePanel from "./AgentVoicePanel";
import { ConversationalPanel } from "./ConversationalPanel";
import { useCMI } from "../hooks/useCMI";
import type { AIConfiguration } from "../ai/types";

// Import 3D spacecraft dynamically with SSR disabled to prevent hydration errors
const Spacecraft3D = dynamic(() => import("./Spacecraft3D"), { ssr: false });

function MissionParametersPanel() {
  const mission = useStore(missionStore);
  const telemetry = useStore(telemetryStore);

  const [realTime, setRealTime] = useState("");
  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setRealTime(now.toLocaleString("en-IN", {
        timeZone: "Asia/Kolkata",
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false
      }).replace(/,/g, "") + " IST");
    };
    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  const formatDuration = (secs: number) => {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = Math.floor(secs % 60);
    return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  const formatETA = (etaStr: string | undefined) => {
    if (!etaStr || etaStr === "N/A") return "N/A";
    try {
      const date = new Date(etaStr);
      return date.toLocaleString("en-IN", {
        timeZone: "Asia/Kolkata",
        dateStyle: "medium",
        timeStyle: "medium",
      }) + " (IST)";
    } catch {
      return etaStr;
    }
  };

  const handleSpeedChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = parseFloat(e.target.value.replace("X", ""));
    try {
      await fetch("http://127.0.0.1:8000/simulation/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ speed_multiplier: val })
      });
    } catch (err) {
      console.error("Failed to update speed config:", err);
    }
  };

  return (
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
        {telemetry && telemetry.trajectory_distance !== undefined && telemetry.trajectory_distance > 0 && (
          <>
            <hr className="border-slate-900" />
            <div>
              <span className="text-slate-500 uppercase block">Required Fuel</span>
              <span className="text-slate-200 font-bold">{(telemetry.fuel_required ?? 0).toLocaleString(undefined, { maximumFractionDigits: 1 })} kg</span>
            </div>
            <hr className="border-slate-900" />
            <div>
              <span className="text-slate-500 uppercase block">Est. Travel Time</span>
              <span className="text-slate-200 font-bold">{(telemetry.travel_time_h ?? 0).toLocaleString(undefined, { maximumFractionDigits: 1 })} hours</span>
            </div>
            <hr className="border-slate-900" />
            <div>
              <span className="text-slate-500 uppercase block">Mission Feasibility</span>
              <span className={`px-2 py-0.5 rounded text-[8px] font-bold uppercase inline-block mt-0.5 ${telemetry.feasibility ? "bg-emerald-950 border border-emerald-500 text-emerald-400" : "bg-rose-950 border border-rose-500 text-rose-400"}`}>
                {telemetry.feasibility ? "FEASIBLE" : "NOT FEASIBLE"}
              </span>
            </div>
          </>
        )}
        <hr className="border-slate-900" />
        <div>
          <span className="text-slate-500 uppercase block">Launch Epoch</span>
          <span className="text-slate-300">
            {mission?.launch_time && mission.launch_time !== "Not Launched"
              ? new Date(mission.launch_time).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) + " (IST)"
              : "WAITING FOR LAUNCH"}
          </span>
        </div>
        <hr className="border-slate-900" />
        <div>
          <span className="text-slate-500 uppercase block">REAL TIME</span>
          <span className="text-slate-200 text-xs font-bold flex items-center gap-1.5 text-cyan-400/90">
            <Clock className="w-3.5 h-3.5" />
            {realTime || "LOADING..."}
          </span>
        </div>
        <hr className="border-slate-900" />
        <div>
          <span className="text-slate-500 uppercase block">MISSION TIME</span>
          <span className="text-slate-200 text-xs font-bold flex items-center gap-1.5 text-emerald-450">
            <Clock className="w-3.5 h-3.5" />
            T+ {telemetry?.mission_elapsed ?? "0 Days"}
          </span>
        </div>
        <hr className="border-slate-900" />
        <div>
          <span className="text-slate-500 uppercase block">Duration (Secs)</span>
          <span className="text-slate-200 text-sm font-bold flex items-center gap-1.5">
            {formatDuration(mission?.duration ?? 0)}
          </span>
        </div>
        <hr className="border-slate-900" />
        <div>
          <span className="text-slate-500 uppercase block">ETA (Asia/Kolkata)</span>
          <span className="text-slate-200 font-bold">
            {formatETA(telemetry?.eta)}
          </span>
        </div>
        <hr className="border-slate-900" />
        <div>
          <span className="text-slate-500 uppercase block mb-1">Simulation Speed</span>
          <select
            value={telemetry?.simulation_speed ?? "1X"}
            onChange={handleSpeedChange}
            className="w-full bg-slate-950/85 border border-slate-800 text-slate-200 text-xs font-mono rounded px-2.5 py-1.5 focus:border-cyan-500/50 outline-none cursor-pointer"
          >
            {["1X", "2X", "4X", "10X", "60X", "600X", "3600X", "86400X"].map((opt) => (
              <option key={opt} value={opt} className="bg-slate-950 text-slate-200">{opt}</option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}



function StateMachinePanel() {
  const state = useStore(missionStore, (m) => m?.state ?? "Idle");
  const stateTimeline = ["Idle", "Launch", "Cruise", "Maneuver", "Emergency", "Completed"];

  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl flex-1">
      <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-850 pb-2 mb-3 uppercase flex items-center gap-2">
        <Compass className="w-4 h-4" />
        State Machine
      </h2>
      <div className="relative pl-4 border-l border-slate-800 space-y-4 py-2">
        {stateTimeline.map((step) => {
          const isCurrent = state === step;
          const isAlertState = step === "Emergency" && isCurrent;

          return (
            <div key={step} className="relative group">
              <div
                className={`absolute -left-[21px] top-1.5 w-2.5 h-2.5 rounded-full transition-all duration-500 ${isCurrent
                    ? isAlertState
                      ? "bg-rose-500 shadow-[0_0_12px_#ef4444]"
                      : "bg-cyan-400 shadow-[0_0_12px_#06b6d4]"
                    : "bg-slate-800 group-hover:bg-slate-700"
                  }`}
              />
              <div className="flex flex-col">
                <span className={`text-[11px] font-mono font-bold tracking-wider uppercase transition-colors duration-300 ${isCurrent
                    ? isAlertState
                      ? "text-rose-400"
                      : "text-cyan-400 font-extrabold"
                    : "text-slate-500"
                  }`}>
                  {step}
                </span>
                {isCurrent && (
                  <span className="text-[9px] font-mono text-slate-400 mt-0.5 leading-snug">
                    {step === "Idle" && "Systems configured. Awaiting launch authorization."}
                    {step === "Launch" && "Chemical thrusters igniting. Escape trajectory active."}
                    {step === "Cruise" && "Solar panels deployed. Kinetic gliding at speed."}
                    {step === "Maneuver" && "Vector adjustments active. Trajectory aligning."}
                    {step === "Emergency" && "System warnings detected. Core diagnostics failure."}
                    {step === "Completed" && "Orbit attained. Systems operating at steady-state."}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TelemetryGaugesPanel() {
  const telemetry = useStore(telemetryStore);

  const getFuelColor = (fuel: number) => (fuel < 15 ? "rose" : fuel < 40 ? "amber" : "cyan");
  const getPowerColor = (power: number) => (power < 20 ? "rose" : power < 50 ? "amber" : "emerald");
  const getOxygenColor = (oxy: number) => (oxy < 20 ? "rose" : oxy < 50 ? "amber" : "cyan");
  const getHealthColor = (health: number) => (health < 30 ? "rose" : health < 75 ? "amber" : "emerald");

  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl flex flex-col gap-4">
      <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-850 pb-2 uppercase flex items-center gap-2">
        <Gauge className="w-4 h-4" />
        Spacecraft Systems
      </h2>

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

      <div className="space-y-2.5 mt-1 border-t border-slate-900 pt-3">
        <ProgressBar
          value={telemetry?.main_fuel_pct ?? 100}
          label="Main Tank"
          unit={telemetry?.main_fuel_mass !== undefined && telemetry.main_fuel_mass > 0 ? `% (${telemetry.main_fuel_mass.toLocaleString(undefined, { maximumFractionDigits: 0 })} kg)` : "%"}
          color={getFuelColor(telemetry?.main_fuel_pct ?? 100)}
        />
        <ProgressBar
          value={telemetry?.backup_fuel_pct ?? 100}
          label="Reserve Tank"
          unit={telemetry?.backup_fuel_mass !== undefined && telemetry.backup_fuel_mass > 0 ? `% (${telemetry.backup_fuel_mass.toLocaleString(undefined, { maximumFractionDigits: 0 })} kg)` : "%"}
          color={getFuelColor(telemetry?.backup_fuel_pct ?? 100)}
        />
        <ProgressBar
          value={telemetry?.emergency_fuel_pct ?? 100}
          label="Emergency Tank"
          unit={telemetry?.emergency_fuel_mass !== undefined && telemetry.emergency_fuel_mass > 0 ? `% (${telemetry.emergency_fuel_mass.toLocaleString(undefined, { maximumFractionDigits: 0 })} kg)` : "%"}
          color={getFuelColor(telemetry?.emergency_fuel_pct ?? 100)}
        />
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
  );
}

function TelemetryGridPanel() {
  const telemetry = useStore(telemetryStore);

  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl flex flex-col gap-3">
      <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-850 pb-2 uppercase flex items-center gap-2">
        <Radio className="w-4 h-4" />
        Telemetry Grid
      </h2>
      <div className="grid grid-cols-1 gap-2.5">
        <ParamGridItem
          title="Velocity"
          value={`${(telemetry?.velocity ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })} km/s`}
          icon={<Activity className="w-4 h-4 text-cyan-400" />}
        />
        <ParamGridItem
          title="Distance Traveled"
          value={`${(telemetry?.distance ?? 0).toLocaleString(undefined, { maximumFractionDigits: 1 })} km`}
          icon={<Compass className="w-4 h-4 text-cyan-400" />}
        />
        <ParamGridItem
          title="Distance Remaining"
          value={telemetry?.distance_remaining ?? "N/A"}
          icon={<Compass className="w-4 h-4 text-cyan-400" />}
        />
        <ParamGridItem
          title="Comm Link Status"
          value={telemetry?.communication ?? "Disconnected"}
          accentColor={telemetry?.communication === "Connected" ? "text-emerald-400" : "text-rose-500"}
          icon={<Radio className="w-4 h-4 text-cyan-400" />}
        />
      </div>
    </div>
  );
}

function MissionPhysicsDebugPanel() {
  const telemetry = useStore(telemetryStore);

  if (!telemetry) return null;

  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl flex flex-col gap-3">
      <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-850 pb-2 uppercase flex items-center gap-2">
        <Sliders className="w-4 h-4 text-cyan-400" />
        Mission Physics Debug
      </h2>
      <div className="grid grid-cols-1 gap-2 font-mono text-[11px] text-slate-350">
        <div className="flex justify-between py-1 border-b border-slate-900/40">
          <span className="text-slate-500 uppercase">Fuel Loaded</span>
          <span className="text-slate-100 font-semibold">
            {(telemetry.total_fuel_mass ?? 0).toLocaleString(undefined, { maximumFractionDigits: 1 })} kg
          </span>
        </div>
        <div className="flex justify-between py-1 border-b border-slate-900/40">
          <span className="text-slate-500 uppercase">Fuel Consumed</span>
          <span className="text-slate-100 font-semibold">
            {(telemetry.fuel_consumed ?? 0).toLocaleString(undefined, { maximumFractionDigits: 1 })} kg
          </span>
        </div>
        <div className="flex justify-between py-1 border-b border-slate-900/40">
          <span className="text-slate-500 uppercase">Fuel Remaining</span>
          <span className="text-cyan-400 font-bold">
            {(telemetry.total_fuel_mass !== undefined && telemetry.fuel_consumed !== undefined ? Math.max(0.0, telemetry.total_fuel_mass - telemetry.fuel_consumed) : 0).toLocaleString(undefined, { maximumFractionDigits: 1 })} kg
          </span>
        </div>
        <div className="flex justify-between py-1 border-b border-slate-900/40 pl-3 border-l border-slate-800">
          <span className="text-slate-500 uppercase">├ Main Tank</span>
          <span className="text-slate-200">
            {(telemetry.main_fuel_mass ?? 0).toLocaleString(undefined, { maximumFractionDigits: 1 })} kg
          </span>
        </div>
        <div className="flex justify-between py-1 border-b border-slate-900/40 pl-3 border-l border-slate-800">
          <span className="text-slate-500 uppercase">├ Backup Tank</span>
          <span className="text-slate-200">
            {(telemetry.backup_fuel_mass ?? 0).toLocaleString(undefined, { maximumFractionDigits: 1 })} kg
          </span>
        </div>
        <div className="flex justify-between py-1 border-b border-slate-900/40 pl-3 border-l border-slate-800">
          <span className="text-slate-500 uppercase">└ Emergency Tank</span>
          <span className="text-slate-200">
            {(telemetry.emergency_fuel_mass ?? 0).toLocaleString(undefined, { maximumFractionDigits: 1 })} kg
          </span>
        </div>
        <div className="flex justify-between py-1 border-b border-slate-900/40">
          <span className="text-slate-500 uppercase">Burn Rate</span>
          <span className="text-amber-400 font-bold">
            {(telemetry.burn_rate ?? 0).toFixed(2)} kg/s
          </span>
        </div>
        <div className="flex justify-between py-1 border-b border-slate-900/40">
          <span className="text-slate-500 uppercase">Velocity</span>
          <span className="text-slate-100 font-semibold">
            {(telemetry.velocity ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })} km/s
          </span>
        </div>
        <div className="flex justify-between py-1 border-b border-slate-900/40">
          <span className="text-slate-500 uppercase">Acceleration</span>
          <span className="text-slate-100 font-semibold">
            {(telemetry.acceleration ?? 0).toLocaleString(undefined, { maximumFractionDigits: 4 })} m/s²
          </span>
        </div>
        <div className="flex justify-between py-1 border-b border-slate-900/40">
          <span className="text-slate-500 uppercase">Distance Traveled</span>
          <span className="text-slate-100 font-semibold">
            {(telemetry.distance ?? 0).toLocaleString(undefined, { maximumFractionDigits: 1 })} km
          </span>
        </div>
        <div className="flex justify-between py-1 border-b border-slate-900/40">
          <span className="text-slate-500 uppercase">Distance Remaining</span>
          <span className="text-slate-100 font-semibold">
            {telemetry.distance_remaining ?? "N/A"}
          </span>
        </div>
        <div className="flex justify-between py-1">
          <span className="text-slate-500 uppercase">Mission Elapsed</span>
          <span className="text-emerald-400 font-bold">
            {telemetry.mission_elapsed ?? "N/A"}
          </span>
        </div>
      </div>
    </div>
  );
}

function EventConsolePanel() {
  const events = useStore(eventsStore);
  const logConsoleRef = useRef<HTMLDivElement>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);

  useEffect(() => {
    if (logConsoleRef.current) {
      logConsoleRef.current.scrollTop = logConsoleRef.current.scrollHeight;
    }
  }, [events]);

  return (
    <section className="fixed bottom-0 left-0 right-0 z-30 flex flex-col border-t border-slate-900 bg-slate-950/95 font-mono text-xs shadow-[0_-8px_30px_rgba(0,0,0,0.5)] backdrop-blur-md">
      <div className="flex items-center justify-between px-6 py-2 bg-slate-900/30 border-b border-slate-900/60">
        <span className="font-bold tracking-widest text-cyan-400 uppercase flex items-center gap-2">
          <Clock className="w-3.5 h-3.5 animate-pulse" />
          Event Console Logs
        </span>
        <div className="flex items-center gap-4">
          <span className="text-[9px] text-slate-500">SYS_TICK_RATE: 1Hz</span>
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="text-[9px] text-cyan-400 hover:text-cyan-300 font-bold uppercase transition-all px-2 py-0.5 rounded border border-cyan-500/25 bg-cyan-500/5 hover:bg-cyan-500/10"
          >
            {isCollapsed ? "Expand Logs" : "Collapse Logs"}
          </button>
        </div>
      </div>

      {!isCollapsed && (
        <div
          ref={logConsoleRef}
          className="h-[80px] overflow-y-auto px-6 py-2.5 font-mono text-[10px] leading-relaxed space-y-1.5 scrollbar-thin scrollbar-thumb-slate-850 scrollbar-track-transparent bg-slate-950/40 text-cyan-500/90"
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
                <div key={index} className={`flex items-start gap-1.5 ${lineClass}`}>
                  <span className="text-slate-600 select-none">&gt;</span>
                  <span>{log}</span>
                </div>
              );
            })
          )}
        </div>
      )}
    </section>
  );
}

export default function MissionControl() {
  const {
    startMission,
    pauseMission,
    resetMission
  } = useWebSocket("127.0.0.1:8000");

  const [activeTab, setActiveTab] = useState<string>("telemetry");

  const status = useStore(statusStore);
  const missionName = useStore(missionStore, (m) => m?.name);
  const missionDifficulty = useStore(missionStore, (m) => m?.difficulty ?? "Normal");
  const missionState = useStore(missionStore, (m) => m?.state ?? "Idle");
  const missionDestination = useStore(missionStore, (m) => m?.destination ?? "Unknown");

  const telemetry = useStore(telemetryStore);
  const activeEvents = useStore(activeEventsStore);

  const successData = useStore(missionSuccessStore);
  const failureData = useStore(missionFailureStore);
  const [viewSummary, setViewSummary] = useState(false);

  // CMI state and config
  const [cmiOpen, setCmiOpen] = useState(false);
  const [highlightedMetrics, setHighlightedMetrics] = useState<Record<string, boolean>>({});

  const [aiConfig, setAiConfig] = useState<AIConfiguration>({
    provider: "mock",
    openaiApiKey: "",
    geminiApiKey: ""
  });

  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("hm_ai_config_v1");
      let parsed: any = {};
      if (saved) {
        try {
          parsed = JSON.parse(saved);
        } catch {}
      }
      setAiConfig({
        provider: parsed.provider || (process.env.NEXT_PUBLIC_AI_PROVIDER as any) || "mock",
        openaiApiKey: parsed.openaiApiKey || process.env.NEXT_PUBLIC_OPENAI_API_KEY || "",
        geminiApiKey: parsed.geminiApiKey || process.env.NEXT_PUBLIC_GEMINI_API_KEY || ""
      });
    }
  }, []);

  const getPositionString = (progress: number) => {
    const dest = missionDestination || "Target";
    if (progress === 0) return "Earth Orbit (Departure)";
    if (progress < 15) return `Trans-${dest} Injection Phase`;
    if (progress < 60) return "Deep Space Cruise Flight";
    if (progress < 85) return "Scientific Operations Horizon";
    if (progress < 95) return `${dest} Orbit Insertion Phase`;
    return `${dest} Orbit / Landing Sequence`;
  };

  const cmiSimState = {
    spacecraft: {
      missionProgress: telemetry?.mission_progress ?? 0,
      health: telemetry?.health ?? 100,
      fuel: telemetry?.fuel ?? 100,
      power: telemetry?.power ?? 100,
      oxygen: telemetry?.oxygen ?? 100,
      temperature: telemetry?.temperature ?? 25,
      velocity: telemetry?.velocity ?? 0,
      position: telemetry ? getPositionString(telemetry.mission_progress) : "Earth Orbit (Departure)",
      communication: telemetry?.communication === "Connected"
    },
    destination: missionDestination,
    activeEvent: activeEvents && activeEvents.length > 0 ? {
      title: activeEvents[0].event_type,
      severity: activeEvents[0].severity,
      description: activeEvents[0].description
    } : null,
    activeDecision: null,
    crew: [
      { name: "Ryland Grace", role: "Mission Commander", health: 100, morale: 100 },
      { name: "Yury Kovalev", role: "Chief Engineer", health: 100, morale: 100 },
      { name: "Dimitri Demchenko", role: "Life Support Officer", health: 100, morale: 100 }
    ],
    objectives: [
      { title: "Primary Directive", status: "In Progress" },
      { title: "Maintain System Integrity", status: "Nominal" },
      { title: "Execute Orbital Insertion", status: "Pending" }
    ],
    missionScore: {
      grade: "A",
      overall: 92
    },
    successProbability: telemetry?.success_probability ?? 95
  };

  const cmiActions = {
    startMission: () => {
      startMission();
    },
    pauseSimulation: () => {
      pauseMission();
    },
    resumeSimulation: () => {
      startMission();
    },
    replayLastDecision: () => {
      setActiveTab("sandbox");
    },
    generateMissionReport: () => {
      setActiveTab("analytics");
    },
    runWhatIfAnalysis: () => {
      setActiveTab("sandbox");
    },
    simulateDualFailure: () => {
      setActiveTab("test_center");
    },
    exportAnalytics: () => {
      setActiveTab("analytics");
    },
    switchMode: (newMode: "space" | "earth") => {
      console.log("[CMI] switchMode triggered to", newMode);
    },
    highlightSection: (section: string) => {
      setHighlightedMetrics(prev => ({ ...prev, [section]: true }));
      setTimeout(() => {
        setHighlightedMetrics(prev => ({ ...prev, [section]: false }));
      }, 3000);
    },
    openKnowledgeGraph: () => {
      setActiveTab("sandbox");
    },
    open3DView: () => {
      setActiveTab("telemetry");
    },
    approveAnomaly: () => {
      setActiveTab("test_center");
    },
    rejectAnomaly: () => {
      setActiveTab("test_center");
    },
    compareAlternatives: () => {
      setActiveTab("sandbox");
    },
    rerunSimulations: () => {
      setActiveTab("sandbox");
    }
  };

  const cmi = useCMI(cmiSimState, cmiActions, aiConfig);

  // Auto-reset viewSummary when modal is closed
  useEffect(() => {
    if (!successData && !failureData) {
      setViewSummary(false);
    }
  }, [successData, failureData]);

  const formatDuration = (secs: number) => {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = Math.floor(secs % 60);
    return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  const summaryData = successData?.summary || failureData?.summary;
  const outcome = successData ? "SUCCESS" : "FAILURE";

  const updateConfig = async (difficulty?: string) => {
    try {
      const payload: any = {};
      if (difficulty) payload.difficulty = difficulty;

      await fetch("http://127.0.0.1:8000/simulation/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    } catch (err) {
      console.error("Failed to update simulation config:", err);
    }
  };

  const getStatusLightColor = () => {
    if (status === "connected") return "bg-emerald-500 shadow-emerald-500/50 animate-pulse";
    if (status === "connecting") return "bg-amber-500 shadow-amber-500/50 animate-pulse";
    return "bg-rose-600 shadow-rose-600/50";
  };

  return (
    <div className="flex flex-col min-h-screen bg-[#020617] text-slate-100 selection:bg-cyan-500/30 pb-32">

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
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-violet-700/60 bg-violet-950/40 text-[10px] font-mono font-bold text-violet-300">
            <span className="w-2 h-2 rounded-full bg-violet-400 shadow-[0_0_8px_#a78bfa] animate-pulse" />
            ⚗ AI MISSION LAB
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-slate-800 bg-slate-900/40 text-[10px] font-mono font-medium">
            <span className={`w-2.5 h-2.5 rounded-full ${getStatusLightColor()} shadow-md`} />
            <span className="text-slate-400 uppercase">SYS_LINK: {status}</span>
          </div>

          <div className="flex items-center gap-2 bg-slate-900/60 p-1 rounded-lg border border-slate-800">
            <button
              onClick={startMission}
              disabled={missionState === "Completed" || status !== "connected"}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-mono font-bold tracking-wider text-emerald-400 hover:bg-emerald-950/40 hover:text-emerald-300 disabled:text-slate-600 disabled:hover:bg-transparent transition-all"
              title="Start or Resume Mission"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              START
            </button>
            <button
              onClick={pauseMission}
              disabled={status !== "connected" || !["Launch", "Cruise", "Maneuver", "Emergency"].includes(missionState)}
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

            <div className="w-px h-5 bg-slate-700 mx-1" />
            <button
              id="inject-anomaly-shortcut"
              onClick={() => setActiveTab("test_center")}
              disabled={status !== "connected"}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-mono font-bold tracking-wider text-amber-300 bg-amber-500/10 border border-amber-500/30 hover:bg-amber-500/20 hover:text-amber-200 disabled:text-slate-600 disabled:border-transparent disabled:bg-transparent transition-all"
              title="Open Mission Testing Lab"
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              INJECT ANOMALY
            </button>
          </div>
        </div>
      </header>

      {/* 1.5. Sub-header Navigation & Controls */}
      <div className="bg-slate-950/40 border-b border-slate-900/60 px-6 py-2.5 flex flex-col xl:flex-row xl:items-center justify-between gap-4 z-20">
        <div className="flex flex-wrap items-center gap-2">
          {[
            { id: "telemetry", label: "Telemetry Console", icon: <Activity className="w-3.5 h-3.5" /> },
            { id: "ops_center", label: "Autonomous Ops Center", icon: <Layers className="w-3.5 h-3.5 text-indigo-400 animate-pulse" /> },

            { id: "test_center", label: "Mission Testing Center", icon: <Sliders className="w-3.5 h-3.5 text-rose-500 animate-pulse" /> },
            { id: "events", label: "Event Center", icon: <AlertTriangle className="w-3.5 h-3.5" /> },

            { id: "sandbox", label: "Sandbox & Replays", icon: <Sliders className="w-3.5 h-3.5 text-amber-400" /> },
            { id: "agent", label: "Autonomous Agent", icon: <Brain className="w-3.5 h-3.5 text-emerald-450 animate-pulse" /> },
            { id: "analytics", label: "Analytics Panel", icon: <Sliders className="w-3.5 h-3.5 text-cyan-500" /> }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-xs font-bold transition-all duration-200 ${activeTab === tab.id
                  ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-md shadow-cyan-500/5"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/40 border border-transparent"
                }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-6 font-mono text-xs">
          <div className="flex items-center gap-2">
            <span className="text-slate-500 font-bold uppercase text-[10px] tracking-wider">Engine Stress:</span>
            <div className="flex items-center gap-1 bg-slate-900/80 p-0.5 rounded-lg border border-slate-800/80">
              {["Easy", "Normal", "Hard", "Extreme"].map((level) => {
                const isActive = missionDifficulty === level;
                const activeColors = {
                  Easy: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
                  Normal: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
                  Hard: "bg-amber-500/10 text-amber-400 border-amber-500/30",
                  Extreme: "bg-rose-500/20 text-rose-400 border-rose-500/40 animate-pulse font-bold"
                }[level];

                return (
                  <button
                    key={level}
                    onClick={() => updateConfig(level)}
                    className={`px-2.5 py-1 rounded text-[10px] font-bold uppercase transition-all duration-200 border ${isActive
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

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-amber-800/40 bg-amber-950/20 text-[10px] font-mono text-amber-500/80">
            <AlertTriangle className="w-3.5 h-3.5" />
            Anomalies: MANUAL INJECTION ONLY
          </div>
        </div>
      </div>

      {/* 2. Main Layout Area */}
      <main className="flex-1 p-4 max-w-[1600px] w-full mx-auto flex flex-col gap-4">
        {activeTab === "telemetry" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">

            {/* Left Panel: Mission Metadata & State Machine */}
            <section className="lg:col-span-3 flex flex-col gap-4">
              <MissionParametersPanel />
              <div className={`transition-all duration-500 rounded-xl ${highlightedMetrics.objectives || highlightedMetrics.progress ? "ring-2 ring-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.5)] bg-cyan-950/10" : ""}`}>
                <StateMachinePanel />
              </div>
              <div className={`transition-all duration-500 rounded-xl ${highlightedMetrics.crew ? "ring-2 ring-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.5)] bg-cyan-950/10" : ""}`}>
                <AgentVoicePanel />
              </div>
            </section>

            {/* Center: 3D Visualization */}
            <section className={`lg:col-span-6 flex flex-col gap-4 rounded-xl border bg-slate-950/70 overflow-hidden shadow-2xl relative transition-all duration-500 ${highlightedMetrics['3d'] || highlightedMetrics.intelligence ? "border-cyan-500 ring-2 ring-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.5)] bg-cyan-950/10" : "border-slate-800/85"}`}>
              <div className="flex items-center justify-between px-4 py-3 bg-slate-900/40 border-b border-slate-900/60 font-mono text-xs z-10">
                <span className="font-bold tracking-widest text-cyan-400 uppercase flex items-center gap-2">
                  <Activity className="w-4 h-4 animate-pulse text-cyan-500" />
                  Digital Twin (3D Render)
                </span>
                <span className="text-[10px] text-slate-500">MODEL_INDEX: HM-DT-01</span>
              </div>

              <div className="flex-1 relative bg-[#020617]">
                <Spacecraft3D />
              </div>
            </section>

            {/* Right Panel: Telemetry Gauges & Parameters Grid */}
            <section className="lg:col-span-3 flex flex-col gap-4">
              <div className={`transition-all duration-500 rounded-xl ${highlightedMetrics.fuel || highlightedMetrics.power || highlightedMetrics.oxygen || highlightedMetrics.health ? "ring-2 ring-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.5)] bg-cyan-950/10" : ""}`}>
                <TelemetryGaugesPanel />
              </div>
              <div className={`transition-all duration-500 rounded-xl ${highlightedMetrics.velocity || highlightedMetrics.health ? "ring-2 ring-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.5)] bg-cyan-950/10" : ""}`}>
                <TelemetryGridPanel />
              </div>
              <MissionPhysicsDebugPanel />
            </section>

          </div>
        )}

        {activeTab === "ops_center" && (
          <AutonomousOpsCenter />
        )}


        {activeTab === "test_center" && (
          <TestingCenterPanel />
        )}

        {activeTab === "events" && (
          <EventDashboard />
        )}



        {activeTab === "sandbox" && (
          <IntelligenceCenter />
        )}

        {activeTab === "agent" && (
          <AgentActivity />
        )}

        {activeTab === "analytics" && (
          <AnalyticsPanel />
        )}

      </main>

      <footer className="text-center py-3 border-t border-slate-900 bg-slate-950/40 font-mono text-[9px] text-slate-600">
        PROJECT HAIL MARY SYSTEM // CORE v1.0.0-ALPHA // STABLE ORBITAL SIMULATION ACTIVE
      </footer>

      {/* Success Modal */}
      {successData && !viewSummary && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-2xl border border-emerald-500/30 bg-slate-900/95 p-6 shadow-2xl shadow-emerald-500/10 font-mono">
            <div className="text-center mb-6">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 mb-4 animate-bounce">
                <Compass className="w-8 h-8" />
              </div>
              <h2 className="text-xl font-bold tracking-wider text-emerald-400 uppercase">
                🚀 MISSION SUCCESS
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Spacecraft has successfully entered stable orbit.
              </p>
            </div>

            <div className="space-y-3 bg-slate-950/50 p-4 rounded-xl border border-slate-800/80 text-[11px]">
              <div className="flex justify-between">
                <span className="text-slate-500">Destination:</span>
                <span className="text-slate-200 font-bold">{successData.destination}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Mission Duration:</span>
                <span className="text-slate-200 font-bold">
                  {Math.floor(successData.duration / 86400)} Days
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Fuel Remaining:</span>
                <span className="text-emerald-400 font-bold">
                  {successData.fuel_remaining_pct.toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Backup Fuel Used:</span>
                <span className="text-cyan-400 font-bold">
                  {successData.backup_fuel_used_pct.toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Commander Decisions:</span>
                <span className="text-indigo-400 font-bold">
                  {successData.commander_decisions}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Recovery Actions:</span>
                <span className="text-indigo-400 font-bold">
                  {successData.recovery_actions}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mt-6">
              <button
                onClick={() => setViewSummary(true)}
                className="w-full py-2.5 rounded-lg border border-slate-700 hover:border-slate-600 bg-slate-800 hover:bg-slate-700 text-xs font-bold text-slate-200 transition-all uppercase"
              >
                View Summary
              </button>
              <button
                onClick={() => {
                  resetMission();
                }}
                className="w-full py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-xs font-bold text-slate-950 transition-all uppercase"
              >
                Restart Run
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Failure Modal */}
      {failureData && !viewSummary && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-2xl border border-rose-500/30 bg-slate-900/95 p-6 shadow-2xl shadow-rose-500/10 font-mono">
            <div className="text-center mb-6">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-500 mb-4 animate-pulse">
                <AlertTriangle className="w-8 h-8" />
              </div>
              <h2 className="text-xl font-bold tracking-wider text-rose-500 uppercase">
                ❌ MISSION FAILED
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Trajectory aborted due to critical failure.
              </p>
            </div>

            <div className="space-y-3 bg-slate-950/50 p-4 rounded-xl border border-slate-800/80 text-[11px]">
              <div className="flex justify-between items-start">
                <span className="text-slate-500">Reason:</span>
                <span className="text-rose-400 font-bold text-right max-w-[200px]">{failureData.failure_cause}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Distance Remaining:</span>
                <span className="text-slate-200 font-bold">
                  {failureData.distance_remaining.toLocaleString(undefined, { maximumFractionDigits: 1 })} km
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Mission Progress:</span>
                <span className="text-rose-400 font-bold">{failureData.mission_progress.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Backup Fuel:</span>
                <span className="text-slate-200 font-bold">
                  {failureData.backup_fuel_pct.toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Emergency Fuel:</span>
                <span className="text-slate-200 font-bold">
                  {failureData.emergency_fuel_pct.toFixed(1)}%
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mt-6">
              <button
                onClick={() => setViewSummary(true)}
                className="w-full py-2.5 rounded-lg border border-slate-700 hover:border-slate-600 bg-slate-800 hover:bg-slate-700 text-xs font-bold text-slate-200 transition-all uppercase"
              >
                View Summary
              </button>
              <button
                onClick={() => {
                  resetMission();
                }}
                className="w-full py-2.5 rounded-lg bg-rose-500 hover:bg-rose-450 text-xs font-bold text-white transition-all uppercase"
              >
                Restart Run
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Summary Report Modal */}
      {viewSummary && summaryData && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl border border-slate-800 bg-slate-900/95 p-6 shadow-2xl font-mono scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent">
            <div className="text-center mb-6">
              <h2 className="text-lg font-bold tracking-widest text-cyan-400 uppercase">
                Mission Summary Report
              </h2>
              <p className="text-[10px] text-slate-500 mt-0.5 uppercase">
                Telemetry Log & Decision History
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="bg-slate-950/50 p-3.5 rounded-xl border border-slate-800/80 text-[11px]">
                <div className="flex justify-between py-1">
                  <span className="text-slate-500">OUTCOME:</span>
                  <span className={`font-bold ${outcome === "SUCCESS" ? "text-emerald-400" : "text-rose-500"}`}>
                    {outcome}
                  </span>
                </div>
                <div className="flex justify-between py-1 border-t border-slate-900">
                  <span className="text-slate-500">DIST TRAVELLED:</span>
                  <span className="text-slate-200 font-bold">
                    {summaryData.distance_travelled.toLocaleString(undefined, { maximumFractionDigits: 1 })} km
                  </span>
                </div>
              </div>
              <div className="bg-slate-950/50 p-3.5 rounded-xl border border-slate-805 text-[11px]">
                <div className="flex justify-between py-1">
                  <span className="text-slate-500">AVG VELOCITY:</span>
                  <span className="text-slate-200 font-bold">
                    {summaryData.avg_velocity.toLocaleString(undefined, { maximumFractionDigits: 2 })} km/s
                  </span>
                </div>
                <div className="flex justify-between py-1 border-t border-slate-900">
                  <span className="text-slate-500">FUEL EFFICIENCY:</span>
                  <span className="text-slate-200 font-bold">
                    {summaryData.fuel_efficiency.toLocaleString(undefined, { maximumFractionDigits: 4 })} km/kg
                  </span>
                </div>
              </div>
            </div>

            <div className="space-y-5">
              <div>
                <h3 className="text-xs font-bold text-cyan-500 uppercase border-b border-slate-800 pb-1.5 mb-2 flex items-center gap-1.5">
                  <Brain className="w-3.5 h-3.5 text-emerald-450" />
                  Autonomous Agent Decisions
                </h3>
                <div className="overflow-x-auto border border-slate-800/50 rounded-lg">
                  <table className="w-full text-left text-[10px] leading-normal">
                    <thead>
                      <tr className="bg-slate-950 text-slate-400 uppercase tracking-wider text-[9px] border-b border-slate-800">
                        <th className="py-2.5 px-3">Event</th>
                        <th className="py-2.5 px-3">Action Chosen</th>
                        <th className="py-2.5 px-3">Timestamp (IST)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800 bg-slate-950/20 text-slate-300">
                      {summaryData.agent_decisions && summaryData.agent_decisions.length > 0 ? (
                        summaryData.agent_decisions.map((d: any, i: number) => (
                          <tr key={i} className="hover:bg-slate-850/30">
                            <td className="py-2 px-3 font-semibold text-amber-400">{d.event}</td>
                            <td className="py-2 px-3 text-slate-350">{d.action}</td>
                            <td className="py-2 px-3 text-slate-500">{d.timestamp}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={3} className="py-4 text-center text-slate-600 italic">
                            No autonomous agent decisions recorded.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              <div>
                <h3 className="text-xs font-bold text-cyan-500 uppercase border-b border-slate-800 pb-1.5 mb-2 flex items-center gap-1.5">
                  <Sliders className="w-3.5 h-3.5 text-amber-400" />
                  Operator Remediation Logs
                </h3>
                <div className="overflow-x-auto border border-slate-800/50 rounded-lg">
                  <table className="w-full text-left text-[10px] leading-normal">
                    <thead>
                      <tr className="bg-slate-950 text-slate-400 uppercase tracking-wider text-[9px] border-b border-slate-800">
                        <th className="py-2.5 px-3">Event</th>
                        <th className="py-2.5 px-3">Correction Action</th>
                        <th className="py-2.5 px-3">Timestamp (IST)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800 bg-slate-950/20 text-slate-300">
                      {summaryData.recovery_actions && summaryData.recovery_actions.length > 0 ? (
                        summaryData.recovery_actions.map((d: any, i: number) => (
                          <tr key={i} className="hover:bg-slate-850/30">
                            <td className="py-2 px-3 font-semibold text-amber-400">{d.event}</td>
                            <td className="py-2 px-3 text-slate-350">{d.action}</td>
                            <td className="py-2 px-3 text-slate-500">{d.timestamp}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={3} className="py-4 text-center text-slate-600 italic">
                            No operator corrections recorded.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setViewSummary(false)}
                className="w-1/3 py-2.5 rounded-lg border border-slate-700 hover:border-slate-600 bg-slate-850 hover:bg-slate-800 text-xs font-bold text-slate-200 transition-all uppercase"
              >
                Back
              </button>
              <button
                onClick={() => {
                  resetMission();
                }}
                className="w-2/3 py-2.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-xs font-bold text-slate-950 transition-all uppercase"
              >
                Restart Run
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Global Event Log rendered fixed at the bottom of the page */}
      <EventConsolePanel />

      {/* CMI Floating Toggle Button */}
      <div className="fixed bottom-24 right-6 z-40">
        <button
          onClick={() => setCmiOpen(!cmiOpen)}
          className="p-3.5 bg-gradient-to-tr from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white rounded-full shadow-lg shadow-cyan-900/40 hover:shadow-cyan-500/30 hover:scale-105 active:scale-95 transition-all duration-200 flex items-center justify-center border border-cyan-400/30"
          title="Toggle Conversational Mission Intelligence"
        >
          <Sparkles className="h-5 w-5" />
        </button>
      </div>

      <ConversationalPanel
        messages={cmi.messages}
        orbState={cmi.orbState}
        voiceMode={cmi.voiceMode}
        currentTranscript={cmi.currentTranscript}
        micVolume={cmi.micVolume}
        sendMessage={cmi.sendMessage}
        toggleVoiceMode={cmi.toggleVoiceMode}
        startPTTListening={cmi.startPTTListening}
        stopPTTListening={cmi.stopPTTListening}
        clearChatHistory={cmi.clearChatHistory}
        onClose={() => setCmiOpen(false)}
        isOpen={cmiOpen}
      />
    </div>
  );
}
