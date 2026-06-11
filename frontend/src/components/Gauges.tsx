import React from "react";

interface CircularGaugeProps {
  value: number;
  label: string;
  unit?: string;
  color?: string; // e.g. "cyan", "emerald", "amber", "rose"
  max?: number;
}

export function CircularGauge({ value, label, unit = "%", color = "cyan", max = 100 }: CircularGaugeProps) {
  const radius = 38;
  const stroke = 6;
  const normalizedValue = Math.min(max, Math.max(0, value));
  const percentage = (normalizedValue / max) * 100;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  const colorClasses = {
    cyan: {
      stroke: "stroke-cyan-500",
      text: "text-cyan-400",
      glow: "shadow-cyan-500/20",
      border: "border-cyan-500/20"
    },
    emerald: {
      stroke: "stroke-emerald-500",
      text: "text-emerald-400",
      glow: "shadow-emerald-500/20",
      border: "border-emerald-500/20"
    },
    amber: {
      stroke: "stroke-amber-500",
      text: "text-amber-400",
      glow: "shadow-amber-500/20",
      border: "border-amber-500/20"
    },
    rose: {
      stroke: "stroke-rose-500",
      text: "text-rose-400",
      glow: "shadow-rose-500/20",
      border: "border-rose-500/20"
    }
  }[color as "cyan" | "emerald" | "amber" | "rose"] || {
    stroke: "stroke-cyan-500",
    text: "text-cyan-400",
    glow: "shadow-cyan-500/20",
    border: "border-cyan-500/20"
  };

  return (
    <div className={`flex flex-col items-center justify-center p-3 rounded-lg border border-slate-800/40 bg-slate-900/50 backdrop-blur-md shadow-lg shadow-black/30 hover:border-slate-700/50 transition-all duration-300`}>
      <div className="relative w-24 h-24">
        {/* Glow Filters */}
        <svg className="w-full h-full transform -rotate-90">
          {/* Background circle */}
          <circle
            cx="48"
            cy="48"
            r={radius}
            className="stroke-slate-800"
            strokeWidth={stroke}
            fill="transparent"
          />
          {/* Progress circle */}
          <circle
            cx="48"
            cy="48"
            r={radius}
            className={`${colorClasses.stroke} transition-all duration-1000 ease-out`}
            strokeWidth={stroke}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            fill="transparent"
          />
        </svg>
        {/* Centered label */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-bold font-mono text-white leading-none tracking-tight">
            {Math.round(value)}
          </span>
          <span className="text-[9px] font-mono font-medium text-slate-500 mt-0.5 uppercase">
            {unit}
          </span>
        </div>
      </div>
      <span className="text-[10px] font-mono font-semibold tracking-wider text-slate-400 mt-2 uppercase">
        {label}
      </span>
    </div>
  );
}

interface ProgressBarProps {
  value: number;
  label: string;
  unit?: string;
  color?: string; // "cyan", "emerald", "amber", "rose"
  max?: number;
}

export function ProgressBar({ value, label, unit = "%", color = "cyan", max = 100 }: ProgressBarProps) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  const colorClasses = {
    cyan: "bg-cyan-500 shadow-[0_0_10px_rgba(6,182,212,0.5)]",
    emerald: "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]",
    amber: "bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.5)]",
    rose: "bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.5)]"
  }[color as "cyan" | "emerald" | "amber" | "rose"] || "bg-cyan-500";

  const textClass = {
    cyan: "text-cyan-400",
    emerald: "text-emerald-400",
    amber: "text-amber-400",
    rose: "text-rose-400"
  }[color as "cyan" | "emerald" | "amber" | "rose"] || "text-cyan-400";

  return (
    <div className="w-full bg-slate-900/40 border border-slate-800/40 p-3 rounded-lg hover:border-slate-700/50 transition-all duration-300">
      <div className="flex justify-between items-center mb-1.5 text-[10px] font-mono tracking-wider text-slate-400 uppercase">
        <span>{label}</span>
        <span className={`font-bold ${textClass}`}>
          {value.toLocaleString(undefined, { maximumFractionDigits: 1 })}{unit}
        </span>
      </div>
      <div className="w-full h-2.5 bg-slate-950 rounded-full overflow-hidden p-[1px] border border-slate-850">
        <div
          className={`h-full rounded-full ${colorClasses} transition-all duration-1000 ease-out`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

interface ParamGridProps {
  title: string;
  value: string | number;
  icon?: React.ReactNode;
  accentColor?: string;
}

export function ParamGridItem({ title, value, icon, accentColor = "text-cyan-400" }: ParamGridProps) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg border border-slate-800/40 bg-slate-900/40 hover:border-slate-700/50 transition-all duration-300 shadow-md">
      {icon && <div className={`${accentColor} p-1.5 bg-slate-950/60 rounded border border-slate-800`}>{icon}</div>}
      <div className="flex flex-col min-w-0">
        <span className="text-[9px] font-mono tracking-wider text-slate-500 uppercase">{title}</span>
        <span className="text-sm font-bold font-mono text-slate-200 mt-0.5 truncate leading-tight">{value}</span>
      </div>
    </div>
  );
}
