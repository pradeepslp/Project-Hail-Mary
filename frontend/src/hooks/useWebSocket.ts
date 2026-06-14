import { useEffect, useRef, useCallback } from "react";
import { 
  telemetryStore, 
  missionStore, 
  activeEventsStore, 
  eventsStore, 
  statusStore, 
  useStore, 
  resetAllStores,
  missionSuccessStore,
  missionFailureStore
} from "./useStore";
import { agentVoiceService } from "./useAgentVoice";


export interface SubsystemInfo {
  health: number;
  status: string;
  performance: number;
  risk: number;
}

export interface Telemetry {
  timestamp: string;
  fuel: number;
  power: number;
  oxygen: number;
  temperature: number;
  health: number;
  velocity: number;
  distance: number;
  mission_progress: number;
  communication: string;
  position: { x: number; y: number; z: number };
  position_error?: number;
  subsystems?: Record<string, SubsystemInfo>;
  success_probability?: number;
  failure_probability?: number;
  confidence_score?: number;
  eta?: string;
  main_fuel_pct?: number;
  backup_fuel_pct?: number;
  emergency_fuel_pct?: number;
  simulation_speed?: string;
  mission_elapsed?: string;
  distance_remaining?: string;
  fuel_required?: number;
  travel_time_h?: number;
  feasibility?: boolean;
  main_fuel_mass?: number;
  backup_fuel_mass?: number;
  emergency_fuel_mass?: number;
  total_fuel_mass?: number;
  trajectory_distance?: number;
  burn_rate?: number;
  fuel_consumed?: number;
  acceleration?: number;
}

export interface Mission {
  name: string;
  destination: string;
  launch_time: string;
  state: string;
  duration: number;
  target_distance: number;
  difficulty: string;
  event_frequency: number;
  risk_score: number;
  risk_level: string;
}

export interface ActiveEvent {
  id: number;
  event_type: string;
  severity: string;
  description: string;
  affected_system: string;
  recommended_actions: string;
  status?: string;
  chosen_action?: string | null;
  root_causes?: string[];
  selected_root_cause?: string;
}


export const useWebSocket = (backendUrl: string = "127.0.0.1:8000") => {
  const telemetry = useStore(telemetryStore);
  const mission = useStore(missionStore);
  const events = useStore(eventsStore);
  const activeEvents = useStore(activeEventsStore);
  const status = useStore(statusStore);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current) return;

    statusStore.setState("connecting");
    const wsUrl = `ws://${backendUrl}/ws`;
    
    console.log(`[WS] Connecting to ${wsUrl}...`);
    const socket = new WebSocket(wsUrl);
    wsRef.current = socket;

    socket.onopen = () => {
      statusStore.setState("connected");
      console.log("[WS] Connection established.");
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "INIT") {
          telemetryStore.setState(data.telemetry);
          missionStore.setState(data.mission);
          eventsStore.setState(data.events || []);
          activeEventsStore.setState(data.active_events || []);
        } else if (data.type === "TELEMETRY" || data.type === "TELEMETRY_TICK") {
          telemetryStore.setState(data.telemetry);
          if (data.mission) {
            missionStore.setState(data.mission);
          }
          if (data.active_events) {
            activeEventsStore.setState(data.active_events);
          }
        } else if (data.type === "MISSION_STATE") {
          missionStore.setState(data.mission);
        } else if (data.type === "ACTIVE_EVENTS") {
          activeEventsStore.setState(data.active_events);
        } else if (data.type === "EVENT") {
          eventsStore.setState((prev) => [...prev, data.message]);
        } else if (data.type === "NEW_EVENT") {
          activeEventsStore.setState((prev) => {
            if (prev.some(e => e.id === data.event.id)) return prev;
            return [...prev, data.event];
          });
        } else if (data.type === "EVENT_RESOLVED") {
          activeEventsStore.setState((prev) => prev.filter(e => e.id !== data.event_id));
        } else if (data.type === "MISSION_SUCCESS") {
          missionSuccessStore.setState(data.data);
        } else if (data.type === "MISSION_FAILED") {
          missionFailureStore.setState(data.data);
        } else if (data.type === "AGENT_ANALYSIS_STARTED") {
          agentVoiceService.speak("Mission Commander Agent", `Attention. Anomaly detected: ${data.event_type}. Convoking agent specialists to evaluate mitigation strategies.`);
        } else if (data.type === "AGENT_RECOMMENDATION_CREATED") {
          const timestamp = new Date().toLocaleTimeString();
          const logMsg = `[RECOMMENDATION] [${timestamp}] ${data.agent_name}: ${data.reasoning}`;
          eventsStore.setState((prev) => [...prev, logMsg]);
        } else if (data.type === "COMMANDER_DECISION_CREATED") {
          agentVoiceService.speak("Mission Commander Agent", data.reasoning);
        }
      } catch (err) {
        console.error("[WS] Error parsing message:", err);
      }
    };

    socket.onclose = () => {
      statusStore.setState("disconnected");
      wsRef.current = null;
      console.log("[WS] Connection closed. Attempting reconnect in 3s...");
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, 3000);
    };

    socket.onerror = (error) => {
      console.warn("[WS] Socket error occurred. Reconnecting...");
      socket.close();
    };
  }, [backendUrl]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connect]);

  // REST API Actions
  const startMission = async () => {
    try {
      missionSuccessStore.setState(null);
      missionFailureStore.setState(null);
      const res = await fetch(`http://${backendUrl}/start-mission`, { method: "POST" });
      return await res.json();
    } catch (err) {
      console.error("[API] Error starting mission:", err);
    }
  };

  const pauseMission = async () => {
    try {
      const res = await fetch(`http://${backendUrl}/pause-mission`, { method: "POST" });
      return await res.json();
    } catch (err) {
      console.error("[API] Error pausing mission:", err);
    }
  };

  const resetMission = async () => {
    try {
      // Optimistic UI updates - clear instantly
      resetAllStores();
      const res = await fetch(`http://${backendUrl}/reset-mission`, { method: "POST" });
      return await res.json();
    } catch (err) {
      console.error("[API] Error resetting mission:", err);
    }
  };

  return {
    telemetry,
    mission,
    events,
    activeEvents,
    status,
    startMission,
    pauseMission,
    resetMission,
  };
};

