"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Shield,
  Activity,
  AlertTriangle,
  Radio,
  Sliders,
  Cpu,
  Brain,
  Layers,
  Zap,
  Target,
  Play,
  Square,
  Plus,
  Trash2,
  Save,
  CheckCircle,
  Clock,
  ArrowRight,
  RefreshCw,
  Gauge,
  Sparkles,
  Award,
  Database,
  Pause,
  RotateCcw,
  FastForward,
  Check,
  X,
  User,
  Send
} from "lucide-react";

// Typewriter effect component
function Typewriter({ text, speed = 12 }: { text: string; speed?: number }) {
  const [displayedText, setDisplayedText] = useState("");
  useEffect(() => {
    let index = 0;
    setDisplayedText("");
    const interval = setInterval(() => {
      setDisplayedText((prev) => prev + text.charAt(index));
      index++;
      if (index >= text.length) {
        clearInterval(interval);
      }
    }, speed);
    return () => clearInterval(interval);
  }, [text, speed]);
  return <span>{displayedText}</span>;
}
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip
} from "recharts";

import { useStore, telemetryStore, activeEventsStore, missionStore } from "../hooks/useStore";

interface TestingCenterPanelProps {
  telemetry?: any;
  activeEvents?: any[];
  mission?: any;
}

interface AnomalyTemplate {
  name: string;
  system: string;
  desc: string;
  defaultMults: Record<string, number>;
}

interface CustomScenarioEvent {
  event_type: string;
  severity: string;
  duration: number;
  affected_system: string;
  propagation_speed: number;
  probability: number;
  impact_multipliers: Record<string, number>;
  trigger_time: number;
}

interface CustomScenario {
  id: number;
  name: string;
  description: string;
  events: CustomScenarioEvent[];
  created_at: string;
}

interface BenchmarkResult {
  id: number;
  timestamp: string;
  scenario_name: string;
  injected_event: string;
  subsystem_impact: Record<string, number>;
  mission_impact: Record<string, any>;
  recovery_outcome: string;
  risk_evolution: number[];
  final_mission_state: string;
}

interface RecoveryMetrics {
  id: number;
  timestamp: string;
  detection_time: number;
  recovery_time: number;
  damage_prevented: number;
  mission_success_change: number;
  risk_reduction: number;
  resource_preservation: number;
}

interface ResilienceScores {
  resilience: number;
  survivability: number;
  adaptability: number;
  stability: number;
  recovery_efficiency: number;
}

interface LLMDecision {
  id: number;
  timestamp: string;
  decision: string;
  confidence: number;
  chosen_action_key: string;
  status: string;
  reasoning: string[];
  expected_outcome: {
    mission_success_change: number;
    risk_reduction: number;
  };
}

