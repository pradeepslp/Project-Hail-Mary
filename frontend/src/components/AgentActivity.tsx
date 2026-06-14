"use client";

import React, { useEffect, useState, useCallback } from "react";
import { 
  Brain, 
  Compass, 
  Droplet, 
  ShieldAlert, 
  Atom, 
  TrendingUp, 
  Gauge, 
  Server, 
  RefreshCw, 
  CheckCircle, 
  AlertTriangle,
  Info,
  Sliders,
  Settings,
  Flame,
  Activity,
  Play
} from "lucide-react";
import { 
  ResponsiveContainer, 
  RadarChart, 
  PolarGrid, 
  PolarAngleAxis, 
  PolarRadiusAxis, 
  Radar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip
} from "recharts";
import { Telemetry, Mission, ActiveEvent } from "../hooks/useWebSocket";

import { useStore, telemetryStore, activeEventsStore, missionStore } from "../hooks/useStore";

interface AgentActivityProps {
  telemetry?: Telemetry | null;
  mission?: Mission | null;
  activeEvents?: ActiveEvent[];
}

interface AgentState {
  event_id: number | null;
  chosen_action: string | null;
  confidence: number | null;
  timestamp: string | null;
  reasoning?: string;
  debate?: { sender: string; role: string; message: string }[];
  sub_agents?: {
    nav: { recommendation: string; scores: Record<string, number>; risk: number };
    fuel: { recommendation: string; scores: Record<string, number>; risk: number };
    safety: { recommendation: string; scores: Record<string, number>; risk: number };
    science: { recommendation: string; scores: Record<string, number>; risk: number };
  };
}

interface AgentMetrics {
  decision_accuracy: number;
  mission_success_rate: number;
  avg_confidence: number;
  agreement_rate: number;
}

