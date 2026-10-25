"use client";

import React, { useState } from "react";
import { Stand } from "../lib/types";
import {
  MapPin,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  Search,
  Filter,
  Layers,
} from "lucide-react";

interface StandAlertsInspectorProps {
  stands: Stand[];
  hourlyInventories: Record<string, Record<number, number>>;
  selectedHour: number;
  selectedStandId?: string | null;
  onSelectStand?: (standId: string) => void;
  searchQuery?: string;
  onSearchChange?: (query: string) => void;
}

export default function StandAlertsInspector({
  stands,
  hourlyInventories,
  selectedHour,
  selectedStandId,
  onSelectStand,
  searchQuery = "",
  onSearchChange,
}: StandAlertsInspectorProps) {
  const [filterType, setFilterType] = useState<"all" | "urgent">("all");
  const [localSearch, setLocalSearch] = useState<string>("");

  const activeSearch = searchQuery || localSearch;
  const handleSearchChange = (val: string) => {
    setLocalSearch(val);
    onSearchChange?.(val);
  };

  // Compute status for all stands
  const standsWithStatus = stands.map((stand) => {
    const bikes =
      hourlyInventories[stand.id]?.[selectedHour] ??
      Math.round(stand.dock_capacity * 0.5);
    const fillPercent = Math.round((bikes / stand.dock_capacity) * 100);

    let status: "starved" | "full" | "balanced" = "balanced";
    if (bikes === 0) {
      status = "starved";
    } else if (fillPercent >= 90) {
      status = "full";
    }

    return {
      stand,
      bikes,
      fillPercent,
      status,
    };
  });

  // Calculate summary counts
  const starvedCount = standsWithStatus.filter((s) => s.status === "starved").length;
  const fullCount = standsWithStatus.filter((s) => s.status === "full").length;
  const balancedCount = standsWithStatus.filter((s) => s.status === "balanced").length;

  // Filter & sort by urgency
  const filteredStands = standsWithStatus
    .filter((item) => {
      // Filter by urgency tab
      if (filterType === "urgent" && item.status === "balanced") return false;

      // Filter by search query
      if (activeSearch.trim()) {
        const q = activeSearch.toLowerCase();
        const matchesName = item.stand.name.toLowerCase().includes(q);
        const matchesZone = item.stand.zone.toLowerCase().includes(q);
        const matchesId = item.stand.id.toLowerCase().includes(q);
        return matchesName || matchesZone || matchesId;
      }
      return true;
    })
    .sort((a, b) => {
      // Prioritize starved, then full, then balanced
      const score = (st: "starved" | "full" | "balanced") =>
        st === "starved" ? 3 : st === "full" ? 2 : 1;
      return score(b.status) - score(a.status);
    });

  return (
    <div className="bg-[#b8b8bc] rounded-2xl p-3.5 border border-zinc-300/60 shadow-sm flex flex-col flex-1 min-h-0">
      {/* Section Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5 text-zinc-700" />
          <h3 className="font-bold text-xs text-zinc-900 leading-tight">
            Stand Status & Urgency
          </h3>
        </div>

        {/* Urgency Counter Badge */}
        <div className="flex items-center gap-1.5 text-[10px] font-mono">
          {starvedCount > 0 && (
            <span className="bg-rose-500 text-white font-bold px-1.5 py-0.5 rounded-full flex items-center gap-0.5 shadow-xs">
              <span className="w-1.5 h-1.5 rounded-full bg-white animate-ping" />
              {starvedCount} Starved
            </span>
          )}
          {fullCount > 0 && (
            <span className="bg-amber-600 text-white font-bold px-1.5 py-0.5 rounded-full shadow-xs">
              {fullCount} Full
            </span>
          )}
          {starvedCount === 0 && fullCount === 0 && (
            <span className="bg-emerald-600 text-white font-bold px-1.5 py-0.5 rounded-full">
              All Balanced
            </span>
          )}
        </div>
      </div>

      {/* Quick Search & Filter Controls */}
      <div className="flex items-center gap-1.5 mb-2.5">
        <div className="bg-white/80 rounded-xl px-2.5 py-1 flex items-center gap-1.5 text-xs text-zinc-800 flex-1 border border-zinc-200/80 shadow-2xs">
          <Search className="w-3 h-3 text-zinc-500 shrink-0" />
          <input
            type="text"
            value={activeSearch}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search stand name / zone..."
            className="bg-transparent focus:outline-none text-zinc-800 placeholder-zinc-500 w-full text-[11px]"
          />
          {activeSearch && (
            <button
              type="button"
              onClick={() => handleSearchChange("")}
              className="text-[10px] text-zinc-500 hover:text-zinc-800 font-bold"
            >
              ✕
            </button>
          )}
        </div>

        <button
          type="button"
          onClick={() => setFilterType(filterType === "all" ? "urgent" : "all")}
          className={`px-2 py-1 rounded-xl text-[10px] font-bold transition flex items-center gap-1 border shadow-xs ${
            filterType === "urgent"
              ? "bg-rose-500 border-rose-600 text-white"
              : "bg-white/80 border-zinc-200/80 text-zinc-700 hover:text-zinc-950"
          }`}
          title="Filter only urgent / starved / saturated stands"
        >
          <Filter className="w-2.5 h-2.5" />
          <span>{filterType === "urgent" ? "Urgent Only" : "All Stands"}</span>
        </button>
      </div>

      {/* Stand Status Cards List */}
      <div className="space-y-1.5 overflow-y-auto flex-1 pr-1 max-h-[300px]">
        {filteredStands.length === 0 ? (
          <div className="py-8 text-center text-xs text-zinc-600 font-mono">
            No stands match query &quot;{activeSearch}&quot;
          </div>
        ) : (
          filteredStands.map(({ stand, bikes, fillPercent, status }) => {
            const isSelected = selectedStandId === stand.id;

            return (
              <div
                key={stand.id}
                onClick={() => onSelectStand?.(stand.id)}
                className={`p-2.5 rounded-xl border transition-all cursor-pointer relative ${
                  isSelected
                    ? "bg-white border-zinc-800 shadow-md ring-1 ring-zinc-800"
                    : status === "starved"
                    ? "bg-rose-50/90 border-rose-300 hover:border-rose-400"
                    : status === "full"
                    ? "bg-amber-50/90 border-amber-300 hover:border-amber-400"
                    : "bg-white/80 border-zinc-200/80 hover:bg-white"
                }`}
              >
                {/* Stand Header: Name, Zone, Status Badge */}
                <div className="flex items-start justify-between gap-1 mb-1.5">
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="font-bold text-xs text-zinc-900 truncate max-w-[170px]">
                        {stand.name}
                      </span>
                      <span className="text-[9px] font-mono text-zinc-500">
                        ({stand.id})
                      </span>
                    </div>
                    <span className="text-[10px] font-medium text-zinc-500">
                      Zone: {stand.zone}
                    </span>
                  </div>

                  {/* Status Tag */}
                  <div>
                    {status === "starved" ? (
                      <span className="inline-flex items-center gap-1 bg-rose-500 text-white text-[9px] font-bold px-1.5 py-0.5 rounded-full shadow-2xs">
                        <AlertTriangle className="w-2.5 h-2.5" />
                        STARVED
                      </span>
                    ) : status === "full" ? (
                      <span className="inline-flex items-center gap-1 bg-amber-600 text-white text-[9px] font-bold px-1.5 py-0.5 rounded-full shadow-2xs">
                        <AlertCircle className="w-2.5 h-2.5" />
                        FULL
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 bg-emerald-600/20 text-emerald-800 text-[9px] font-bold px-1.5 py-0.5 rounded-full">
                        <CheckCircle2 className="w-2.5 h-2.5 text-emerald-700" />
                        BALANCED
                      </span>
                    )}
                  </div>
                </div>

                {/* Fill Level Progress Bar & Counts */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[10px] font-mono">
                    <span className="text-zinc-600">
                      Bikes: <strong className="text-zinc-900">{bikes}</strong> / {stand.dock_capacity}
                    </span>
                    <span
                      className={`font-bold ${
                        status === "starved"
                          ? "text-rose-600"
                          : status === "full"
                          ? "text-amber-700"
                          : "text-emerald-700"
                      }`}
                    >
                      {fillPercent}%
                    </span>
                  </div>

                  {/* Visual Progress Bar */}
                  <div className="w-full h-1.5 bg-zinc-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-300 rounded-full ${
                        status === "starved"
                          ? "bg-rose-500"
                          : status === "full"
                          ? "bg-amber-500"
                          : "bg-emerald-500"
                      }`}
                      style={{ width: `${Math.min(fillPercent, 100)}%` }}
                    />
                  </div>
                </div>

                {/* Click action indicator */}
                <div className="mt-1.5 pt-1 border-t border-zinc-200/50 flex items-center justify-between text-[9.5px]">
                  <span className="text-zinc-400 font-mono">
                    Free docks: {stand.dock_capacity - bikes}
                  </span>
                  <span className="inline-flex items-center gap-0.5 text-sky-700 hover:text-sky-900 font-bold">
                    <MapPin className="w-2.5 h-2.5" />
                    <span>Focus on Map</span>
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
