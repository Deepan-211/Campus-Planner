"use client";

import React, { useState } from "react";
import { ForecastResponse, ForecastEvalResponse, Stand, DataSourceInfo } from "../lib/types";
import { BarChart3, TrendingUp, Info } from "lucide-react";

export default function ForecastTab({
  stands,
  forecast,
  forecastEval,
  isLoading,
  dataSource,
}: {
  stands: Stand[];
  forecast: ForecastResponse | null;
  forecastEval: ForecastEvalResponse | null;
  isLoading: boolean;
  dataSource?: DataSourceInfo | null;
}) {
  const [metricMode, setMetricMode] = useState<"pickups" | "dropoffs">("pickups");

  if (isLoading || !forecast) {
    return (
      <div className="glass-card rounded-2xl p-6 border border-white/10 animate-pulse text-zinc-400 text-xs">
        Loading demand forecasts and machine learning evaluation...
      </div>
    );
  }

  // Hours range 07:00 to 22:00
  const hours = Array.from({ length: 16 }, (_, i) => i + 7);

  // Group forecast by stand and hour
  const forecastMap: Record<string, Record<number, { pickups: number; dropoffs: number }>> = {};
  forecast.predictions.forEach((p) => {
    if (!forecastMap[p.stand_id]) forecastMap[p.stand_id] = {};
    forecastMap[p.stand_id][p.hour] = {
      pickups: p.predicted_pickups,
      dropoffs: p.predicted_dropoffs,
    };
  });

  // Find max value for heatmap color normalization
  let maxVal = 1;
  stands.forEach((s) => {
    hours.forEach((h) => {
      const v =
        metricMode === "pickups"
          ? forecastMap[s.id]?.[h]?.pickups ?? 0
          : forecastMap[s.id]?.[h]?.dropoffs ?? 0;
      if (v > maxVal) maxVal = v;
    });
  });

  // Calculate cell color based on intensity
  const getCellBg = (val: number) => {
    const ratio = Math.min(1, Math.max(0, val / maxVal));
    if (ratio < 0.05) return "bg-zinc-900/60 text-zinc-500";
    if (ratio < 0.25) return "bg-blue-950/60 text-blue-200";
    if (ratio < 0.5) return "bg-blue-800/70 text-white font-medium";
    if (ratio < 0.75) return "bg-indigo-600/80 text-white font-bold";
    return "bg-violet-500 text-white font-extrabold shadow-[0_0_10px_rgba(139,92,246,0.5)]";
  };

  return (
    <div className="space-y-6">
      {/* Top Banner: Heatmap Controls & Overview */}
      <div className="glass-cockpit rounded-3xl p-5 border border-white/10 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="font-classic font-bold text-base text-white tracking-wider uppercase">
              Predicted Spatiotemporal Demand Heatmap
            </h2>
            <span
              className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full border ${
                dataSource?.type === "survey"
                  ? "bg-emerald-950/60 border-emerald-500/40 text-emerald-300"
                  : "bg-blue-950/60 border-blue-500/40 text-blue-300"
              }`}
            >
              {dataSource?.label || "Synthetic data (NHPP model, bell-calibrated)"}
            </span>
            <span className="text-[10px] bg-white/10 text-zinc-300 font-mono px-2 py-0.5 rounded-full">
              {forecast.model_name}
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Hourly predicted rider flow across campus stands. Colored by demand volume.
          </p>
        </div>

        {/* Pickups vs Dropoffs Toggle */}
        <div className="flex items-center gap-1 glass-pill p-1 rounded-full self-start md:self-auto">
          <button
            onClick={() => setMetricMode("pickups")}
            className={`px-3 py-1 rounded-full text-xs font-classic tracking-wider uppercase transition ${
              metricMode === "pickups"
                ? "bg-white text-black font-bold shadow-md"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            Pickups (Outflow)
          </button>
          <button
            onClick={() => setMetricMode("dropoffs")}
            className={`px-3 py-1 rounded-full text-xs font-classic tracking-wider uppercase transition ${
              metricMode === "dropoffs"
                ? "bg-white text-black font-bold shadow-md"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            Dropoffs (Inflow)
          </button>
        </div>
      </div>

      {/* Heatmap Grid */}
      <div className="glass-cockpit rounded-3xl p-5 border border-white/10 shadow-xl overflow-x-auto">
        <table className="w-full border-collapse min-w-[700px]">
          <thead>
            <tr>
              <th className="text-left py-2 px-3 text-[11px] font-classic uppercase text-zinc-400 font-semibold border-b border-white/10">
                Stand / Station
              </th>
              {hours.map((h) => (
                <th
                  key={h}
                  className="py-2 px-1 text-center text-[10px] font-mono text-zinc-400 border-b border-white/10"
                >
                  {h.toString().padStart(2, "0")}:00
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {stands.map((stand) => (
              <tr key={stand.id} className="border-b border-white/[0.05] hover:bg-white/[0.02]">
                <td className="py-2.5 px-3 text-xs">
                  <div className="font-classic font-bold text-white text-xs">{stand.name}</div>
                  <div className="text-[10px] text-zinc-400 font-mono">
                    {stand.id} • {stand.zone} ({stand.dock_capacity} docks)
                  </div>
                </td>
                {hours.map((h) => {
                  const val =
                    metricMode === "pickups"
                      ? forecastMap[stand.id]?.[h]?.pickups ?? 0
                      : forecastMap[stand.id]?.[h]?.dropoffs ?? 0;
                  const bgClass = getCellBg(val);

                  return (
                    <td key={h} className="py-2 px-1 text-center">
                      <div
                        className={`mx-auto rounded-lg py-1.5 px-1 text-[11px] font-mono transition duration-150 cursor-default ${bgClass}`}
                        title={`${stand.name} @ ${h}:00 - Predicted ${metricMode}: ${val.toFixed(1)}`}
                      >
                        {val > 0 ? val.toFixed(1) : "—"}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>

        {/* Legend */}
        <div className="flex items-center justify-end gap-3 pt-3 text-[10px] text-zinc-400 font-mono">
          <span>Low Demand</span>
          <div className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-zinc-900 border border-white/10" />
            <span className="w-3 h-3 rounded bg-blue-950" />
            <span className="w-3 h-3 rounded bg-blue-800" />
            <span className="w-3 h-3 rounded bg-indigo-600" />
            <span className="w-3 h-3 rounded bg-violet-500" />
          </div>
          <span>Peak Surge</span>
        </div>
      </div>

    </div>
  );
}
