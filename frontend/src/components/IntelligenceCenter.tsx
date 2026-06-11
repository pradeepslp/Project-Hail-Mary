"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Activity,
  AlertTriangle,
  Play,
  Pause,
  RotateCcw,
  Sliders,
  TrendingUp,
  Award,
  ShieldAlert,
  Zap,
  Gauge,
  Radio,
  Clock,
  Compass,
  ArrowRight,
  RefreshCw,
  FastForward,
  ChevronRight,
  Database,
  History
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell
} from "recharts";

import { Telemetry, Mission, ActiveEvent, SubsystemInfo } from "../hooks/useWebSocket";

interface IntelligenceCenterProps {
  telemetry: Telemetry | null;
  mission: Mission | null;
  activeEvents: ActiveEvent[];
}

interface Objective {
  id: number;
  objective_name: string;
  description: string;
  success_conditions: Record<string, number>;
  failure_conditions: Record<string, number>;
  status: string;
}

interface EventDependency {
  id: number;
  parent_event_type: string;
  child_event_type: string;
  propagation_probability: number;
}

interface Replay {
  id: number;
  replay_name: string;
  history_data: any[];
  created_at: string;
}

export default function IntelligenceCenter({
  telemetry: liveTelemetry,
  mission: liveMission,
  activeEvents: liveActiveEvents
}: IntelligenceCenterProps) {
  // Config & API connection
  const backendUrl = "127.0.0.1:8000";

  // State caches
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [dependencies, setDependencies] = useState<EventDependency[]>([]);
  const [actionOptions, setActionOptions] = useState<Record<string, any[]>>({});
  const [actionPredictions, setActionPredictions] = useState<Record<string, any>>({});
  
  // Hover predictions
  const [hoveredAction, setHoveredAction] = useState<string | null>(null);

  // Monte Carlo states
  const [mcIterations, setMcIterations] = useState<number>(500);
  const [mcLoading, setMcLoading] = useState<boolean>(false);
  const [mcResults, setMcResults] = useState<any | null>(null);

  // Replay timeline states
  const [replays, setReplays] = useState<Replay[]>([]);
  const [liveHistory, setLiveHistory] = useState<any[]>([]);
  const [selectedReplayId, setSelectedReplayId] = useState<string>("live");
  const [replayIndex, setReplayIndex] = useState<number>(0);
  const [replayPlaying, setReplayPlaying] = useState<boolean>(false);
  const [replaySpeed, setReplaySpeed] = useState<number>(1); // frames per tick

  const replayTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Load static and db items
  const fetchObjectives = async () => {
    try {
      const res = await fetch(`http://${backendUrl}/mission/objectives`);
      if (res.ok) {
        const data = await res.json();
        setObjectives(data);
      }
    } catch (err) {
      console.error("Failed to fetch objectives:", err);
    }
  };

  const fetchDependencies = async () => {
    try {
      const res = await fetch(`http://${backendUrl}/events/dependencies`);
      if (res.ok) {
        const data = await res.json();
        setDependencies(data);
      }
    } catch (err) {
      console.error("Failed to fetch dependencies:", err);
    }
  };

  const fetchActionOptions = async () => {
    try {
      const res = await fetch(`http://${backendUrl}/actions/options`);
      if (res.ok) {
        const data = await res.json();
        setActionOptions(data);
      }
    } catch (err) {
      console.error("Failed to fetch action options:", err);
    }
  };

  const fetchActionPredictions = async () => {
    try {
      const res = await fetch(`http://${backendUrl}/actions/predictions`);
      if (res.ok) {
        const data = await res.json();
        setActionPredictions(data);
      }
    } catch (err) {
      console.error("Failed to fetch action predictions:", err);
    }
  };

  const fetchReplays = async () => {
    try {
      const res = await fetch(`http://${backendUrl}/mission/replay`);
      if (res.ok) {
        const data = await res.json();
        setReplays(data.saved_replays || []);
        setLiveHistory(data.live_history || []);
      }
    } catch (err) {
      console.error("Failed to fetch replays:", err);
    }
  };

  useEffect(() => {
    fetchObjectives();
    fetchDependencies();
    fetchActionOptions();
    fetchActionPredictions();
    fetchReplays();

    // Poll objectives and replays every 5 seconds for updates
    const interval = setInterval(() => {
      fetchObjectives();
      fetchReplays();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  // Determine current context (Live vs Replay)
  const isReplayMode = selectedReplayId !== "live";

  // Replay timeline buffer
  const getSelectedReplayData = (): any[] => {
    if (selectedReplayId === "live") return liveHistory;
    const r = replays.find(item => item.id.toString() === selectedReplayId);
    return r ? r.history_data : [];
  };

  const replayData = getSelectedReplayData();
  const currentSnapshot = isReplayMode && replayData.length > 0
    ? replayData[Math.min(replayIndex, replayData.length - 1)]
    : null;

  // Resolved active variables based on live or replay snapshot
  const currentTelemetry: Telemetry | null = isReplayMode
    ? (currentSnapshot ? {
        timestamp: currentSnapshot.timestamp,
        fuel: currentSnapshot.fuel,
        power: currentSnapshot.power,
        oxygen: currentSnapshot.oxygen,
        temperature: 25.0, // fallback
        health: currentSnapshot.risk_score ? (100 - currentSnapshot.risk_score) : 100, // fallback
        velocity: currentSnapshot.velocity,
        distance: currentSnapshot.distance,
        mission_progress: currentSnapshot.mission_progress,
        communication: currentSnapshot.subsystems?.Communication?.health >= 30 ? "Connected" : "Disconnected",
        position: { x: 0, y: 0, z: 0 },
        position_error: currentSnapshot.position_error,
        subsystems: currentSnapshot.subsystems,
        success_probability: currentSnapshot.subsystems 
          ? (0.25 * currentSnapshot.fuel + 
             0.20 * currentSnapshot.power + 
             0.20 * (Object.values(currentSnapshot.subsystems).reduce((acc: number, s: any) => acc + s.health, 0) as number / 7) + 
             0.15 * (currentSnapshot.subsystems?.Communication?.health >= 30 ? 100 : 0) + 
             0.20 * Math.max(0, 100 - currentSnapshot.position_error))
          : 80,
        failure_probability: currentSnapshot.subsystems
          ? 100 - (0.25 * currentSnapshot.fuel + 
                   0.20 * currentSnapshot.power + 
                   0.20 * (Object.values(currentSnapshot.subsystems).reduce((acc: number, s: any) => acc + s.health, 0) as number / 7) + 
                   0.15 * (currentSnapshot.subsystems?.Communication?.health >= 30 ? 100 : 0) + 
                   0.20 * Math.max(0, 100 - currentSnapshot.position_error))
          : 20,
        confidence_score: currentSnapshot.subsystems
          ? (Object.values(currentSnapshot.subsystems).reduce((acc: number, s: any) => acc + s.health, 0) as number / 7) * (0.5 + 0.005 * currentSnapshot.mission_progress)
          : 50
      } : null)
    : liveTelemetry;

  const currentMission: Mission | null = isReplayMode
    ? (liveMission ? {
        ...liveMission,
        state: currentSnapshot ? (currentSnapshot.mission_progress >= 100 ? "Completed" : currentSnapshot.fuel <= 0 ? "Emergency" : "Cruise") : "Idle",
        duration: currentSnapshot ? replayIndex : 0,
        risk_score: currentSnapshot ? currentSnapshot.risk_score : 0,
        risk_level: currentSnapshot ? (currentSnapshot.risk_score > 75 ? "CRITICAL" : currentSnapshot.risk_score > 50 ? "HIGH" : "LOW") : "LOW"
      } : null)
    : liveMission;

  const currentActiveEvents: any[] = isReplayMode
    ? (currentSnapshot && currentSnapshot.active_events
        ? currentSnapshot.active_events.map((e: any, i: number) => ({
            id: i + 999,
            event_type: e.event_type,
            severity: ["Solar Storm", "Micrometeorite Impact"].includes(e.event_type) ? "CRITICAL" : "HIGH",
            description: `Historical event trace: ${e.event_type}`,
            affected_system: e.event_type === "Fuel Leak" ? "Propulsion" : "Electrical Systems",
            recommended_actions: "Review historical decision log.",
            status: e.status
          }))
        : [])
    : liveActiveEvents;

  // Playback timer ticker logic
  useEffect(() => {
    if (replayPlaying) {
      replayTimerRef.current = setInterval(() => {
        setReplayIndex((prev) => {
          if (prev >= replayData.length - 1) {
            setReplayPlaying(false);
            return prev;
          }
          return prev + replaySpeed;
        });
      }, 1000);
    } else {
      if (replayTimerRef.current) clearInterval(replayTimerRef.current);
    }

    return () => {
      if (replayTimerRef.current) clearInterval(replayTimerRef.current);
    };
  }, [replayPlaying, replayData.length, replaySpeed]);

  // Handle slide scrubbing
  const handleScrubChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setReplayIndex(parseInt(e.target.value));
  };

  // Run Monte Carlo Forecast
  const runMonteCarloForecast = async () => {
    setMcLoading(true);
    try {
      const res = await fetch(`http://${backendUrl}/forecast/montecarlo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ iterations: mcIterations })
      });
      if (res.ok) {
        const results = await res.json();
        setMcResults(results);
      }
    } catch (err) {
      console.error("Monte Carlo execution failed:", err);
    } finally {
      setMcLoading(false);
    }
  };

  // Execute Sandbox Action
  const executeSandboxAction = async (eventId: number, actionKey: string) => {
    try {
      const res = await fetch(`http://${backendUrl}/actions/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_id: eventId, action_key: actionKey })
      });
      if (res.ok) {
        // Fetch fresh objectives state post execution
        fetchObjectives();
      }
    } catch (err) {
      console.error("Action execution failed:", err);
    }
  };

  // Circular gauge drawing helper
  const renderNeonGauge = (
    value: number,
    label: string,
    color: "cyan" | "rose" | "indigo",
    desc: string
  ) => {
    const radius = 42;
    const strokeWidth = 8;
    const normValue = Math.min(100, Math.max(0, value));
    const circumference = 2 * Math.PI * radius;
    const strokeOffset = circumference - (normValue / 100) * circumference;

    const theme = {
      cyan: {
        stroke: "stroke-cyan-500",
        bg: "stroke-cyan-950/40",
        text: "text-cyan-400",
        glow: "drop-shadow-[0_0_8px_rgba(6,182,212,0.6)]"
      },
      rose: {
        stroke: "stroke-rose-500",
        bg: "stroke-rose-950/40",
        text: "text-rose-400",
        glow: "drop-shadow-[0_0_8px_rgba(244,63,94,0.6)]"
      },
      indigo: {
        stroke: "stroke-indigo-500",
        bg: "stroke-indigo-950/40",
        text: "text-indigo-400",
        glow: "drop-shadow-[0_0_8px_rgba(99,102,241,0.6)]"
      }
    }[color];

    return (
      <div className="flex flex-col items-center p-4 rounded-xl border border-slate-900 bg-slate-950/40 backdrop-blur-sm shadow-md text-center hover:border-slate-800 transition-all duration-300">
        <div className="relative w-28 h-28 mb-3">
          <svg className="w-full h-full transform -rotate-90">
            {/* Background path */}
            <circle
              cx="56"
              cy="56"
              r={radius}
              className={`${theme.bg}`}
              strokeWidth={strokeWidth}
              fill="transparent"
            />
            {/* Primary stroke path */}
            <circle
              cx="56"
              cy="56"
              r={radius}
              className={`${theme.stroke} transition-all duration-1000 ease-out`}
              strokeWidth={strokeWidth}
              strokeDasharray={circumference}
              strokeDashoffset={strokeOffset}
              strokeLinecap="round"
              fill="transparent"
              style={{ filter: theme.glow }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-bold font-mono text-white leading-none tracking-tight">
              {Math.round(value)}%
            </span>
            <span className="text-[8px] font-mono text-slate-500 mt-1 uppercase tracking-widest">
              probability
            </span>
          </div>
        </div>
        <span className="text-xs font-mono font-bold tracking-wider text-slate-300 uppercase">
          {label}
        </span>
        <span className="text-[9px] font-mono text-slate-500 mt-1 leading-normal max-w-[120px]">
          {desc}
        </span>
      </div>
    );
  };

  // Convert Monte Carlo failure distribution data for chart
  const getMcChartData = () => {
    if (!mcResults || !mcResults.failure_distribution) return [];
    return Object.entries(mcResults.failure_distribution).map(([system, count]) => ({
      system,
      count
    }));
  };

  return (
    <div className="flex flex-col gap-4 font-mono text-slate-200">
      
      {/* Replay state context banner */}
      <div className={`p-3 rounded-xl border flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs font-bold shadow-lg transition-all duration-300 ${
        isReplayMode
          ? "border-amber-500/30 bg-amber-950/15 text-amber-300"
          : "border-slate-800/80 bg-slate-950/70 text-slate-400"
      }`}>
        <div className="flex items-center gap-2">
          {isReplayMode ? (
            <>
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse shadow-[0_0_8px_#f59e0b]" />
              <span>TIMELINE REPLAY ACTIVE // SIMULATOR CURRENT TICK STATE PAUSED</span>
            </>
          ) : (
            <>
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_#10b981]" />
              <span>LIVE TELEMETRY STREAM ACTIVE // REAL-TIME DECISION INFERENCE MONITORING</span>
            </>
          )}
        </div>
        {isReplayMode && (
          <button
            onClick={() => {
              setSelectedReplayId("live");
              setReplayPlaying(false);
            }}
            className="px-3 py-1 rounded bg-amber-500/20 hover:bg-amber-500/35 border border-amber-500/30 text-amber-200 text-[10px] tracking-widest uppercase transition-all"
          >
            Switch to Live Feed
          </button>
        )}
      </div>

      {/* Grid Row 1: Checklist & Gauges */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        
        {/* Mission Objectives Checklist */}
        <div className="xl:col-span-5 rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl flex flex-col">
          <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-900 pb-2 mb-3 uppercase flex items-center gap-2">
            <Award className="w-4 h-4" />
            Mission Objectives Status
          </h2>
          <div className="flex-1 space-y-3 overflow-y-auto max-h-[280px]">
            {objectives.length === 0 ? (
              <div className="text-[11px] text-slate-500 italic py-4">No objectives configured.</div>
            ) : (
              objectives.map((obj) => {
                const isAchieved = obj.status === "ACHIEVED";
                const isFailed = obj.status === "FAILED";
                const badgeColor = isAchieved
                  ? "bg-emerald-950/40 text-emerald-400 border-emerald-500/30"
                  : isFailed
                  ? "bg-rose-950/40 text-rose-400 border-rose-500/30"
                  : "bg-cyan-950/20 text-cyan-400 border-cyan-500/20";

                return (
                  <div
                    key={obj.id}
                    className="p-3 rounded-lg border border-slate-900 bg-slate-900/20 hover:border-slate-800 transition-all duration-300"
                  >
                    <div className="flex items-center justify-between gap-3 mb-1.5">
                      <span className="text-xs font-bold text-slate-100">{obj.objective_name}</span>
                      <span className={`px-2 py-0.5 rounded text-[8px] font-bold border uppercase tracking-wider ${badgeColor}`}>
                        {obj.status}
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-400 leading-normal mb-3">{obj.description}</p>
                    
                    {/* Conditions lists */}
                    <div className="grid grid-cols-2 gap-2 text-[9px] font-mono border-t border-slate-900/60 pt-2 bg-slate-950/30 p-1.5 rounded">
                      <div>
                        <span className="text-slate-500 uppercase block mb-1">Target Limits</span>
                        <div className="space-y-0.5 text-emerald-400">
                          {Object.entries(obj.success_conditions).map(([k, v]) => (
                            <div key={k} className="flex justify-between">
                              <span className="capitalize">{k}:</span>
                              <span className="font-bold">
                                {k === "distance" ? `${(v/1000).toLocaleString()}k km` : `>=${v}%`}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="border-l border-slate-900/60 pl-2">
                        <span className="text-slate-500 uppercase block mb-1">Failure Thresholds</span>
                        <div className="space-y-0.5 text-rose-400">
                          {Object.entries(obj.failure_conditions).map(([k, v]) => (
                            <div key={k} className="flex justify-between">
                              <span className="capitalize">{k}:</span>
                              <span className="font-bold">&lt;={v}%</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Dynamic Neon Probability Gauges */}
        <div className="xl:col-span-7 rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl flex flex-col">
          <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-900 pb-2 mb-4 uppercase flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            Dynamic Success Predictor (Heuristics Engine)
          </h2>
          <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-4 justify-center items-center">
            {renderNeonGauge(
              currentTelemetry?.success_probability ?? 100,
              "Success Probability",
              "cyan",
              "Compound index of health, power, fuel, and nav accuracy."
            )}
            {renderNeonGauge(
              currentTelemetry?.failure_probability ?? 0,
              "Failure Probability",
              "rose",
              "Probability of critical systems depletion before orbit."
            )}
            {renderNeonGauge(
              currentTelemetry?.confidence_score ?? 50,
              "Confidence Index",
              "indigo",
              "Degrades during hazard impacts; rises with flight progress."
            )}
          </div>
        </div>

      </div>

      {/* Grid Row 2: Subsystem Diagnostics & Sandbox */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        
        {/* Subsystem Diagnostics Matrix */}
        <div className="xl:col-span-6 rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl flex flex-col">
          <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-900 pb-2 mb-3 uppercase flex items-center gap-2">
            <Gauge className="w-4 h-4" />
            Subsystem Diagnostics Matrix
          </h2>
          <div className="flex-1 space-y-2.5 overflow-y-auto max-h-[380px]">
            {currentTelemetry?.subsystems ? (
              Object.entries(currentTelemetry.subsystems).map(([name, data]: [string, SubsystemInfo]) => {
                const statusColor = data.status === "OPERATIONAL"
                  ? "text-emerald-400 border-emerald-500/25 bg-emerald-950/15"
                  : data.status === "DEGRADED"
                  ? "text-amber-400 border-amber-500/25 bg-amber-950/15"
                  : "text-rose-400 border-rose-500/25 bg-rose-950/15";

                const healthPercent = data.health;
                const healthBarColor = healthPercent > 70 
                  ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)]"
                  : healthPercent > 30
                  ? "bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.4)]"
                  : "bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.4)]";

                return (
                  <div
                    key={name}
                    className="p-2.5 rounded-lg border border-slate-900 bg-slate-900/10 hover:border-slate-800/80 transition-all duration-300 flex flex-col md:flex-row md:items-center justify-between gap-3"
                  >
                    {/* Left: Name and bar */}
                    <div className="flex-1 flex flex-col gap-1.5">
                      <div className="flex justify-between items-center text-[10px] font-bold text-slate-300">
                        <span className="uppercase tracking-wider">{name}</span>
                        <span className="font-mono text-slate-400">{healthPercent.toFixed(1)}% Health</span>
                      </div>
                      <div className="w-full h-2 bg-slate-950 rounded overflow-hidden border border-slate-900 p-[1px]">
                        <div
                          className={`h-full rounded-sm ${healthBarColor} transition-all duration-1000 ease-out`}
                          style={{ width: `${healthPercent}%` }}
                        />
                      </div>
                    </div>
                    {/* Right: Badges */}
                    <div className="flex items-center gap-3 shrink-0 self-end md:self-center font-mono text-[9px] font-bold">
                      <div className="flex flex-col items-center">
                        <span className="text-[7px] text-slate-500 uppercase font-medium">performance</span>
                        <span className="text-cyan-400 text-xs mt-0.5">{data.performance.toFixed(2)}x</span>
                      </div>
                      <div className="flex flex-col items-center">
                        <span className="text-[7px] text-slate-500 uppercase font-medium">risk score</span>
                        <span className="text-slate-400 text-xs mt-0.5">{data.risk.toFixed(0)}%</span>
                      </div>
                      <span className={`px-2 py-1 rounded border uppercase tracking-wider font-bold ${statusColor}`}>
                        {data.status}
                      </span>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="text-[11px] text-slate-500 italic py-8 text-center">
                Waiting for telemetry subsystem telemetry reports...
              </div>
            )}
          </div>
        </div>

        {/* Decision Sandbox Action Predictor */}
        <div className="xl:col-span-6 rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl flex flex-col">
          <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-900 pb-2 mb-3 uppercase flex items-center gap-2">
            <ShieldAlert className="w-4 h-4" />
            Decision Sandbox Action Predictor
          </h2>
          <div className="flex-1 space-y-3.5 overflow-y-auto max-h-[380px]">
            {currentActiveEvents.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-slate-500 border border-dashed border-slate-900 rounded-lg">
                <ShieldAlert className="w-10 h-10 text-slate-700 animate-pulse mb-2" />
                <p className="text-xs font-bold uppercase tracking-wider">No active hazard anomalies</p>
                <p className="text-[10px] text-slate-600 mt-1 max-w-[280px] text-center leading-normal">
                  Spacecraft parameters operating at stable equilibrium. Sandbox will render selectable actions when anomalies arise.
                </p>
              </div>
            ) : (
              currentActiveEvents.map((event) => {
                const options = actionOptions[event.event_type] || [];
                const isMitigating = event.status === "MITIGATING";
                const isPending = event.status === "PENDING";

                return (
                  <div
                    key={event.id}
                    className={`p-3 rounded-lg border bg-slate-900/10 flex flex-col gap-3 transition-all duration-300 ${
                      isMitigating
                        ? "border-amber-500/25 bg-amber-950/5"
                        : isPending
                        ? "border-cyan-500/20 bg-cyan-950/5 animate-pulse"
                        : "border-rose-500/25 bg-rose-950/5"
                    }`}
                  >
                    {/* Event header */}
                    <div className="flex justify-between items-start gap-3 border-b border-slate-900 pb-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-slate-100 uppercase">{event.event_type}</span>
                          <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold tracking-widest ${
                            event.severity === "CRITICAL"
                              ? "bg-rose-950/40 text-rose-400 border border-rose-500/30"
                              : "bg-amber-950/40 text-amber-400 border border-amber-500/30"
                          }`}>
                            {event.severity}
                          </span>
                        </div>
                        <span className="text-[8.5px] text-slate-500 mt-1 block uppercase">
                          System Affected: {event.affected_system}
                        </span>
                      </div>
                      <span className={`px-2 py-0.5 rounded text-[9px] font-bold border uppercase tracking-wider ${
                        isMitigating 
                          ? "bg-amber-500/15 border-amber-500/30 text-amber-300" 
                          : isPending
                          ? "bg-cyan-500/15 border-cyan-500/30 text-cyan-300"
                          : "bg-rose-500/15 border-rose-500/30 text-rose-300"
                      }`}>
                        {event.status ?? "ACTIVE"}
                      </span>
                    </div>

                    <p className="text-[10px] text-slate-400 leading-normal">{event.description}</p>

                    {/* Actions Sandbox area */}
                    <div className="flex flex-col gap-2 border-t border-slate-950/60 pt-2">
                      <span className="text-[9px] text-slate-500 font-bold uppercase mb-1">Selectable Sandbox Remediation Options:</span>
                      
                      {options.map((opt) => {
                        const pred = actionPredictions[opt.action_key] || {};
                        const isHovered = hoveredAction === opt.action_key;

                        return (
                          <div
                            key={opt.action_key}
                            onMouseEnter={() => setHoveredAction(opt.action_key)}
                            onMouseLeave={() => setHoveredAction(null)}
                            className="relative group flex flex-col gap-1.5 p-2 rounded border border-slate-900 bg-slate-950/40 hover:border-slate-800 transition-all duration-350"
                          >
                            <div className="flex justify-between items-center gap-3">
                              <div className="flex flex-col">
                                <span className="text-[10px] font-bold text-slate-300">{opt.action_name}</span>
                                <span className="text-[8.5px] text-slate-500 leading-tight mt-0.5">{opt.description}</span>
                              </div>
                              <button
                                onClick={() => executeSandboxAction(event.id, opt.action_key)}
                                disabled={isMitigating || isReplayMode}
                                className="px-2.5 py-1 rounded bg-cyan-600 hover:bg-cyan-500 border border-cyan-500/30 text-[9px] font-bold text-white uppercase tracking-wider transition-all disabled:opacity-30 disabled:hover:bg-cyan-600 shadow-md shadow-cyan-950/30 shrink-0"
                              >
                                {isMitigating ? "Executing..." : "Execute"}
                              </button>
                            </div>

                            {/* Hover predictions details indicator overlay */}
                            {isHovered && (
                              <div className="mt-2 p-2 rounded bg-slate-900/90 border border-slate-800 text-[8.5px] font-mono grid grid-cols-2 md:grid-cols-4 gap-2 animate-fade-in shadow-xl">
                                <div>
                                  <span className="text-slate-500 uppercase block">propellant delta</span>
                                  <span className={`font-bold ${pred.fuel_delta >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                                    {pred.fuel_delta >= 0 ? `+${pred.fuel_delta}%` : `${pred.fuel_delta}%`}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-slate-500 uppercase block">solar power delta</span>
                                  <span className={`font-bold ${pred.power_delta >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                                    {pred.power_delta >= 0 ? `+${pred.power_delta}%` : `${pred.power_delta}%`}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-slate-500 uppercase block">risk mitigation</span>
                                  <span className="font-bold text-cyan-400">-{pred.risk_reduction}% Risk</span>
                                </div>
                                <div>
                                  <span className="text-slate-500 uppercase block">success factor</span>
                                  <span className={`font-bold ${pred.success_delta >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                                    {pred.success_delta >= 0 ? `+${pred.success_delta}%` : `${pred.success_delta}%`}
                                  </span>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

      </div>

      {/* Grid Row 3: Monte Carlo & Dependency Graph */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        
        {/* Monte Carlo Forecaster Panel */}
        <div className="xl:col-span-6 rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl flex flex-col">
          <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-900 pb-2 mb-3 uppercase flex items-center gap-2">
            <Sliders className="w-4 h-4" />
            Monte Carlo Prediction Forecaster
          </h2>
          <div className="flex-1 flex flex-col gap-4">
            
            {/* Iteration config controls */}
            <div className="flex flex-wrap items-center gap-3 p-3 rounded-lg border border-slate-900 bg-slate-900/20 text-[10px]">
              <span className="text-slate-500 uppercase font-bold tracking-wider">simulation iterations:</span>
              <div className="flex items-center gap-1.5">
                {[100, 500, 1000, 3000].map((num) => (
                  <button
                    key={num}
                    onClick={() => setMcIterations(num)}
                    className={`px-2.5 py-1 rounded border font-bold uppercase transition-all ${
                      mcIterations === num
                        ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/30"
                        : "text-slate-500 border-transparent hover:text-slate-350"
                    }`}
                  >
                    {num}
                  </button>
                ))}
              </div>
              <button
                onClick={runMonteCarloForecast}
                disabled={mcLoading}
                className="ml-auto px-4 py-1.5 rounded bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 font-bold text-white uppercase tracking-wider transition-all shadow-md flex items-center gap-1.5 disabled:opacity-40"
              >
                {mcLoading ? (
                  <>
                    <RefreshCw className="w-3 h-3 animate-spin" />
                    computing...
                  </>
                ) : (
                  <>
                    <FastForward className="w-3.5 h-3.5" />
                    run forecast
                  </>
                )}
              </button>
            </div>

            {/* Results Panel */}
            {mcLoading ? (
              <div className="flex-1 flex flex-col items-center justify-center text-slate-500 py-12">
                <RefreshCw className="w-8 h-8 text-cyan-500 animate-spin mb-3" />
                <p className="text-xs uppercase font-bold text-slate-400 tracking-wider">Simulating Trajectory Fast-Forwards</p>
                <p className="text-[9px] text-slate-600 mt-1 max-w-[320px] text-center leading-normal">
                  Monte Carlo engine is running {mcIterations} worker-threaded flight loop paths using Newtonian math modifiers.
                </p>
              </div>
            ) : mcResults ? (
              <div className="flex-1 grid grid-cols-1 md:grid-cols-12 gap-4">
                
                {/* Stats Summary cards */}
                <div className="md:col-span-5 grid grid-cols-2 gap-2 text-[9px] font-mono">
                  <div className="p-2.5 rounded border border-slate-900 bg-slate-950/50">
                    <span className="text-slate-500 uppercase block">avg success probability</span>
                    <span className="text-sm font-extrabold text-cyan-400 font-mono mt-1 block">
                      {mcResults.avg_success_prob}%
                    </span>
                  </div>
                  <div className="p-2.5 rounded border border-slate-900 bg-slate-950/50">
                    <span className="text-slate-500 uppercase block">avg fuel remaining</span>
                    <span className="text-sm font-extrabold text-slate-200 font-mono mt-1 block">
                      {mcResults.avg_fuel_remaining.toFixed(1)}%
                    </span>
                  </div>
                  <div className="p-2.5 rounded border border-slate-900 bg-slate-950/50">
                    <span className="text-slate-500 uppercase block">avg mission duration</span>
                    <span className="text-sm font-extrabold text-slate-200 font-mono mt-1 block">
                      {mcResults.avg_mission_time.toFixed(0)} ticks
                    </span>
                  </div>
                  <div className="p-2.5 rounded border border-slate-900 bg-slate-950/50">
                    <span className="text-slate-500 uppercase block">avg risk factor</span>
                    <span className="text-sm font-extrabold text-rose-400 font-mono mt-1 block">
                      {mcResults.avg_risk.toFixed(1)}%
                    </span>
                  </div>
                </div>

                {/* Failure distribution chart */}
                <div className="md:col-span-7 flex flex-col bg-slate-950/30 p-2 border border-slate-900 rounded">
                  <span className="text-[8px] text-slate-500 uppercase font-bold tracking-widest block mb-2 px-1">
                    failure cause attribution distribution ratio
                  </span>
                  <div className="flex-1 min-h-[120px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={getMcChartData()} margin={{ top: 5, right: 10, left: -25, bottom: 0 }}>
                        <XAxis dataKey="system" stroke="#475569" fontSize={7} tickLine={false} />
                        <YAxis stroke="#475569" fontSize={8} tickLine={false} axisLine={false} />
                        <Tooltip
                          contentStyle={{ background: "#090d16", border: "1px border #1e293b", fontSize: "9px" }}
                          itemStyle={{ color: "#06b6d4" }}
                        />
                        <Bar dataKey="count" fill="#3b82f6" radius={[2, 2, 0, 0]}>
                          {getMcChartData().map((entry, index) => {
                            const colors = ["#ef4444", "#f59e0b", "#10b981", "#06b6d4", "#6366f1", "#8b5cf6", "#ec4899"];
                            return <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />;
                          })}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-slate-500 py-12 border border-dashed border-slate-900 rounded-lg">
                <Sliders className="w-10 h-10 text-slate-700 animate-pulse mb-2" />
                <p className="text-xs uppercase font-bold text-slate-400 tracking-wider">Prediction Matrix Empty</p>
                <p className="text-[9px] text-slate-600 mt-1 max-w-[280px] text-center leading-normal">
                  Configure simulation iterations and trigger the forecaster compute deck to view Newtonian flight trajectories predictions.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Dependency Propagation Graph */}
        <div className="xl:col-span-6 rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl flex flex-col">
          <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-900 pb-2 mb-3 uppercase flex items-center gap-2">
            <Radio className="w-4 h-4" />
            Consequence Propagation Cascades
          </h2>
          <div className="flex-1 flex flex-col gap-3 overflow-y-auto max-h-[300px]">
            <span className="text-[9px] text-slate-500 font-bold uppercase mb-1">Active Failure Chain Risk Paths:</span>
            
            {/* Hardcoded visual representational flow charts of seeded pairs */}
            <div className="space-y-3.5 font-mono text-[9px]">
              
              {/* Path 1 */}
              <div className="p-2.5 rounded border border-slate-900 bg-slate-900/10 hover:border-slate-800 transition-all duration-300">
                <div className="flex justify-between text-[10px] font-bold text-slate-300 mb-2">
                  <span>CHAIN A: ELECTROMAGNETIC CASCADE</span>
                  <span className="text-cyan-400">70% propagation risk</span>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <div className={`p-1.5 rounded border text-[9.5px] ${
                    currentActiveEvents.some(e => e.event_type === "Solar Storm")
                      ? "border-rose-500 bg-rose-950/20 text-rose-400 font-bold animate-pulse"
                      : "border-slate-800 bg-slate-950/60 text-slate-400"
                  }`}>
                    Solar Storm ⚡
                  </div>
                  <ChevronRight className="w-3.5 h-3.5 text-slate-600" />
                  <div className={`p-1.5 rounded border text-[9.5px] ${
                    currentActiveEvents.some(e => e.event_type === "Communication Loss")
                      ? "border-amber-500 bg-amber-950/20 text-amber-400 font-bold animate-pulse"
                      : "border-slate-800 bg-slate-950/60 text-slate-400"
                  }`}>
                    Communication Loss 📡
                  </div>
                  <ChevronRight className="w-3.5 h-3.5 text-slate-600" />
                  <div className={`p-1.5 rounded border text-[9.5px] ${
                    currentActiveEvents.some(e => e.event_type === "Navigation Drift")
                      ? "border-amber-500 bg-amber-950/20 text-amber-400 font-bold animate-pulse"
                      : "border-slate-800 bg-slate-950/60 text-slate-400"
                  }`}>
                    Navigation Drift 🧭
                  </div>
                </div>
              </div>

              {/* Path 2 */}
              <div className="p-2.5 rounded border border-slate-900 bg-slate-900/10 hover:border-slate-800 transition-all duration-300">
                <div className="flex justify-between text-[10px] font-bold text-slate-300 mb-2">
                  <span>CHAIN B: PROPULSION FEED PRESSURE</span>
                  <span className="text-cyan-400">60% propagation risk</span>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <div className={`p-1.5 rounded border text-[9.5px] ${
                    currentActiveEvents.some(e => e.event_type === "Fuel Leak")
                      ? "border-rose-500 bg-rose-950/20 text-rose-400 font-bold animate-pulse"
                      : "border-slate-800 bg-slate-950/60 text-slate-400"
                  }`}>
                    Fuel Leak 💧
                  </div>
                  <ChevronRight className="w-3.5 h-3.5 text-slate-600" />
                  <div className={`p-1.5 rounded border text-[9.5px] ${
                    currentActiveEvents.some(e => e.event_type === "Thruster Failure")
                      ? "border-rose-500 bg-rose-950/20 text-rose-400 font-bold animate-pulse"
                      : "border-slate-800 bg-slate-950/60 text-slate-400"
                  }`}>
                    Thruster Failure 🔥
                  </div>
                  <ChevronRight className="w-3.5 h-3.5 text-slate-600" />
                  <div className={`p-1.5 rounded border text-[9.5px] ${
                    currentActiveEvents.some(e => e.event_type === "Navigation Drift")
                      ? "border-amber-500 bg-amber-950/20 text-amber-400 font-bold animate-pulse"
                      : "border-slate-800 bg-slate-950/60 text-slate-400"
                  }`}>
                    Navigation Drift 🧭
                  </div>
                </div>
              </div>

              {/* Path 3 */}
              <div className="p-2.5 rounded border border-slate-900 bg-slate-900/10 hover:border-slate-800 transition-all duration-300">
                <div className="flex justify-between text-[10px] font-bold text-slate-300 mb-2">
                  <span>CHAIN C: TRANSIENT VOLTAGE DISCHARGE</span>
                  <span className="text-cyan-400">50% propagation risk</span>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <div className={`p-1.5 rounded border text-[9.5px] ${
                    currentActiveEvents.some(e => e.event_type === "Power Fluctuation")
                      ? "border-rose-500 bg-rose-950/20 text-rose-400 font-bold animate-pulse"
                      : "border-slate-800 bg-slate-950/60 text-slate-400"
                  }`}>
                    Power Fluctuation 🔌
                  </div>
                  <ChevronRight className="w-3.5 h-3.5 text-slate-600" />
                  <div className={`p-1.5 rounded border text-[9.5px] ${
                    currentActiveEvents.some(e => e.event_type === "Sensor Malfunction")
                      ? "border-amber-500 bg-amber-950/20 text-amber-400 font-bold animate-pulse"
                      : "border-slate-800 bg-slate-950/60 text-slate-400"
                  }`}>
                    Sensor Malfunction 🛠️
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>

      </div>

      {/* Grid Row 4: Timeline Replay Controls Drawer */}
      <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl flex flex-col gap-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-900 pb-2">
          <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 uppercase flex items-center gap-2">
            <History className="w-4 h-4" />
            Timeline Replay Console
          </h2>
          
          {/* Replay Selector */}
          <div className="flex items-center gap-2 text-[10px] font-mono bg-slate-900/40 p-1.5 border border-slate-800/80 rounded-lg">
            <Database className="w-3.5 h-3.5 text-slate-500" />
            <span className="text-slate-500 font-bold uppercase whitespace-nowrap">Load Memory Run:</span>
            <select
              value={selectedReplayId}
              onChange={(e) => {
                const val = e.target.value;
                setSelectedReplayId(val);
                setReplayIndex(0);
                setReplayPlaying(false);
              }}
              className="bg-slate-950 text-cyan-400 font-bold font-mono outline-none border-none py-0.5 px-2 rounded cursor-pointer"
            >
              <option value="live">Current Session (Live History)</option>
              {replays.map((rep) => (
                <option key={rep.id} value={rep.id.toString()}>
                  {rep.replay_name} ({rep.history_data.length} pts)
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Console scrubbing controls */}
        <div className="flex flex-col gap-3">
          
          {/* Play/Pause controls */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 bg-slate-900/60 p-1 rounded-lg border border-slate-800">
              <button
                onClick={() => setReplayIndex(0)}
                disabled={replayData.length === 0}
                className="p-1.5 rounded hover:bg-slate-850/60 text-slate-400 hover:text-slate-100 disabled:opacity-30 transition-all"
                title="Restart Timeline"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setReplayIndex(prev => Math.max(0, prev - 1))}
                disabled={replayData.length === 0 || replayIndex === 0}
                className="p-1.5 rounded hover:bg-slate-850/60 text-slate-400 hover:text-slate-100 disabled:opacity-30 transition-all"
                title="Step Backward"
              >
                <FastForward className="w-3.5 h-3.5 rotate-180" />
              </button>
              <button
                onClick={() => setReplayPlaying(!replayPlaying)}
                disabled={replayData.length === 0 || replayIndex >= replayData.length - 1}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-bold tracking-wider ${
                  replayPlaying
                    ? "text-amber-400 hover:bg-amber-950/20"
                    : "text-emerald-400 hover:bg-emerald-950/20"
                } disabled:opacity-30 transition-all`}
                title={replayPlaying ? "Pause Playback" : "Play Playback"}
              >
                {replayPlaying ? (
                  <>
                    <Pause className="w-3 h-3 fill-current" />
                    PAUSE
                  </>
                ) : (
                  <>
                    <Play className="w-3 h-3 fill-current" />
                    PLAY
                  </>
                )}
              </button>
              <button
                onClick={() => setReplayIndex(prev => Math.min(replayData.length - 1, prev + 1))}
                disabled={replayData.length === 0 || replayIndex >= replayData.length - 1}
                className="p-1.5 rounded hover:bg-slate-850/60 text-slate-400 hover:text-slate-100 disabled:opacity-30 transition-all"
                title="Step Forward"
              >
                <FastForward className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Speed slider */}
            <div className="flex items-center gap-4 text-[10px] font-mono">
              <span className="text-slate-500 uppercase font-bold tracking-wider">Playback Speed:</span>
              <div className="flex items-center gap-1 bg-slate-900/60 p-0.5 rounded-lg border border-slate-800">
                {[1, 2, 5, 10].map((sp) => (
                  <button
                    key={sp}
                    onClick={() => setReplaySpeed(sp)}
                    className={`px-2 py-0.5 rounded text-[9.5px] font-bold transition-all ${
                      replaySpeed === sp
                        ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/25"
                        : "text-slate-500 border-transparent hover:text-slate-350"
                    }`}
                  >
                    {sp}x
                  </button>
                ))}
              </div>
            </div>

            {/* Step Counter index */}
            <div className="text-[10px] font-mono font-bold text-slate-400 bg-slate-900/30 px-3 py-1.5 rounded border border-slate-900">
              STEP REGISTER INDEX:{" "}
              <span className="text-cyan-400 font-mono">
                {replayData.length > 0 ? replayIndex + 1 : 0}
              </span>{" "}
              / <span className="text-slate-500 font-mono">{replayData.length}</span> ticks
            </div>
          </div>

          {/* Timeline slider Scrubber bar */}
          <div className="flex items-center gap-3 w-full bg-slate-900/25 border border-slate-900 rounded-lg p-2.5">
            <span className="text-[9px] font-mono text-slate-500 uppercase font-bold whitespace-nowrap">scrubber timeline:</span>
            <input
              type="range"
              min="0"
              max={Math.max(0, replayData.length - 1)}
              value={replayIndex}
              onChange={handleScrubChange}
              disabled={replayData.length === 0}
              className="flex-1 accent-cyan-500 bg-slate-950 border border-slate-900 rounded h-2.5 cursor-pointer disabled:opacity-20"
            />
            <span className="text-[10px] font-mono font-bold text-cyan-400 w-16 text-right">
              {currentTelemetry ? currentTelemetry.mission_progress.toFixed(1) : 0.0}%
            </span>
          </div>

        </div>
      </div>

    </div>
  );
}