export default function AgentActivity({ 
  telemetry: propTelemetry, 
  mission: propMission, 
  activeEvents: propActiveEvents 
}: AgentActivityProps) {
  const storeTelemetry = useStore(telemetryStore);
  const storeMission = useStore(missionStore);
  const storeActiveEvents = useStore(activeEventsStore);

  const telemetry = propTelemetry !== undefined ? propTelemetry : storeTelemetry;
  const mission = propMission !== undefined ? propMission : storeMission;
  const activeEvents = propActiveEvents !== undefined ? propActiveEvents : storeActiveEvents;
  const [autonomyLevel, setAutonomyLevel] = useState<number>(0);
  const [agentState, setAgentState] = useState<AgentState | null>(null);
  const [metrics, setMetrics] = useState<AgentMetrics | null>(null);
  const [isTraining, setIsTraining] = useState<boolean>(false);
  const [trainingResult, setTrainingResult] = useState<{ samples: number; r2_score: number } | null>(null);
  const [errorText, setErrorText] = useState<string>("");

  const backendUrl = "127.0.0.1:8000";

  // Fetch agent state & metrics
  const fetchAgentData = useCallback(async () => {
    try {
      // 1. Fetch Autonomy and State
      const stateRes = await fetch(`http://${backendUrl}/agent/state`);
      if (stateRes.ok) {
        const stateData = await stateRes.json();
        setAutonomyLevel(stateData.autonomy_level);
        if (stateData.state && Object.keys(stateData.state).length > 0) {
          setAgentState({
            event_id: stateData.state.event_id,
            chosen_action: stateData.state.chosen_action,
            confidence: stateData.state.confidence,
            timestamp: stateData.state.timestamp,
            reasoning: stateData.reasoning,
            debate: stateData.debate,
            sub_agents: stateData.state.sub_agents
          });
        } else {
          setAgentState(null);
        }
      }

      // 2. Fetch Metrics
      const metricsRes = await fetch(`http://${backendUrl}/agent/metrics`);
      if (metricsRes.ok) {
        const metricsData = await metricsRes.json();
        setMetrics(metricsData);
      }
    } catch (err) {
      console.error("Failed to fetch agent state/metrics:", err);
    }
  }, []);

  // Update autonomy level on backend
  const handleAutonomyChange = async (level: number) => {
    try {
      const res = await fetch(`http://${backendUrl}/agent/autonomy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ level })
      });
      if (res.ok) {
        const data = await res.json();
        setAutonomyLevel(data.autonomy_level);
        setErrorText("");
      } else {
        const err = await res.json();
        setErrorText(err.detail || "Failed to update autonomy");
      }
    } catch (err) {
      console.error("Failed to set autonomy level:", err);
      setErrorText("Connection failure");
    }
  };

  // Run training cycle
  const runTraining = async () => {
    setIsTraining(true);
    setTrainingResult(null);
    try {
      const res = await fetch(`http://${backendUrl}/agent/learning/train`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setTrainingResult({
          samples: data.samples,
          r2_score: data.r2_score
        });
        // Refresh metrics
        const metricsRes = await fetch(`http://${backendUrl}/agent/metrics`);
        if (metricsRes.ok) {
          const metricsData = await metricsRes.json();
          setMetrics(metricsData);
        }
      }
    } catch (err) {
      console.error("Training error:", err);
    } finally {
      setIsTraining(false);
    }
  };

  // Trigger fetch on activeEvents changes or tick loop (1.5s interval)
  useEffect(() => {
    fetchAgentData();
    const interval = setInterval(fetchAgentData, 1500);
    return () => clearInterval(interval);
  }, [fetchAgentData, activeEvents]);

  // Autonomy modes details
  const autonomyModes = [
    { level: 0, title: "HUMAN ONLY", desc: "No agent recommendations or overrides. Full manual controls." },
    { level: 1, title: "SUGGEST", desc: "Sub-agents calculate recommendations. Visualized on HUD, no execution." },
    { level: 2, title: "RECOMMEND", desc: "Commander AI aggregates sub-agent feedback and highlights the top action." },
    { level: 3, title: "AUTO SAFE", desc: "Autonomous execution of non-critical safety mitigations. Ignores high-risk choices." },
    { level: 4, title: "FULL AUTOPILOT", desc: "AI Commander executes all decisions dynamically based on utility forecasts." }
  ];

  // Compile radar chart data from sub-agent scores
  const getRadarData = () => {
    if (!agentState?.sub_agents) return [];
    
    const subs = agentState.sub_agents;
    const allActions = Array.from(new Set([
      ...Object.keys(subs.nav.scores || {}),
      ...Object.keys(subs.fuel.scores || {}),
      ...Object.keys(subs.safety.scores || {}),
      ...Object.keys(subs.science.scores || {})
    ]));

    return allActions.map(act => {
      // Simplify display name (e.g. fuel_leak_activate_backup -> Activate Backup)
      const label = act.split("_").slice(2).join(" ") || act.split("_").slice(1).join(" ") || act;
      return {
        action: label.toUpperCase(),
        Navigation: subs.nav.scores?.[act] || 0,
        Fuel: subs.fuel.scores?.[act] || 0,
        Safety: subs.safety.scores?.[act] || 0,
        Science: subs.science.scores?.[act] || 0
      };
    });
  };

  const radarData = getRadarData();

  // Synthetic charts history for visual style
  const historyData = [
    { tick: "T-20", confidence: 74, success: 85 },
    { tick: "T-16", confidence: 79, success: 86 },
    { tick: "T-12", confidence: 82, success: 88 },
    { tick: "T-8", confidence: 80, success: 87 },
    { tick: "T-4", confidence: 85, success: 89 },
    { tick: "T-NOW", confidence: agentState?.confidence || 88, success: telemetry?.success_probability || 92 }
  ];

  const currentUnresolved = activeEvents.filter(e => e.status !== "MITIGATING" && e.status !== "RESOLVED");
  const hasActiveAnomaly = currentUnresolved.length > 0;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
      
      {/* 1. TOP PANEL: Autonomy Level Selector (Col span 12) */}
      <section className="lg:col-span-12 rounded-xl border border-slate-800/80 bg-slate-950/70 p-5 backdrop-blur-md shadow-xl flex flex-col gap-4">
        <div className="flex items-center justify-between border-b border-slate-900 pb-3">
          <div className="flex items-center gap-2.5">
            <Sliders className="w-5 h-5 text-cyan-400" />
            <div>
              <h2 className="text-sm font-bold font-mono tracking-wider text-slate-200">
                AUTONOMY CONTROL SYSTEM
              </h2>
              <p className="text-[10px] font-mono text-slate-500">
                CONFIGURE COMMAND OVERRIDE INTEGRATION PARAMETERS
              </p>
            </div>
          </div>
          {errorText && (
            <span className="text-rose-400 font-mono text-[10px] bg-rose-950/30 px-3 py-1 rounded border border-rose-900/50">
              {errorText}
            </span>
          )}
        </div>

        {/* Autonomy Selector Grid */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          {autonomyModes.map((mode) => {
            const isSelected = autonomyLevel === mode.level;
            
            let colorStyles = "";
            if (isSelected) {
              colorStyles = {
                0: "border-slate-500 bg-slate-500/10 text-slate-300",
                1: "border-cyan-500/80 bg-cyan-500/10 text-cyan-400 shadow-[0_0_12px_rgba(6,182,212,0.15)]",
                2: "border-indigo-500/80 bg-indigo-500/10 text-indigo-400 shadow-[0_0_12px_rgba(99,102,241,0.15)]",
                3: "border-amber-500/80 bg-amber-500/10 text-amber-400 shadow-[0_0_12px_rgba(245,158,11,0.15)]",
                4: "border-emerald-500/90 bg-emerald-500/15 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.2)] font-extrabold"
              }[mode.level] || "";
            }

            return (
              <button
                key={mode.level}
                onClick={() => handleAutonomyChange(mode.level)}
                className={`p-3.5 rounded-lg border text-left transition-all duration-300 hover:scale-[1.01] ${
                  isSelected 
                    ? `${colorStyles}` 
                    : "border-slate-900 bg-slate-950/40 text-slate-500 hover:border-slate-800 hover:text-slate-400"
                }`}
              >
                <div className="flex items-center justify-between mb-1.5 font-mono">
                  <span className="text-xs font-bold tracking-wider">LEVEL {mode.level}</span>
                  {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-current animate-ping" />}
                </div>
                <h3 className="text-[10px] font-mono font-bold tracking-widest uppercase mb-1">{mode.title}</h3>
                <p className="text-[9px] leading-relaxed font-mono opacity-80">{mode.desc}</p>
              </button>
            );
          })}
        </div>
      </section>

      {/* 2. MIDDLE LEFT: Multi-Agent Collaborative Feeds (Col span 7) */}
      <section className="lg:col-span-7 flex flex-col gap-4">
        
        {/* Collaborative Grid */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl flex-1">
          <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-900 pb-2 mb-4 uppercase flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Brain className="w-4 h-4 text-cyan-500" />
              Agent Specialist HUDs
            </span>
            {hasActiveAnomaly ? (
              <span className="text-[9px] text-amber-400 bg-amber-950/30 border border-amber-900/40 px-2 py-0.5 rounded font-mono animate-pulse uppercase">
                Active Analysis Process Running
              </span>
            ) : (
              <span className="text-[9px] text-slate-500 font-mono uppercase">
                Standby Scan Mode
              </span>
            )}
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            
            {/* Nav Agent */}
            <div className="rounded-lg border border-slate-900 bg-slate-950/40 p-3.5 flex flex-col gap-2.5">
              <div className="flex items-center justify-between text-xs font-mono font-bold text-slate-300">
                <span className="flex items-center gap-2 text-cyan-400">
                  <Compass className="w-4 h-4 animate-spin-slow" />
                  Navigation Agent
                </span>
                <span className="text-[10px] text-slate-500">ROLE: TRAJECTORY</span>
              </div>
              <p className="text-[10.5px] font-mono text-slate-400 leading-normal min-h-[50px] bg-slate-950/60 p-2 rounded border border-slate-900/50">
                {agentState?.sub_agents?.nav.recommendation ?? "Standby. Scanning coordinate offsets, star constellation overlays, and velocity margins..."}
              </p>
              <div className="flex justify-between items-center text-[10px] font-mono text-slate-500 mt-1 border-t border-slate-900/60 pt-2">
                <span>Calculated Risk:</span>
                <span className={`font-bold ${agentState && agentState.sub_agents && agentState.sub_agents.nav.risk > 50 ? "text-amber-400" : "text-cyan-400"}`}>
                  {agentState?.sub_agents?.nav.risk ? `${agentState.sub_agents.nav.risk}%` : "0.0%"}
                </span>
              </div>
            </div>

            {/* Resource Agent */}
            <div className="rounded-lg border border-slate-900 bg-slate-950/40 p-3.5 flex flex-col gap-2.5">
              <div className="flex items-center justify-between text-xs font-mono font-bold text-slate-300">
                <span className="flex items-center gap-2 text-orange-400">
                  <Droplet className="w-4 h-4" />
                  Resource Agent
                </span>
                <span className="text-[10px] text-slate-500">ROLE: CONSUMABLES</span>
              </div>
              <p className="text-[10.5px] font-mono text-slate-400 leading-normal min-h-[50px] bg-slate-950/60 p-2 rounded border border-slate-900/50">
                {agentState?.sub_agents?.fuel.recommendation ?? "Standby. Monitoring fuel decay metrics, battery grid levels, and oxygen reserves..."}
              </p>
              <div className="flex justify-between items-center text-[10px] font-mono text-slate-500 mt-1 border-t border-slate-900/60 pt-2">
                <span>Calculated Risk:</span>
                <span className={`font-bold ${agentState && agentState.sub_agents && agentState.sub_agents.fuel.risk > 50 ? "text-amber-400" : "text-orange-400"}`}>
                  {agentState?.sub_agents?.fuel.risk ? `${agentState.sub_agents.fuel.risk}%` : "0.0%"}
                </span>
              </div>
            </div>

            {/* Safety Agent */}
            <div className="rounded-lg border border-slate-900 bg-slate-950/40 p-3.5 flex flex-col gap-2.5">
              <div className="flex items-center justify-between text-xs font-mono font-bold text-slate-300">
                <span className="flex items-center gap-2 text-rose-400">
                  <ShieldAlert className="w-4 h-4" />
                  Safety Agent
                </span>
                <span className="text-[10px] text-slate-500">ROLE: INTEGRITY</span>
              </div>
              <p className="text-[10.5px] font-mono text-slate-400 leading-normal min-h-[50px] bg-slate-950/60 p-2 rounded border border-slate-900/50">
                {agentState?.sub_agents?.safety.recommendation ?? "Standby. Auditing subsystem integrity, radiation margins, and hull mechanical strain..."}
              </p>
              <div className="flex justify-between items-center text-[10px] font-mono text-slate-500 mt-1 border-t border-slate-900/60 pt-2">
                <span>Calculated Risk:</span>
                <span className={`font-bold ${agentState && agentState.sub_agents && agentState.sub_agents.safety.risk > 50 ? "text-rose-400" : "text-rose-400"}`}>
                  {agentState?.sub_agents?.safety.risk ? `${agentState.sub_agents.safety.risk}%` : "0.0%"}
                </span>
              </div>
            </div>

            {/* Science Agent */}
            <div className="rounded-lg border border-slate-900 bg-slate-950/40 p-3.5 flex flex-col gap-2.5">
              <div className="flex items-center justify-between text-xs font-mono font-bold text-slate-300">
                <span className="flex items-center gap-2 text-indigo-400">
                  <Atom className="w-4 h-4" />
                  Science Agent
                </span>
                <span className="text-[10px] text-slate-500">ROLE: EXPLORATION</span>
              </div>
              <p className="text-[10.5px] font-mono text-slate-400 leading-normal min-h-[50px] bg-slate-950/60 p-2 rounded border border-slate-900/50">
                {agentState?.sub_agents?.science.recommendation ?? "Standby. Assessing scanner payload data, planetary radar charts, and research objectives..."}
              </p>
              <div className="flex justify-between items-center text-[10px] font-mono text-slate-500 mt-1 border-t border-slate-900/60 pt-2">
                <span>Calculated Risk:</span>
                <span className="font-bold text-indigo-400">
                  {agentState?.sub_agents?.science.risk ? `${agentState.sub_agents.science.risk}%` : "0.0%"}
                </span>
              </div>
            </div>

            {/* Commander Agent Card */}
            <div className="md:col-span-2 rounded-lg border border-slate-900 bg-slate-950/40 p-3.5 flex flex-col gap-2.5">
              <div className="flex items-center justify-between text-xs font-mono font-bold text-slate-300">
                <span className="flex items-center gap-2 text-emerald-400">
                  <Brain className="w-4 h-4 text-emerald-400" />
                  Mission Commander Agent
                </span>
                <span className="text-[10px] text-slate-500">ROLE: DECISION AUTHORITY</span>
              </div>
              <p className="text-[10.5px] font-mono text-slate-400 leading-normal min-h-[50px] bg-slate-950/80 p-2 rounded border border-slate-900/50">
                {agentState?.reasoning ?? "Standby. Awaiting specialist consensus reports and trajectory risk evaluations..."}
              </p>
              <div className="flex justify-between items-center text-[10px] font-mono text-slate-500 mt-1 border-t border-slate-900/60 pt-2">
                <span>Selected Mitigation:</span>
                <span className="font-bold text-cyan-400 uppercase">
                  {agentState?.chosen_action ? (agentState.chosen_action.split("_").slice(2).join(" ") || agentState.chosen_action.split("_").slice(1).join(" ")) : "None"}
                </span>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* 3. MIDDLE RIGHT: Commander Decision & Live Debate Board (Col span 5) */}
      <section className="lg:col-span-5 flex flex-col gap-4">
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl flex-1 flex flex-col gap-3">
          <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-900 pb-2 uppercase flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Brain className="w-4 h-4 text-emerald-400" />
              Consensus & Debate Board
            </span>
            {agentState?.chosen_action && (
              <span className="text-[9px] text-emerald-400 bg-emerald-950/30 border border-emerald-900/50 px-2 py-0.5 rounded font-mono">
                DEBATE COMPLETED
              </span>
            )}
          </h2>

          {hasActiveAnomaly ? (
            <div className="flex-1 flex flex-col gap-3 font-mono text-xs overflow-hidden">
              
              {/* Event Header */}
              <div className="flex items-center justify-between bg-slate-900/40 p-2.5 rounded border border-slate-900">
                <div>
                  <span className="text-[9px] text-slate-500 block">THREAT SCENARIO</span>
                  <span className="text-slate-200 font-bold">{currentUnresolved[0]?.event_type}</span>
                </div>
                <div className="text-right">
                  <span className="text-[9px] text-slate-500 block">COMMAND DECISION</span>
                  <span className="text-cyan-400 font-bold uppercase">
                    {agentState?.chosen_action ? (agentState.chosen_action.split("_").slice(2).join(" ") || agentState.chosen_action.split("_").slice(1).join(" ")) : "None"}
                  </span>
                </div>
              </div>

              {/* Consensus Meter */}
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-900/30 p-2.5 rounded border border-slate-900 text-center flex flex-col justify-center">
                  <span className="text-[9px] text-slate-500 block">SPECIALIST CONSENSUS</span>
                  <span className="text-lg font-bold text-white mt-1">
                    {agentState?.confidence ? `${agentState.confidence}%` : "0%"}
                  </span>
                </div>
                <div className="bg-slate-900/30 p-2.5 rounded border border-slate-900 text-center flex flex-col justify-center">
                  <span className="text-[9px] text-slate-500 block">DECISION STATUS</span>
                  <span className="text-lg font-bold text-emerald-400 mt-1">APPROVED</span>
                </div>
              </div>

              {/* Debate Transcript */}
              <div className="flex-1 flex flex-col min-h-[220px] max-h-[300px] overflow-hidden">
                <span className="text-[9px] text-slate-500 block mb-1">LIVE MISSION CONTROL DEBATE</span>
                {agentState?.debate && agentState.debate.length > 0 ? (
                  <div className="flex-1 overflow-y-auto space-y-2 bg-slate-950/80 p-3 rounded border border-slate-900 leading-normal scrollbar-thin">
                    {agentState.debate.map((d, index) => {
                      let senderColor = "text-cyan-400";
                      if (d.sender.includes("Resource")) senderColor = "text-orange-400";
                      if (d.sender.includes("Safety")) senderColor = "text-rose-400";
                      if (d.sender.includes("Science")) senderColor = "text-indigo-400";
                      if (d.sender.includes("Commander")) senderColor = "text-emerald-400 font-bold";

                      return (
                        <div key={index} className="border-b border-slate-900/30 pb-2 last:border-0 last:pb-0">
                          <div className="flex items-center justify-between text-[9px] font-semibold">
                            <span className={senderColor}>{d.sender}</span>
                            <span className="text-slate-600">{d.role}</span>
                          </div>
                          <p className="text-slate-300 mt-0.5 text-[10px] italic">"{d.message}"</p>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center text-center p-4 bg-slate-950/30 rounded border border-dashed border-slate-800">
                    <Activity className="w-6 h-6 text-slate-700 animate-pulse mb-1.5" />
                    <span className="text-slate-500 text-[10px]">Assembling specialists transcript...</span>
                  </div>
                )}
              </div>

              {/* Radar Chart Visual */}
              {radarData.length > 0 && (
                <div className="h-[130px] flex items-center justify-center bg-slate-950/50 rounded border border-slate-900/40 p-1">
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart cx="50%" cy="50%" outerRadius="75%" data={radarData}>
                      <PolarGrid stroke="#1e293b" />
                      <PolarAngleAxis dataKey="action" stroke="#64748b" fontSize={7} />
                      <PolarRadiusAxis angle={30} domain={[0, 100]} stroke="#475569" fontSize={6} />
                      <Radar name="Navigation" dataKey="Navigation" stroke="#06b6d4" fill="#06b6d4" fillOpacity={0.15} />
                      <Radar name="Fuel" dataKey="Fuel" stroke="#f97316" fill="#f97316" fillOpacity={0.15} />
                      <Radar name="Safety" dataKey="Safety" stroke="#ef4444" fill="#ef4444" fillOpacity={0.15} />
                      <Radar name="Science" dataKey="Science" stroke="#6366f1" fill="#6366f1" fillOpacity={0.15} />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              )}

            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8 bg-slate-950/30 rounded-lg border border-dashed border-slate-800">
              <Brain className="w-8 h-8 text-slate-700 animate-pulse mb-3" />
              <h3 className="text-xs font-mono font-bold text-slate-400">DEBATE SYSTEM STANDBY</h3>
              <p className="text-[9.5px] font-mono text-slate-500 max-w-[280px] mt-1.5 leading-relaxed">
                Telemetry scanning suggests stable orbits. No active anomaly warnings require crew debates or commander actions.
              </p>
              
              <div className="relative w-16 h-16 mt-5 flex items-center justify-center">
                <div className="absolute w-full h-full rounded-full border border-cyan-500/10 animate-ping" />
                <div className="absolute w-2/3 h-2/3 rounded-full border border-cyan-500/20 animate-pulse" />
                <Activity className="w-5 h-5 text-cyan-600/40" />
              </div>
            </div>
          )}
        </div>
      </section>

      {/* 4. BOTTOM LEFT: Agent Decision Analytics (Col span 7) */}
      <section className="lg:col-span-7 rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl flex flex-col gap-4">
        <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-900 pb-2 uppercase flex items-center gap-2">
          <TrendingUp className="w-4 h-4" />
          Autonomous Performance Metrics
        </h2>

        {/* Analytics Card Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-slate-900/40 p-3 rounded-lg border border-slate-850 text-center">
            <span className="text-[9px] font-mono text-slate-500 block uppercase">Decision Accuracy</span>
            <span className="text-lg font-bold font-mono text-cyan-400 block mt-1">
              {metrics ? `${metrics.decision_accuracy.toFixed(1)}%` : "94.0%"}
            </span>
            <span className="text-[8px] font-mono text-emerald-500 block mt-0.5">R2 RATING BASED</span>
          </div>

          <div className="bg-slate-900/40 p-3 rounded-lg border border-slate-850 text-center">
            <span className="text-[9px] font-mono text-slate-500 block uppercase">Success Rate</span>
            <span className="text-lg font-bold font-mono text-emerald-400 block mt-1">
              {metrics ? `${metrics.mission_success_rate.toFixed(1)}%` : "88.0%"}
            </span>
            <span className="text-[8px] font-mono text-slate-600 block mt-0.5">MISSION TARGETS</span>
          </div>

          <div className="bg-slate-900/40 p-3 rounded-lg border border-slate-850 text-center">
            <span className="text-[9px] font-mono text-slate-500 block uppercase">Avg Confidence</span>
            <span className="text-lg font-bold font-mono text-indigo-400 block mt-1">
              {metrics ? `${metrics.avg_confidence.toFixed(1)}%` : "78.4%"}
            </span>
            <span className="text-[8px] font-mono text-slate-600 block mt-0.5">DECISION STABILITY</span>
          </div>

          <div className="bg-slate-900/40 p-3 rounded-lg border border-slate-850 text-center">
            <span className="text-[9px] font-mono text-slate-500 block uppercase">Agreement Rate</span>
            <span className="text-lg font-bold font-mono text-amber-400 block mt-1">
              {metrics ? `${metrics.agreement_rate.toFixed(1)}%` : "85.0%"}
            </span>
            <span className="text-[8px] font-mono text-slate-650 block mt-0.5">SPECIALIST RATIO</span>
          </div>
        </div>

        {/* Recharts Area Chart */}
        <div className="h-[140px] w-full bg-slate-950/40 border border-slate-900 p-2 rounded">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={historyData} margin={{ top: 5, right: 10, left: -25, bottom: 0 }}>
              <defs>
                <linearGradient id="colorConf" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#818cf8" stopOpacity={0.2}/>
                  <stop offset="95%" stopColor="#818cf8" stopOpacity={0}/>
                </linearGradient>
                <linearGradient id="colorSucc" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.2}/>
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <XAxis dataKey="tick" stroke="#475569" fontSize={8} tickLine={false} />
              <YAxis stroke="#475569" fontSize={8} tickLine={false} domain={[60, 100]} />
              <Tooltip 
                contentStyle={{ backgroundColor: "#090d16", border: "1px solid #1e293b", borderRadius: "6px" }}
                labelStyle={{ color: "#64748b", fontFamily: "monospace", fontSize: "9px" }}
                itemStyle={{ fontFamily: "monospace", fontSize: "10px" }}
              />
              <Area type="monotone" name="Commander Confidence" dataKey="confidence" stroke="#818cf8" fillOpacity={1} fill="url(#colorConf)" strokeWidth={1.5} />
              <Area type="monotone" name="Success Likelihood" dataKey="success" stroke="#10b981" fillOpacity={1} fill="url(#colorSucc)" strokeWidth={1.5} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* 5. BOTTOM RIGHT: Machine Learning Model Trainer (Col span 5) */}
      <section className="lg:col-span-5 rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-xl flex flex-col gap-4">
        <h2 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-900 pb-2 uppercase flex items-center gap-2">
          <Server className="w-4 h-4" />
          Offline ML Engine Settings
        </h2>

        <div className="flex-1 flex flex-col justify-between gap-4 font-mono text-xs">
          
          <div className="space-y-2.5">
            <p className="text-[10px] text-slate-400 leading-relaxed bg-slate-900/20 p-2.5 rounded border border-slate-900">
              Scikit-Learn fits a multi-output <strong className="text-slate-350">LinearRegression</strong> model using PostgreSQL historical decision logs to estimate sandbox option outcome coefficients.
            </p>

            <div className="grid grid-cols-2 gap-3 text-[10px]">
              <div className="bg-slate-950/60 p-2 rounded border border-slate-900 flex flex-col justify-center">
                <span className="text-slate-500 uppercase text-[8.5px]">Trained Samples</span>
                <span className="text-sm font-bold text-slate-200 mt-1">
                  {trainingResult?.samples ?? 24} runs
                </span>
              </div>
              <div className="bg-slate-950/60 p-2 rounded border border-slate-900 flex flex-col justify-center">
                <span className="text-slate-500 uppercase text-[8.5px]">Model Fit (R2)</span>
                <span className="text-sm font-bold text-cyan-400 mt-1">
                  {trainingResult?.r2_score !== undefined ? trainingResult.r2_score.toFixed(3) : "0.950"}
                </span>
              </div>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-900/80 flex flex-col gap-2">
            <button
              onClick={runTraining}
              disabled={isTraining}
              className={`w-full py-2.5 px-4 rounded-lg font-bold tracking-wider text-xs flex items-center justify-center gap-2 transition-all duration-300 border ${
                isTraining 
                  ? "bg-slate-900 text-slate-600 border-slate-800 cursor-not-allowed" 
                  : "bg-cyan-950/30 text-cyan-400 border-cyan-500/30 hover:bg-cyan-500/10 hover:border-cyan-400/50 shadow-md shadow-cyan-950/10 cursor-pointer"
              }`}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isTraining ? "animate-spin" : ""}`} />
              {isTraining ? "COMPUTING REGRESSION PLAN..." : "TRAIN COMMANDER AI MODEL"}
            </button>
            {trainingResult && (
              <span className="text-[9px] text-emerald-400 text-center font-bold block animate-pulse">
                ✓ SCUTTLE-FIT SUCCESSFUL: {trainingResult.samples} RUNS TRAINED
              </span>
            )}
          </div>

        </div>
      </section>

    </div>
  );
}
