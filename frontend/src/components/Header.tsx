"use client";

import React from "react";
import { Cpu, ChevronDown, Database, MapPin, Navigation } from "lucide-react";
import { CampusInfo, DataSourceInfo } from "../lib/types";

export default function Header({
  campuses,
  selectedCampusId,
  onSelectCampus,
  dataSource,
  isEvaluating,
  onRunEvaluation,
  currentView = "rider",
  onToggleView,
}: {
  campuses: CampusInfo[];
  selectedCampusId: string;
  onSelectCampus: (id: string) => void;
  dataSource: DataSourceInfo | null;
  isEvaluating: boolean;
  onRunEvaluation: () => void;
  currentView?: "rider" | "operator";
  onToggleView?: (view: "rider" | "operator") => void;
}) {
  const currentCampus = campuses.find((c) => c.id === selectedCampusId);

  return (
    <header className="w-full max-w-7xl mx-auto pt-5 pb-3 px-4 sm:px-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
      {/* Brand & Campus Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div>
          <div className="flex items-baseline gap-2">
            <h1 className="text-xl sm:text-2xl font-classic font-bold tracking-widest text-white uppercase">
              CampusRide
            </h1>
            <span className="text-[10px] font-classic uppercase text-zinc-300 tracking-wider">
              / Digital Twin
            </span>
          </div>
          <p className="text-xs font-editorial italic text-zinc-400 mt-0.5">
            {currentCampus ? `${currentCampus.name} (${currentCampus.city})` : "Micromobility Fleet Simulator"}
          </p>
        </div>

        {/* Campus Preset Selector Dropdown */}
        <div className="relative inline-flex items-center">
          <div className="glass-pill flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-white/20 hover:border-white/40 transition">
            <MapPin className="w-3.5 h-3.5 text-zinc-300" />
            <select
              value={selectedCampusId}
              onChange={(e) => onSelectCampus(e.target.value)}
              className="bg-transparent text-xs font-classic tracking-wide text-white focus:outline-none cursor-pointer pr-1"
            >
              {campuses.map((c) => (
                <option key={c.id} value={c.id} className="bg-zinc-900 text-white">
                  {c.name} ({c.id === "berkeley" ? "Demo Preset" : c.city})
                </option>
              ))}
            </select>
            <ChevronDown className="w-3 h-3 text-zinc-400 pointer-events-none" />
          </div>
        </div>
      </div>

      {/* View Switcher: Rider vs Operator View */}
      {onToggleView && (
        <div className="glass-pill p-1 rounded-full border border-white/20 flex items-center gap-1 shadow-lg bg-black/40 self-center">
          <button
            onClick={() => onToggleView("rider")}
            className={`px-3.5 py-1.5 rounded-full text-xs font-classic tracking-wider uppercase transition flex items-center gap-1.5 ${
              currentView === "rider"
                ? "bg-white text-black font-bold shadow-md"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <Navigation className="w-3.5 h-3.5" />
            <span>Rider View</span>
          </button>
          <button
            onClick={() => onToggleView("operator")}
            className={`px-3.5 py-1.5 rounded-full text-xs font-classic tracking-wider uppercase transition flex items-center gap-1.5 ${
              currentView === "operator"
                ? "bg-white text-black font-bold shadow-md"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            <span>Operator View</span>
          </button>
        </div>
      )}

      {/* Right Badges & Evaluation Trigger */}
      <div className="flex items-center gap-3 self-end sm:self-auto">
        {/* Visible Data Source Badge (Issue 3) */}
        <div
          className={`flex items-center gap-1.5 text-xs font-classic uppercase tracking-wider px-3 py-1.5 rounded-full border shadow-sm ${
            dataSource?.type === "survey"
              ? "bg-emerald-950/40 text-emerald-300 border-emerald-500/40"
              : "bg-blue-950/40 text-blue-300 border-blue-500/40"
          }`}
          title="Data source used for trip distributions and calibration"
        >
          <Database className="w-3.5 h-3.5" />
          <span>{dataSource?.label || "Synthetic Data (NHPP Model)"}</span>
        </div>

        {/* Action Button */}
        <button
          onClick={onRunEvaluation}
          disabled={isEvaluating}
          className="px-4 py-2 bg-white text-black hover:bg-zinc-200 text-xs font-classic font-bold tracking-wider uppercase rounded-full transition shadow-[0_0_20px_rgba(255,255,255,0.25)] disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <Cpu className="w-3.5 h-3.5" />
          <span>{isEvaluating ? "Evaluating..." : "Run Evaluation (N=30)"}</span>
        </button>
      </div>
    </header>
  );
}
