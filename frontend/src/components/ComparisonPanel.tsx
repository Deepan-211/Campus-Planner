"use client";

import React from "react";
import { EvaluationResponse, AllocationResponse } from "../lib/types";
import { TrendingDown, TrendingUp, CheckCircle, HelpCircle } from "lucide-react";

export default function ComparisonPanel({
  evaluation,
  allocation,
  isLoading,
}: {
  evaluation: EvaluationResponse | null;
  allocation: AllocationResponse | null;
  isLoading: boolean;
}) {
  if (isLoading || !evaluation) {
    return (
      <div className="glass-card rounded-2xl p-4 border border-white/10 animate-pulse text-zinc-400 text-xs">
        Loading comparative policy performance metrics...
      </div>
    );
  }

  const metrics = [
    {
      label: "Unmet Demand (Stockouts)",
      metric: evaluation.unmet_demand_pct,
      unit: "%",
      isLowerBetter: true,
      description: "Percentage of requested student trips refused due to stand depletion.",
    },
    {
      label: "Average Rider Wait Time",
      metric: evaluation.avg_wait_time_min,
      unit: "min",
      isLowerBetter: true,
      description: "Average minutes queued before obtaining an available bicycle or balking.",
    },
    {
      label: "Rides / Vehicle / Day",
      metric: evaluation.rides_per_vehicle_per_day || evaluation.fleet_utilization_pct,
      unit: evaluation.rides_per_vehicle_per_day ? " rides" : "%",
      isLowerBetter: false,
      description: "Daily trip throughput per deployed bicycle across campus.",
    },
    {
      label: "Peak-Hour Utilization",
      metric: evaluation.peak_hour_utilization_pct || evaluation.fleet_utilization_pct,
      unit: "%",
      isLowerBetter: false,
      description: "Maximum simultaneous fleet utilization during campus peak rush hour.",
    },
  ];

  return (
    <div className="glass-card rounded-2xl p-4 sm:p-5 border border-white/10 shadow-xl space-y-4">
      {/* Header with Title and MILP Explanation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/10 pb-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-classic font-bold text-sm text-white tracking-wider uppercase">
              Policy Comparison: Baseline vs. Optimized
            </h3>
            <span className="text-[10px] bg-white/10 text-zinc-300 font-mono px-2 py-0.5 rounded-full">
              N={evaluation.replications} Seeds • 95% CI
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5">
            Paired Monte Carlo simulation of Baseline (uniform + no vans) vs. Optimized (MILP + midday OR-Tools CVRP).
          </p>
        </div>

        {/* Explained Efficiency Metric (Issue 3: Relabeled as Optimizer Objective) */}
        {allocation && (
          <div className="glass-pill px-3 py-1.5 rounded-xl border border-white/15 flex items-center gap-2 self-start sm:self-auto group relative">
            <div>
              <span className="text-[10px] text-zinc-400 block font-classic uppercase">
                Optimizer Objective (Math Loss)
              </span>
              <span className="text-xs font-mono font-bold text-zinc-300">
                {allocation.cost_improvement_pct}% Penalty Reduction (Not a Measured Outcome)
              </span>
            </div>
            <HelpCircle className="w-3.5 h-3.5 text-zinc-400 group-hover:text-white transition cursor-help" />
            
            {/* Tooltip explaining the 87.75% metric */}
            <div className="absolute right-0 top-full mt-2 w-72 p-3 bg-zinc-950 border border-white/20 rounded-xl shadow-2xl text-[11px] text-zinc-300 z-50 opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition duration-200">
              <strong className="text-white block mb-1">Algorithmic Explanation:</strong>
              The MILP morning optimizer reduced the weighted expected stockout + overflow penalty cost by{" "}
              <span className="text-white font-bold">{allocation.cost_improvement_pct}%</span> compared to uniform distribution (Baseline Cost: {allocation.baseline_cost.toFixed(1)} → Optimized Cost: {allocation.optimized_cost.toFixed(1)}).
              <p className="mt-1 text-zinc-400 text-[10px] italic">
                Note: This is a mathematical optimization objective value, not an empirically measured simulation outcome.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* 4 Metric Comparison Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {metrics.map(({ label, metric, unit, isLowerBetter, description }) => {
          const isBetter = isLowerBetter
            ? metric.absolute_improvement < 0
            : metric.absolute_improvement > 0;
          const diff = metric.optimized.mean - metric.baseline.mean;
          const isPercentage = unit === "%";
          const diffFormatted = isPercentage
            ? `${diff > 0 ? "+" : ""}${diff.toFixed(1)} pp`
            : `${diff > 0 ? "+" : ""}${diff.toFixed(2)}${unit}`;
          const relPct = Math.abs(metric.pct_improvement).toFixed(1);
          const relSigned = metric.pct_improvement > 0 ? (isLowerBetter ? "-" : "+") : (isLowerBetter ? "+" : "-");

          return (
            <div
              key={label}
              className="bg-black/40 rounded-xl p-3.5 border border-white/10 flex flex-col justify-between space-y-3"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-classic font-semibold text-zinc-300 tracking-wide uppercase">
                    {label}
                  </span>
                  <span
                    className={`inline-flex items-center gap-1 text-[11px] font-mono font-bold px-2 py-0.5 rounded-full border ${
                      isBetter
                        ? "bg-emerald-950/60 text-emerald-300 border-emerald-500/30"
                        : "bg-amber-950/60 text-amber-300 border-amber-500/30"
                    }`}
                  >
                    {isBetter ? (
                      <TrendingDown className="w-3 h-3" />
                    ) : (
                      <TrendingUp className="w-3 h-3" />
                    )}
                    {diffFormatted} ({relSigned}{relPct}% rel)
                  </span>
                </div>
                <p className="text-[10px] text-zinc-400 mt-1">{description}</p>
              </div>

              {/* Baseline vs Optimized Values */}
              <div className="grid grid-cols-2 gap-2 text-xs pt-1 border-t border-white/10">
                <div className="space-y-0.5">
                  <span className="text-[10px] text-zinc-400 uppercase font-mono block">Baseline</span>
                  <div className="font-mono font-bold text-zinc-300 text-sm">
                    {metric.baseline.mean.toFixed(2)}{unit}
                  </div>
                  <span className="text-[9px] text-zinc-400 font-mono block">
                    95% CI: [{metric.baseline.ci_lower.toFixed(2)}, {metric.baseline.ci_upper.toFixed(2)}]
                  </span>
                </div>

                <div className="space-y-0.5">
                  <span className="text-[10px] text-emerald-400 uppercase font-mono block">Optimized</span>
                  <div className="font-mono font-bold text-white text-sm">
                    {metric.optimized.mean.toFixed(2)}{unit}
                  </div>
                  <span className="text-[9px] text-zinc-400 font-mono block">
                    95% CI: [{metric.optimized.ci_lower.toFixed(2)}, {metric.optimized.ci_upper.toFixed(2)}]
                  </span>
                </div>
              </div>

              {/* Statistical Significance Indicator */}
              <div className="flex items-center justify-between text-[10px] text-zinc-400 pt-1 font-mono">
                <span className="flex items-center gap-1">
                  <CheckCircle className="w-3 h-3 text-emerald-400" />
                  {metric.is_statistically_significant ? "Statistically Significant" : "Not Significant"}
                </span>
                <span>paired test: p = {metric.p_value < 0.001 ? "< 0.001" : metric.p_value.toFixed(3)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
