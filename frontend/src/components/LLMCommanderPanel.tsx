"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Brain,
  Cpu,
  Terminal,
  Activity,
  AlertTriangle,
  Layers,
  Key,
  Shield,
  Gauge,
  Sliders,
  CheckCircle,
  Play,
  RotateCcw,
  Sparkles,
  TrendingUp,
  BarChart2,
  FileText,
  Clock
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
  Bar,
  Cell
} from "recharts";

interface LLMConfig {
  provider_type: string;
  model_name: string;
  ollama_url: string;
  has_openai_key: boolean;
  has_anthropic_key: boolean;
  has_gemini_key: boolean;
  temperature: number;
}

interface DecisionRecord {
  id: number;
  timestamp: string;
  decision: string;
  confidence: number;
  chosen_action_key: string;
  status: string;
  autonomy_level: number;
  reasoning: string[];
  expected_outcome: {
    mission_success_change: number;
    risk_reduction: number;
    power_change: number;
    fuel_change: number;
  };
  actual_outcome: {
    actual_success: number | null;
    actual_risk: number | null;
    evaluated: boolean;
  };
  prompt_text: string;
}

interface Metrics {
  decision_accuracy: number;
  avg_confidence: number;
  success_rate: number;
  reasoning_quality: number;
}

export default function LLMCommanderPanel() {
  const [config, setConfig] = useState<LLMConfig>({
    provider_type: "ollama",
    model_name: "llama3:latest",
    ollama_url: "http://localhost:11434",
    has_openai_key: false,
    has_anthropic_key: false,
    has_gemini_key: false,
    temperature: 0.2
  });

  const [metrics, setMetrics] = useState<Metrics>({
    decision_accuracy: 85.0,
    avg_confidence: 78.0,
    success_rate: 90.0,
    reasoning_quality: 92.5
  });

  const [decisions, setDecisions] = useState<DecisionRecord[]>([]);
  const [selectedDecision, setSelectedDecision] = useState<DecisionRecord | null>(null);

  // Form states for key updates
  const [providerType, setProviderType] = useState<string>("ollama");
  const [modelName, setModelName] = useState<string>("");
  const [ollamaUrl, setOllamaUrl] = useState<string>("http://localhost:11434");
  const [openaiKey, setOpenaiKey] = useState<string>("");
  const [anthropicKey, setAnthropicKey] = useState<string>("");
  const [geminiKey, setGeminiKey] = useState<string>("");
  const [temperature, setTemperature] = useState<number>(0.2);

  // Live decision WebSocket events stream
  const [wsLogs, setWsLogs] = useState<string[]>([]);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const [wsStatus, setWsStatus] = useState<string>("disconnected");

  const backendUrl = "127.0.0.1:8000";

  // Sync data from endpoints
  const fetchLLMData = useCallback(async () => {
    try {
      // 1. Fetch Config
      const configRes = await fetch(`http://${backendUrl}/api/llm/config`);
      if (configRes.ok) {
        const cData = await configRes.json();
        setConfig(cData);
        setProviderType(cData.provider_type);
        setModelName(cData.model_name);
        setOllamaUrl(cData.ollama_url);
        setTemperature(cData.temperature);
      }

      // 2. Fetch Metrics
      const metricsRes = await fetch(`http://${backendUrl}/api/llm/metrics`);
      if (metricsRes.ok) {
        const mData = await metricsRes.json();
        setMetrics(mData);
      }

      // 3. Fetch Decisions
      const decisionsRes = await fetch(`http://${backendUrl}/api/llm/decisions`);
      if (decisionsRes.ok) {
        const dData = await decisionsRes.json();
        setDecisions(dData);
        if (dData.length > 0 && !selectedDecision) {
          setSelectedDecision(dData[0]);
        }
      }
    } catch (err) {
      console.error("[LLM API Error] Failed to sync parameters:", err);
    }
  }, [selectedDecision]);

  useEffect(() => {
    fetchLLMData();
    const interval = setInterval(fetchLLMData, 4000);
    return () => clearInterval(interval);
  }, [fetchLLMData]);

  // Connect WebSockets for live logging
  useEffect(() => {
    const ws = new WebSocket(`ws://${backendUrl}/ws`);
    setWsStatus("connecting");

    ws.onopen = () => {
      setWsStatus("connected");
      setWsLogs((prev) => [...prev, `[SYS] WebSocket established. Awaiting LLM broadcasts...`]);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "LLM_PROMPT_GENERATED") {
          setWsLogs((prev) => [
            ...prev,
            `[TICK] LLM context prompt generated for event: ${data.event_type} (ID: ${data.event_id}).`
          ]);
        } else if (data.type === "LLM_DECISION_RECEIVED") {
          setWsLogs((prev) => [
            ...prev,
            `[DECISION] Selected action '${data.decision}' with confidence ${data.confidence}% (Status: ${data.status}).`
          ]);
          fetchLLMData();
        } else if (data.type === "LLM_METRICS_UPDATED") {
          setMetrics({
            decision_accuracy: data.accuracy,
            avg_confidence: data.avg_confidence,
            success_rate: data.success_rate,
            reasoning_quality: data.reasoning_quality
          });
        }
      } catch (err) {
        console.error("WS parse error:", err);
      }
    };

    ws.onclose = () => {
      setWsStatus("disconnected");
      setWsLogs((prev) => [...prev, `[SYS] WebSocket link terminated.`]);
    };

    return () => ws.close();
  }, []);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [wsLogs]);

  // Save Configuration Updates
  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload: any = {
        provider_type: providerType,
        model_name: modelName,
        ollama_url: ollamaUrl,
        temperature: temperature
      };
      if (openaiKey) payload.openai_key = openaiKey;
      if (anthropicKey) payload.anthropic_key = anthropicKey;
      if (geminiKey) payload.gemini_key = geminiKey;

      const res = await fetch(`http://${backendUrl}/api/llm/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        setWsLogs((prev) => [...prev, `[CONFIG] Active LLM provider switched to ${providerType.toUpperCase()}.`]);
        setOpenaiKey("");
        setAnthropicKey("");
        setGeminiKey("");
        fetchLLMData();
      }
    } catch (err) {
      console.error("Failed to update config:", err);
    }
  };

  // Recharts calculations
  const confidenceHistory = decisions
    .slice()
    .reverse()
    .map((d, index) => ({
      index: index + 1,
      confidence: d.confidence,
      decision: d.decision.split(" ")[0]
    }));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 text-slate-100 font-mono text-xs">
      
      {/* 1. TOP HEADER STATUS ROW */}
      <div className="lg:col-span-12 p-3.5 bg-gradient-to-r from-rose-950/40 via-slate-950/60 to-rose-950/40 border border-rose-900/30 rounded-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-tr from-rose-600 to-amber-600 rounded-lg shadow-lg shadow-rose-900/20">
            <Brain className="w-5 h-5 text-white animate-pulse" />
          </div>
          <div>
            <h2 className="text-sm font-bold tracking-widest text-slate-200 uppercase">
              LLM Commander Brain (Phase 3.5)
            </h2>
            <p className="text-[10px] text-slate-500 mt-0.5">
              Active Provider: <span className="text-rose-400 font-bold uppercase">{config.provider_type}</span> ({config.model_name || "Default Model"})
            </p>
          </div>
        </div>

        {/* Speedometer status indicators */}
        <div className="flex items-center gap-6">
          <div className="text-center">
            <span className="text-[9px] text-slate-500 uppercase block font-bold">Accuracy</span>
            <span className="text-sm font-extrabold text-cyan-400 mt-0.5 block">{metrics.decision_accuracy}%</span>
          </div>
          <div className="text-center">
            <span className="text-[9px] text-slate-500 uppercase block font-bold">Avg Confidence</span>
            <span className="text-sm font-extrabold text-rose-400 mt-0.5 block">{metrics.avg_confidence}%</span>
          </div>
          <div className="text-center">
            <span className="text-[9px] text-slate-500 uppercase block font-bold">Success Rate</span>
            <span className="text-sm font-extrabold text-emerald-400 mt-0.5 block">{metrics.success_rate}%</span>
          </div>
          <div className="text-center border-l border-slate-900 pl-4">
            <span className="text-[9px] text-slate-500 uppercase block font-bold">WS Pipeline</span>
            <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold uppercase block mt-1 ${
              wsStatus === "connected" ? "bg-emerald-950 text-emerald-400 border border-emerald-800/20" : "bg-rose-950 text-rose-400 border border-rose-800/20"
            }`}>
              {wsStatus}
            </span>
          </div>
        </div>
      </div>

      {/* 2. LEFT GRID: PROVIDER CONFIG & LIVE LOGS (Col Span 4) */}
      <div className="lg:col-span-4 flex flex-col gap-4">
        
        {/* Provider Config panel */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md">
          <h3 className="text-xs font-bold tracking-widest text-rose-400 border-b border-slate-900 pb-2 mb-3 uppercase flex items-center gap-2">
            <Sliders className="w-4 h-4 text-rose-400" />
            Commander Provider config
          </h3>

          <form onSubmit={handleSaveConfig} className="space-y-3">
            <div>
              <label className="text-slate-500 block mb-1 text-[9px] uppercase font-bold">LLM Provider</label>
              <select
                value={providerType}
                onChange={(e) => setProviderType(e.target.value)}
                className="w-full bg-slate-900 border border-slate-850 p-1.5 rounded text-slate-200 outline-none"
              >
                <option value="ollama">Ollama (Local Models)</option>
                <option value="openai">OpenAI API</option>
                <option value="anthropic">Anthropic API</option>
                <option value="gemini">Google Gemini API</option>
              </select>
            </div>

            <div>
              <label className="text-slate-500 block mb-1 text-[9px] uppercase font-bold">Model name</label>
              <input
                type="text"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                placeholder={
                  providerType === "ollama" ? "llama3:latest" :
                  providerType === "openai" ? "gpt-4o" :
                  providerType === "anthropic" ? "claude-3-5-sonnet-20240620" : "gemini-1.5-flash"
                }
                className="w-full bg-slate-900 border border-slate-850 p-1.5 rounded text-slate-200 outline-none"
              />
            </div>

            {providerType === "ollama" && (
              <div>
                <label className="text-slate-500 block mb-1 text-[9px] uppercase font-bold">Ollama API URL</label>
                <input
                  type="text"
                  value={ollamaUrl}
                  onChange={(e) => setOllamaUrl(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-850 p-1.5 rounded text-slate-200 outline-none"
                />
              </div>
            )}

            {providerType === "openai" && (
              <div>
                <label className="text-slate-500 block mb-1 text-[9px] uppercase font-bold">
                  OpenAI API Key {config.has_openai_key && <span className="text-emerald-400 font-bold text-[8px]">(Loaded)</span>}
                </label>
                <input
                  type="password"
                  value={openaiKey}
                  onChange={(e) => setOpenaiKey(e.target.value)}
                  placeholder={config.has_openai_key ? "••••••••••••••••" : "sk-..."}
                  className="w-full bg-slate-900 border border-slate-850 p-1.5 rounded text-slate-200 outline-none"
                />
              </div>
            )}

            {providerType === "anthropic" && (
              <div>
                <label className="text-slate-500 block mb-1 text-[9px] uppercase font-bold">
                  Anthropic API Key {config.has_anthropic_key && <span className="text-emerald-400 font-bold text-[8px]">(Loaded)</span>}
                </label>
                <input
                  type="password"
                  value={anthropicKey}
                  onChange={(e) => setAnthropicKey(e.target.value)}
                  placeholder={config.has_anthropic_key ? "••••••••••••••••" : "sk-ant-..."}
                  className="w-full bg-slate-900 border border-slate-850 p-1.5 rounded text-slate-200 outline-none"
                />
              </div>
            )}

            {providerType === "gemini" && (
              <div>
                <label className="text-slate-500 block mb-1 text-[9px] uppercase font-bold">
                  Gemini API Key {config.has_gemini_key && <span className="text-emerald-400 font-bold text-[8px]">(Loaded)</span>}
                </label>
                <input
                  type="password"
                  value={geminiKey}
                  onChange={(e) => setGeminiKey(e.target.value)}
                  placeholder={config.has_gemini_key ? "••••••••••••••••" : "AIzaSy..."}
                  className="w-full bg-slate-900 border border-slate-850 p-1.5 rounded text-slate-200 outline-none"
                />
              </div>
            )}

            <button
              type="submit"
              className="w-full py-2 bg-gradient-to-r from-rose-700 to-amber-700 hover:from-rose-600 hover:to-amber-600 text-white font-bold tracking-widest rounded"
            >
              SAVE CONFIGURATION
            </button>
          </form>
        </div>

        {/* Live stream logs panel */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md flex-1 flex flex-col min-h-[180px]">
          <h3 className="text-xs font-bold tracking-widest text-rose-400 border-b border-slate-900 pb-2 mb-2 uppercase flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-rose-400" />
              Live Decision stream
            </span>
          </h3>

          <div className="flex-1 overflow-y-auto max-h-[220px] p-3 rounded-lg border border-slate-900 bg-slate-950 font-mono text-[9px] text-rose-500 leading-relaxed space-y-1">
            {wsLogs.map((log, index) => {
              const isDec = log.includes("[DECISION]");
              return (
                <div key={index} className={`flex items-start gap-1 ${isDec ? "text-emerald-400 font-bold" : "text-rose-500/85"}`}>
                  <span>&gt;</span>
                  <span>{log}</span>
                </div>
              );
            })}
            <div ref={logsEndRef} />
          </div>
        </div>

      </div>

      {/* 3. CENTER GRID: PROMPT SENT VS DECISION RETURNED (Col Span 8) */}
      <div className="lg:col-span-8 flex flex-col gap-4">
        
        {/* Explainable AI Workspace */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          
          {/* Context Prompt Panel */}
          <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md flex flex-col h-[280px]">
            <h3 className="text-xs font-bold tracking-widest text-rose-400 border-b border-slate-900 pb-2 mb-3 uppercase flex items-center gap-2">
              <FileText className="w-4 h-4 text-rose-400" />
              Ingested context prompt
            </h3>
            
            <div className="flex-1 overflow-y-auto p-3 rounded bg-slate-950/80 border border-slate-900 font-mono text-[10px] text-slate-400 whitespace-pre-wrap leading-relaxed select-all">
              {selectedDecision?.prompt_text ? (
                selectedDecision.prompt_text
              ) : (
                <span className="text-slate-600 italic">No prompt generated on this cycle. Ingesting nominal parameters...</span>
              )}
            </div>
          </div>

          {/* Structured JSON Panel */}
          <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md flex flex-col h-[280px]">
            <h3 className="text-xs font-bold tracking-widest text-rose-400 border-b border-slate-900 pb-2 mb-3 uppercase flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-rose-400" />
                Structured response (JSON)
              </span>
              <span className="text-[9px] text-slate-600 font-bold">SCHEMA: COMMAND_V2</span>
            </h3>

            <div className="flex-1 overflow-y-auto p-3 rounded bg-slate-950/80 border border-slate-900 font-mono text-[10px] text-emerald-400 leading-normal">
              {selectedDecision ? (
                <pre>{JSON.stringify({
                  decision: selectedDecision.decision,
                  confidence: selectedDecision.confidence,
                  reasoning: selectedDecision.reasoning,
                  expected_outcome: selectedDecision.expected_outcome
                }, null, 2)}</pre>
              ) : (
                <span className="text-slate-600 italic">Awaiting model inference execution...</span>
              )}
            </div>
          </div>

        </div>

        {/* Explainable AI details and Comparison outcomes */}
        {selectedDecision && (
          <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl backdrop-blur-md grid grid-cols-1 md:grid-cols-12 gap-4">
            
            {/* Reasoning & Actions justification */}
            <div className="md:col-span-7 space-y-3">
              <h4 className="font-bold text-slate-200 border-b border-slate-900 pb-1.5 uppercase text-[11px] flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-400 animate-spin-slow" />
                Commander reasoning justification
              </h4>
              <div className="space-y-2">
                {selectedDecision.reasoning.map((step, idx) => (
                  <div key={idx} className="flex items-start gap-2 bg-slate-900/40 p-2 border border-slate-850/60 rounded">
                    <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    <span className="text-slate-300 text-[11px] leading-relaxed">{step}</span>
                  </div>
                ))}
              </div>
              
              <div className="text-[10px] text-slate-500 pt-1 leading-snug">
                <strong>Failsafe Level checks:</strong> Autonomy level {selectedDecision.autonomy_level} matches status classification <span className="text-rose-400 font-bold">'{selectedDecision.status}'</span>.
              </div>
            </div>

            {/* expected vs actual outcomes validation */}
            <div className="md:col-span-5 space-y-3">
              <h4 className="font-bold text-slate-200 border-b border-slate-900 pb-1.5 uppercase text-[11px] flex items-center gap-2">
                <Activity className="w-4 h-4 text-rose-400" />
                Decision outcome evaluation
              </h4>

              <div className="space-y-2.5">
                <div className="grid grid-cols-2 gap-2 text-center text-[10px] font-bold">
                  <div className="p-2 bg-slate-900/50 border border-slate-850 rounded">
                    <span className="text-slate-500 block mb-0.5">Success probability</span>
                    <span className="text-slate-200 text-xs font-mono">{selectedDecision.expected_outcome.mission_success_change >= 0 ? "+" : ""}{selectedDecision.expected_outcome.mission_success_change}%</span>
                  </div>
                  <div className="p-2 bg-slate-900/50 border border-slate-850 rounded">
                    <span className="text-slate-500 block mb-0.5">Risk reduction</span>
                    <span className="text-slate-200 text-xs font-mono">-{selectedDecision.expected_outcome.risk_reduction}%</span>
                  </div>
                </div>

                <div className="p-2.5 bg-slate-950 rounded border border-slate-900 text-[10px]">
                  <span className="text-slate-400 block font-bold mb-1 uppercase">Actual outcomes (Evaluated 5 ticks later)</span>
                  {selectedDecision.actual_outcome.evaluated ? (
                    <div className="space-y-1 text-emerald-450 font-bold">
                      <div>• Actual Success Probability: {selectedDecision.actual_outcome.actual_success}%</div>
                      <div>• Actual Risk Level: {selectedDecision.actual_outcome.actual_risk}%</div>
                      <div className="text-[9px] text-slate-500 font-normal mt-1 italic">Deltas successfully verified against prediction coefficients.</div>
                    </div>
                  ) : (
                    <div className="text-amber-400 font-bold flex items-center gap-1.5 animate-pulse">
                      <Clock className="w-3.5 h-3.5" />
                      Pending simulator verification cycle...
                    </div>
                  )}
                </div>
              </div>
            </div>

          </div>
        )}

      </div>

      {/* 4. HISTORICAL DECISION LOGS AND CHARTS (Col Span 12) */}
      <div className="lg:col-span-12 grid grid-cols-1 xl:grid-cols-12 gap-4">
        
        {/* Chart representation */}
        <div className="xl:col-span-7 rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl">
          <h3 className="text-xs font-bold tracking-widest text-rose-400 border-b border-slate-900 pb-2 mb-3 uppercase flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-rose-400" />
            Historical confidence profiles
          </h3>
          
          <div className="h-44">
            {confidenceHistory.length === 0 ? (
              <div className="h-full flex items-center justify-center text-slate-650 italic">
                Awaiting telemetry decisions to compile chart metrics...
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={confidenceHistory} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorConf" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.4}/>
                      <stop offset="95%" stopColor="#f43f5e" stopOpacity={0.0}/>
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="index" stroke="#475569" fontSize={9} />
                  <YAxis stroke="#475569" fontSize={9} domain={[0, 100]} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#020617", border: "1px solid #1e293b", fontSize: "10px" }}
                    labelStyle={{ color: "#94a3b8" }}
                  />
                  <Area type="monotone" dataKey="confidence" name="Confidence Score" stroke="#f43f5e" strokeWidth={1.5} fillOpacity={1} fill="url(#colorConf)" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Table list of decisions */}
        <div className="xl:col-span-5 rounded-xl border border-slate-800/80 bg-slate-950/70 p-4 shadow-xl">
          <h3 className="text-xs font-bold tracking-widest text-rose-400 border-b border-slate-900 pb-2 mb-3 uppercase flex items-center gap-2">
            <FileText className="w-4 h-4 text-rose-400" />
            Decision logs history
          </h3>

          <div className="overflow-y-auto max-h-44 border border-slate-900 rounded bg-slate-950/40 text-[10px]">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-850 text-slate-500">
                  <th className="py-2 px-3">Time</th>
                  <th className="py-2 px-3">Decision Choice</th>
                  <th className="py-2 px-3 text-center">Conf</th>
                  <th className="py-2 px-3 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-900/40 text-slate-350">
                {decisions.map((dec) => {
                  const isSelected = selectedDecision?.id === dec.id;
                  const fallback = dec.status === "Fallback";
                  const failed = dec.status === "Failed";
                  
                  let statusColor = "text-emerald-450";
                  if (fallback) statusColor = "text-amber-400 font-bold";
                  if (failed) statusColor = "text-rose-500 font-extrabold";

                  return (
                    <tr
                      key={dec.id}
                      onClick={() => setSelectedDecision(dec)}
                      className={`cursor-pointer transition-all ${
                        isSelected ? "bg-rose-500/10 text-rose-300 font-bold" : "hover:bg-slate-900/30"
                      }`}
                    >
                      <td className="py-2 px-3 text-slate-500">{new Date(dec.timestamp).toLocaleTimeString()}</td>
                      <td className="py-2 px-3 truncate max-w-[120px]" title={dec.decision}>{dec.decision}</td>
                      <td className="py-2 px-3 text-center font-bold">{dec.confidence}%</td>
                      <td className={`py-2 px-3 text-center font-bold ${statusColor}`}>{dec.status}</td>
                    </tr>
                  );
                })}
                {decisions.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-6 text-center text-slate-650 italic">
                      No decisions registered in history logs...
                    </td>
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
