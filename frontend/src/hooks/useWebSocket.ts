import { useEffect, useState, useRef, useCallback } from "react";

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
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [mission, setMission] = useState<Mission | null>(null);
  const [events, setEvents] = useState<string[]>([]);
  const [activeEvents, setActiveEvents] = useState<ActiveEvent[]>([]);
  const [status, setStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected");
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current) return;

    setStatus("connecting");
    const wsUrl = `ws://${backendUrl}/ws`;
    
    console.log(`[WS] Connecting to ${wsUrl}...`);
    const socket = new WebSocket(wsUrl);
    wsRef.current = socket;

    socket.onopen = () => {
      setStatus("connected");
      console.log("[WS] Connection established.");
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "INIT") {
          setTelemetry(data.telemetry);
          setMission(data.mission);
          setEvents(data.events || []);
          setActiveEvents(data.active_events || []);
        } else if (data.type === "TELEMETRY") {
          setTelemetry(data.telemetry);
          setMission(data.mission);
          if (data.active_events) {
            setActiveEvents(data.active_events);
          }
        } else if (data.type === "EVENT") {
          setEvents((prev) => [...prev, data.message]);
        } else if (data.type === "NEW_EVENT") {
          setActiveEvents((prev) => {
            if (prev.some(e => e.id === data.event.id)) return prev;
            return [...prev, data.event];
          });
        } else if (data.type === "EVENT_RESOLVED") {
          setActiveEvents((prev) => prev.filter(e => e.id !== data.event_id));
        }
      } catch (err) {
        console.error("[WS] Error parsing message:", err);
      }
    };

    socket.onclose = () => {
      setStatus("disconnected");
      wsRef.current = null;
      console.log("[WS] Connection closed. Attempting reconnect in 3s...");
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, 3000);
    };

    socket.onerror = (error) => {
      console.error("[WS] Error:", error);
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
      const res = await fetch(`http://${backendUrl}/reset-mission`, { method: "POST" });
      setEvents([]);
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
