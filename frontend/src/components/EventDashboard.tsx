"use client";

import React, { useState, useEffect, useCallback } from "react";
import { 
  Search, 
  Filter, 
  ArrowUpDown, 
  CheckCircle, 
  AlertOctagon, 
  ShieldAlert, 
  Info, 
  Activity, 
  Cpu, 
  Radio, 
  Zap, 
  ShieldCheck 
} from "lucide-react";
import { Telemetry, Mission } from "../hooks/useWebSocket";

interface ActiveEvent {
  id: number;
  event_type: string;
  severity: string;
  description: string;
  affected_system: string;
  recommended_actions: string;
}

interface HistoricalEvent {
  id: number;
  event_type: string;
  severity: string;
  timestamp: string;
  description: string;
  affected_system: string;
  probability: number;
  recommended_actions: string;
  resolved: boolean;
  resolution_time: string | null;
}

interface EventDashboardProps {
  telemetry: Telemetry | null;
  mission: Mission | null;
  activeEvents: ActiveEvent[];
}

export default function EventDashboard({ telemetry, mission, activeEvents }: EventDashboardProps) {
  const [history, setHistory] = useState<HistoricalEvent[]>([]);
  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [systemFilter, setSystemFilter] = useState("");
  const [sortOrder, setSortOrder] = useState<"desc" | "asc">("desc");
  const [isLoading, setIsLoading] = useState(false);

  // Fetch Event History from API
  const fetchHistory = useCallback(async () => {
    setIsLoading(true);
    try {
      const queryParams = new URLSearchParams();
      if (severityFilter) queryParams.append("severity", severityFilter);
      if (systemFilter) queryParams.append("system", systemFilter);
      if (search) queryParams.append("search", search);
      queryParams.append("sort", sortOrder);
      queryParams.append("limit", "50");

      const res = await fetch(`http://127.0.0.1:8000/events/history?${queryParams.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch (err) {
      console.error("Failed to load event logs:", err);
    } finally {
      setIsLoading(false);
    }
  }, [severityFilter, systemFilter, search, sortOrder]);

  // Re-fetch when filter triggers or when active events change
  useEffect(() => {
    fetchHistory();
  }, [fetchHistory, activeEvents]);

  // Translate severities to colors
  const getSeverityBadgeClass = (severity: string) => {
    const maps = {
      INFO: "bg-slate-950 text-slate-400 border-slate-900",
      LOW: "bg-blue-950/60 text-blue-400 border-blue-500/20",
      MEDIUM: "bg-amber-950/60 text-amber-400 border-amber-500/20",
      HIGH: "bg-orange-950/60 text-orange-400 border-orange-500/20",
      CRITICAL: "bg-rose-950/60 text-rose-400 border-rose-500/20 animate-pulse border"
    }[severity] || "bg-slate-950 text-slate-400";
    return `px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${maps}`;
  };

  // Systems diagnostic schematic status check
  const getSystemStatus = (systemName: string) => {
    const match = activeEvents.find(e => e.affected_system === systemName);
    if (!match) return { status: "OPERATIONAL", color: "text-emerald-400 border-emerald-500/10 bg-emerald-950/20" };
    if (match.severity === "CRITICAL" || match.severity === "HIGH") {
      return { status: "MALFUNCTION", color: "text-rose-400 border-rose-500/30 bg-rose-950/30 animate-pulse" };
    }
    return { status: "WARNING", color: "text-amber-400 border-amber-500/20 bg-amber-950/20" };
  };

  const riskScore = mission?.risk_score ?? 0;
  const riskLevel = mission?.risk_level ?? "LOW";

  const getRiskColorClass = (level: string) => {
    if (level === "CRITICAL") return "text-rose-500 shadow-rose-500/30";
    if (level === "HIGH") return "text-orange-400 shadow-orange-400/30";
    if (level === "MODERATE") return "text-amber-400 shadow-amber-400/30";
    return "text-cyan-400 shadow-cyan-500/30";
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
      
      {/* LEFT SECTION: Active Alerts & Affected Systems (Col span 4) */}
      <div className="xl:col-span-4 flex flex-col gap-4">
        
        {/* Risk Gauge Header */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-lg flex flex-col items-center justify-center relative overflow-hidden">
          <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-br from-cyan-500/10 to-indigo-500/10 rounded-full blur-2xl" />
          <h2 className="text-xs font-mono font-bold tracking-widest text-slate-400 mb-2 uppercase">
            Overall Mission Risk
          </h2>
          
          <div className="relative flex items-center justify-center w-36 h-20 overflow-hidden">
            {/* Curved Gauge Arch Background */}
            <svg className="absolute w-36 h-36 bottom-[-54px]">
              <circle
                cx="72"
                cy="72"
                r="56"
                className="stroke-slate-800"
                strokeWidth="8"
                fill="transparent"
                strokeDasharray="176"
                strokeDashoffset="0"
                strokeLinecap="round"
              />
              <circle
                cx="72"
                cy="72"
                r="56"
                className={`transition-all duration-1000 ease-out ${
                  riskLevel === "CRITICAL" ? "stroke-rose-500" :
                  riskLevel === "HIGH" ? "stroke-orange-500" :
                  riskLevel === "MODERATE" ? "stroke-amber-500" :
                  "stroke-cyan-500"
                }`}
                strokeWidth="8"
                fill="transparent"
                strokeDasharray="176"
                strokeDashoffset={176 - (riskScore / 100) * 176}
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute bottom-0 flex flex-col items-center">
              <span className={`text-2xl font-bold font-mono leading-none tracking-tighter ${getRiskColorClass(riskLevel)}`}>
                {riskScore}%
              </span>
              <span className="text-[9px] font-mono text-slate-500 tracking-widest mt-1 uppercase">
                Level: {riskLevel}
              </span>
            </div>
          </div>
        </div>

        {/* Affected Systems Schematic grid */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-lg flex-1">
          <h3 className="text-xs font-mono font-bold tracking-widest text-cyan-400 border-b border-slate-850 pb-2 mb-3 uppercase flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5" />
            System Diagnostic Schematic
          </h3>
          <div className="grid grid-cols-1 gap-2.5 font-mono text-[11px]">
            {[
              { name: "Propulsion", label: "Propulsion Struts", icon: <Activity className="w-3.5 h-3.5" /> },
              { name: "Electrical Systems", label: "Solar Energy Grid", icon: <Zap className="w-3.5 h-3.5" /> },
              { name: "Communications", label: "HG Antennas Array", icon: <Radio className="w-3.5 h-3.5" /> },
              { name: "Structural Armor", label: "Hull Integrity Plates", icon: <ShieldCheck className="w-3.5 h-3.5" /> },
              { name: "Nav Computers", label: "Guidance Computers", icon: <Cpu className="w-3.5 h-3.5" /> }
            ].map(sys => {
              const diag = getSystemStatus(sys.name);
              return (
                <div key={sys.name} className={`flex items-center justify-between p-2.5 rounded border ${diag.color} transition-all duration-300`}>
                  <div className="flex items-center gap-2">
                    {sys.icon}
                    <span>{sys.label}</span>
                  </div>
                  <span className="text-[9px] font-extrabold tracking-wider">{diag.status}</span>
                </div>
              );
            })}
          </div>
        </div>

      </div>

      {/* CENTER & RIGHT SECTION: Active Anomaly Alerts & Filters Timeline (Col span 8) */}
      <div className="xl:col-span-8 flex flex-col gap-4">
        
        {/* Active Alerts console */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-lg">
          <h3 className="text-xs font-mono font-bold tracking-widest text-rose-500 border-b border-slate-850 pb-2 mb-3 uppercase flex items-center gap-1.5">
            <AlertOctagon className="w-4 h-4 animate-pulse" />
            Active Hazards & Warnings ({activeEvents.length})
          </h3>
          
          {activeEvents.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-6 text-slate-500 border border-dashed border-slate-900 rounded-lg">
              <ShieldCheck className="w-8 h-8 text-emerald-500/40 mb-2" />
              <p className="text-[11px] font-mono uppercase tracking-wide">Nominal Status - No Active Warnings</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {activeEvents.map(event => (
                <div 
                  key={event.id} 
                  className={`p-3 rounded-lg border bg-slate-950/50 shadow-md ${
                    event.severity === "CRITICAL" ? "border-rose-500/30" : 
                    event.severity === "HIGH" ? "border-orange-500/20" : "border-amber-500/20"
                  }`}
                >
                  <div className="flex justify-between items-center gap-2 mb-2">
                    <span className="font-bold font-mono text-slate-200 text-xs truncate uppercase">{event.event_type}</span>
                    <span className={getSeverityBadgeClass(event.severity)}>{event.severity}</span>
                  </div>
                  <p className="text-[10px] font-mono text-slate-400 mb-2 leading-relaxed">{event.description}</p>
                  
                  <div className="p-2 rounded bg-slate-900/40 border border-slate-850 text-[10px] font-mono text-cyan-400">
                    <span className="text-[9px] uppercase text-slate-500 font-bold block mb-1">Recommended Response:</span>
                    {event.recommended_actions}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Filters Timeline Panel */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 backdrop-blur-md shadow-lg flex-1 flex flex-col">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-850 pb-3 mb-3">
            <h3 className="text-xs font-mono font-bold tracking-widest text-cyan-400 uppercase flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5" />
              Event Timeline History
            </h3>
            
            {/* Filters panel */}
            <div className="flex flex-wrap items-center gap-2 font-mono text-[10px]">
              {/* Search */}
              <div className="relative">
                <input
                  type="text"
                  placeholder="Search anomaly..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="bg-slate-950 border border-slate-900 rounded px-2.5 py-1.5 pl-7 text-[10px] text-slate-200 focus:outline-none focus:border-cyan-500/40 w-36"
                />
                <Search className="absolute left-2.5 top-2 w-3.5 h-3.5 text-slate-600" />
              </div>
              
              {/* Severity filter */}
              <select
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
                className="bg-slate-950 border border-slate-900 rounded px-2 py-1.5 focus:outline-none focus:border-cyan-500/40 text-[10px] text-slate-300"
              >
                <option value="">All Severities</option>
                <option value="INFO">INFO</option>
                <option value="LOW">LOW</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="HIGH">HIGH</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>

              {/* System Filter */}
              <select
                value={systemFilter}
                onChange={(e) => setSystemFilter(e.target.value)}
                className="bg-slate-950 border border-slate-900 rounded px-2 py-1.5 focus:outline-none focus:border-cyan-500/40 text-[10px] text-slate-300"
              >
                <option value="">All Systems</option>
                <option value="Propulsion">Propulsion</option>
                <option value="Electrical Systems">Electrical</option>
                <option value="Communications">Communications</option>
                <option value="Structural Armor">Structural Armor</option>
                <option value="Nav Computers">Nav Computers</option>
              </select>

              {/* Sort Switch */}
              <button
                onClick={() => setSortOrder(prev => prev === "desc" ? "asc" : "desc")}
                className="flex items-center gap-1.5 border border-slate-900 bg-slate-950 hover:bg-slate-900 px-2 py-1.5 rounded text-slate-400 uppercase transition-all"
              >
                <ArrowUpDown className="w-3 h-3" />
                Sort: {sortOrder}
              </button>
            </div>
          </div>

          {/* Historical Log list */}
          <div className="flex-1 overflow-y-auto max-h-[220px] scrollbar-thin scrollbar-thumb-slate-850 scrollbar-track-transparent">
            {isLoading ? (
              <div className="text-center font-mono text-[10px] text-slate-600 py-6">
                Querying database records...
              </div>
            ) : history.length === 0 ? (
              <div className="text-center font-mono text-[10px] text-slate-600 py-6">
                No logs matching filter configurations.
              </div>
            ) : (
              <div className="space-y-1.5 pr-2 font-mono text-[10px]">
                {history.map(item => (
                  <div 
                    key={item.id} 
                    className="flex flex-col md:flex-row md:items-center justify-between gap-2 p-2 rounded border border-slate-900/60 bg-slate-950/40 hover:border-slate-800/80 transition-all duration-200"
                  >
                    <div className="flex items-start gap-2">
                      <span className="text-slate-600">[{new Date(item.timestamp).toLocaleTimeString()}]</span>
                      <span className={getSeverityBadgeClass(item.severity)}>{item.severity}</span>
                      <div className="flex flex-col">
                        <span className="font-bold text-slate-200 uppercase">{item.event_type}</span>
                        <span className="text-slate-500 mt-0.5 leading-relaxed">{item.description}</span>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-3 self-end md:self-auto text-[9px] text-slate-500 whitespace-nowrap">
                      <span>SYS: {item.affected_system}</span>
                      <span className="flex items-center gap-1">
                        {item.resolved ? (
                          <>
                            <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
                            <span className="text-emerald-500 font-bold uppercase">RESOLVED</span>
                          </>
                        ) : (
                          <>
                            <AlertOctagon className="w-3.5 h-3.5 text-rose-500 animate-pulse" />
                            <span className="text-rose-400 font-bold uppercase">ACTIVE</span>
                          </>
                        )}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

      </div>

    </div>
  );
}
