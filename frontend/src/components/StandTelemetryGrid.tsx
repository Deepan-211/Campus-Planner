"use client";

import React, { useState } from "react";
import { Stand } from "../lib/types";
import { Layers, ShieldCheck, ChevronRight, X } from "lucide-react";

export default function StandTelemetryGrid({
  stands,
  hourlyInventories,
  selectedHour,
  onSelectStand,
}: {
  stands: Stand[];
  hourlyInventories: Record<string, Record<number, number>>;
  selectedHour: number;
  onSelectStand?: (standId: string) => void;
}) {
  const [showAllModal, setShowAllModal] = useState<boolean>(false);

  // Focus on top 4 representative stands for the 2x2 grid
  const topStands = stands.slice(0, 4);
  const totalDocks = stands.reduce((sum, s) => sum + s.dock_capacity, 0);

  return (
    <div className="flex flex-col gap-2.5 h-full justify-between">
      {/* 2x2 Grid of Stand Cards */}
      <div className="grid grid-cols-2 gap-2.5">
        {topStands.map((stand) => {
          const bikes =
            hourlyInventories[stand.id]?.[selectedHour] ??
            Math.round(stand.dock_capacity * 0.5);
          const fillPct = Math.min(
            100,
            Math.round((bikes / stand.dock_capacity) * 100)
          );

          return (
            <div
              key={stand.id}
              onClick={() => onSelectStand && onSelectStand(stand.id)}
              className="glass-card p-3 rounded-2xl flex flex-col justify-between cursor-pointer group"
            >
              <div className="flex items-start justify-between">
                {/* Circular ring indicator */}
                <div className="relative w-8 h-8 rounded-full bg-zinc-900 border border-white/20 flex items-center justify-center">
                  <svg className="w-full h-full -rotate-90 p-0.5" viewBox="0 0 36 36">
                    <path
                      className="text-zinc-800"
                      strokeWidth="3"
                      stroke="currentColor"
                      fill="none"
                      d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                    <path
                      className="text-white transition-all duration-500"
                      strokeDasharray={`${fillPct}, 100`}
                      strokeWidth="3.5"
                      strokeLinecap="round"
                      stroke="currentColor"
                      fill="none"
                      d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                  </svg>
                  <span className="absolute text-[9px] font-mono font-bold text-white">
                    {bikes}
                  </span>
                </div>

                {/* Zone badge */}
                <span className="text-[9px] font-mono text-zinc-300 px-1.5 py-0.5 rounded-full bg-white/[0.04] border border-white/10 uppercase">
                  {stand.zone.slice(0, 3)}
                </span>
              </div>

              <div className="mt-2.5">
                <div className="text-xs font-classic font-semibold text-white tracking-wide truncate group-hover:text-zinc-200">
                  {stand.name}
                </div>
                <div className="flex items-center justify-between mt-1 text-[10px] text-zinc-400 font-mono">
                  <span>Cap: {stand.dock_capacity}</span>
                  <span className="text-zinc-300 font-bold">{fillPct}%</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Pill underneath 2x2 grid */}
      <button
        onClick={() => setShowAllModal(true)}
        className="glass-pill px-3.5 py-2 rounded-xl flex items-center justify-between text-xs text-zinc-300 hover:text-white transition group w-full"
      >
        <div className="flex items-center gap-2">
          <Layers className="w-3.5 h-3.5 text-zinc-300 group-hover:text-white" />
          <span className="font-classic text-[10.5px] uppercase tracking-wider">
            {stands.length} Campus Stands
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-[10px] font-mono text-zinc-300">
          <span>{totalDocks} Docks</span>
          <ChevronRight className="w-3 h-3 text-zinc-400 group-hover:translate-x-0.5 transition" />
        </div>
      </button>

      {/* Modal to view all stands */}
      {showAllModal && (
        <div className="fixed inset-0 z-[2000] bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="glass-cockpit max-w-lg w-full p-6 rounded-3xl relative">
            <div className="flex items-center justify-between mb-4 border-b border-white/10 pb-3">
              <div className="flex items-center gap-2.5">
                <ShieldCheck className="w-5 h-5 text-white" />
                <h3 className="font-bold text-white text-base">
                  Campus Stand Network Telemetry ({stands.length} Stands, {totalDocks} Docks)
                </h3>
              </div>
              <button
                onClick={() => setShowAllModal(false)}
                className="p-1 rounded-full text-zinc-400 hover:text-white bg-white/5 hover:bg-white/10"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
              {stands.map((s) => {
                const b =
                  hourlyInventories[s.id]?.[selectedHour] ??
                  Math.round(s.dock_capacity * 0.5);
                const pct = Math.round((b / s.dock_capacity) * 100);

                return (
                  <div
                    key={s.id}
                    className="glass-card p-3 rounded-xl flex items-center justify-between text-xs"
                  >
                    <div>
                      <div className="font-bold text-white">{s.name}</div>
                      <div className="text-[11px] text-zinc-400 font-mono">
                        Zone: {s.zone} • {s.latitude.toFixed(4)}, {s.longitude.toFixed(4)}
                      </div>
                    </div>
                    <div className="text-right font-mono">
                      <div className="text-sm font-bold text-white">
                        {b} / {s.dock_capacity}
                      </div>
                      <div className="text-[10px] text-zinc-400">{pct}% filled</div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-4 pt-3 border-t border-white/10 text-right">
              <button
                onClick={() => setShowAllModal(false)}
                className="px-4 py-1.5 bg-white text-black font-semibold text-xs rounded-xl hover:bg-zinc-200 transition"
              >
                Close Telemetry
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
