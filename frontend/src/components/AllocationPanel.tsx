"use client";

import React, { useState } from "react";
import { Stand, AllocationResponse } from "../lib/types";
import { Zap, CheckCircle, ChevronRight, X, Table } from "lucide-react";

export default function AllocationPanel({
  stands,
  allocation,
  isLoading,
}: {
  stands: Stand[];
  allocation: AllocationResponse | null;
  isLoading: boolean;
}) {
  const [showTableModal, setShowTableModal] = useState<boolean>(false);

  if (isLoading || !allocation) {
    return (
      <div className="glass-card p-4 rounded-2xl animate-pulse h-full flex flex-col justify-between">
        <div className="h-4 bg-zinc-800 rounded w-1/3" />
        <div className="h-16 bg-zinc-800/50 rounded-xl" />
        <div className="h-4 bg-zinc-800 rounded w-1/2" />
      </div>
    );
  }

  const {
    baseline_allocation,
    optimized_allocation,
    cost_improvement_pct,
    solve_time_ms,
    solver_status,
  } = allocation;

  // Find top allocated stand and lowest allocated stand dynamically
  const sortedAlloc = [...stands].sort(
    (a, b) => (optimized_allocation[b.id] ?? 0) - (optimized_allocation[a.id] ?? 0)
  );
  const topStand = sortedAlloc[0];
  const lowestStand = sortedAlloc[sortedAlloc.length - 1];

  return (
    <div className="glass-card p-4 rounded-2xl flex flex-col justify-between h-full">
      {/* Header */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-white" />
            <span className="text-xs font-classic font-bold text-white tracking-widest uppercase">
              Fleet Allocation (MILP)
            </span>
          </div>
          <span
            className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-950/80 border border-emerald-500/30 text-emerald-300 font-bold"
            title="Optimizer mathematical objective penalty reduction vs uniform allocation (not a measured simulation outcome)"
          >
            -{cost_improvement_pct}% Objective Loss
          </span>
        </div>

        <p className="text-[11px] text-zinc-300 line-clamp-2 mb-2.5">
          Mixed-Integer Program sets 07:00 AM inventories to eliminate morning rush stockouts.
        </p>

        {/* Dynamic Preview Pill Grid */}
        <div className="grid grid-cols-2 gap-2 bg-black/40 p-2.5 rounded-xl border border-white/10 mb-2">
          <div>
            <div className="text-[9px] font-classic text-zinc-400 uppercase tracking-wider truncate">
              Peak Origin ({topStand?.name.split(" ")[0]})
            </div>
            <div className="text-xs font-mono font-bold text-white">
              {topStand ? `${optimized_allocation[topStand.id] ?? 0} Bikes` : "—"}
            </div>
          </div>
          <div>
            <div className="text-[9px] font-classic text-zinc-400 uppercase tracking-wider truncate">
              Low Origin ({lowestStand?.name.split(" ")[0]})
            </div>
            <div className="text-xs font-mono font-bold text-zinc-300">
              {lowestStand ? `${optimized_allocation[lowestStand.id] ?? 0} Bikes` : "—"}
            </div>
          </div>
        </div>
      </div>

      {/* Button to open full allocation table */}
      <div>
        <button
          onClick={() => setShowTableModal(true)}
          className="w-full glass-pill py-2 px-3 rounded-xl flex items-center justify-between text-xs text-zinc-300 hover:text-white transition group"
        >
          <div className="flex items-center gap-2">
            <Table className="w-3.5 h-3.5 text-zinc-400 group-hover:text-white" />
            <span className="text-[10.5px] font-classic uppercase tracking-wider">Full Allocation Matrix</span>
          </div>
          <div className="flex items-center gap-1 text-[10px] font-mono text-zinc-300">
            <span>{stands.length} Stands</span>
            <ChevronRight className="w-3 h-3 text-zinc-400 group-hover:translate-x-0.5 transition" />
          </div>
        </button>

        <div className="mt-2 pt-2 border-t border-white/[0.08] flex items-center justify-between text-[10px] text-zinc-400 font-classic uppercase tracking-wider">
          <span>{solver_status} ({solve_time_ms.toFixed(1)}ms)</span>
          <span className="text-zinc-300 flex items-center gap-1">
            <CheckCircle className="w-3 h-3 text-white" />
            OR-Tools CBC
          </span>
        </div>
      </div>

      {/* Full Allocation Table Modal */}
      {showTableModal && (
        <div className="fixed inset-0 z-[2000] bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="glass-cockpit max-w-2xl w-full p-6 rounded-3xl relative">
            <div className="flex items-center justify-between mb-4 border-b border-white/10 pb-3">
              <div className="flex items-center gap-2.5">
                <Zap className="w-5 h-5 text-white" />
                <div>
                  <h3 className="font-bold text-white text-base">
                    Morning Fleet Allocation (MILP Solution)
                  </h3>
                  <p className="text-xs text-zinc-400">
                    Fleet Size: {allocation.fleet_size} Bicycles • Google OR-Tools CBC Solver
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowTableModal(false)}
                className="p-1 rounded-full text-zinc-400 hover:text-white bg-white/5 hover:bg-white/10"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="overflow-x-auto max-h-[380px] overflow-y-auto">
              <table className="w-full text-xs text-left">
                <thead className="text-[10px] text-zinc-400 uppercase tracking-wider border-b border-white/10 bg-white/[0.02]">
                  <tr>
                    <th className="py-2.5 px-3">Stand Name</th>
                    <th className="py-2.5 px-2">Zone</th>
                    <th className="py-2.5 px-2 text-right">Docks</th>
                    <th className="py-2.5 px-2 text-right">Uniform</th>
                    <th className="py-2.5 px-2 text-right font-bold text-white">MILP Opt</th>
                    <th className="py-2.5 px-2 text-right">Delta</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.06] font-mono text-zinc-300">
                  {stands.map((s) => {
                    const base = baseline_allocation[s.id] ?? Math.round(s.dock_capacity * 0.5);
                    const opt = optimized_allocation[s.id] ?? Math.round(s.dock_capacity * 0.5);
                    const diff = opt - base;

                    return (
                      <tr key={s.id} className="hover:bg-white/[0.04] transition">
                        <td className="py-2.5 px-3 font-sans font-medium text-white">
                          {s.name}
                        </td>
                        <td className="py-2.5 px-2 font-sans text-zinc-300 text-[11px]">
                          {s.zone}
                        </td>
                        <td className="py-2.5 px-2 text-right text-zinc-300">
                          {s.dock_capacity}
                        </td>
                        <td className="py-2.5 px-2 text-right text-zinc-400">
                          {base}
                        </td>
                        <td className="py-2.5 px-2 text-right font-bold text-white">
                          {opt}
                        </td>
                        <td className="py-2.5 px-2 text-right font-bold">
                          {diff > 0 ? (
                            <span className="text-emerald-400">+{diff}</span>
                          ) : diff < 0 ? (
                            <span className="text-amber-400">{diff}</span>
                          ) : (
                            <span className="text-zinc-500">0</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="mt-4 pt-3 border-t border-white/10 flex items-center justify-between">
              <span className="text-xs text-zinc-400 font-mono">
                Optimization Objective: Min(w_s * Stockouts + w_o * Overflows)
              </span>
              <button
                onClick={() => setShowTableModal(false)}
                className="px-4 py-1.5 bg-white text-black font-semibold text-xs rounded-xl hover:bg-zinc-200 transition"
              >
                Close Table
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
