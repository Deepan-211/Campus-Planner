"use client";

import React, { useState } from "react";
import { RebalancingResponse } from "../lib/types";
import {
  Truck,
  ArrowUpRight,
  ArrowDownRight,
  Flag,
  Navigation,
  ChevronRight,
  X,
  ListOrdered,
} from "lucide-react";

export default function RebalancingPanel({
  rebalancing,
  isLoading,
  vanCapacity = 15,
  shiftWindowMinutes = 90,
  onRunEvaluation,
  isEvaluating,
}: {
  rebalancing: RebalancingResponse | null;
  isLoading: boolean;
  vanCapacity?: number;
  shiftWindowMinutes?: number;
  onRunEvaluation?: () => void;
  isEvaluating?: boolean;
}) {
  const [showManifestModal, setShowManifestModal] = useState<boolean>(false);

  if (isLoading || !rebalancing) {
    return (
      <div className="glass-card p-4 rounded-2xl animate-pulse h-full flex flex-col justify-between">
        <div className="h-4 bg-zinc-800 rounded w-1/3" />
        <div className="h-16 bg-zinc-800/50 rounded-xl" />
        <div className="h-4 bg-zinc-800 rounded w-1/2" />
      </div>
    );
  }

  return (
    <div className="glass-card p-4 rounded-2xl flex flex-col justify-between h-full">
      {/* Header */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2">
            <Truck className="w-4 h-4 text-white" />
            <span className="text-xs font-classic font-bold text-white tracking-widest uppercase">
              Van Rebalancing (CVRP)
            </span>
          </div>
          <span
            className="text-[10px] font-classic px-2 py-0.5 rounded-full bg-white/[0.08] border border-white/20 text-white font-bold"
            title="Total bikes rebalanced from surplus to deficit stands"
          >
            {rebalancing.bikes_moved} BIKES REBALANCED
          </span>
        </div>

        <p className="text-[11px] text-zinc-300 line-clamp-2 mb-2">
          {vanCapacity}-capacity van transfers surplus bikes from lecture hubs back to dorms.
        </p>

        {/* Multi-Trip Alert if bikes moved exceed van capacity */}
        {rebalancing.bikes_moved > vanCapacity && (
          <div className="mb-2.5 p-2 rounded-xl bg-amber-500/15 border border-amber-500/40 text-[10.5px] font-mono text-amber-200 flex items-center justify-between">
            <div className="flex items-center gap-1.5 font-bold text-amber-300">
              <Truck className="w-3.5 h-3.5 text-amber-400" />
              <span>{rebalancing.van_trips ?? Math.ceil(rebalancing.bikes_moved / vanCapacity)} Van Trips Required</span>
            </div>
            <span className="text-[9.5px] text-amber-300/80">
              ({rebalancing.bikes_moved} moved &gt; {vanCapacity} cap)
            </span>
          </div>
        )}

        {/* 4-metric preview row with honest time breakdown */}
        {(() => {
          const drivingTime = rebalancing.driving_time_minutes ?? Math.max(0, Number(((rebalancing.total_distance_km / 20) * 60).toFixed(1)));
          const loadingTime = rebalancing.loading_time_minutes ?? Number(((rebalancing.bikes_moved * 90) / 60).toFixed(1));
          const unloadingTime = rebalancing.unloading_time_minutes ?? Number(((rebalancing.bikes_moved * 90) / 60).toFixed(1));
          const totalOps = rebalancing.total_operations ?? (rebalancing.bikes_moved * 2);

          return (
            <>
              <div className="grid grid-cols-4 gap-1.5 bg-black/40 p-2 rounded-xl border border-white/10 mb-1.5 text-center">
                <div>
                  <div className="text-[8px] font-classic text-zinc-400 uppercase tracking-wider">Distance</div>
                  <div className="text-xs font-mono font-bold text-white">
                    {rebalancing.total_distance_km} km
                  </div>
                </div>
                <div>
                  <div className="text-[8px] font-classic text-zinc-400 uppercase tracking-wider">Driving</div>
                  <div className="text-xs font-mono font-bold text-white">
                    {drivingTime} min
                  </div>
                </div>
                <div>
                  <div className="text-[8px] font-classic text-zinc-400 uppercase tracking-wider">Handling</div>
                  <div className="text-xs font-mono font-bold text-white" title={`Loading: ${loadingTime}m, Unloading: ${unloadingTime}m`}>
                    {(loadingTime + unloadingTime).toFixed(1)} min
                  </div>
                </div>
                <div>
                  <div className="text-[8px] font-classic text-zinc-400 uppercase tracking-wider">Total Shift</div>
                  <div className="text-xs font-mono font-bold text-emerald-400">
                    {rebalancing.total_time_minutes} min
                  </div>
                </div>
              </div>

              <div className="text-[9.5px] text-zinc-400 font-mono mb-2 flex items-center justify-between px-0.5">
                <span>{rebalancing.bikes_moved} bikes moved ({totalOps} dock ops)</span>
                <span className="text-zinc-500">90s/bike handle</span>
              </div>
            </>
          );
        })()}
      </div>

      {/* Action Button */}
      <div>
        <button
          onClick={() => setShowManifestModal(true)}
          className="w-full bg-white text-black hover:bg-zinc-200 py-2 px-3 rounded-xl flex items-center justify-between text-xs font-classic font-bold uppercase tracking-wider transition shadow-lg group"
        >
          <div className="flex items-center gap-1.5">
            <ListOrdered className="w-3.5 h-3.5" />
            <span>Inspect Van Manifest</span>
          </div>
          <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition" />
        </button>

        <div className="mt-2 pt-2 border-t border-white/[0.08] flex items-center justify-between text-[10px] text-zinc-400 font-classic uppercase tracking-wider">
          <span>{shiftWindowMinutes}m Shift Window</span>
          <span className="text-zinc-300 flex items-center gap-1">
            <Navigation className="w-3 h-3 text-white" />
            OR-Tools CVRP
          </span>
        </div>
      </div>

      {/* Turn-by-Turn Manifest Modal */}
      {showManifestModal && (
        <div className="fixed inset-0 z-[2000] bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="glass-cockpit max-w-xl w-full p-6 rounded-3xl relative">
            <div className="flex items-center justify-between mb-4 border-b border-white/10 pb-3">
              <div className="flex items-center gap-2.5">
                <Truck className="w-5 h-5 text-white" />
                <div>
                  <h3 className="font-bold text-white text-base">
                    Midday Van Rebalancing Manifest
                  </h3>
                  <p className="text-xs text-zinc-400 font-mono">
                    Shift Budget: {shiftWindowMinutes} min • Van Capacity: {vanCapacity} Bikes • {rebalancing.van_trips ?? Math.ceil(rebalancing.bikes_moved / vanCapacity)} Van Trip(s) • OR-Tools CVRP
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowManifestModal(false)}
                className="p-1 rounded-full text-zinc-400 hover:text-white bg-white/5 hover:bg-white/10"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-2 max-h-[380px] overflow-y-auto pr-1">
              {rebalancing.route_steps.map((step) => {
                const isPickup = step.action === "PICKUP";
                const isDropoff = step.action === "DROPOFF";
                const isStart = step.action === "START";
                const isEnd = step.action === "END";

                return (
                  <div
                    key={step.stop_order}
                    className="p-3 rounded-xl bg-zinc-900/60 border border-white/10 flex items-center justify-between text-xs hover:border-white/20 transition"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-6 h-6 rounded-full bg-white/10 border border-white/20 flex items-center justify-center text-[10px] font-mono font-bold text-white shrink-0">
                        {step.stop_order}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-white">{step.stand_name}</span>
                          {step.trip_number && (
                            <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-sky-950/90 text-sky-300 border border-sky-500/40">
                              Trip {step.trip_number}
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-zinc-400 font-mono">
                          Arr: {step.arrival_time_min} min • Dep: {step.departure_time_min} min
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      {isPickup && (
                        <span className="flex items-center gap-1 font-mono font-bold text-white text-xs px-2 py-0.5 rounded bg-white/10 border border-white/20">
                          <ArrowUpRight className="w-3.5 h-3.5" />
                          +{step.bikes_change} PICKUP
                        </span>
                      )}
                      {isDropoff && (
                        <span className="flex items-center gap-1 font-mono font-bold text-zinc-200 text-xs px-2 py-0.5 rounded bg-white/10 border border-white/20">
                          <ArrowDownRight className="w-3.5 h-3.5" />
                          {step.bikes_change} DROPOFF
                        </span>
                      )}
                      {(isStart || isEnd) && (
                        <span className="flex items-center gap-1 text-zinc-300 text-[11px] font-mono">
                          <Flag className="w-3 h-3 text-white" />
                          {step.action}
                        </span>
                      )}

                      <div className="px-2 py-0.5 rounded bg-black border border-white/10 text-[10px] font-mono text-zinc-200">
                        Van: {step.van_load_after}/{vanCapacity}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-4 pt-3 border-t border-white/10 flex items-center justify-between">
              <span className="text-xs text-zinc-300 font-mono">
                Total Travel: {rebalancing.total_distance_km} km in {rebalancing.total_time_minutes} min • {rebalancing.van_trips ?? Math.ceil(rebalancing.bikes_moved / vanCapacity)} Van Trip(s)
              </span>
              <button
                onClick={() => setShowManifestModal(false)}
                className="px-4 py-1.5 bg-white text-black font-semibold text-xs rounded-xl hover:bg-zinc-200 transition"
              >
                Close Manifest
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
