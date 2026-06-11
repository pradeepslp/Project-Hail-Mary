"use client";

import React, { useState, useEffect, useCallback } from "react";
import { 
  ResponsiveContainer, 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  Tooltip, 
  Legend, 
  BarChart, 
  Bar, 
  PieChart, 
  Pie, 
  Cell 
} from "recharts";
import { Activity, Sliders, RefreshCw } from "lucide-react";

interface SeverityPoint {
  name: string;
  value: number;
}

interface SystemPoint {
  system: string;
  count: number;
}

interface RiskPoint {
  timestamp: string;
  risk: number;
}

interface TelemetryPoint {
  timestamp: string;
  fuel: number;
  power: number;
  health: number;
}

interface HourlyPoint {
  time: string;
  count: number;
}

interface AnalyticsData {
  severity_distribution: SeverityPoint[];
  system_frequency: SystemPoint[];
  risk_trend: RiskPoint[];
  telemetry_trend: TelemetryPoint[];
  hourly_frequency: HourlyPoint[];
}

export default function AnalyticsPanel() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchAnalytics = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/analytics/events");
      if (res.ok) {
        const payload = await res.json();
        setData(payload);
      }
    } catch (err) {
      console.error("Failed to load analytics data:", err);
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  // Poll analytics data every 3 seconds for real-time updates
  useEffect(() => {
    fetchAnalytics();
    const interval = setInterval(fetchAnalytics, 3000);
    return () => clearInterval(interval);
  }, [fetchAnalytics]);

  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-slate-500 font-mono text-[11px] uppercase border border-slate-900 rounded-xl bg-slate-950/40">
        <RefreshCw className="w-6 h-6 animate-spin text-cyan-500 mb-2" />
        Hydrating telemetry analytics models...
      </div>
    );
  }

  // Color mappings
  const COLORS = ["#06b6d4", "#10b981", "#eab308", "#f97316", "#ef4444"];
  const SEVERITY_COLORS: Record<string, string> = {
    INFO: "#94a3b8",
    LOW: "#38bdf8",
    MEDIUM: "#ca8a04",
    HIGH: "#f97316",
    CRITICAL: "#dc2626"
  };

  // Safe checks for empty data to prevent charting issues
  const severityData = data.severity_distribution.length > 0 
    ? data.severity_distribution 
    : [{ name: "Nominal", value: 1 }];

  const systemData = data.system_frequency.length > 0 
    ? data.system_frequency 
    : [{ system: "None", count: 0 }];

  return (
    <div className="flex flex-col gap-4">
      
      {/* Title & Refresh Heartbeat */}
      <div className="flex items-center justify-between border-b border-slate-850 pb-2">
        <h3 className="text-xs font-mono font-bold tracking-widest text-cyan-400 uppercase flex items-center gap-1.5">
          <Activity className="w-4 h-4 text-cyan-500" />
          Simulation Flight Analytics
        </h3>
        <span className="text-[9px] font-mono text-slate-500 flex items-center gap-1">
          <RefreshCw className={`w-3 h-3 ${isRefreshing ? "animate-spin text-cyan-400" : ""}`} />
          REAL-TIME (3s POLL)
        </span>
      </div>

      {/* FIRST ROW: Trends Line Charts (Col span 12) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        
        {/* Risk Level Trend */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-lg flex flex-col min-h-[260px]">
          <span className="text-[10px] font-mono font-bold tracking-wider text-slate-400 uppercase mb-3 block">
            System Risk score trend
          </span>
          <div className="flex-1 w-full h-[200px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.risk_trend} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                <XAxis dataKey="timestamp" stroke="#475569" fontSize={9} tickLine={false} />
                <YAxis stroke="#475569" fontSize={9} domain={[0, 100]} tickLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: "#020617", borderColor: "#1e293b", fontSize: 10, fontFamily: "monospace" }} 
                  labelClassName="text-slate-500"
                />
                <Line 
                  type="monotone" 
                  dataKey="risk" 
                  stroke="#ef4444" 
                  strokeWidth={2} 
                  dot={false}
                  activeDot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Telemetry Losses (Fuel, Power, Health) */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-lg flex flex-col min-h-[260px]">
          <span className="text-[10px] font-mono font-bold tracking-wider text-slate-400 uppercase mb-3 block">
            Telemetry Decay Curves
          </span>
          <div className="flex-1 w-full h-[200px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.telemetry_trend} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                <XAxis dataKey="timestamp" stroke="#475569" fontSize={9} tickLine={false} />
                <YAxis stroke="#475569" fontSize={9} domain={[0, 100]} tickLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: "#020617", borderColor: "#1e293b", fontSize: 10, fontFamily: "monospace" }}
                  labelClassName="text-slate-500"
                />
                <Legend iconSize={8} wrapperStyle={{ fontSize: 9, fontFamily: "monospace", color: "#94a3b8" }} />
                <Line type="monotone" dataKey="fuel" stroke="#06b6d4" strokeWidth={1.5} dot={false} name="Fuel %" />
                <Line type="monotone" dataKey="power" stroke="#ca8a04" strokeWidth={1.5} dot={false} name="Power %" />
                <Line type="monotone" dataKey="health" stroke="#10b981" strokeWidth={1.5} dot={false} name="Health %" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>

      {/* SECOND ROW: Histograms & Distributions (Col span 12) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        
        {/* Severity Pie Chart */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-lg flex flex-col items-center min-h-[240px]">
          <span className="text-[10px] font-mono font-bold tracking-wider text-slate-400 uppercase mb-2 self-start w-full border-b border-slate-900 pb-1">
            Severity Distribution
          </span>
          <div className="w-full h-[150px] relative flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={severityData}
                  cx="50%"
                  cy="50%"
                  innerRadius={35}
                  outerRadius={55}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {severityData.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={SEVERITY_COLORS[entry.name] || COLORS[index % COLORS.length]} 
                    />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ backgroundColor: "#020617", borderColor: "#1e293b", fontSize: 9, fontFamily: "monospace" }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          {/* Labels legend */}
          <div className="flex flex-wrap justify-center gap-x-3 gap-y-1 font-mono text-[9px] text-slate-500">
            {severityData.map((entry, index) => (
              <div key={index} className="flex items-center gap-1">
                <span 
                  className="w-1.5 h-1.5 rounded-full" 
                  style={{ backgroundColor: SEVERITY_COLORS[entry.name] || COLORS[index % COLORS.length] }} 
                />
                <span>{entry.name}: {entry.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* System Failure Counts Bar Chart */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-lg flex flex-col min-h-[240px] md:col-span-2">
          <span className="text-[10px] font-mono font-bold tracking-wider text-slate-400 uppercase mb-3 block">
            System Failure Frequencies
          </span>
          <div className="flex-1 w-full h-[160px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={systemData} margin={{ top: 5, right: 10, left: -25, bottom: 5 }}>
                <XAxis dataKey="system" stroke="#475569" fontSize={8} tickLine={false} />
                <YAxis stroke="#475569" fontSize={8} tickLine={false} allowDecimals={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: "#020617", borderColor: "#1e293b", fontSize: 9, fontFamily: "monospace" }}
                  cursor={{ fill: "rgba(15, 23, 42, 0.3)" }}
                />
                <Bar dataKey="count" fill="#38bdf8" radius={[2, 2, 0, 0]} name="Failures">
                  {systemData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>

    </div>
  );
}
