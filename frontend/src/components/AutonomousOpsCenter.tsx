"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Compass,
  Zap,
  Play,
  RotateCcw,
  Sliders,
  Activity,
  AlertTriangle,
  Brain,
  Layers,
  Clock,
  CheckCircle,
  XCircle,
  HelpCircle,
  Database,
  Shield,
  Gauge,
  Terminal,
  BarChart2,
  GitPullRequest,
  Tv
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  BarChart,
  Bar
} from "recharts";

// TypeScript Interfaces for Ops Center
import AgentVoicePanel from "./AgentVoicePanel";
interface RouteStage {
  stage: string;
  checkpoint: string;
  burn_profile: string;
}

interface ResourcePlan {
  estimated_fuel_needed: number;
  estimated_power_drain: number;
  oxygen_reserve_ticks: number;
  efficiency_target: number;
}

interface Hazard {
  hazard: string;
  probability: number;
  severity: string;
}

interface RiskAssessment {
  hazards: Hazard[];
  average_risk_rating: number;
  critical_path_integrity: string;
}

interface MissionPlan {
  id: number;
  destination: string;
  payload: string;
  duration: number;
  available_fuel: number;
  science_objectives: string[];
  constraints: string[];
  route_plan: RouteStage[];
  resource_plan: ResourcePlan;
  risk_assessment: RiskAssessment;
  success_forecast: number;
}

interface TimelineItem {
  id?: number;
  time_offset: string;
  phase: string;
  event_name: string;
  description: string;
  status: string; // PENDING, COMPLETED, ACTIVE
}

interface StrategyComparison {
  strategy_name: string;
  success_probability: number;
  projected_fuel: number;
  projected_power: number;
  projected_risk: number;
  description: string;
}

interface ForecastHorizon {
  horizon: string;
  projected_success: number;
  projected_fuel: number;
  projected_power: number;
  projected_risk: number;
  predicted_failures: string[];
}

interface AutonomyTrace {
  id: number;
  timestamp: string;
  event_type: string;
  chosen_action: string;
  confidence_score: number;
  expected_outcome: { risk_reduction?: number; success_delta?: number; [key: string]: any };
  actual_outcome: { risk_reduction?: number; success_delta?: number; [key: string]: any };
  autonomy_level: number;
  reasoning: string;
  utility_scores: Record<string, number>;
}

interface ConsensusRecord {
  id?: number;
  timestamp: string;
  decision_key: string;
  nav_recommendation: string;
  fuel_recommendation: string;
  safety_recommendation: string;
  science_recommendation: string;
  prediction_rating: number;
  learning_rating: number;
  consensus_score: number;
  commander_override: boolean;
}

interface AutonomyIndex {
  compound_index: number;
  metrics: {
    decision_accuracy: number;
    prediction_accuracy: number;
    recovery_effectiveness: number;
    learning_efficiency: number;
    resource_efficiency: number;
  };
}

interface BenchmarkResults {
  trials: number;
  aggressive: {
    success_rate: number;
    avg_fuel_remaining: number;
    fuel_distribution: number[];
  };
  conservative: {
    success_rate: number;
    avg_fuel_remaining: number;
    fuel_distribution: number[];
  };
}

// Subsystem health diagnostic helper
interface SubsystemHealth {
  name: string;
  health: number;
  status: string;
}

