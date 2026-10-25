"use client";

import React, { useState } from "react";
import { ConfigSummary } from "../lib/types";
import { Sliders, ShieldCheck, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";

export default function AssumptionsPanel({
  assumptions,
  isLoading,
}: {
  assumptions: ConfigSummary | null;
  isLoading: boolean;
}) {
  const [isOpen, setIsOpen] = useState<boolean>(true);

  if (isLoading || !assumptions) {
    return (
      <div className="glass-card rounded-2xl p-6 border border-white/10 animate-pulse text-zinc-400 text-xs">
        Loading system operational assumptions and parameters...
      </div>
    );
  }

  return (
    <div className="glass-cockpit rounded-3xl p-5 border border-white/10 shadow-xl space-y-4">
      {/* Title Bar with Accordion Toggle */}
      <div
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between cursor-pointer select-none"
      >
        <div>
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-white" />
            <h3 className="font-classic font-bold text-sm text-white tracking-wider uppercase">
              Operational Assumptions & System Parameters ({assumptions.campus_name})
            </h3>
            <span className="text-[10px] bg-blue-950/60 border border-blue-500/40 text-blue-300 font-mono px-2 py-0.5 rounded-full">
              Synthetic data (NHPP model, bell-calibrated)
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5">
            Full transparency into empirical benchmarks, physical parameters, and optimization weights.
          </p>
        </div>
        <button className="text-zinc-400 hover:text-white p-1 rounded-lg">
          {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {isOpen && (
        <>
          {/* Summary Metric Pills */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 pt-2">
            <div className="bg-black/40 rounded-xl p-3 border border-white/10">
              <span className="text-[10px] text-zinc-400 font-mono uppercase block">Fleet Size</span>
              <strong className="text-sm font-mono text-white">{assumptions.total_bikes} Bikes</strong>
            </div>
            <div className="bg-black/40 rounded-xl p-3 border border-white/10">
              <span className="text-[10px] text-zinc-400 font-mono uppercase block">Total Docks</span>
              <strong className="text-sm font-mono text-zinc-200">{assumptions.total_docks} Docks</strong>
            </div>
            <div className="bg-black/40 rounded-xl p-3 border border-white/10">
              <span className="text-[10px] text-zinc-400 font-mono uppercase block">Campus Stands</span>
              <strong className="text-sm font-mono text-zinc-200">{assumptions.num_stands} Stands</strong>
            </div>
            <div className="bg-black/40 rounded-xl p-3 border border-white/10">
              <span className="text-[10px] text-zinc-400 font-mono uppercase block">Van Capacity</span>
              <strong className="text-sm font-mono text-zinc-200">{assumptions.van_capacity} Bikes</strong>
            </div>
            <div className="bg-black/40 rounded-xl p-3 border border-white/10 col-span-2 sm:col-span-1">
              <span className="text-[10px] text-zinc-400 font-mono uppercase block">Operating Window</span>
              <strong className="text-sm font-mono text-zinc-200">{assumptions.operating_hours}</strong>
            </div>
          </div>

          {/* Full Assumptions Table */}
          <div className="overflow-x-auto pt-2">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-white/10 text-[10px] font-classic uppercase text-zinc-400 tracking-wider">
                  <th className="py-2.5 px-3">Parameter</th>
                  <th className="py-2.5 px-3">Value</th>
                  <th className="py-2.5 px-3">Units</th>
                  <th className="py-2.5 px-3">Empirical Source / Justification</th>
                  <th className="py-2.5 px-3 font-mono">Config Key</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.06] text-xs">
                {assumptions.assumptions.map((item, idx) => (
                  <tr key={idx} className="hover:bg-white/[0.02] transition">
                    <td className="py-2.5 px-3 font-medium text-white">{item.parameter}</td>
                    <td className="py-2.5 px-3 font-mono font-bold text-emerald-400">{item.value}</td>
                    <td className="py-2.5 px-3 font-mono text-zinc-400">{item.units || "—"}</td>
                    <td className="py-2.5 px-3 text-zinc-300 max-w-xs">{item.source}</td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-zinc-400">{item.config_key}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