export default function TestingCenterPanel({ 
  telemetry: propTelemetry, 
  activeEvents: propActiveEvents, 
  mission: propMission 
}: TestingCenterPanelProps) {
  const storeTelemetry = useStore(telemetryStore);
  const storeActiveEvents = useStore(activeEventsStore);
  const storeMission = useStore(missionStore);

  const telemetry = propTelemetry !== undefined ? propTelemetry : storeTelemetry;
  const activeEvents = propActiveEvents !== undefined ? propActiveEvents : storeActiveEvents;
  const mission = propMission !== undefined ? propMission : storeMission;

  const backendUrl = "127.0.5.1:8000"; // fallback-resilient binding prefix or host
  const actualBackendHost = "127.0.0.1:8000";

  // Categories and Anomalies List (36 anomalies)
  const anomalies: Record<string, AnomalyTemplate[]> = {
    Environmental: [
      { name: "Solar Storm", system: "Power", desc: "Solar CME electromagnetic charge disruption.", defaultMults: { power: -1.5, "subsystems.Power": -2.0, "subsystems.Communication": -2.5 } },
      { name: "Radiation Burst", system: "Life Support", desc: "High alpha particles. life support stress.", defaultMults: { oxygen: -0.5, "subsystems.Life Support": -1.5 } },
      { name: "Asteroid Field", system: "Thermal Control", desc: "Entering debris dense zone. Collision hazard.", defaultMults: { health: -1.2, "subsystems.Thermal Control": -3.0 } },
      { name: "Micrometeorite Impact", system: "Thermal Control", desc: "Minor outer shell impact registered.", defaultMults: { health: -0.8, "subsystems.Thermal Control": -3.0 } },
      { name: "Magnetic Interference", system: "Communication", desc: "Magnetic fields distort radio channels.", defaultMults: { "subsystems.Communication": -1.5, "subsystems.Navigation": -1.0 } },
      { name: "Space Debris Collision", system: "Thermal Control", desc: "Debris collision on secondary cargo bay.", defaultMults: { health: -2.5, "subsystems.Thermal Control": -4.0 } }
    ],
    Communication: [
      { name: "Communication Loss", system: "Communication", desc: "S-Band High Gain Antenna signal loss.", defaultMults: { "subsystems.Communication": -1.8 } },
      { name: "Signal Delay", system: "Communication", desc: "Heavy interplanetary noise telemetry delays.", defaultMults: { "subsystems.Communication": -0.8 } },
      { name: "Signal Corruption", system: "Communication", desc: "Checksum failures on packet streams.", defaultMults: { "subsystems.Communication": -1.2 } },
      { name: "Ground Station Failure", system: "Communication", desc: "Deep Space Network Earth receiver offline.", defaultMults: { "subsystems.Communication": -1.0 } },
      { name: "Relay Failure", system: "Communication", desc: "Mars orbiter relayer suffers transponder drop.", defaultMults: { "subsystems.Communication": -1.4 } },
      { name: "Network Saturation", system: "Communication", desc: "Bandwidth limit exceeded. Telemetry drop spike.", defaultMults: { "subsystems.Communication": -0.5 } }
    ],
    Navigation: [
      { name: "Navigation Drift", system: "Navigation", desc: "IMU gyro drift coordinate discrepancy.", defaultMults: { "subsystems.Navigation": -1.5, position_error: 0.4 } },
      { name: "Sensor Failure", system: "Navigation", desc: "Optical navigation sensor camera occlusion.", defaultMults: { "subsystems.Navigation": -1.2 } },
      { name: "Star Tracker Failure", system: "Navigation", desc: "Stellar camera alignment camera shutter fault.", defaultMults: { "subsystems.Navigation": -2.0, position_error: 0.8 } },
      { name: "Trajectory Deviation", system: "Navigation", desc: "Flight path deviates from guidance vector.", defaultMults: { "subsystems.Navigation": -1.0, position_error: 0.6 } },
      { name: "Position Estimation Error", system: "Navigation", desc: "Kalman filters register high state variance.", defaultMults: { "subsystems.Navigation": -0.8, position_error: 0.5 } }
    ],
    Resource: [
      { name: "Fuel Leak", system: "Propulsion", desc: "Gasket leak. Slow propellant drop.", defaultMults: { fuel: -0.4, "subsystems.Propulsion": -1.2 } },
      { name: "Power Failure", system: "Power", desc: "Buss grid short battery discharge.", defaultMults: { power: -1.5, "subsystems.Power": -2.5 } },
      { name: "Battery Degradation", system: "Power", desc: "Lithium matrix cell temperature spike.", defaultMults: { power: -0.6, "subsystems.Power": -1.2 } },
      { name: "Oxygen Leak", system: "Life Support", desc: "Module seals micro-fissures drop rate.", defaultMults: { oxygen: -1.2, "subsystems.Life Support": -2.0 } },
      { name: "Cooling System Failure", system: "Thermal Control", desc: "Freon cooling pump failure telemetry drop.", defaultMults: { temperature: 1.2, "subsystems.Thermal Control": -2.5 } },
      { name: "Thermal Imbalance", system: "Thermal Control", desc: "Extreme temperature discrepancy on panels.", defaultMults: { temperature: 0.8, "subsystems.Thermal Control": -1.5 } }
    ],
    Propulsion: [
      { name: "Thruster Failure", system: "Propulsion", desc: "Asymmetrical RCS thrusters bells feedback failure.", defaultMults: { "subsystems.Propulsion": -2.5 } },
      { name: "Engine Failure", system: "Propulsion", desc: "Main combustion chamber automatic cut.", defaultMults: { velocity: -0.8, "subsystems.Propulsion": -4.0 } },
      { name: "Partial Engine Loss", system: "Propulsion", desc: "RCS manifold secondary thrusters offline.", defaultMults: { velocity: -0.3, "subsystems.Propulsion": -2.0 } },
      { name: "Attitude Control Failure", system: "Propulsion", desc: "Command logic fails to orient bells.", defaultMults: { "subsystems.Propulsion": -1.8, position_error: 0.5 } },
      { name: "Fuel Pump Failure", system: "Propulsion", desc: "Turbopump cavitation limits flow rate.", defaultMults: { fuel: -0.2, "subsystems.Propulsion": -2.2 } }
    ],
    LifeSupport: [
      { name: "Oxygen Contamination", system: "Life Support", desc: "Filters register high particulate matter.", defaultMults: { oxygen: -0.6, "subsystems.Life Support": -1.8 } },
      { name: "Pressure Loss", system: "Life Support", desc: "Cabin compartment pressure decompression.", defaultMults: { oxygen: -1.8, "subsystems.Life Support": -3.5 } },
      { name: "CO2 Filter Failure", system: "Life Support", desc: "Zeolite scrubber beds saturated warning.", defaultMults: { oxygen: -0.8, "subsystems.Life Support": -2.0 } },
      { name: "Life Support Failure", system: "Life Support", desc: "Environmental control grids offline.", defaultMults: { oxygen: -2.5, "subsystems.Life Support": -5.0 } }
    ],
    Science: [
      { name: "Unknown Object Detection", system: "Science Systems", desc: "LIDAR registers orbiting localized mass.", defaultMults: { "subsystems.Science Systems": -0.2 } },
      { name: "Unidentified Signal", system: "Science Systems", desc: "Broadband radio picks up stellar signal.", defaultMults: { "subsystems.Science Systems": -0.2 } },
      { name: "Scientific Opportunity", system: "Science Systems", desc: "Gravitational pocket offers scans telemetry.", defaultMults: {} },
      { name: "Resource Discovery", system: "Science Systems", desc: "Asteroid scan reveals heavy trace isotopes.", defaultMults: {} }
    ]
  };

  const presets = [
    { id: 1, name: "Solar Storm Emergency", desc: "CME grid discharge & battery drops." },
    { id: 2, name: "Deep Space Fuel Crisis", desc: "Port tank valve leak & thruster loss." },
    { id: 3, name: "Communication Blackout", desc: "High gain carrier loss & signal drops." },
    { id: 4, name: "Navigation Failure", desc: "IMU drift & tracking occlusions." },
    { id: 5, name: "Engine Catastrophic Failure", desc: "Combustion chamber failure & RCS loss." },
    { id: 6, name: "Mars Landing Emergency", desc: "RCS attitude failures & cabin leaks during entry." },
    { id: 7, name: "Life Support Crisis", desc: "O2 leak, filter saturation & critical drops." },
    { id: 8, name: "Perfect Storm", desc: "Simultaneous solar storm, comm drop, fuel leak, nav drift." },
    { id: 9, name: "Total Systems Failure", desc: "Severe degradation across all 7 subsystems." },
    { id: 10, name: "Judge Demo Showcase", desc: "Storm, Comm Loss, and Micrometeorites sequentially." }
  ];

  // States
  const [activeCategory, setActiveCategory] = useState<string>("Environmental");
  const [selectedAnomaly, setSelectedAnomaly] = useState<AnomalyTemplate | null>(null);

  // Configuration forms
  const [customSeverity, setCustomSeverity] = useState<string>("HIGH");
  const [customDuration, setCustomDuration] = useState<number>(30);
  const [customSpeed, setCustomSpeed] = useState<number>(1.0);
  const [customMults, setCustomMults] = useState<string>("{}");

  // Custom Timeline Builder
  const [customScenarioName, setCustomScenarioName] = useState<string>("");
  const [customScenarioDesc, setCustomScenarioDesc] = useState<string>("");
  const [timelineEvents, setTimelineEvents] = useState<CustomScenarioEvent[]>([]);
  const [timelineTriggerTime, setTimelineTriggerTime] = useState<number>(0);
  const [selectedBuilderAnomaly, setSelectedBuilderAnomaly] = useState<string>("Solar Storm");

  // Loaded Custom Scenarios
  const [customScenarios, setCustomScenarios] = useState<CustomScenario[]>([]);

  // Benchmarks & Telemetry Records
  const [benchmarks, setBenchmarks] = useState<BenchmarkResult[]>([]);
  const [recoveryLog, setRecoveryLog] = useState<RecoveryMetrics[]>([]);
  const [resilienceScore, setResilienceScore] = useState<ResilienceScores>({
    resilience: 100.0,
    survivability: 100.0,
    adaptability: 100.0,
    stability: 100.0,
    recovery_efficiency: 100.0
  });

  // Scenario state
  const [activeScenarioInfo, setActiveScenarioInfo] = useState<any>({ active: false });

  // LLM Commander Integration state
  const [llmMetrics, setLlmMetrics] = useState<any>({
    accuracy: 85.0,
    avg_confidence: 78.0,
    success_rate: 90.0,
    reasoning_quality: 92.5
  });
  const [lastLlmDecision, setLastLlmDecision] = useState<LLMDecision | null>(null);

  // --- Live Agent Collaboration states ---
  const [rightPanelTab, setRightPanelTab] = useState<"collaboration" | "analysis">("collaboration");
  const [wsStatus, setWsStatus] = useState<string>("disconnected");

  const [activeEventHeader, setActiveEventHeader] = useState<{
    eventType: string;
    severity: string;
    affected: string;
    risk: number;
  } | null>(null);

  const [agentStatuses, setAgentStatuses] = useState<Record<string, string>>({
    "Navigation Agent": "COMPLETED",
    "Resource Agent": "COMPLETED",
    "Safety Agent": "COMPLETED",
    "Science Agent": "COMPLETED",
    "Mission Commander Agent": "COMPLETED"
  });

  const [agentCards, setAgentCards] = useState<Record<string, {
    recommendation: string;
    confidence: number;
    reasoning: string;
    status: string;
    lastAction: string;
  }>>({
    "Navigation Agent": { recommendation: "No Action", confidence: 0, reasoning: "System nominal.", status: "COMPLETED", lastAction: "Idle" },
    "Resource Agent": { recommendation: "No Action", confidence: 0, reasoning: "System nominal.", status: "COMPLETED", lastAction: "Idle" },
    "Safety Agent": { recommendation: "No Action", confidence: 0, reasoning: "System nominal.", status: "COMPLETED", lastAction: "Idle" },
    "Science Agent": { recommendation: "No Action", confidence: 0, reasoning: "System nominal.", status: "COMPLETED", lastAction: "Idle" }
  });

  const [consensusData, setConsensusData] = useState<{
    action: string;
    score: number;
    votes: Record<string, boolean>;
  } | null>(null);

  const [commanderDecision, setCommanderDecision] = useState<{
    action: string;
    confidence: number;
    reasoning: string;
    expectedOutcome: {
      riskReduction: number;
      successChange: number;
    }
  } | null>(null);

  const [digitalTwinOutcome, setDigitalTwinOutcome] = useState<{
    fuel: number;
    power: number;
    risk: number;
    success: number;
  } | null>(null);

  const [chatStream, setChatStream] = useState<any[]>([]);
  const [collaborationTimeline, setCollaborationTimeline] = useState<any[]>([]);
  const [agentMemory, setAgentMemory] = useState<{
    previousEvent: string;
    bestAction: string;
    successRate: number;
  } | null>(null);

  // Replay Mode states
  const [isReplayActive, setIsReplayActive] = useState<boolean>(false);
  const [replayHistory, setReplayHistory] = useState<any[]>([]);
  const [selectedReplayId, setSelectedReplayId] = useState<number | null>(null);
  const [replayStepsData, setReplayStepsData] = useState<any[]>([]);
  const [replayStepIndex, setReplayStepIndex] = useState<number>(0);
  const [isPlayingReplay, setIsPlayingReplay] = useState<boolean>(false);

  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll chat stream
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatStream]);

  // WebSocket real-time listener
  useEffect(() => {
    if (isReplayActive) return;

    console.log("[Collaboration WS] Initializing WebSocket client connection...");
    const ws = new WebSocket(`ws://${actualBackendHost}/ws`);

    ws.onopen = () => {
      setWsStatus("connected");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "INIT" || data.type === "TELEMETRY") {
          if (data.active_events && data.active_events.length > 0) {
            const ev = data.active_events[0];
            setActiveEventHeader({
              eventType: ev.event_type,
              severity: ev.severity,
              affected: ev.affected_system,
              risk: Math.round(data.telemetry?.risk_score || 0)
            });
            setAgentMemory({
              previousEvent: ev.event_type,
              bestAction: ev.event_type.includes("Storm") ? "Enter Safe Mode" : ev.event_type.includes("Leak") ? "Activate Backup Tank" : "Standard Recovery",
              successRate: ev.event_type.includes("Storm") ? 92 : ev.event_type.includes("Leak") ? 88 : 85
            });
          } else {
            setActiveEventHeader(null);
            setDigitalTwinOutcome(null);
          }
        } else if (data.type === "AGENT_ANALYSIS_STARTED") {
          setActiveEventHeader({
            eventType: data.event_type,
            severity: "HIGH",
            affected: "Telemetry Grid",
            risk: 50
          });
          setChatStream([]);
          setAgentStatuses({
            "Navigation Agent": "ANALYZING",
            "Resource Agent": "ANALYZING",
            "Safety Agent": "ANALYZING",
            "Science Agent": "ANALYZING",
            "Mission Commander Agent": "ANALYZING"
          });
          setAgentCards({
            "Navigation Agent": { recommendation: "Analyzing...", confidence: 0, reasoning: "Scanning orbit trajectory...", status: "ANALYZING", lastAction: "Searching" },
            "Resource Agent": { recommendation: "Analyzing...", confidence: 0, reasoning: "Scanning fuel grids...", status: "ANALYZING", lastAction: "Searching" },
            "Safety Agent": { recommendation: "Analyzing...", confidence: 0, reasoning: "Scanning compartment seals...", status: "ANALYZING", lastAction: "Searching" },
            "Science Agent": { recommendation: "Analyzing...", confidence: 0, reasoning: "Scanning spectral filters...", status: "ANALYZING", lastAction: "Searching" }
          });
          setConsensusData(null);
          setCommanderDecision(null);
          setCollaborationTimeline([
            { text: "Event Detected", status: "completed", time: new Date().toLocaleTimeString() },
            { text: "Agent Analysis Started", status: "active", time: new Date().toLocaleTimeString() },
            { text: "Agent Recommendations", status: "pending" },
            { text: "Consensus Formed", status: "pending" },
            { text: "Commander Decision", status: "pending" },
            { text: "Mitigation Executing", status: "pending" }
          ]);
        } else if (data.type === "AGENT_RECOMMENDATION_CREATED") {
          const name = data.agent_name;
          setAgentStatuses((prev) => ({ ...prev, [name]: "RECOMMENDING" }));
          setAgentCards((prev) => ({
            ...prev,
            [name]: {
              recommendation: data.recommendation,
              confidence: data.confidence,
              reasoning: data.reasoning,
              status: "RECOMMENDING",
              lastAction: "Published recommendation"
            }
          }));
          setChatStream((prev) => {
            if (prev.some(m => m.sender === name && m.message === data.reasoning)) return prev;
            return [...prev, {
              sender: name,
              role: name.includes("Navigation") ? "Trajectory Specialist" : name.includes("Resource") ? "Propulsion & Consumables Officer" : name.includes("Safety") ? "Hull & Crew Officer" : "Sensor and Analytics Officer",
              message: data.reasoning,
              confidence: data.confidence
            }];
          });
          setCollaborationTimeline((prev) => {
            const next = [...prev];
            if (next[2]) next[2] = { text: "Agent Recommendations", status: "active", time: new Date().toLocaleTimeString() };
            return next;
          });
        } else if (data.type === "CONSENSUS_UPDATED") {
          setAgentStatuses((prev) => {
            const next = { ...prev };
            Object.keys(next).forEach(k => { if (k !== "Mission Commander Agent") next[k] = "VOTING"; });
            return next;
          });
          const consensusAction = data.chosen_action;
          setConsensusData({
            action: consensusAction,
            score: data.agreement_score,
            votes: {
              "Navigation Agent": true,
              "Resource Agent": true,
              "Safety Agent": true,
              "Science Agent": false
            }
          });
          setCollaborationTimeline((prev) => {
            const next = [...prev];
            if (next[2]) next[2] = { ...next[2], status: "completed" };
            if (next[3]) next[3] = { text: "Consensus Formed", status: "active", time: new Date().toLocaleTimeString() };
            return next;
          });
        } else if (data.type === "COMMANDER_DECISION_CREATED") {
          setCommanderDecision({
            action: data.chosen_action,
            confidence: data.confidence,
            reasoning: data.reasoning,
            expectedOutcome: {
              riskReduction: 20,
              successChange: 8
            }
          });
          setAgentStatuses((prev) => ({ ...prev, "Mission Commander Agent": "EXECUTING" }));
          setChatStream((prev) => {
            if (prev.some(m => m.sender === "Mission Commander Agent")) return prev;
            return [...prev, {
              sender: "Mission Commander Agent",
              role: "Mission Commander",
              message: data.reasoning,
              confidence: data.confidence
            }];
          });
          setCollaborationTimeline((prev) => {
            const next = [...prev];
            if (next[3]) next[3] = { ...next[3], status: "completed" };
            if (next[4]) next[4] = { text: "Commander Decision", status: "completed", time: new Date().toLocaleTimeString() };
            if (next[5]) next[5] = { text: "Mitigation Executing", status: "active", time: new Date().toLocaleTimeString() };
            return next;
          });
        } else if (data.type === "DECISION_EXECUTED") {
          setAgentStatuses((prev) => {
            const next = { ...prev };
            Object.keys(next).forEach(k => { next[k] = "EXECUTING"; });
            return next;
          });
          setDigitalTwinOutcome({
            fuel: data.predictions_deltas?.fuel_delta || -2,
            power: data.predictions_deltas?.power_delta || -15,
            risk: -(data.predictions_deltas?.risk_reduction || 20),
            success: data.predictions_deltas?.success_delta || 8
          });
          setCollaborationTimeline((prev) => {
            const next = [...prev];
            if (next[5]) next[5] = { ...next[5], status: "completed" };
            if (next.length === 6) {
              next.push({ text: "Execution Completed", status: "active", time: new Date().toLocaleTimeString() });
            }
            return next;
          });
        } else if (data.type === "EVENT_RESOLVED" || data.type === "Recovery Completed") {
          setAgentStatuses((prev) => {
            const next = { ...prev };
            Object.keys(next).forEach(k => { next[k] = "COMPLETED"; });
            return next;
          });
          setCollaborationTimeline((prev) => {
            const next = [...prev];
            if (next[6]) next[6] = { text: "Execution Completed", status: "completed", time: new Date().toLocaleTimeString() };
            return next;
          });
        }
      } catch (err) {
        console.error("[Collaboration WS] Message parse error:", err);
      }
    };

    ws.onclose = () => {
      setWsStatus("disconnected");
    };

    return () => {
      ws.close();
    };
  }, [isReplayActive]);

  // Replay Controller actions
  const loadDecisionReplay = (decision: any) => {
    setIsPlayingReplay(false);
    setIsReplayActive(true);
    setReplayStepIndex(0);

    const actionKey = decision.chosen_action;
    let eventName = "System Anomaly";
    let severity = "MEDIUM";
    let affected = "Core Subsystems";
    let risk = 40;

    if (actionKey.includes("solar")) {
      eventName = "Solar Storm";
      severity = "HIGH";
      affected = "Communication, Power";
      risk = 73;
    } else if (actionKey.includes("fuel")) {
      eventName = "Fuel Leak";
      severity = "HIGH";
      affected = "Propulsion";
      risk = 65;
    } else if (actionKey.includes("comm")) {
      eventName = "Communication Loss";
      severity = "MEDIUM";
      affected = "Communication";
      risk = 50;
    } else if (actionKey.includes("thruster")) {
      eventName = "Thruster Failure";
      severity = "HIGH";
      affected = "Propulsion";
      risk = 55;
    } else if (actionKey.includes("nav") || actionKey.includes("drift")) {
      eventName = "Navigation Drift";
      severity = "LOW";
      affected = "Navigation";
      risk = 30;
    } else if (actionKey.includes("meteor") || actionKey.includes("seal")) {
      eventName = "Micrometeorite Impact";
      severity = "HIGH";
      affected = "Thermal Control";
      risk = 60;
    }

    const header = {
      eventType: eventName,
      severity,
      affected,
      risk
    };

    const memory = {
      previousEvent: eventName,
      bestAction: actionKey.includes("solar") ? "Enter Safe Mode" : actionKey.includes("fuel") ? "Activate Backup Tank" : "Standard Recovery",
      successRate: actionKey.includes("solar") ? 92 : actionKey.includes("fuel") ? 88 : 85
    };

    const navRec = {
      recommendation: actionKey.includes("nav") || actionKey.includes("drift") ? "Perform Star-Field Overlay" : "Re-vector Remaining Bells",
      confidence: 89,
      reasoning: "Trajectory analysis suggests course adjustment to offset positional error.",
      status: "COMPLETED",
      lastAction: "Route optimized"
    };

    const resRec = {
      recommendation: actionKey.includes("fuel") ? "Activate Backup Tank" : "Bypass Compromised Lines",
      confidence: 92,
      reasoning: "Resource monitors indicate electrical grid discharge risk. Conservation mode recommended.",
      status: "COMPLETED",
      lastAction: "Power diverted"
    };

    const safeRec = {
      recommendation: actionKey.includes("meteor") || actionKey.includes("leak") ? "Seal Bulkheads" : "Divert Power to Deflectors",
      confidence: 95,
      reasoning: "Integrity alert registers cabin module seals pressure hazard.",
      status: "COMPLETED",
      lastAction: "Hull secured"
    };

    const sciRec = {
      recommendation: "Run Damage Diagnostic",
      confidence: 78,
      reasoning: "Scanners identify science payload telemetry drop risk.",
      status: "COMPLETED",
      lastAction: "Scanners online"
    };

    const actionClean = actionKey.split("_").slice(2).join(" ").toUpperCase() || actionKey;

    const replaySteps = [
      {
        header,
        chat: [],
        statuses: {
          "Navigation Agent": "ANALYZING",
          "Resource Agent": "ANALYZING",
          "Safety Agent": "ANALYZING",
          "Science Agent": "ANALYZING",
          "Mission Commander Agent": "ANALYZING"
        },
        cards: {
          "Navigation Agent": { recommendation: "Analyzing...", confidence: 0, reasoning: "Scanning orbit trajectory...", status: "ANALYZING", lastAction: "Searching" },
          "Resource Agent": { recommendation: "Analyzing...", confidence: 0, reasoning: "Scanning fuel grids...", status: "ANALYZING", lastAction: "Searching" },
          "Safety Agent": { recommendation: "Analyzing...", confidence: 0, reasoning: "Scanning compartment seals...", status: "ANALYZING", lastAction: "Searching" },
          "Science Agent": { recommendation: "Analyzing...", confidence: 0, reasoning: "Scanning spectral filters...", status: "ANALYZING", lastAction: "Searching" }
        },
        consensus: null,
        commander: null,
        outcome: null,
        memory,
        timeline: [
          { text: "Event Detected", status: "completed", time: "T+0s" },
          { text: "Agent Analysis Started", status: "active", time: "T+1s" },
          { text: "Agent Recommendations", status: "pending" },
          { text: "Consensus Formed", status: "pending" },
          { text: "Commander Decision", status: "pending" },
          { text: "Mitigation Executing", status: "pending" }
        ]
      },
      {
        header,
        chat: [
          { sender: "Navigation Agent", role: "Trajectory Specialist", message: "Trajectory offsets are drifting. Course correction recommended.", confidence: 89 }
        ],
        statuses: {
          "Navigation Agent": "RECOMMENDING",
          "Resource Agent": "ANALYZING",
          "Safety Agent": "ANALYZING",
          "Science Agent": "ANALYZING",
          "Mission Commander Agent": "ANALYZING"
        },
        cards: {
          "Navigation Agent": navRec,
          "Resource Agent": { recommendation: "Analyzing...", confidence: 0, reasoning: "Scanning fuel grids...", status: "ANALYZING", lastAction: "Searching" },
          "Safety Agent": { recommendation: "Analyzing...", confidence: 0, reasoning: "Scanning compartment seals...", status: "ANALYZING", lastAction: "Searching" },
          "Science Agent": { recommendation: "Analyzing...", confidence: 0, reasoning: "Scanning spectral filters...", status: "ANALYZING", lastAction: "Searching" }
        },
        consensus: null,
        commander: null,
        outcome: null,
        memory,
        timeline: [
          { text: "Event Detected", status: "completed", time: "T+0s" },
          { text: "Agent Analysis Started", status: "completed", time: "T+1s" },
          { text: "Agent Recommendations", status: "active", time: "T+3s" },
          { text: "Consensus Formed", status: "pending" },
          { text: "Commander Decision", status: "pending" },
          { text: "Mitigation Executing", status: "pending" }
        ]
      },
      {
        header,
        chat: [
          { sender: "Navigation Agent", role: "Trajectory Specialist", message: "Trajectory offsets are drifting. Course correction recommended.", confidence: 89 },
          { sender: "Resource Agent", role: "Propulsion & Consumables Officer", message: "Resource grids are showing pressure variations. Adjusting feed pressure.", confidence: 92 }
        ],
        statuses: {
          "Navigation Agent": "VOTING",
          "Resource Agent": "RECOMMENDING",
          "Safety Agent": "ANALYZING",
          "Science Agent": "ANALYZING",
          "Mission Commander Agent": "ANALYZING"
        },
        cards: {
          "Navigation Agent": navRec,
          "Resource Agent": resRec,
          "Safety Agent": { recommendation: "Analyzing...", confidence: 0, reasoning: "Scanning compartment seals...", status: "ANALYZING", lastAction: "Searching" },
          "Science Agent": { recommendation: "Analyzing...", confidence: 0, reasoning: "Scanning spectral filters...", status: "ANALYZING", lastAction: "Searching" }
        },
        consensus: null,
        commander: null,
        outcome: null,
        memory,
        timeline: [
          { text: "Event Detected", status: "completed", time: "T+0s" },
          { text: "Agent Analysis Started", status: "completed", time: "T+1s" },
          { text: "Agent Recommendations", status: "active", time: "T+5s" },
          { text: "Consensus Formed", status: "pending" },
          { text: "Commander Decision", status: "pending" },
          { text: "Mitigation Executing", status: "pending" }
        ]
      },
      {
        header,
        chat: [
          { sender: "Navigation Agent", role: "Trajectory Specialist", message: "Trajectory offsets are drifting. Course correction recommended.", confidence: 89 },
          { sender: "Resource Agent", role: "Propulsion & Consumables Officer", message: "Resource grids are showing pressure variations. Adjusting feed pressure.", confidence: 92 },
          { sender: "Safety Agent", role: "Hull Integrity & Crew Officer", message: "Subsystem anomaly propagation is detected. Safeguarding hull modules.", confidence: 95 }
        ],
        statuses: {
          "Navigation Agent": "VOTING",
          "Resource Agent": "VOTING",
          "Safety Agent": "RECOMMENDING",
          "Science Agent": "ANALYZING",
          "Mission Commander Agent": "ANALYZING"
        },
        cards: {
          "Navigation Agent": navRec,
          "Resource Agent": resRec,
          "Safety Agent": safeRec,
          "Science Agent": { recommendation: "Analyzing...", confidence: 0, reasoning: "Scanning spectral filters...", status: "ANALYZING", lastAction: "Searching" }
        },
        consensus: null,
        commander: null,
        outcome: null,
        memory,
        timeline: [
          { text: "Event Detected", status: "completed", time: "T+0s" },
          { text: "Agent Analysis Started", status: "completed", time: "T+1s" },
          { text: "Agent Recommendations", status: "active", time: "T+7s" },
          { text: "Consensus Formed", status: "pending" },
          { text: "Commander Decision", status: "pending" },
          { text: "Mitigation Executing", status: "pending" }
        ]
      },
      {
        header,
        chat: [
          { sender: "Navigation Agent", role: "Trajectory Specialist", message: "Trajectory offsets are drifting. Course correction recommended.", confidence: 89 },
          { sender: "Resource Agent", role: "Propulsion & Consumables Officer", message: "Resource grids are showing pressure variations. Adjusting feed pressure.", confidence: 92 },
          { sender: "Safety Agent", role: "Hull Integrity & Crew Officer", message: "Subsystem anomaly propagation is detected. Safeguarding hull modules.", confidence: 95 },
          { sender: "Science Agent", role: "Sensor and Analytics Officer", message: "Scanning background stellar noise. Ready for diagnostic calibrations.", confidence: 78 }
        ],
        statuses: {
          "Navigation Agent": "VOTING",
          "Resource Agent": "VOTING",
          "Safety Agent": "VOTING",
          "Science Agent": "RECOMMENDING",
          "Mission Commander Agent": "ANALYZING"
        },
        cards: {
          "Navigation Agent": navRec,
          "Resource Agent": resRec,
          "Safety Agent": safeRec,
          "Science Agent": sciRec
        },
        consensus: null,
        commander: null,
        outcome: null,
        memory,
        timeline: [
          { text: "Event Detected", status: "completed", time: "T+0s" },
          { text: "Agent Analysis Started", status: "completed", time: "T+1s" },
          { text: "Agent Recommendations", status: "completed", time: "T+9s" },
          { text: "Consensus Formed", status: "active", time: "T+10s" },
          { text: "Commander Decision", status: "pending" },
          { text: "Mitigation Executing", status: "pending" }
        ]
      },
      {
        header,
        chat: [
          { sender: "Navigation Agent", role: "Trajectory Specialist", message: "Trajectory offsets are drifting. Course correction recommended.", confidence: 89 },
          { sender: "Resource Agent", role: "Propulsion & Consumables Officer", message: "Resource grids are showing pressure variations. Adjusting feed pressure.", confidence: 92 },
          { sender: "Safety Agent", role: "Hull Integrity & Crew Officer", message: "Subsystem anomaly propagation is detected. Safeguarding hull modules.", confidence: 95 },
          { sender: "Science Agent", role: "Sensor and Analytics Officer", message: "Scanning background stellar noise. Ready for diagnostic calibrations.", confidence: 78 }
        ],
        statuses: {
          "Navigation Agent": "VOTING",
          "Resource Agent": "VOTING",
          "Safety Agent": "VOTING",
          "Science Agent": "VOTING",
          "Mission Commander Agent": "VOTING"
        },
        cards: {
          "Navigation Agent": navRec,
          "Resource Agent": resRec,
          "Safety Agent": safeRec,
          "Science Agent": sciRec
        },
        consensus: {
          action: actionClean,
          score: decision.confidence,
          votes: {
            "Navigation Agent": true,
            "Resource Agent": true,
            "Safety Agent": true,
            "Science Agent": false
          }
        },
        commander: null,
        outcome: null,
        memory,
        timeline: [
          { text: "Event Detected", status: "completed", time: "T+0s" },
          { text: "Agent Analysis Started", status: "completed", time: "T+1s" },
          { text: "Agent Recommendations", status: "completed", time: "T+9s" },
          { text: "Consensus Formed", status: "completed", time: "T+10s" },
          { text: "Commander Decision", status: "active", time: "T+11s" },
          { text: "Mitigation Executing", status: "pending" }
        ]
      },
      {
        header,
        chat: [
          { sender: "Navigation Agent", role: "Trajectory Specialist", message: "Trajectory offsets are drifting. Course correction recommended.", confidence: 89 },
          { sender: "Resource Agent", role: "Propulsion & Consumables Officer", message: "Resource grids are showing pressure variations. Adjusting feed pressure.", confidence: 92 },
          { sender: "Safety Agent", role: "Hull Integrity & Crew Officer", message: "Subsystem anomaly propagation is detected. Safeguarding hull modules.", confidence: 95 },
          { sender: "Science Agent", role: "Sensor and Analytics Officer", message: "Scanning background stellar noise. Ready for diagnostic calibrations.", confidence: 78 },
          { sender: "Commander Agent", role: "Mission Commander", message: decision.reasoning, confidence: decision.confidence }
        ],
        statuses: {
          "Navigation Agent": "VOTING",
          "Resource Agent": "VOTING",
          "Safety Agent": "VOTING",
          "Science Agent": "VOTING",
          "Mission Commander Agent": "EXECUTING"
        },
        cards: {
          "Navigation Agent": navRec,
          "Resource Agent": resRec,
          "Safety Agent": safeRec,
          "Science Agent": sciRec
        },
        consensus: {
          action: actionClean,
          score: decision.confidence,
          votes: {
            "Navigation Agent": true,
            "Resource Agent": true,
            "Safety Agent": true,
            "Science Agent": false
          }
        },
        commander: {
          action: actionClean,
          confidence: decision.confidence,
          reasoning: decision.reasoning,
          expectedOutcome: {
            riskReduction: decision.outcome_details?.risk_reduction || 20,
            successChange: decision.outcome_details?.success_delta || 8
          }
        },
        outcome: null,
        memory,
        timeline: [
          { text: "Event Detected", status: "completed", time: "T+0s" },
          { text: "Agent Analysis Started", status: "completed", time: "T+1s" },
          { text: "Agent Recommendations", status: "completed", time: "T+9s" },
          { text: "Consensus Formed", status: "completed", time: "T+10s" },
          { text: "Commander Decision", status: "completed", time: "T+11s" },
          { text: "Mitigation Executing", status: "active", time: "T+12s" }
        ]
      },
      {
        header,
        chat: [
          { sender: "Navigation Agent", role: "Trajectory Specialist", message: "Trajectory offsets are drifting. Course correction recommended.", confidence: 89 },
          { sender: "Resource Agent", role: "Propulsion & Consumables Officer", message: "Resource grids are showing pressure variations. Adjusting feed pressure.", confidence: 92 },
          { sender: "Safety Agent", role: "Hull Integrity & Crew Officer", message: "Subsystem anomaly propagation is detected. Safeguarding hull modules.", confidence: 95 },
          { sender: "Science Agent", role: "Sensor and Analytics Officer", message: "Scanning background stellar noise. Ready for diagnostic calibrations.", confidence: 78 },
          { sender: "Commander Agent", role: "Mission Commander", message: decision.reasoning, confidence: decision.confidence }
        ],
        statuses: {
          "Navigation Agent": "COMPLETED",
          "Resource Agent": "COMPLETED",
          "Safety Agent": "COMPLETED",
          "Science Agent": "COMPLETED",
          "Mission Commander Agent": "COMPLETED"
        },
        cards: {
          "Navigation Agent": { ...navRec, status: "COMPLETED", lastAction: "Nominal Course" },
          "Resource Agent": { ...resRec, status: "COMPLETED", lastAction: "Power Balanced" },
          "Safety Agent": { ...safeRec, status: "COMPLETED", lastAction: "Shields Configured" },
          "Science Agent": { ...sciRec, status: "COMPLETED", lastAction: "Sensors Normalized" }
        },
        consensus: {
          action: actionClean,
          score: decision.confidence,
          votes: {
            "Navigation Agent": true,
            "Resource Agent": true,
            "Safety Agent": true,
            "Science Agent": false
          }
        },
        commander: {
          action: actionClean,
          confidence: decision.confidence,
          reasoning: decision.reasoning,
          expectedOutcome: {
            riskReduction: decision.outcome_details?.risk_reduction || 20,
            successChange: decision.outcome_details?.success_delta || 8
          }
        },
        outcome: {
          fuel: decision.outcome_details?.fuel_delta || -2,
          power: decision.outcome_details?.power_delta || -15,
          risk: -(decision.outcome_details?.risk_reduction || 20),
          success: decision.outcome_details?.success_delta || 8
        },
        memory,
        timeline: [
          { text: "Event Detected", status: "completed", time: "T+0s" },
          { text: "Agent Analysis Started", status: "completed", time: "T+1s" },
          { text: "Agent Recommendations", status: "completed", time: "T+9s" },
          { text: "Consensus Formed", status: "completed", time: "T+10s" },
          { text: "Commander Decision", status: "completed", time: "T+11s" },
          { text: "Mitigation Executing", status: "completed", time: "T+12s" },
          { text: "Execution Completed", status: "completed", time: "T+15s" }
        ]
      }
    ];

    setReplayStepsData(replaySteps);
    applyReplayStep(replaySteps[0]);
  };

  const applyReplayStep = (step: any) => {
    setActiveEventHeader(step.header);
    setChatStream(step.chat);
    setAgentStatuses(step.statuses);
    setAgentCards(step.cards);
    setConsensusData(step.consensus);
    setCommanderDecision(step.commander);
    setDigitalTwinOutcome(step.outcome);
    setCollaborationTimeline(step.timeline);
    if (step.memory) setAgentMemory(step.memory);
  };

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (isPlayingReplay) {
      interval = setInterval(() => {
        setReplayStepIndex((prevIndex) => {
          const nextIndex = prevIndex + 1;
          if (nextIndex >= replayStepsData.length) {
            setIsPlayingReplay(false);
            return prevIndex;
          }
          applyReplayStep(replayStepsData[nextIndex]);
          return nextIndex;
        });
      }, 2000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isPlayingReplay, replayStepsData]);

  // Helper for status classes
  const getStatusClasses = (status: string) => {
    switch (status) {
      case "ANALYZING":
        return "text-cyan-400 border-cyan-500/35 bg-cyan-950/20";
      case "RECOMMENDING":
        return "text-yellow-400 border-yellow-500/35 bg-yellow-950/20";
      case "SIMULATING":
        return "text-purple-400 border-purple-500/35 bg-purple-950/20";
      case "VOTING":
        return "text-orange-400 border-orange-500/35 bg-orange-950/20";
      case "EXECUTING":
        return "text-emerald-400 border-emerald-500/35 bg-emerald-950/20";
      case "COMPLETED":
      default:
        return "text-slate-400 border-slate-700 bg-slate-900/40";
    }
  };


  // Auto-refresher
  const syncTestingParameters = useCallback(async () => {
    try {
      // 1. Scenario Active Info
      const scRes = await fetch(`http://${actualBackendHost}/api/test/scenario/active`);
      if (scRes.ok) setActiveScenarioInfo(await scRes.json());

      // 2. Resilience Score
      const resRes = await fetch(`http://${actualBackendHost}/api/test/resilience-score`);
      if (resRes.ok) {
        const data = await resRes.json();
        if (data.length > 0) {
          setResilienceScore({
            resilience: data[0].resilience_score,
            survivability: data[0].survivability_score,
            adaptability: data[0].adaptability_score,
            stability: data[0].system_stability,
            recovery_efficiency: data[0].recovery_efficiency
          });
        } else {
          // Dynamic calculation if empty
          calculateLocalResilience();
        }
      }

      // 3. Benchmarks List
      const benchRes = await fetch(`http://${actualBackendHost}/api/test/benchmarks`);
      if (benchRes.ok) setBenchmarks(await benchRes.json());

      // 4. Recovery metrics
      const recRes = await fetch(`http://${actualBackendHost}/api/test/recovery-metrics`);
      if (recRes.ok) setRecoveryLog(await recRes.json());

      // 5. Custom Scenarios saved
      const customRes = await fetch(`http://${actualBackendHost}/api/test/custom-scenarios`);
      if (customRes.ok) setCustomScenarios(await customRes.json());

      // 6. LLM Stats
      const llmMetricsRes = await fetch(`http://${actualBackendHost}/api/llm/metrics`);
      if (llmMetricsRes.ok) {
        const mData = await llmMetricsRes.json();
        setLlmMetrics({
          accuracy: mData.decision_accuracy,
          avg_confidence: mData.avg_confidence,
          success_rate: mData.success_rate,
          reasoning_quality: mData.reasoning_quality
        });
      }

      // 7. Last LLM Decision
      const llmDecRes = await fetch(`http://${actualBackendHost}/api/llm/decisions`);
      if (llmDecRes.ok) {
        const decisions = await llmDecRes.json();
        if (decisions.length > 0) {
          setLastLlmDecision(decisions[0]);
        }
      }

      // 8. Agent decisions history
      const agentDecsRes = await fetch(`http://${actualBackendHost}/api/agent/decisions`);
      if (agentDecsRes.ok) {
        setReplayHistory(await agentDecsRes.json());
      }
    } catch (err) {
      console.warn("Error syncing test center endpoints:", err);
    }
  }, [telemetry]);

  useEffect(() => {
    syncTestingParameters();
    const timer = setInterval(syncTestingParameters, 3000);
    return () => clearInterval(timer);
  }, [syncTestingParameters]);

  const calculateLocalResilience = () => {
    if (!telemetry) return;
    const avgHealth = telemetry.health || 100.0;
    const adaptability = Math.max(0.0, 100.0 - (telemetry.risk_score || 0.0));
    
    // Subsystem stability proxy
    let stdDev = 0;
    if (telemetry.subsystems) {
      const vals = Object.values(telemetry.subsystems).map((s: any) => s.health);
      if (vals.length > 0) {
        const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
        const variance = vals.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / vals.length;
        stdDev = Math.sqrt(variance);
      }
    }
    const stability = Math.max(0.0, 100.0 - stdDev);
    const score = 0.3 * avgHealth + 0.3 * adaptability + 0.2 * 100.0 + 0.2 * stability;
    
    setResilienceScore({
      resilience: parseFloat(score.toFixed(1)),
      survivability: parseFloat(avgHealth.toFixed(1)),
      adaptability: parseFloat(adaptability.toFixed(1)),
      stability: parseFloat(stability.toFixed(1)),
      recovery_efficiency: 100.0
    });
  };

  // Trigger individual anomaly injection
  const triggerInject = async (anomaly: AnomalyTemplate) => {
    try {
      let parsedMults = {};
      try {
        parsedMults = JSON.parse(customMults);
      } catch {
        parsedMults = anomaly.defaultMults;
      }

      const res = await fetch(`http://${actualBackendHost}/api/test/inject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_type: anomaly.name,
          severity: customSeverity,
          duration: customDuration,
          affected_system: anomaly.system,
          propagation_speed: customSpeed,
          probability: 1.0,
          impact_multipliers: parsedMults
        })
      });
      if (res.ok) {
        setSelectedAnomaly(null);
        syncTestingParameters();
      }
    } catch (err) {
      console.error("Inject call failure:", err);
    }
  };

  // Trigger Scenario start
  const handleStartPreset = async (idx: number) => {
    try {
      const res = await fetch(`http://${actualBackendHost}/api/test/scenario/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario_idx: idx })
      });
      if (res.ok) syncTestingParameters();
    } catch (err) {
      console.error("Preset start failure:", err);
    }
  };

  const handleStartCustom = async (id: number) => {
    try {
      const res = await fetch(`http://${actualBackendHost}/api/test/scenario/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario_id: id })
      });
      if (res.ok) syncTestingParameters();
    } catch (err) {
      console.error("Custom scenario start failure:", err);
    }
  };

  const handleStopScenario = async () => {
    try {
      const res = await fetch(`http://${actualBackendHost}/api/test/scenario/stop`, {
        method: "POST"
      });
      if (res.ok) syncTestingParameters();
    } catch (err) {
      console.error("Stop scenario failure:", err);
    }
  };

  // Stress tests
  const triggerStressTest = async (count: number) => {
    try {
      const res = await fetch(`http://${actualBackendHost}/api/test/stress`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ num_events: count, severity: "HIGH" })
      });
      if (res.ok) syncTestingParameters();
    } catch (err) {
      console.error("Stress call failure:", err);
    }
  };

  // Monte carlo stress runs
  const triggerMonteCarlo = async (iterations: number) => {
    try {
      await fetch(`http://${actualBackendHost}/api/test/montecarlo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ iterations })
      });
    } catch (err) {
      console.error("Monte Carlo failure:", err);
    }
  };

  // Add event to timeline builder
  const addTimelineEvent = () => {
    // Find template for matching system
    let matchedTemplate: AnomalyTemplate | null = null;
    for (const cat in anomalies) {
      const found = anomalies[cat].find(a => a.name === selectedBuilderAnomaly);
      if (found) {
        matchedTemplate = found;
        break;
      }
    }
    if (!matchedTemplate) return;

    const newEv: CustomScenarioEvent = {
      event_type: selectedBuilderAnomaly,
      severity: "HIGH",
      duration: 30,
      affected_system: matchedTemplate.system,
      propagation_speed: 1.0,
      probability: 1.0,
      impact_multipliers: matchedTemplate.defaultMults,
      trigger_time: timelineTriggerTime
    };

    setTimelineEvents((prev) => [...prev, newEv].sort((a, b) => a.trigger_time - b.trigger_time));
    setTimelineTriggerTime((prev) => prev + 10);
  };

  // Save Custom Scenario
  const saveCustomScenario = async () => {
    if (!customScenarioName || timelineEvents.length === 0) return;
    try {
      const res = await fetch(`http://${actualBackendHost}/api/test/custom-scenario/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: customScenarioName,
          description: customScenarioDesc || "Custom structured timed simulation test sequence.",
          events: timelineEvents
        })
      });
      if (res.ok) {
        setCustomScenarioName("");
        setCustomScenarioDesc("");
        setTimelineEvents([]);
        syncTestingParameters();
      }
    } catch (err) {
      console.error("Save custom scenario failed:", err);
    }
  };

  // Recharts resilience timeline
  const resilienceChartData = benchmarks.slice().reverse().map((b, idx) => ({
    index: idx + 1,
    resilience: b.mission_impact ? (b.mission_impact.health || 80.0) : 80.0,
    name: b.scenario_name.split(" ")[0]
  }));

  // Render Category Tab contents
  const activeAnomalyItems = anomalies[activeCategory] || [];

  return (
    <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 text-slate-100 font-mono text-xs select-none">
      
      {/* 1. TOP HEADER SUMMARY & METRICS */}
      <div className="xl:col-span-12 grid grid-cols-1 md:grid-cols-5 gap-3 p-4 bg-gradient-to-r from-rose-950/40 via-slate-950/60 to-rose-950/40 border border-rose-900/30 rounded-xl">
        
        {/* Radial Index Meter */}
        <div className="flex items-center gap-3 border-r border-slate-900/80 pr-2">
          <div className="p-2.5 bg-gradient-to-tr from-rose-600 to-amber-600 rounded-lg shadow-lg shadow-rose-950/20">
            <Shield className="w-6 h-6 text-white animate-pulse" />
          </div>
          <div>
            <span className="text-[9px] text-slate-500 uppercase block font-bold">Spacecraft resilience</span>
            <span className="text-xl font-black text-rose-400 mt-0.5 block">{resilienceScore.resilience} <span className="text-slate-500 font-normal text-xs">/100</span></span>
          </div>
        </div>

        {/* Resilience Components */}
        <div className="flex flex-col justify-center gap-1">
          <div className="flex justify-between text-[10px]">
            <span className="text-slate-400">Survivability</span>
            <span className="text-cyan-400 font-bold">{resilienceScore.survivability}%</span>
          </div>
          <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden">
            <div className="bg-cyan-500 h-full transition-all duration-500" style={{ width: `${resilienceScore.survivability}%` }} />
          </div>
        </div>

        <div className="flex flex-col justify-center gap-1">
          <div className="flex justify-between text-[10px]">
            <span className="text-slate-400">Adaptability</span>
            <span className="text-emerald-450 font-bold">{resilienceScore.adaptability}%</span>
          </div>
          <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden">
            <div className="bg-emerald-500 h-full transition-all duration-500" style={{ width: `${resilienceScore.adaptability}%` }} />
          </div>
        </div>

        <div className="flex flex-col justify-center gap-1">
          <div className="flex justify-between text-[10px]">
            <span className="text-slate-400">System Stability</span>
            <span className="text-amber-400 font-bold">{resilienceScore.stability}%</span>
          </div>
          <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden">
            <div className="bg-amber-500 h-full transition-all duration-500" style={{ width: `${resilienceScore.stability}%` }} />
          </div>
        </div>

        <div className="flex flex-col justify-center gap-1">
          <div className="flex justify-between text-[10px]">
            <span className="text-slate-400">Recovery Efficiency</span>
            <span className="text-indigo-400 font-bold">{resilienceScore.recovery_efficiency}%</span>
          </div>
          <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden">
            <div className="bg-indigo-500 h-full transition-all duration-500" style={{ width: `${resilienceScore.recovery_efficiency}%` }} />
          </div>
        </div>

      </div>

      {/* 2. MAIN ACTIVE CONTROL HEADER BAR */}
      <div className="xl:col-span-12 p-3 bg-slate-950/80 border border-slate-900/60 rounded-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-ping" />
          <span className="font-bold text-slate-200">
            {activeScenarioInfo.active 
              ? `Scenario In Progress: '${activeScenarioInfo.name}' (T+${Math.floor(activeScenarioInfo.timer)}s)` 
              : "READY FOR LAB TESTS / SCENARIO INJECTION"}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {activeScenarioInfo.active && (
            <button
              onClick={handleStopScenario}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-950 hover:bg-rose-900 text-rose-400 rounded-lg font-bold border border-rose-800/20"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
              STOP TEST RUN
            </button>
          )}

          <div className="flex items-center gap-1.5 bg-slate-900 px-2.5 py-1.5 rounded-lg border border-slate-800">
            <span className="text-slate-500 text-[10px] font-bold uppercase">Inject:</span>
            <button onClick={() => triggerStressTest(3)} className="px-2 py-0.5 hover:bg-slate-850 rounded text-cyan-400 font-bold">STRESS x3</button>
            <button onClick={() => triggerStressTest(5)} className="px-2 py-0.5 hover:bg-slate-850 rounded text-amber-400 font-bold">STRESS x5</button>
            <button onClick={() => triggerMonteCarlo(500)} className="px-2 py-0.5 hover:bg-slate-850 rounded text-rose-400 font-bold">MONTE CARLO 500</button>
          </div>
        </div>
      </div>

      {/* 3. LEFT AREA: QUICK ANOMALY INJECTION GRID & BUILDER (7 Cols) */}
      <div className="xl:col-span-7 flex flex-col gap-4">
        
        {/* Quick Anomaly Injection tab panel */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md">
          
          <div className="flex items-center justify-between border-b border-slate-900 pb-2 mb-3">
            <h3 className="text-xs font-bold tracking-widest text-rose-400 uppercase flex items-center gap-2">
              <Zap className="w-4 h-4 text-rose-400" />
              Quick Anomaly Injector
            </h3>
            <span className="text-[10px] text-slate-500">28+ SPACE DECAY VECTORS REGISTERED</span>
          </div>

          {/* Categories Horizontal Tabs */}
          <div className="flex flex-wrap gap-1.5 mb-3.5 bg-slate-950/50 p-1 rounded-lg border border-slate-900">
            {Object.keys(anomalies).map((cat) => (
              <button
                key={cat}
                onClick={() => {
                  setActiveCategory(cat);
                  setSelectedAnomaly(null);
                }}
                className={`px-3 py-1.5 rounded font-bold transition-all ${
                  activeCategory === cat 
                    ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" 
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          {/* Anomaly Buttons Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
            {activeAnomalyItems.map((anomaly) => {
              const isSelected = selectedAnomaly?.name === anomaly.name;
              const isCurrentlyActive = activeEvents.some(ae => ae.event_type === anomaly.name);
              
              return (
                <div 
                  key={anomaly.name}
                  onClick={() => {
                    setSelectedAnomaly(anomaly);
                    setCustomMults(JSON.stringify(anomaly.defaultMults));
                  }}
                  className={`p-2.5 rounded-lg border cursor-pointer transition-all flex flex-col gap-1 justify-between ${
                    isCurrentlyActive 
                      ? "bg-rose-950/15 border-rose-500/50 shadow-md shadow-rose-950/10" 
                      : isSelected 
                        ? "bg-slate-900 border-slate-700 font-bold" 
                        : "bg-slate-950/45 border-slate-900 hover:bg-slate-900/30"
                  }`}
                >
                  <div className="flex items-center justify-between gap-1.5">
                    <span className={`font-bold tracking-wide ${isCurrentlyActive ? "text-rose-450 font-black animate-pulse" : "text-slate-200"}`}>
                      {anomaly.name}
                    </span>
                    {isCurrentlyActive && (
                      <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping shrink-0" />
                    )}
                  </div>
                  <p className="text-[10px] text-slate-500 leading-snug line-clamp-2">{anomaly.desc}</p>
                </div>
              );
            })}
          </div>

          {/* Injection Parameters Configuration (When anomaly is selected) */}
          {selectedAnomaly && (
            <div className="mt-4 p-3.5 bg-slate-900/40 border border-slate-850 rounded-lg space-y-3 animate-fade-in">
              <div className="flex items-center justify-between border-b border-slate-850 pb-2">
                <span className="font-bold text-rose-400">Configure Injection: {selectedAnomaly.name}</span>
                <button onClick={() => setSelectedAnomaly(null)} className="text-slate-500 hover:text-slate-300">Close</button>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div>
                  <label className="text-[9px] text-slate-500 uppercase font-bold block mb-1">Severity</label>
                  <select 
                    value={customSeverity} 
                    onChange={e => setCustomSeverity(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-900 p-1 rounded outline-none"
                  >
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH</option>
                    <option value="CRITICAL">CRITICAL</option>
                    <option value="CATASTROPHIC">CATASTROPHIC</option>
                  </select>
                </div>
                <div>
                  <label className="text-[9px] text-slate-500 uppercase font-bold block mb-1">Duration (s)</label>
                  <input 
                    type="number" 
                    value={customDuration} 
                    onChange={e => setCustomDuration(parseFloat(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-900 p-1 rounded outline-none text-slate-255"
                  />
                </div>
                <div>
                  <label className="text-[9px] text-slate-500 uppercase font-bold block mb-1">Prop. Speed</label>
                  <input 
                    type="number" 
                    step="0.1" 
                    value={customSpeed} 
                    onChange={e => setCustomSpeed(parseFloat(e.target.value))}
                    className="w-full bg-slate-950 border border-slate-900 p-1 rounded outline-none text-slate-255"
                  />
                </div>
                <div>
                  <label className="text-[9px] text-slate-500 uppercase font-bold block mb-1">Affected System</label>
                  <input 
                    type="text" 
                    disabled 
                    value={selectedAnomaly.system} 
                    className="w-full bg-slate-950 border border-slate-900 p-1 rounded text-slate-500 select-none outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-[9px] text-slate-500 uppercase font-bold block mb-1">Decay multipliers JSON mapping</label>
                <input 
                  type="text" 
                  value={customMults} 
                  onChange={e => setCustomMults(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-900 p-1.5 rounded font-mono text-[10px] outline-none text-emerald-450"
                />
              </div>

              <button
                onClick={() => triggerInject(selectedAnomaly)}
                className="w-full py-2 bg-gradient-to-r from-rose-700 to-amber-700 hover:from-rose-650 hover:to-amber-650 text-white font-bold tracking-widest rounded"
              >
                TRIGGER DYNAMIC DECAY INJECTION
              </button>
            </div>
          )}

        </div>

        {/* Custom Timeline Builder */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md">
          <h3 className="text-xs font-bold tracking-widest text-rose-400 border-b border-slate-900 pb-2 mb-3 uppercase flex items-center gap-2">
            <Sliders className="w-4 h-4 text-rose-400" />
            Custom Scenario Builder (Timed timeline)
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
            
            {/* Input configs */}
            <div className="md:col-span-5 space-y-3">
              <div>
                <label className="text-[9px] text-slate-500 block mb-0.5 uppercase font-bold">Scenario Name</label>
                <input 
                  type="text" 
                  placeholder="e.g., Solar Storm Complex" 
                  value={customScenarioName}
                  onChange={e => setCustomScenarioName(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-850 p-1.5 rounded text-slate-200 outline-none"
                />
              </div>

              <div>
                <label className="text-[9px] text-slate-500 block mb-0.5 uppercase font-bold">Description</label>
                <textarea 
                  rows={2} 
                  placeholder="Scenario description..." 
                  value={customScenarioDesc}
                  onChange={e => setCustomScenarioDesc(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-850 p-1.5 rounded text-slate-200 outline-none"
                />
              </div>

              <div className="border-t border-slate-900 pt-2.5 space-y-2">
                <span className="font-bold text-slate-300 text-[10px] block uppercase">Add timed event:</span>
                
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[8px] text-slate-500 uppercase block font-bold">Anomaly</label>
                    <select 
                      value={selectedBuilderAnomaly} 
                      onChange={e => setSelectedBuilderAnomaly(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-850 p-1 rounded outline-none text-slate-255"
                    >
                      {Object.keys(anomalies).flatMap(cat => anomalies[cat]).map(a => (
                        <option key={a.name} value={a.name}>{a.name}</option>
                      ))}
                    </select>
                  </div>
                  
                  <div>
                    <label className="text-[8px] text-slate-500 uppercase block font-bold">Trigger at T+ (s)</label>
                    <input 
                      type="number" 
                      value={timelineTriggerTime} 
                      onChange={e => setTimelineTriggerTime(parseInt(e.target.value))}
                      className="w-full bg-slate-900 border border-slate-850 p-1 rounded outline-none text-slate-255"
                    />
                  </div>
                </div>

                <button 
                  onClick={addTimelineEvent} 
                  className="w-full py-1 bg-slate-900 hover:bg-slate-850 border border-slate-800 text-cyan-400 font-bold rounded flex items-center justify-center gap-1"
                >
                  <Plus className="w-3.5 h-3.5" /> ADD EVENT
                </button>
              </div>
            </div>

            {/* Timeline Events list */}
            <div className="md:col-span-7 flex flex-col justify-between">
              <div>
                <label className="text-[9px] text-slate-500 block mb-1.5 uppercase font-bold">Timeline Preview</label>
                <div className="max-h-[160px] overflow-y-auto border border-slate-900 rounded bg-slate-950 p-2 space-y-1.5">
                  {timelineEvents.map((ev, i) => (
                    <div key={i} className="flex items-center justify-between bg-slate-900/40 px-2 py-1.5 border border-slate-850/60 rounded">
                      <div className="flex items-center gap-2">
                        <span className="text-rose-400 font-bold font-mono">T+{ev.trigger_time}s</span>
                        <ArrowRight className="w-3.5 h-3.5 text-slate-650" />
                        <span className="text-slate-200">{ev.event_type}</span>
                      </div>
                      <button 
                        onClick={() => setTimelineEvents(prev => prev.filter((_, idx) => idx !== i))}
                        className="text-slate-600 hover:text-rose-400"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                  {timelineEvents.length === 0 && (
                    <span className="text-slate-600 italic block py-4 text-center">Timeline empty. Build event sequence.</span>
                  )}
                </div>
              </div>

              <button
                onClick={saveCustomScenario}
                disabled={!customScenarioName || timelineEvents.length === 0}
                className="w-full py-2 bg-gradient-to-r from-cyan-700 to-indigo-700 hover:from-cyan-650 hover:to-indigo-650 disabled:from-slate-900 disabled:to-slate-900 disabled:text-slate-600 text-white font-bold tracking-widest rounded flex items-center justify-center gap-2 mt-3"
              >
                <Save className="w-4 h-4" /> SAVE CUSTOM TIMELINE
              </button>
            </div>

          </div>

        </div>

      </div>

      {/* 4. RIGHT AREA: TABS PANEL */}
      <div className="xl:col-span-5 flex flex-col gap-4">
        
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md flex-1 flex flex-col gap-4">
          
          {/* Tab Selector Header */}
          <div className="flex items-center justify-between border-b border-slate-900 pb-2">
            <div className="flex gap-2">
              <button
                onClick={() => setRightPanelTab("collaboration")}
                className={`px-3 py-1 text-[10px] uppercase font-bold tracking-wider rounded transition-all ${
                  rightPanelTab === "collaboration"
                    ? "bg-purple-650/20 border border-purple-500/35 text-purple-400 font-extrabold"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                MISSION AGENT COLLABORATION CENTER
              </button>
              <button
                onClick={() => setRightPanelTab("analysis")}
                className={`px-3 py-1 text-[10px] uppercase font-bold tracking-wider rounded transition-all ${
                  rightPanelTab === "analysis"
                    ? "bg-purple-650/20 border border-purple-500/35 text-purple-400 font-extrabold"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                System Analysis
              </button>
            </div>
            
            {/* Live WS connection status vs Replay Active indicator */}
            <div>
              {isReplayActive ? (
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-955/50 border border-amber-800/30 text-amber-400 font-extrabold animate-pulse uppercase">
                  REPLAY ACTIVE
                </span>
              ) : (
                <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold border uppercase flex items-center gap-1 ${
                  wsStatus === "connected"
                    ? "bg-emerald-955/40 border-emerald-800/30 text-emerald-400"
                    : "bg-rose-955/40 border-rose-800/30 text-rose-405"
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${wsStatus === "connected" ? "bg-emerald-400 animate-ping" : "bg-rose-400"}`} />
                  {wsStatus === "connected" ? "LIVE STREAM" : "OFFLINE"}
                </span>
              )}
            </div>
          </div>

          {rightPanelTab === "collaboration" ? (
            // TAB 1: MISSION AGENT COLLABORATION CENTER
            <div className="flex-1 flex flex-col gap-4 overflow-y-auto max-h-[820px] pr-1">
              
              {/* SECTION 1: ACTIVE EVENT HEADER */}
              <div className="p-3 bg-gradient-to-r from-slate-900/60 to-purple-950/15 border border-purple-900/20 rounded-lg flex items-center justify-between">
                <div>
                  <span className="text-[9px] text-slate-500 font-bold block uppercase">Current Event</span>
                  <span className={`text-xs font-black tracking-wide ${activeEventHeader ? "text-rose-400 animate-pulse" : "text-emerald-450"}`}>
                    {activeEventHeader ? activeEventHeader.eventType.toUpperCase() : "NOMINAL OPERATION"}
                  </span>
                </div>
                <div className="text-center">
                  <span className="text-[9px] text-slate-500 font-bold block uppercase">Severity</span>
                  <span className={`text-[10px] font-bold ${activeEventHeader?.severity === "CRITICAL" || activeEventHeader?.severity === "HIGH" ? "text-rose-450" : "text-slate-400"}`}>
                    {activeEventHeader ? activeEventHeader.severity : "NORMAL"}
                  </span>
                </div>
                <div className="text-center">
                  <span className="text-[9px] text-slate-500 font-bold block uppercase">Affected</span>
                  <span className="text-[10px] text-slate-300 font-mono">
                    {activeEventHeader ? activeEventHeader.affected : "None"}
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-[9px] text-slate-500 font-bold block uppercase">Risk Factor</span>
                  <span className="text-xs text-rose-400 font-black">
                    {activeEventHeader ? `${activeEventHeader.risk}%` : "12%"}
                  </span>
                </div>
              </div>

              {/* SECTION 12: DECISION REPLAY MODE PLAYER CONTROLS */}
              <div className="p-2.5 bg-slate-900/40 border border-slate-900 rounded-lg space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[9px] text-slate-400 font-bold uppercase flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    Decision Replay Deck
                  </span>
                  {isReplayActive && (
                    <button 
                      onClick={() => {
                        setIsReplayActive(false);
                        setSelectedReplayId(null);
                        setChatStream([]);
                        setActiveEventHeader(null);
                        setDigitalTwinOutcome(null);
                        setConsensusData(null);
                        setCommanderDecision(null);
                        setAgentStatuses({
                          "Navigation Agent": "COMPLETED",
                          "Resource Agent": "COMPLETED",
                          "Safety Agent": "COMPLETED",
                          "Science Agent": "COMPLETED",
                          "Mission Commander Agent": "COMPLETED"
                        });
                        setAgentCards({
                          "Navigation Agent": { recommendation: "No Action", confidence: 0, reasoning: "System nominal.", status: "COMPLETED", lastAction: "Idle" },
                          "Resource Agent": { recommendation: "No Action", confidence: 0, reasoning: "System nominal.", status: "COMPLETED", lastAction: "Idle" },
                          "Safety Agent": { recommendation: "No Action", confidence: 0, reasoning: "System nominal.", status: "COMPLETED", lastAction: "Idle" },
                          "Science Agent": { recommendation: "No Action", confidence: 0, reasoning: "System nominal.", status: "COMPLETED", lastAction: "Idle" }
                        });
                      }}
                      className="text-[9px] text-rose-400 hover:underline font-bold"
                    >
                      Exit Replay Mode
                    </button>
                  )}
                </div>
                
                <div className="flex items-center gap-2 flex-wrap">
                  {/* Select past decision */}
                  <select
                    value={selectedReplayId || ""}
                    onChange={(e) => {
                      const id = parseInt(e.target.value);
                      setSelectedReplayId(id);
                      const dec = replayHistory.find(d => d.id === id);
                      if (dec) loadDecisionReplay(dec);
                    }}
                    className="flex-1 bg-slate-950 border border-slate-900 text-slate-300 rounded p-1 text-[10px] outline-none font-mono"
                  >
                    <option value="" disabled>Select historical run to replay...</option>
                    {replayHistory.map(dec => (
                      <option key={dec.id} value={dec.id}>
                        {new Date(dec.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} - {dec.chosen_action.split("_").slice(2).join(" ").toUpperCase()} ({dec.confidence}%)
                      </option>
                    ))}
                  </select>

                  {/* Playback Buttons */}
                  <div className="flex items-center gap-1 bg-slate-950 p-0.5 border border-slate-900 rounded">
                    <button
                      onClick={() => {
                        if (!isReplayActive && replayHistory.length > 0) {
                          setSelectedReplayId(replayHistory[0].id);
                          loadDecisionReplay(replayHistory[0]);
                        } else if (isReplayActive) {
                          setReplayStepIndex(0);
                          applyReplayStep(replayStepsData[0]);
                        }
                      }}
                      className="p-1 hover:bg-slate-900 text-slate-400 hover:text-slate-200 rounded"
                      title="Rewind"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => {
                        if (!isReplayActive) return;
                        setIsPlayingReplay(!isPlayingReplay);
                      }}
                      className="p-1 hover:bg-slate-900 text-slate-400 hover:text-slate-200 rounded"
                      title={isPlayingReplay ? "Pause" : "Play"}
                    >
                      {isPlayingReplay ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                    </button>
                    <button
                      onClick={() => {
                        if (!isReplayActive) return;
                        setIsPlayingReplay(false);
                        const nextStep = Math.min(replayStepsData.length - 1, replayStepIndex + 1);
                        setReplayStepIndex(nextStep);
                        applyReplayStep(replayStepsData[nextStep]);
                      }}
                      className="p-1 hover:bg-slate-900 text-slate-400 hover:text-slate-200 rounded"
                      title="Forward Step"
                    >
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => {
                        if (!isReplayActive) return;
                        setIsPlayingReplay(false);
                        const lastStep = replayStepsData.length - 1;
                        setReplayStepIndex(lastStep);
                        applyReplayStep(replayStepsData[lastStep]);
                      }}
                      className="p-1 hover:bg-slate-900 text-slate-400 hover:text-slate-200 rounded"
                      title="Fast Forward to End"
                    >
                      <FastForward className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>

              {/* SECTION 2: AGENT CONVERSATION STREAM */}
              <div className="flex-1 min-h-[180px] max-h-[260px] border border-slate-900 rounded-lg bg-slate-950/80 p-3 overflow-y-auto flex flex-col gap-2.5 shadow-inner">
                <span className="text-[9px] text-slate-500 uppercase tracking-widest block font-bold border-b border-slate-900 pb-1.5">
                  Crew Debate Channel
                </span>
                
                <div className="flex-1 flex flex-col gap-2 overflow-y-auto">
                  {chatStream.map((msg, i) => {
                    const isLast = i === chatStream.length - 1;
                    return (
                      <div key={i} className={`p-2.5 rounded-lg border max-w-[85%] animate-fade-in ${
                        msg.sender.includes("Commander") 
                          ? "bg-purple-950/25 border-purple-800/40 text-purple-200 self-end ml-auto shadow-sm shadow-purple-950/30" 
                          : "bg-slate-900/60 border-slate-850/60 text-slate-200 self-start mr-auto"
                      }`}>
                        <div className="flex justify-between items-center gap-2 mb-1">
                          <span className="font-bold text-[10px] text-cyan-400">{msg.sender} <span className="text-slate-550 font-normal">({msg.role})</span></span>
                          {msg.confidence && <span className="text-[9px] text-amber-400 font-mono font-bold">Conf: {msg.confidence}%</span>}
                        </div>
                        <p className="text-[10px] leading-relaxed font-mono">
                          {isLast ? <Typewriter text={msg.message} /> : msg.message}
                        </p>
                      </div>
                    );
                  })}
                  {chatStream.length === 0 && (
                    <span className="text-slate-650 italic text-center block py-10">
                      Awaiting debate event trigger...
                    </span>
                  )}
                  <div ref={chatEndRef} />
                </div>
              </div>

              {/* SECTION 3 & 4: AGENT CARDS */}
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(agentCards).map(([name, card]) => {
                  const status = agentStatuses[name] || card.status;
                  const isCommander = name.includes("Commander");
                  if (isCommander) return null;

                  return (
                    <div key={name} className="p-2.5 bg-slate-950/90 border border-slate-900 rounded-lg flex flex-col justify-between gap-1.5 relative overflow-hidden group hover:border-slate-800 transition-all">
                      <div className="flex items-center justify-between border-b border-slate-900/60 pb-1">
                        <span className="font-bold text-[10px] text-slate-200 group-hover:text-cyan-405 transition-colors">{name}</span>
                        <span className={`text-[8px] font-mono px-1 py-0.2 rounded border font-bold ${getStatusClasses(status)}`}>
                          {status}
                        </span>
                      </div>
                      
                      <div className="space-y-1">
                        <div className="flex justify-between text-[9px]">
                          <span className="text-slate-550">Rec:</span>
                          <span className="text-cyan-300 font-bold max-w-[100px] truncate" title={card.recommendation}>{card.recommendation}</span>
                        </div>
                        <div className="flex justify-between text-[9px]">
                          <span className="text-slate-550">Confidence:</span>
                          <span className="text-amber-400 font-mono font-bold">{card.confidence}%</span>
                        </div>
                        <p className="text-[8px] text-slate-400 leading-snug line-clamp-2" title={card.reasoning}>
                          {card.reasoning}
                        </p>
                      </div>

                      <div className="border-t border-slate-905/60 pt-1 mt-0.5 flex justify-between text-[8px] text-slate-500 font-mono">
                        <span>Last Action:</span>
                        <span className="text-slate-400 font-bold truncate max-w-[80px]">{card.lastAction}</span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* SECTION 5: AGENT CONFIDENCE CHART & SECTION 11: AGENT MEMORY DISPLAY */}
              <div className="grid grid-cols-2 gap-3 p-3 bg-slate-955/80 border border-slate-900 rounded-lg">
                
                {/* Confidence Bars */}
                <div className="space-y-2 border-r border-slate-900/60 pr-2">
                  <span className="text-[9px] text-slate-500 uppercase tracking-wider block font-bold">Confidence matrix</span>
                  <div className="space-y-1.5">
                    {Object.entries(agentCards).map(([name, card]) => (
                      <div key={name} className="space-y-0.5">
                        <div className="flex justify-between text-[8px] font-mono">
                          <span className="text-slate-400 truncate max-w-[90px]">{name.split(" ")[0]} Specialist</span>
                          <span className="text-amber-450 font-bold">{card.confidence}%</span>
                        </div>
                        <div className="w-full bg-slate-900 rounded-full h-1 overflow-hidden">
                          <div 
                            className={`h-full rounded-full transition-all duration-700 ${
                              name.includes("Navigation") ? "bg-cyan-500" : name.includes("Resource") ? "bg-orange-500" : name.includes("Safety") ? "bg-rose-500" : "bg-emerald-505"
                            }`} 
                            style={{ width: `${card.confidence}%` }} 
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Agent Memory display */}
                <div className="space-y-2">
                  <span className="text-[9px] text-slate-500 uppercase tracking-wider block font-bold">Historical memory cache</span>
                  {agentMemory ? (
                    <div className="space-y-1 text-[9px] leading-relaxed">
                      <div>
                        <span className="text-slate-550 block text-[8px]">Previous Event match:</span>
                        <span className="text-slate-200 font-bold font-mono">{agentMemory.previousEvent}</span>
                      </div>
                      <div>
                        <span className="text-slate-550 block text-[8px]">Best historical action:</span>
                        <span className="text-cyan-400 font-bold">{agentMemory.bestAction}</span>
                      </div>
                      <div className="flex justify-between items-center border-t border-slate-900 pt-1 mt-1 font-mono">
                        <span className="text-slate-550 text-[8px]">Historical success:</span>
                        <span className="text-emerald-450 font-bold">{agentMemory.successRate}%</span>
                      </div>
                    </div>
                  ) : (
                    <div className="h-full flex items-center justify-center text-slate-650 italic text-[9px]">
                      Awaiting cache lookup...
                    </div>
                  )}
                </div>

              </div>

              {/* SECTION 6: CONSENSUS ENGINE VIEW & SECTION 7: COMMANDER DECISION PANEL */}
              <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
                
                {/* Consensus Gauge (Col span 5) */}
                <div className="md:col-span-5 p-3.5 bg-slate-950/60 border border-slate-900 rounded-lg flex flex-col justify-between gap-2.5">
                  <div>
                    <span className="text-[9px] text-slate-500 uppercase tracking-wider block font-bold mb-1">Consensus engine</span>
                    <div className="flex items-center gap-2">
                      <div className="relative w-12 h-12 flex items-center justify-center shrink-0 border border-purple-500/20 rounded-full bg-slate-950 shadow-md shadow-purple-950/10">
                        <span className="text-[11px] font-black text-purple-400">{consensusData ? `${consensusData.score}%` : "0%"}</span>
                      </div>
                      <div className="min-w-0">
                        <span className="text-[8px] text-slate-550 block font-bold">Consensus Decision</span>
                        <span className="text-[10px] text-slate-200 font-bold truncate block">{consensusData ? consensusData.action : "AWAITING"}</span>
                      </div>
                    </div>
                  </div>

                  <div className="border-t border-slate-900 pt-2 space-y-1">
                    <span className="text-[8px] text-slate-500 uppercase block font-bold">Voter Matrix</span>
                    <div className="grid grid-cols-2 gap-1 text-[8px] font-mono">
                      {consensusData ? (
                        Object.entries(consensusData.votes).map(([name, vote]) => (
                          <div key={name} className="flex items-center justify-between bg-slate-900/40 p-1 border border-slate-850/50 rounded animate-fade-in">
                            <span className="text-slate-400 truncate max-w-[60px]">{name.split(" ")[0]}</span>
                            {vote ? (
                              <span className="text-emerald-400 font-bold bg-emerald-950/20 px-1 py-0.2 rounded border border-emerald-800/10">YES</span>
                            ) : (
                              <span className="text-rose-450 font-bold bg-rose-955/20 px-1 py-0.2 rounded border border-rose-800/10">NO</span>
                            )}
                          </div>
                        ))
                      ) : (
                        <span className="text-slate-650 italic col-span-2 text-center py-1">Voters idle</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Commander Decision panel (Col span 7) */}
                <div className="md:col-span-7 p-3.5 bg-gradient-to-tr from-purple-950/20 to-slate-950 border border-purple-800/40 rounded-lg shadow-lg shadow-purple-950/10 flex flex-col justify-between gap-2 relative">
                  <div className="absolute top-0 right-0 w-16 h-16 bg-purple-500/5 blur-xl pointer-events-none rounded-full" />
                  <div className="flex items-center justify-between border-b border-purple-900/40 pb-1">
                    <span className="font-bold text-[10px] text-purple-400 uppercase tracking-widest flex items-center gap-1.5 animate-pulse">
                      <Brain className="w-3.5 h-3.5 text-purple-400" />
                      Commander command
                    </span>
                    <span className="text-[8px] text-slate-400 font-mono">Autonomy Core</span>
                  </div>

                  {commanderDecision ? (
                    <div className="space-y-1.5 flex-1 flex flex-col justify-between animate-fade-in">
                      <div>
                        <span className="text-[8px] text-slate-500 block uppercase">Selected Mitigation Action</span>
                        <span className="text-[11px] text-emerald-450 font-black tracking-wide font-mono block">{commanderDecision.action}</span>
                      </div>
                      <p className="text-[8.5px] text-purple-200 leading-relaxed font-mono border-l-2 border-purple-500/50 pl-2">
                        {commanderDecision.reasoning}
                      </p>
                      
                      <div className="grid grid-cols-2 gap-1.5 text-[8.5px] font-mono border-t border-purple-900/30 pt-1.5 mt-1">
                        <div className="bg-slate-950/45 p-1 rounded border border-purple-950/50">
                          <span className="text-slate-550 block">Success probability</span>
                          <span className="text-emerald-450 font-bold">+{commanderDecision.expectedOutcome.successChange}%</span>
                        </div>
                        <div className="bg-slate-950/45 p-1 rounded border border-purple-950/50">
                          <span className="text-slate-550 block">Risk score change</span>
                          <span className="text-emerald-450 font-bold">-{commanderDecision.expectedOutcome.riskReduction}%</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="flex-1 flex items-center justify-center text-slate-650 italic text-[9px] py-10">
                      Awaiting Commander decision finalization...
                    </div>
                  )}
                </div>

              </div>

              {/* SECTION 8: DECISION TIMELINE & SECTION 9: DIGITAL TWIN OUTCOME */}
              <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
                
                {/* Decision Timeline (Col span 7) */}
                <div className="md:col-span-7 p-3.5 bg-slate-950/80 border border-slate-900 rounded-lg">
                  <span className="text-[9px] text-slate-500 uppercase tracking-wider block font-bold border-b border-slate-900 pb-1.5 mb-2">
                    Decision lifecycle progression
                  </span>

                  <div className="space-y-2 font-mono text-[9px] max-h-[160px] overflow-y-auto">
                    {collaborationTimeline.map((step, idx) => (
                      <div key={idx} className="flex items-start gap-2.5 animate-fade-in">
                        <div className="flex flex-col items-center shrink-0">
                          <div className={`w-2 h-2 rounded-full border ${
                            step.status === "completed" 
                              ? "bg-emerald-500 border-emerald-450" 
                              : step.status === "active" 
                                ? "bg-amber-500 border-amber-400 animate-pulse" 
                                : "bg-slate-900 border-slate-800"
                          }`} />
                          {idx < collaborationTimeline.length - 1 && (
                            <div className="w-0.5 h-4 bg-slate-900/60" />
                          )}
                        </div>
                        <div className="flex justify-between flex-1 text-[8.5px]">
                          <span className={step.status === "completed" ? "text-slate-300 font-bold" : step.status === "active" ? "text-amber-400 font-bold" : "text-slate-600"}>
                            {step.text}
                          </span>
                          <span className="text-slate-500 font-normal">{step.time || "--:--:--"}</span>
                        </div>
                      </div>
                    ))}
                    {collaborationTimeline.length === 0 && (
                      <span className="text-slate-650 italic text-center block py-4">Timeline idle</span>
                    )}
                  </div>
                </div>

                {/* Digital Twin Prediction Outcome (Col span 5) */}
                <div className="md:col-span-5 p-3.5 bg-slate-950/60 border border-slate-900 rounded-lg flex flex-col justify-between">
                  <span className="text-[9px] text-slate-500 uppercase tracking-wider block font-bold border-b border-slate-900 pb-1.5 mb-2">
                    Predictive deltas
                  </span>
                  
                  {digitalTwinOutcome ? (
                    <div className="space-y-1 text-[10px] font-mono animate-fade-in">
                      <div className="flex justify-between items-center bg-slate-900/20 px-2 py-0.5 rounded border border-slate-900">
                        <span className="text-slate-400">Fuel Impact</span>
                        <span className={`font-bold ${digitalTwinOutcome.fuel >= 0 ? "text-emerald-450" : "text-rose-450"}`}>
                          {digitalTwinOutcome.fuel >= 0 ? `+${digitalTwinOutcome.fuel}%` : `${digitalTwinOutcome.fuel}%`}
                        </span>
                      </div>
                      <div className="flex justify-between items-center bg-slate-900/20 px-2 py-0.5 rounded border border-slate-900">
                        <span className="text-slate-400">Power Impact</span>
                        <span className={`font-bold ${digitalTwinOutcome.power >= 0 ? "text-emerald-450" : "text-rose-450"}`}>
                          {digitalTwinOutcome.power >= 0 ? `+${digitalTwinOutcome.power}%` : `${digitalTwinOutcome.power}%`}
                        </span>
                      </div>
                      <div className="flex justify-between items-center bg-slate-900/20 px-2 py-0.5 rounded border border-slate-900">
                        <span className="text-slate-400">Risk Change</span>
                        <span className={`font-bold ${digitalTwinOutcome.risk >= 0 ? "text-rose-450" : "text-emerald-450"}`}>
                          {digitalTwinOutcome.risk >= 0 ? `+${digitalTwinOutcome.risk}%` : `${digitalTwinOutcome.risk}%`}
                        </span>
                      </div>
                      <div className="flex justify-between items-center bg-slate-900/20 px-2 py-0.5 rounded border border-slate-900">
                        <span className="text-slate-400">Success Change</span>
                        <span className={`font-bold ${digitalTwinOutcome.success >= 0 ? "text-emerald-450" : "text-rose-450"}`}>
                          {digitalTwinOutcome.success >= 0 ? `+${digitalTwinOutcome.success}%` : `${digitalTwinOutcome.success}%`}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="flex-1 flex items-center justify-center text-slate-655 italic text-[9px] py-6">
                      Awaiting decision outcomes...
                    </div>
                  )}
                </div>

              </div>

            </div>
          ) : (
            // TAB 2: SYSTEM ANALYSIS (SVG Cascading Maps)
            <div className="flex-1 flex flex-col justify-between gap-4">
              <div className="relative border border-slate-900 rounded-lg bg-slate-950/90 h-[480px] p-2 flex items-center justify-center overflow-hidden">
                <svg className="absolute inset-0 w-full h-full pointer-events-none">
                  <defs>
                    <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                      <path d="M 0 0 L 10 5 L 0 10 z" fill="#475569" />
                    </marker>
                    <marker id="arrow-active" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                      <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
                    </marker>
                  </defs>

                  {/* Connections paths */}
                  {/* Solar CME -> Power Fluc */}
                  <line x1="90" y1="80" x2="220" y2="80" stroke={activeEvents.some(e => e.event_type === "Solar Storm") ? "#ef4444" : "#1e293b"} strokeWidth={1.5} markerEnd={activeEvents.some(e => e.event_type === "Solar Storm") ? "url(#arrow-active)" : "url(#arrow)"} />
                  
                  {/* Power Fluc -> Comm Loss */}
                  <line x1="260" y1="100" x2="350" y2="160" stroke={activeEvents.some(e => e.event_type === "Power Fluctuation") ? "#ef4444" : "#1e293b"} strokeWidth={1.5} markerEnd={activeEvents.some(e => e.event_type === "Power Fluctuation") ? "url(#arrow-active)" : "url(#arrow)"} />
                  
                  {/* Fuel Leak -> Thruster Failure */}
                  <line x1="90" y1="360" x2="220" y2="360" stroke={activeEvents.some(e => e.event_type === "Fuel Leak") ? "#ef4444" : "#1e293b"} strokeWidth={1.5} markerEnd={activeEvents.some(e => e.event_type === "Fuel Leak") ? "url(#arrow-active)" : "url(#arrow)"} />
                  
                  {/* Thruster Failure -> Attitude failure */}
                  <line x1="260" y1="340" x2="350" y2="280" stroke={activeEvents.some(e => e.event_type === "Thruster Failure") ? "#ef4444" : "#1e293b"} strokeWidth={1.5} markerEnd={activeEvents.some(e => e.event_type === "Thruster Failure") ? "url(#arrow-active)" : "url(#arrow)"} />
                </svg>

                {/* Nodes */}
                <div className="absolute top-[60px] left-[15px] flex flex-col items-center animate-fade-in">
                  <span className={`w-14 h-8 rounded border flex items-center justify-center font-bold text-[9px] ${
                    activeEvents.some(e => e.event_type === "Solar Storm") ? "bg-rose-955/20 border-rose-500 text-rose-400 animate-pulse font-black" : "bg-slate-900 border-slate-800 text-slate-500"
                  }`}>Solar CME</span>
                </div>

                <div className="absolute top-[60px] left-[180px] flex flex-col items-center animate-fade-in">
                  <span className={`w-18 h-8 rounded border flex items-center justify-center font-bold text-[9px] text-center px-1 ${
                    activeEvents.some(e => e.event_type === "Power Fluctuation") ? "bg-rose-955/20 border-rose-500 text-rose-400 animate-pulse font-black" : "bg-slate-900 border-slate-800 text-slate-500"
                  }`}>Power Fluctuation</span>
                </div>

                <div className="absolute bottom-[80px] left-[15px] flex flex-col items-center animate-fade-in">
                  <span className={`w-14 h-8 rounded border flex items-center justify-center font-bold text-[9px] ${
                    activeEvents.some(e => e.event_type === "Fuel Leak") ? "bg-rose-955/20 border-rose-500 text-rose-400 animate-pulse font-black" : "bg-slate-900 border-slate-800 text-slate-500"
                  }`}>Fuel Leak</span>
                </div>

                <div className="absolute bottom-[80px] left-[180px] flex flex-col items-center animate-fade-in">
                  <span className={`w-18 h-8 rounded border flex items-center justify-center font-bold text-[9px] text-center px-1 ${
                    activeEvents.some(e => e.event_type === "Thruster Failure") ? "bg-rose-955/20 border-rose-500 text-rose-400 animate-pulse font-black" : "bg-slate-900 border-slate-800 text-slate-500"
                  }`}>Thruster Failure</span>
                </div>

                <div className="absolute top-[210px] right-[15px] flex flex-col items-center animate-fade-in">
                  <span className={`w-20 h-10 rounded border flex items-center justify-center font-bold text-[9px] text-center px-1.5 ${
                    activeEvents.some(e => ["Communication Loss", "Attitude Control Failure"].includes(e.event_type)) ? "bg-rose-955/20 border-rose-500 text-rose-400 animate-pulse font-black" : "bg-slate-900 border-slate-800 text-slate-500"
                  }`}>Subsystem Failures</span>
                </div>
              </div>

              <div className="p-3 bg-slate-900/40 border border-slate-850 rounded-lg text-slate-400 text-[10px] leading-relaxed">
                <span className="font-bold text-slate-350 block mb-1">Failure Propagation Diagnostic</span>
                This graph shows structural dependencies between environmental anomalies and primary subsystems. Injected hazards propagate down logical vectors if not mitigated by commander commands.
              </div>
            </div>
          )}

        </div>

      </div>

      {/* 5. PRESETS AND SCENARIOS SELECTION CAROUSEL (Col span 12) */}
      <div className="xl:col-span-12 rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-900 pb-2 mb-3">
          <h3 className="text-xs font-bold tracking-widest text-rose-400 uppercase flex items-center gap-2">
            <Award className="w-4 h-4 text-rose-400" />
            Preset Scenario Testing templates
          </h3>
          <span className="text-[10px] text-slate-500">SELECT TO RUN STRUCTURED STRESS TIMELINES</span>
        </div>

        {/* Preset Cards grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
          {presets.map((preset) => {
            const isScenActive = activeScenarioInfo.active && activeScenarioInfo.name === preset.name;
            
            return (
              <div 
                key={preset.id}
                className={`p-3 rounded-lg border flex flex-col justify-between gap-3 transition-all ${
                  isScenActive 
                    ? "bg-rose-950/20 border-rose-500/50 shadow-md shadow-rose-950/20" 
                    : "bg-slate-950/50 border-slate-900 hover:bg-slate-900/20"
                }`}
              >
                <div>
                  <span className="font-bold text-slate-200 block text-xs">{preset.name}</span>
                  <p className="text-[10px] text-slate-550 leading-snug mt-1">{preset.desc}</p>
                </div>
                <button
                  onClick={() => handleStartPreset(preset.id)}
                  disabled={activeScenarioInfo.active}
                  className={`w-full py-1.5 font-bold tracking-wide rounded text-[10px] flex items-center justify-center gap-1 border transition-all ${
                    isScenActive 
                      ? "bg-rose-500/10 border-rose-500/30 text-rose-400" 
                      : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-850 disabled:text-slate-700 disabled:bg-slate-950 disabled:border-slate-950"
                  }`}
                >
                  <Play className="w-3 h-3 fill-current" />
                  {isScenActive ? "RUNNING" : "TRIGGER"}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* 6. HISTORICAL TEST BENCHMARKS TABLE & SCENARIO PLOTS */}
      <div className="xl:col-span-12 grid grid-cols-1 lg:grid-cols-12 gap-4">
        
        {/* Historical benchmarks table (Col span 7) */}
        <div className="lg:col-span-7 rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl flex flex-col">
          <h3 className="text-xs font-bold tracking-widest text-rose-400 border-b border-slate-900 pb-2 mb-3 uppercase flex items-center gap-2">
            <Database className="w-4 h-4 text-rose-400" />
            Historical stress-test benchmarks
          </h3>

          <div className="overflow-x-auto border border-slate-900 rounded bg-slate-950/40 text-[10px] flex-1 max-h-[220px]">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-850 text-slate-500 uppercase font-bold">
                  <th className="py-2.5 px-3">Date</th>
                  <th className="py-2.5 px-3">Scenario</th>
                  <th className="py-2.5 px-3">Injected Threats</th>
                  <th className="py-2.5 px-3 text-center">Avg Success</th>
                  <th className="py-2.5 px-3 text-center">Outcome</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-900/40 text-slate-350">
                {benchmarks.map((bench) => {
                  const finalSucc = bench.mission_impact ? bench.mission_impact.success_probability : 0;
                  const isSuccess = bench.recovery_outcome === "SUCCESS" || finalSucc > 50.0;
                  
                  return (
                    <tr key={bench.id} className="hover:bg-slate-900/30">
                      <td className="py-2.5 px-3 text-slate-500">{new Date(bench.timestamp).toLocaleDateString()} {new Date(bench.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</td>
                      <td className="py-2.5 px-3 font-bold text-slate-200">{bench.scenario_name}</td>
                      <td className="py-2.5 px-3 max-w-[200px] truncate" title={bench.injected_event}>{bench.injected_event}</td>
                      <td className="py-2.5 px-3 text-center font-bold text-cyan-400">{finalSucc}%</td>
                      <td className={`py-2.5 px-3 text-center font-black ${isSuccess ? "text-emerald-400" : "text-rose-400"}`}>
                        {bench.recovery_outcome}
                      </td>
                    </tr>
                  );
                })}
                {benchmarks.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-slate-650 italic">
                      No historical benchmark records found. Run a test.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recharts Area Plot of Resilience Index History (Col span 5) */}
        <div className="lg:col-span-5 rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl">
          <h3 className="text-xs font-bold tracking-widest text-rose-400 border-b border-slate-900 pb-2 mb-3 uppercase flex items-center gap-2">
            <Activity className="w-4 h-4 text-rose-400" />
            Resilience Index trajectory logs
          </h3>

          <div className="h-[180px]">
            {resilienceChartData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-slate-650 italic">
                Awaiting benchmark records to compile chart trajectory...
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={resilienceChartData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorRes" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0.0}/>
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="name" stroke="#475569" fontSize={8} />
                  <YAxis stroke="#475569" fontSize={8} domain={[0, 100]} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#020617", border: "1px solid #1e293b", fontSize: "9px" }}
                    labelStyle={{ color: "#94a3b8" }}
                  />
                  <Area type="monotone" dataKey="resilience" name="Resilience" stroke="#ef4444" strokeWidth={1.5} fillOpacity={1} fill="url(#colorRes)" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

      </div>

      {/* 7. CUSTOM USER TIMELINE SCENARIOS LIST */}
      {customScenarios.length > 0 && (
        <div className="xl:col-span-12 rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl">
          <h3 className="text-xs font-bold tracking-widest text-cyan-400 border-b border-slate-900 pb-2 mb-3 uppercase flex items-center gap-2">
            <Sliders className="w-4 h-4 text-cyan-400" />
            Saved User Custom Scenarios
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {customScenarios.map((scen) => (
              <div key={scen.id} className="p-3 bg-slate-950/50 border border-slate-900 rounded-lg flex flex-col justify-between gap-3">
                <div>
                  <span className="font-bold text-slate-250 block text-xs">{scen.name}</span>
                  <span className="text-[8px] text-slate-500 block uppercase font-mono mt-0.5">Custom timeline: {scen.events.length} timed events</span>
                  <p className="text-[10px] text-slate-500 leading-snug mt-1.5">{scen.description}</p>
                </div>
                
                <button
                  onClick={() => handleStartCustom(scen.id)}
                  disabled={activeScenarioInfo.active}
                  className="w-full py-1.5 bg-slate-900 hover:bg-slate-850 border border-slate-800 text-cyan-400 font-bold rounded text-[10px] flex items-center justify-center gap-1 disabled:text-slate-700 disabled:bg-slate-950 disabled:border-transparent"
                >
                  <Play className="w-3 h-3 fill-current" /> RUN CUSTOM SCENARIO
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}