export default function AutonomousOpsCenter() {
  // Websocket states (Synced with backend simulator via WS)
  const [telemetry, setTelemetry] = useState<any>(null);
  const [simulatorState, setSimulatorState] = useState<string>("Idle");
  const [activeEvents, setActiveEvents] = useState<any[]>([]);
  const [wsStatus, setWsStatus] = useState<string>("disconnected");

  // REST endpoints query states
  const [latestPlan, setLatestPlan] = useState<MissionPlan | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [strategies, setStrategies] = useState<StrategyComparison[]>([]);
  const [forecasts, setForecasts] = useState<ForecastHorizon[]>([]);
  const [autonomyTraces, setAutonomyTraces] = useState<AutonomyTrace[]>([]);
  const [consensusRecords, setConsensusRecords] = useState<ConsensusRecord[]>([]);
  const [autonomyIndex, setAutonomyIndex] = useState<AutonomyIndex | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkResults | null>(null);

  // Forms states for Plan Generator
  const [destination, setDestination] = useState<string>("Mars");
  const [payload, setPayload] = useState<string>("Science Lab Payload v5");
  const [duration, setDuration] = useState<number>(720);
  const [availableFuel, setAvailableFuel] = useState<number>(100);
  const [scienceObjs, setScienceObjs] = useState<string[]>([
    "Measure Gamma Burst",
    "Assess Subsurface Ice"
  ]);
  const [constraints, setConstraints] = useState<string[]>(["Solar Storms"]);

  // New Autonomous Trajectory Planner states
  const [destinationsList, setDestinationsList] = useState<any[]>([]);
  const [origin, setOrigin] = useState<string>("Earth");
  const [payloadMass, setPayloadMass] = useState<number>(10000);
  const [missionType, setMissionType] = useState<string>("Science Deep Probe");
  const [trajectoryOutputs, setTrajectoryOutputs] = useState<any>(null);
  const [trajectoryActiveEvents, setTrajectoryActiveEvents] = useState<string[]>([]);

  // Lab Config States
  const [difficulty, setDifficulty] = useState<string>("Normal");
  const [eventFrequency, setEventFrequency] = useState<number>(30);

  // Demo showcase states
  const [demoLogs, setDemoLogs] = useState<string[]>([]);
  const [isDemoRunning, setIsDemoRunning] = useState<boolean>(false);

  // UI state variables
  const [loadingPlan, setLoadingPlan] = useState<boolean>(false);
  const [benchmarking, setBenchmarking] = useState<boolean>(false);
  const [overrideInProgress, setOverrideInProgress] = useState<string | null>(null);

  const demoLogContainerRef = useRef<HTMLDivElement>(null);

  // Setup WebSocket connection locally
  useEffect(() => {
    setWsStatus("connecting");
    const ws = new WebSocket("ws://127.0.0.1:8000/ws");

    ws.onopen = () => {
      setWsStatus("connected");
      console.log("[Ops Center WS] Connected");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "INIT" || data.type === "TELEMETRY") {
          setTelemetry(data.telemetry);
          if (data.mission) {
            setSimulatorState(data.mission.state);
          }
          if (data.active_events) {
            setActiveEvents(data.active_events);
          }
        } else if (data.type === "EVENT") {
          // If demo logs or simulator warnings arrive, print to active demo panel
          setDemoLogs((prev) => [...prev, data.message]);
        } else if (data.type === "NEW_EVENT") {
          setActiveEvents((prev) => {
            if (prev.some((e) => e.id === data.event.id)) return prev;
            return [...prev, data.event];
          });
        } else if (data.type === "EVENT_RESOLVED") {
          setActiveEvents((prev) => prev.filter((e) => e.id !== data.event_id));
        } else if (data.type === "PHASE_UPDATED") {
          setDemoLogs((prev) => [...prev, `[PHASE CHANGE] ${data.message}`]);
        } else if (data.type === "MISSION_COMPLETED") {
          setIsDemoRunning(false);
          setDemoLogs((prev) => [...prev, `[SYSTEM COMPLETE] Demo Mars Mission trajectory finished.`]);
        } else if (data.type === "TRAJECTORY_UPDATE") {
          if (data.data.inputs) {
            setDestination(data.data.inputs.destination);
            setPayloadMass(data.data.inputs.payload_mass);
            setMissionType(data.data.inputs.mission_type || "Science Deep Probe");
            setTrajectoryActiveEvents(data.data.inputs.active_events || []);
          }
          if (data.data.outputs) {
            setTrajectoryOutputs(data.data.outputs);
          }
        }
      } catch (err) {
        console.error("[Ops Center WS] Parse Error:", err);
      }
    };

    ws.onclose = () => {
      setWsStatus("disconnected");
      console.log("[Ops Center WS] Disconnected");
    };

    return () => {
      ws.close();
    };
  }, []);

  // Fetch telemetry independent updates in parallel
  const fetchAllData = useCallback(async () => {
    const fetchers = [
      // 1. Latest Trajectory Plan
      fetch("http://127.0.0.1:8000/api/phase5/mission/plan/latest")
        .then(res => res.ok ? res.json().then(setLatestPlan) : null)
        .catch(e => console.error("Error fetching plan:", e)),

      // 2. Timeline Checkpoints
      fetch("http://127.0.0.1:8000/api/phase5/mission/timeline")
        .then(res => res.ok ? res.json().then(setTimeline) : null)
        .catch(e => console.error("Error fetching timeline:", e)),

      // 3. Strategy Scorecards
      fetch("http://127.0.0.1:8000/api/phase5/mission/strategies/compare")
        .then(res => res.ok ? res.json().then(setStrategies) : null)
        .catch(e => console.error("Error fetching strategies:", e)),

      // 4. Horizon Forecasts
      fetch("http://127.0.0.1:8000/api/phase5/mission/forecasts")
        .then(res => res.ok ? res.json().then(setForecasts) : null)
        .catch(e => console.error("Error fetching forecasts:", e)),

      // 5. Autonomy Traces
      fetch("http://127.0.0.1:8000/api/phase5/mission/explainable-autonomy")
        .then(res => res.ok ? res.json().then(setAutonomyTraces) : null)
        .catch(e => console.error("Error fetching traces:", e)),

      // 6. Agent Consensus Records
      fetch("http://127.0.0.1:8000/api/phase5/mission/consensus")
        .then(res => res.ok ? res.json().then(setConsensusRecords) : null)
        .catch(e => console.error("Error fetching consensus:", e)),

      // 7. Autonomy Performance Metrics index
      fetch("http://127.0.0.1:8000/api/phase5/mission/autonomy-index")
        .then(res => res.ok ? res.json().then(setAutonomyIndex) : null)
        .catch(e => console.error("Error fetching autonomy index:", e))
    ];

    await Promise.allSettled(fetchers);
  }, []);

  // Poll for live metrics updates every 4 seconds to sync simulation state
  useEffect(() => {
    fetchAllData();
    const timer = setInterval(() => {
      fetchAllData();
    }, 4000);
    return () => clearInterval(timer);
  }, [fetchAllData]);

  // Scroll to bottom of demo log console when logs append
  useEffect(() => {
    if (demoLogContainerRef.current) {
      demoLogContainerRef.current.scrollTop = demoLogContainerRef.current.scrollHeight;
    }
  }, [demoLogs]);

  // --- ACTIONS ---

  // Generate Mission Plan Trajectory
  // Load Destinations and initial trajectory on mount
  useEffect(() => {
    const initData = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/api/destinations");
        if (res.ok) {
          const list = await res.json();
          setDestinationsList(list);
          if (list.length > 0) {
            setDestination(list[0].name);
            
            // Retrieve current active state if preset in Redis
            const currRes = await fetch("http://127.0.0.1:8000/api/trajectory/current");
            if (currRes.ok) {
              const currData = await currRes.json();
              if (currData.inputs) {
                setDestination(currData.inputs.destination);
                setPayloadMass(currData.inputs.payload_mass);
                setMissionType(currData.inputs.mission_type || "Science Deep Probe");
                setTrajectoryActiveEvents(currData.inputs.active_events || []);
              }
              if (currData.outputs) {
                setTrajectoryOutputs(currData.outputs);
              }
            } else {
              // Calculate default
              const calcRes = await fetch("http://127.0.0.1:8000/api/trajectory/calculate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  origin: "Earth",
                  destination: list[0].name,
                  payload_mass: 10000,
                  mission_type: "Science Deep Probe"
                })
              });
              if (calcRes.ok) {
                const calcData = await calcRes.json();
                if (calcData.outputs) setTrajectoryOutputs(calcData.outputs);
              }
            }
          }
        }
      } catch (err) {
        console.error("Failed to load destinations:", err);
      }
    };
    initData();
  }, []);

  const handleCalculateTrajectory = async (e?: React.FormEvent, inputsOverride?: any) => {
    if (e) e.preventDefault();
    setLoadingPlan(true);
    const targetInputs = inputsOverride || {
      origin,
      destination,
      payload_mass: payloadMass,
      mission_type: missionType
    };
    try {
      const res = await fetch("http://127.0.0.1:8000/api/trajectory/calculate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(targetInputs)
      });
      if (res.ok) {
        const data = await res.json();
        if (data.outputs) {
          setTrajectoryOutputs(data.outputs);
        }
      }
    } catch (err) {
      console.error("Failed to calculate trajectory:", err);
    } finally {
      setLoadingPlan(false);
    }
  };

  const handleDestinationChange = async (newDest: string) => {
    const targetInputs = {
      origin,
      destination: newDest,
      payload_mass: payloadMass,
      mission_type: missionType
    };
    // Perform immediate trajectory calculation
    await handleCalculateTrajectory(undefined, targetInputs);
  };

  // Launch Trajectory Simulation
  const handleStartMissionOps = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/phase5/mission/start", {
        method: "POST"
      });
      if (res.ok) {
        setDemoLogs((prev) => [...prev, `[INIT] Deploying trajectory parameters. Countdown initiated.`]);
        fetchAllData();
      }
    } catch (err) {
      console.error("Failed to start mission ops:", err);
    }
  };

  // Override decision toggle
  const handleCommanderOverride = async (decisionKey: string, currentVal: boolean) => {
    setOverrideInProgress(decisionKey);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/phase5/mission/override", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision_key: decisionKey,
          override: !currentVal
        })
      });
      if (res.ok) {
        setDemoLogs((prev) => [...prev, `[COMMAND OVERRIDE] Commander manually ${!currentVal ? "AUTHORIZED" : "REVOKED"} decision protocol override: ${decisionKey}`]);
        fetchAllData();
      }
    } catch (err) {
      console.error("Override action failed:", err);
    } finally {
      setOverrideInProgress(null);
    }
  };

  // Inject Custom Anomaly
  const handleInjectContingency = async (eventType: string) => {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/phase5/mission/contingency/inject", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_type: eventType })
      });
      if (res.ok) {
        setDemoLogs((prev) => [...prev, `[CONTEST INJECT] Telemetry anomaly manual injection: ${eventType}`]);
        fetchAllData();
      }
    } catch (err) {
      console.error("Anomaly injection failed:", err);
    }
  };

  // Adjust Lab Config parameters
  const handleLabConfigSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch("http://127.0.0.1:8000/api/phase5/mission/lab/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          difficulty,
          event_frequency: eventFrequency
        })
      });
      if (res.ok) {
        setDemoLogs((prev) => [...prev, `[LAB CONFIG] Stress metrics updated: ${difficulty} at check rate ${eventFrequency}s.`]);
      }
    } catch (err) {
      console.error("Lab configuration update failed:", err);
    }
  };

  // Run Benchmark simulation
  const handleRunBenchmark = async () => {
    setBenchmarking(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/phase5/mission/research/benchmark", {
        method: "POST"
      });
      if (res.ok) {
        const results = await res.json();
        setBenchmark(results);
        setDemoLogs((prev) => [...prev, `[RESEARCH LAB] Side-by-side strategy trials completed successfully.`]);
      }
    } catch (err) {
      console.error("Benchmark failed:", err);
    } finally {
      setBenchmarking(false);
    }
  };

  // One-Click Showcase Demo Mode trigger
  const handleStartShowcaseDemo = async () => {
    setIsDemoRunning(true);
    setDemoLogs([]);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/phase5/mission/demo/start", {
        method: "POST"
      });
      if (res.ok) {
        setDemoLogs((prev) => [
          ...prev,
          `[SHOWCASE] Launching automated judge Mars showcase demonstration sequence.`,
          `[SHOWCASE] Monitoring real-time anomaly injections and AI self-recovery reactions...`
        ]);
      }
    } catch (err) {
      console.error("Failed to start showcase:", err);
      setIsDemoRunning(false);
    }
  };

  const toggleScienceObjective = (obj: string) => {
    setScienceObjs((prev) =>
      prev.includes(obj) ? prev.filter((o) => o !== obj) : [...prev, obj]
    );
  };

  const toggleConstraint = (con: string) => {
    setConstraints((prev) =>
      prev.includes(con) ? prev.filter((c) => c !== con) : [...prev, con]
    );
  };

  // Map progress to active state machine checkpoints
  const lifecyclePhases = [
    "Pre-Launch",
    "Launch",
    "Orbit Insertion",
    "Cruise Phase",
    "Course Correction",
    "Scientific Ops",
    "Approach Phase",
    "Landing / Deployment",
    "Completed"
  ];

  const currentPhaseIndex = lifecyclePhases.indexOf(
    telemetry?.mission_progress === 100.0 ? "Completed" : simulatorState
  );

  // Derive subsystem status lists
  const subsystems: SubsystemHealth[] = [
    { name: "Propulsion", health: telemetry?.subsystems?.propulsion?.health ?? 100, status: telemetry?.subsystems?.propulsion?.status ?? "Nominal" },
    { name: "Power Grid", health: telemetry?.subsystems?.power?.health ?? 100, status: telemetry?.subsystems?.power?.status ?? "Nominal" },
    { name: "Thermal System", health: telemetry?.subsystems?.thermal?.health ?? 100, status: telemetry?.subsystems?.thermal?.status ?? "Nominal" },
    { name: "Communication", health: telemetry?.subsystems?.communication?.health ?? 100, status: telemetry?.subsystems?.communication?.status ?? "Nominal" },
    { name: "Life Support", health: telemetry?.subsystems?.life_support?.health ?? 100, status: telemetry?.subsystems?.life_support?.status ?? "Nominal" }
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 text-slate-100 font-mono text-xs">
      
      {/* 1. COMPREHENSIVE CRITICAL WARNING BAR */}
      {activeEvents.length > 0 && (
        <div className="lg:col-span-12 p-3 bg-rose-950/60 border border-rose-500/40 rounded-xl flex items-center justify-between shadow-xl shadow-rose-950/20 animate-pulse">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-400 animate-bounce" />
            <div>
              <span className="font-bold text-rose-300 uppercase tracking-widest text-xs">
                Emergency Alert: Autonomous Recovery Active
              </span>
              <p className="text-[10px] text-rose-400 mt-0.5 leading-snug">
                Compounding mission hazard risk index has exceeded limits. Command AI executing backup safety protocols.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {activeEvents.map((ev) => (
              <span key={ev.id} className="px-2.5 py-1 bg-rose-900 border border-rose-500 text-white font-bold rounded uppercase text-[10px]">
                {ev.event_type}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 2. LEFT GRID: MISSION TRAJECTORY PLANNER & CONFIG DECK */}
      <div className="lg:col-span-4 flex flex-col gap-4">
        
        {/* Trajectory Planner Card */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md">
          <h2 className="text-xs font-bold tracking-widest text-cyan-400 border-b border-slate-800 pb-2 mb-3 uppercase flex items-center gap-2">
            <GitPullRequest className="w-4 h-4 text-cyan-400" />
            Trajectory Planner
          </h2>

          <form onSubmit={handleCalculateTrajectory} className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-slate-500 block mb-1 text-[10px] uppercase font-bold">Origin</label>
                <input
                  type="text"
                  value={origin}
                  readOnly
                  className="w-full bg-slate-900 border border-slate-850 p-2 rounded text-slate-400 outline-none cursor-not-allowed text-xs font-semibold"
                />
              </div>
              <div>
                <label className="text-slate-500 block mb-1 text-[10px] uppercase font-bold">Destination</label>
                <select
                  value={destination}
                  onChange={(e) => {
                    const val = e.target.value;
                    setDestination(val);
                    handleDestinationChange(val);
                  }}
                  className="w-full bg-slate-900 border border-slate-850 p-2 rounded text-slate-200 outline-none focus:border-cyan-500/50 text-xs font-semibold"
                >
                  {destinationsList.map((d) => (
                    <option key={d.name} value={d.name}>
                      {d.name} ({d.avg_distance_km.toLocaleString()} km)
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-slate-500 block mb-1 text-[10px] uppercase font-bold">Payload Mass (kg)</label>
                <input
                  type="number"
                  value={payloadMass}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value) || 0;
                    setPayloadMass(val);
                    handleCalculateTrajectory(undefined, {
                      origin,
                      destination,
                      payload_mass: val,
                      mission_type: missionType
                    });
                  }}
                  className="w-full bg-slate-900 border border-slate-850 p-2 rounded text-slate-200 outline-none focus:border-cyan-500/50 text-xs font-semibold"
                />
              </div>
              <div>
                <label className="text-slate-500 block mb-1 text-[10px] uppercase font-bold">Mission Type</label>
                <select
                  value={missionType}
                  onChange={(e) => {
                    const val = e.target.value;
                    setMissionType(val);
                    handleCalculateTrajectory(undefined, {
                      origin,
                      destination,
                      payload_mass: payloadMass,
                      mission_type: val
                    });
                  }}
                  className="w-full bg-slate-900 border border-slate-850 p-2 rounded text-slate-200 outline-none focus:border-cyan-500/50 text-xs font-semibold"
                >
                  <option value="Science Deep Probe">Science Deep Probe</option>
                  <option value="Heavy Cargo Transport">Heavy Cargo Transport</option>
                  <option value="Colonization Habitat">Colonization Habitat</option>
                  <option value="Satellite Deployment">Satellite Deployment</option>
                </select>
              </div>
            </div>

            <button
              type="submit"
              disabled={loadingPlan}
              className="w-full mt-2 py-2 bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white font-bold tracking-widest rounded-lg shadow-lg shadow-cyan-900/20 disabled:opacity-40 uppercase text-[10px]"
            >
              {loadingPlan ? "Recalculating Trajectory..." : "Calculate Trajectory"}
            </button>
          </form>
        </div>

        {/* Trajectory Assessment Outputs Card */}
        {trajectoryOutputs && (
          <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md">
            <h3 className="text-[11px] font-bold text-cyan-400 uppercase tracking-widest mb-3 flex items-center justify-between border-b border-slate-900 pb-2">
              <span>Trajectory Assessment</span>
            </h3>
            
            <div className="space-y-2 text-[10px]">
              <div className="flex justify-between items-center bg-slate-900/40 p-1.5 rounded border border-slate-900/60">
                <span className="text-slate-500 uppercase font-semibold">Distance:</span>
                <span className="font-bold text-slate-200">{(trajectoryOutputs.distance_km || 0).toLocaleString(undefined, {maximumFractionDigits: 0})} km</span>
              </div>
              <div className="flex justify-between items-center bg-slate-900/40 p-1.5 rounded border border-slate-900/60">
                <span className="text-slate-500 uppercase font-semibold">Estimated Travel Time:</span>
                <span className="font-bold text-slate-200">{(trajectoryOutputs.travel_time_h || 0).toLocaleString(undefined, {maximumFractionDigits: 1})} hours</span>
              </div>
              <div className="flex justify-between items-center bg-slate-900/40 p-1.5 rounded border border-slate-900/60">
                <span className="text-slate-500 uppercase font-semibold">Fuel Required:</span>
                <span className="font-bold text-slate-200">{(trajectoryOutputs.fuel_required_kg || 0).toLocaleString(undefined, {maximumFractionDigits: 1})} kg</span>
              </div>
              <div className="flex justify-between items-center bg-slate-900/40 p-1.5 rounded border border-slate-900/60">
                <span className="text-slate-500 uppercase font-semibold">Mission Feasibility:</span>
                <span className={`px-2 py-0.5 rounded text-[8px] font-bold uppercase ${trajectoryOutputs.feasibility ? "bg-emerald-950 border border-emerald-500 text-emerald-400" : "bg-rose-950 border border-rose-500 text-rose-400"}`}>
                  {trajectoryOutputs.feasibility ? "FEASIBLE" : "NOT FEASIBLE"}
                </span>
              </div>
              <div className="flex justify-between items-center bg-slate-900/40 p-1.5 rounded border border-slate-900/60">
                <span className="text-slate-500 uppercase font-semibold">Estimated Arrival Time:</span>
                <span className="font-bold text-cyan-400">
                  {new Date(trajectoryOutputs.arrival_time).toLocaleString("en-IN", {
                    timeZone: "Asia/Kolkata",
                    dateStyle: "short",
                    timeStyle: "short"
                  })} (IST)
                </span>
              </div>
            </div>


          </div>
        )
}

        {/* Interactive Controls & Showcase Demo Mode */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md flex flex-col gap-3">
          <h2 className="text-xs font-bold tracking-widest text-cyan-400 border-b border-slate-800 pb-2 uppercase flex items-center gap-2">
            <Tv className="w-4 h-4 text-cyan-400" />
            Control & Demo Center
          </h2>

          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={handleStartMissionOps}
              className="flex items-center justify-center gap-1.5 py-2.5 border border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 font-bold rounded-lg transition-all"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              DEPLOY OPS
            </button>
            <button
              onClick={handleStartShowcaseDemo}
              disabled={isDemoRunning}
              className="flex items-center justify-center gap-1.5 py-2.5 border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 font-bold rounded-lg transition-all disabled:opacity-40"
            >
              <Tv className="w-3.5 h-3.5" />
              SHOWCASE RUN
            </button>
          </div>
        </div>

        <AgentVoicePanel />

      </div>

      {/* 3. CENTER GRID: STEPPED LIFECYCLE, WS LOGS, AND FORECAST CHART */}
      <div className="lg:col-span-5 flex flex-col gap-4">
        
        {/* Stepped Mission Lifecycle */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md">
          <h2 className="text-xs font-bold tracking-widest text-cyan-400 border-b border-slate-800 pb-2 mb-3 uppercase flex items-center gap-2">
            <Layers className="w-4 h-4 text-cyan-400" />
            Autonomous Mission Lifecycle (9 Stages)
          </h2>
          
          <div className="grid grid-cols-3 gap-2 py-1">
            {lifecyclePhases.map((phase, idx) => {
              const isPassed = idx < currentPhaseIndex;
              const isActive = idx === currentPhaseIndex;
              
              let bgClass = "bg-slate-900 border-slate-900 text-slate-500";
              if (isActive) bgClass = "bg-cyan-950 border-cyan-500/40 text-cyan-400 font-bold shadow-md shadow-cyan-500/5 animate-pulse border";
              if (isPassed) bgClass = "bg-slate-900/60 border-slate-850 text-slate-400 line-through border";

              return (
                <div key={phase} className={`p-1.5 rounded-lg flex flex-col items-center justify-center text-center font-mono ${bgClass}`}>
                  <span className="text-[8px] uppercase tracking-wider block font-bold">Phase 0{idx+1}</span>
                  <span className="text-[9px] mt-0.5 truncate max-w-full" title={phase}>{phase}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Real-time WebSocket / Demo Showcase Live Command stream */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md flex-1 flex flex-col min-h-[180px]">
          <h2 className="text-xs font-bold tracking-widest text-cyan-400 border-b border-slate-800 pb-2 mb-2 uppercase flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-cyan-400" />
              Live System Broadcast Stream
            </span>
            <span className={`w-2 h-2 rounded-full shadow-md ${wsStatus === "connected" ? "bg-emerald-500 shadow-emerald-500/40" : "bg-rose-500 animate-pulse"}`} />
          </h2>

          <div ref={demoLogContainerRef} className="flex-1 overflow-y-auto max-h-[220px] p-3 rounded-lg border border-slate-900 bg-slate-950 font-mono text-[9px] text-cyan-500 leading-normal space-y-1">
            {demoLogs.length === 0 ? (
              <p className="text-slate-600 italic">Awaiting showcase activation telemetry feeds...</p>
            ) : (
              demoLogs.map((log, index) => {
                const isWarn = log.includes("[WARNING]") || log.includes("Warning");
                const isErr = log.includes("[ERROR]");
                const isDemo = log.includes("[DEMO]");
                let textClass = "text-cyan-500/80";
                if (isWarn) textClass = "text-amber-400 font-bold";
                if (isErr) textClass = "text-rose-500 font-extrabold";
                if (isDemo && !isWarn && !isErr) textClass = "text-emerald-400 font-medium";

                return (
                  <div key={index} className={`flex items-start gap-1 ${textClass}`}>
                    <span>&gt;&gt;</span>
                    <span>{log}</span>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Recharts Projections Chart */}
        {forecasts.length > 0 && (
          <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md">
            <h2 className="text-xs font-bold tracking-widest text-cyan-400 border-b border-slate-800 pb-2 mb-3 uppercase flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-cyan-400" />
              Resource Projections (1h - 7d Horizons)
            </h2>
            <div className="h-32">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={forecasts} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                  <XAxis dataKey="horizon" stroke="#475569" fontSize={10} className="font-mono" />
                  <YAxis stroke="#475569" fontSize={10} className="font-mono" />
                  <Tooltip contentStyle={{ backgroundColor: "#090d16", border: "1px solid #1e293b", fontSize: "10px" }} />
                  <Legend iconSize={8} wrapperStyle={{ fontSize: "9px" }} />
                  <Area type="monotone" dataKey="projected_fuel" name="Fuel Reserve" stroke="#06b6d4" fillOpacity={0.15} fill="url(#colorFuel)" />
                  <Area type="monotone" dataKey="projected_risk" name="Compounding Risk" stroke="#ef4444" fillOpacity={0.1} fill="url(#colorRisk)" />
                  <defs>
                    <linearGradient id="colorFuel" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#06b6d4" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorRisk" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

      </div>

      {/* 4. RIGHT GRID: SYSTEM INTEGRITY, CONSENSUS DECISION, EXPLAINABLE LOGS */}
      <div className="lg:col-span-3 flex flex-col gap-4">
        
        {/* Global Autonomy Performance Index Card */}
        {autonomyIndex && (
          <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md">
            <h2 className="text-xs font-bold tracking-widest text-cyan-400 border-b border-slate-800 pb-2 mb-3 uppercase flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Gauge className="w-4 h-4 text-cyan-400" />
                Autonomy Index
              </span>
              <span className="text-emerald-400 text-sm font-extrabold">{autonomyIndex.compound_index}%</span>
            </h2>

            <div className="space-y-2 text-[10px]">
              <div>
                <div className="flex justify-between text-slate-500 mb-1">
                  <span>DECISION ACCURACY</span>
                  <span className="text-slate-300 font-bold">{autonomyIndex.metrics?.decision_accuracy}%</span>
                </div>
                <div className="w-full bg-slate-900 h-1.5 rounded overflow-hidden">
                  <div className="bg-cyan-500 h-full" style={{ width: `${autonomyIndex.metrics?.decision_accuracy}%` }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-slate-500 mb-1">
                  <span>RECOVERY EFFECTIVENESS</span>
                  <span className="text-slate-300 font-bold">{autonomyIndex.metrics?.recovery_effectiveness}%</span>
                </div>
                <div className="w-full bg-slate-900 h-1.5 rounded overflow-hidden">
                  <div className="bg-emerald-500 h-full" style={{ width: `${autonomyIndex.metrics?.recovery_effectiveness}%` }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-slate-500 mb-1">
                  <span>LEARNING VELOCITY</span>
                  <span className="text-slate-300 font-bold">{autonomyIndex.metrics?.learning_efficiency}%</span>
                </div>
                <div className="w-full bg-slate-900 h-1.5 rounded overflow-hidden">
                  <div className="bg-amber-500 h-full" style={{ width: `${autonomyIndex.metrics?.learning_efficiency}%` }} />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Subsystem health grid */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md">
          <h2 className="text-xs font-bold tracking-widest text-cyan-400 border-b border-slate-800 pb-2 mb-2 uppercase flex items-center gap-2">
            <Activity className="w-4 h-4 text-cyan-400" />
            Digital Subsystem Schematic
          </h2>
          <div className="grid grid-cols-1 gap-2">
            {subsystems.map((sub) => {
              const isLow = sub.health < 60;
              return (
                <div key={sub.name} className="flex justify-between items-center bg-slate-900/40 p-2 rounded border border-slate-850">
                  <span className="text-slate-400 font-bold uppercase">{sub.name}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-slate-500">{sub.status}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${isLow ? "bg-rose-950/60 text-rose-400" : "bg-emerald-950/60 text-emerald-400"}`}>
                      {sub.health}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Strategic Goal priorities */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md">
          <h2 className="text-xs font-bold tracking-widest text-cyan-400 border-b border-slate-800 pb-2 mb-3 uppercase flex items-center gap-2">
            <Shield className="w-4 h-4 text-cyan-400" />
            Strategic Target Priorities
          </h2>
          <div className="space-y-2 text-[10px]">
            <div className="p-2 bg-cyan-950/40 border border-cyan-800/30 rounded flex items-center justify-between">
              <span className="font-bold text-cyan-400">PRIMARY</span>
              <span className="text-slate-200">Orbit Mars Alpha</span>
            </div>
            <div className="p-2 bg-slate-900 border border-slate-850 rounded flex items-center justify-between">
              <span className="font-bold text-slate-500">SECONDARY</span>
              <span className="text-slate-350">Assess Ice & Core</span>
            </div>
            <div className="p-2 bg-rose-950/30 border border-rose-900/20 rounded flex items-center justify-between">
              <span className="font-bold text-rose-400">CONTINGENCY</span>
              <span className="text-slate-300">Auto-isolate manifold leaks</span>
            </div>
          </div>
        </div>

      </div>

      {/* 5. BOTTOM GRID: AGENT CONSENSUS DECISIONS (Col Span 6) & CONTINGENCY INJECTOR (Col Span 3) & RESEARCH LAB TRIAL (Col Span 3) */}
      <div className="lg:col-span-6 flex flex-col gap-4">
        
        {/* Consensus Grid with Override Toggle */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md flex-1">
          <h2 className="text-xs font-bold tracking-widest text-cyan-400 border-b border-slate-800 pb-2 mb-3 uppercase flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Brain className="w-4 h-4 text-cyan-400 animate-pulse" />
              Collaborative Agent Consensus Grid
            </span>
          </h2>

          <div className="space-y-3">
            {consensusRecords.slice(0, 1).map((record) => (
              <div key={record.id} className="p-3 bg-slate-900/40 border border-slate-850 rounded-lg">
                <div className="flex justify-between items-center mb-2 border-b border-slate-850/60 pb-1.5">
                  <span className="font-bold text-slate-300">Decision: {record.decision_key}</span>
                  <span className="text-cyan-400 font-bold bg-cyan-950 border border-cyan-800/40 px-1.5 py-0.5 rounded text-[10px]">
                    Consensus Score: {record.consensus_score}%
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-[10px] text-slate-400">
                  <div className="p-2 bg-slate-950/40 border border-slate-900 rounded">
                    <span className="font-bold text-slate-500 block uppercase mb-0.5">Navigation Agent</span>
                    {record.nav_recommendation}
                  </div>
                  <div className="p-2 bg-slate-950/40 border border-slate-900 rounded">
                    <span className="font-bold text-slate-500 block uppercase mb-0.5">Propellant Agent</span>
                    {record.fuel_recommendation}
                  </div>
                  <div className="p-2 bg-slate-950/40 border border-slate-900 rounded">
                    <span className="font-bold text-slate-500 block uppercase mb-0.5">Safety Shield Agent</span>
                    {record.safety_recommendation}
                  </div>
                  <div className="p-2 bg-slate-950/40 border border-slate-900 rounded">
                    <span className="font-bold text-slate-500 block uppercase mb-0.5">Science Scanner Agent</span>
                    {record.science_recommendation}
                  </div>
                </div>

                <div className="mt-3 flex justify-between items-center">
                  <span className="text-[10px] text-slate-500">
                    *Toggling manual override suspends decentralized consensus checks and applies commands immediately.
                  </span>
                  <button
                    onClick={() => handleCommanderOverride(record.decision_key, record.commander_override)}
                    disabled={overrideInProgress === record.decision_key}
                    className={`px-3 py-1.5 rounded text-[10px] font-bold transition-all border ${
                      record.commander_override
                        ? "bg-rose-950 border-rose-500 text-rose-300"
                        : "bg-slate-950 border-slate-850 hover:border-slate-700 text-slate-400"
                    }`}
                  >
                    {overrideInProgress === record.decision_key
                      ? "PROCESSING..."
                      : record.commander_override
                      ? "REVOKE OVERRIDE"
                      : "COMMAND OVERRIDE"}
                  </button>
                </div>
              </div>
            ))}
            {consensusRecords.length === 0 && (
              <p className="text-slate-500 text-center italic py-6">Awaiting decentralized voting proposals...</p>
            )}
          </div>
        </div>

      </div>

      <div className="lg:col-span-3 flex flex-col gap-4">
        
        {/* Contingency Injector Panel */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md">
          <h2 className="text-xs font-bold tracking-widest text-cyan-400 border-b border-slate-800 pb-2 mb-3 uppercase flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-cyan-400" />
            Contingency Injector
          </h2>
          
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            {[
              "Solar Storm",
              "Fuel Leak",
              "Thruster Failure",
              "Communication Loss",
              "Navigation Drift",
              "Micrometeorite Impact",
              "Power Emergency",
              "Life Support Failure"
            ].map((ev) => (
              <button
                key={ev}
                onClick={() => handleInjectContingency(ev)}
                className="py-2 border border-slate-850 bg-slate-900/60 hover:bg-slate-800/60 hover:border-slate-700 text-slate-300 rounded text-center transition-all font-mono font-bold"
              >
                {ev.split(" ")[0]}
              </button>
            ))}
          </div>

          <form onSubmit={handleLabConfigSubmit} className="mt-4 border-t border-slate-850 pt-3 space-y-2">
            <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Lab Settings</h3>
            
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Engine stress:</span>
              <div className="flex gap-1">
                {["Easy", "Normal", "Hard"].map((lvl) => (
                  <button
                    key={lvl}
                    type="button"
                    onClick={() => setDifficulty(lvl)}
                    className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase transition-all ${
                      difficulty === lvl ? "bg-cyan-950 text-cyan-400 border border-cyan-800/50" : "text-slate-500 bg-slate-900"
                    }`}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-slate-500">Anomaly Check:</span>
              <div className="flex items-center gap-1.5">
                <input
                  type="number"
                  min="10"
                  max="120"
                  value={eventFrequency}
                  onChange={(e) => setEventFrequency(parseFloat(e.target.value))}
                  className="w-12 bg-slate-900 border border-slate-850 rounded p-0.5 text-center text-slate-200"
                />
                <span className="text-slate-500">s</span>
              </div>
            </div>

            <button
              type="submit"
              className="w-full py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded font-bold uppercase text-[9px] tracking-wider text-slate-300 transition-all"
            >
              APPLY SETTINGS
            </button>
          </form>
        </div>

      </div>

      <div className="lg:col-span-3 flex flex-col gap-4">
        
        {/* Research Lab Trial & Histogram */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md">
          <h2 className="text-xs font-bold tracking-widest text-cyan-400 border-b border-slate-800 pb-2 mb-3 uppercase flex items-center gap-2">
            <Sliders className="w-4 h-4 text-cyan-400" />
            Strategy Research Lab
          </h2>

          <p className="text-[10px] text-slate-500 mb-3 leading-normal">
            Runs 100 fast-time simulation trials to benchmark Conservative (low burn gliding) against Aggressive (max thrust velocity) strategies.
          </p>

          <button
            onClick={handleRunBenchmark}
            disabled={benchmarking}
            className="w-full py-2 border border-cyan-500/20 bg-cyan-950/40 hover:bg-cyan-500/10 text-cyan-400 font-bold rounded-lg transition-all disabled:opacity-40"
          >
            {benchmarking ? "SIMULATING TRIALS..." : "RUN STRATEGY TRIALS"}
          </button>

          {benchmark && (
            <div className="mt-3 space-y-2.5 text-[10px]">
              <div className="grid grid-cols-2 gap-2 text-center border-t border-slate-850 pt-2.5">
                <div className="p-1.5 bg-slate-900 border border-slate-850 rounded">
                  <span className="text-[9px] text-slate-500 block uppercase">Conservative</span>
                  <span className="text-emerald-400 font-bold text-xs mt-0.5 block">{benchmark.conservative.success_rate}% Success</span>
                  <span className="text-[8px] text-slate-500 block mt-0.5">{benchmark.conservative.avg_fuel_remaining}% Fuel Remaining</span>
                </div>
                <div className="p-1.5 bg-slate-900 border border-slate-850 rounded">
                  <span className="text-[9px] text-slate-500 block uppercase">Aggressive</span>
                  <span className="text-rose-450 font-bold text-xs mt-0.5 block">{benchmark.aggressive.success_rate}% Success</span>
                  <span className="text-[8px] text-slate-500 block mt-0.5">{benchmark.aggressive.avg_fuel_remaining}% Fuel Remaining</span>
                </div>
              </div>
            </div>
          )}
        </div>

      </div>

      {/* 6. BOTTOM FULL-WIDTH: DECISION TRACE AUDIT LOG */}
      <div className="lg:col-span-12">
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md">
          <h2 className="text-xs font-bold tracking-widest text-cyan-400 border-b border-slate-800 pb-2 mb-3 uppercase flex items-center gap-2">
            <Sliders className="w-4 h-4 text-cyan-400 animate-spin-slow" />
            Explainable Autonomy Audit Log (Recent AI Decision Traces)
          </h2>

          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-[10px] leading-normal border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-500">
                  <th className="py-2 px-3 uppercase">Timestamp</th>
                  <th className="py-2 px-3 uppercase">Trigger Event</th>
                  <th className="py-2 px-3 uppercase">Chosen Action</th>
                  <th className="py-2 px-3 uppercase">Confidence</th>
                  <th className="py-2 px-3 uppercase">Logic & Explanation</th>
                  <th className="py-2 px-3 uppercase">Autonomy Level</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-900 text-slate-300">
                {autonomyTraces.map((trace) => (
                  <tr key={trace.id} className="hover:bg-slate-900/30">
                    <td className="py-2 px-3 text-slate-500">{new Date(trace.timestamp).toLocaleTimeString()}</td>
                    <td className="py-2 px-3 font-bold text-cyan-400">{trace.event_type}</td>
                    <td className="py-2 px-3 font-semibold text-slate-200">{trace.chosen_action}</td>
                    <td className="py-2 px-3 text-emerald-400 font-bold">{trace.confidence_score}%</td>
                    <td className="py-2 px-3 max-w-sm text-slate-400 truncate" title={trace.reasoning}>
                      {trace.reasoning}
                    </td>
                    <td className="py-2 px-3">
                      <span className="bg-slate-900 border border-slate-850 px-1.5 py-0.5 rounded text-[8px] font-bold text-slate-400 uppercase">
                        Level {trace.autonomy_level}
                      </span>
                    </td>
                  </tr>
                ))}
                {autonomyTraces.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-slate-500 italic">No decision traces processed yet...</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

    </div>
  );
}
