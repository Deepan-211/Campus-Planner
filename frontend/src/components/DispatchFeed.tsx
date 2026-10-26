"use client";

import React, { useState } from "react";
import { Stand, TransitRoute, RebalancingResponse, TelemetryEvent } from "../lib/types";
import {
  Radio,
  Truck,
  Bus,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ArrowRight,
  MapPin,
  Sparkles,
  Zap,
} from "lucide-react";

export interface DispatchEvent {
  id: string;
  time: string;
  type: "van" | "shuttle" | "alert" | "system";
  title: string;
  detail: string;
  standId?: string;
  severity?: "normal" | "warning" | "success" | "critical";
}

interface DispatchFeedProps {
  selectedHour: number;
  stands: Stand[];
  hourlyInventories: Record<string, Record<number, number>>;
  rebalancing: RebalancingResponse | null;
  transitRoutes: TransitRoute[];
  onSelectStand?: (standId: string) => void;
  liveEvents?: TelemetryEvent[];
}

export default function DispatchFeed({
  selectedHour,
  stands,
  hourlyInventories,
  rebalancing,
  transitRoutes,
  onSelectStand,
  liveEvents,
}: DispatchFeedProps) {
  const [filter, setFilter] = useState<"all" | "van" | "alerts">("all");

  // Construct dynamic events based on live hourly state and rebalancing routes
  const events: DispatchEvent[] = [];

  // Prepend live real-time WebSocket events if available
  if (liveEvents && liveEvents.length > 0) {
    liveEvents.forEach((evt) => {
      const isPick = evt.type.includes("PICKUP");
      const isDrop = evt.type.includes("DROPOFF");
      const isRental = evt.type === "RENTAL";
      events.push({
        id: evt.id,
        time: evt.time,
        type: isPick || isDrop ? "van" : "system",
        title: isPick
          ? "Van Rebalance Pickup"
          : isDrop
          ? "Van Rebalance Drop-off"
          : isRental
          ? "Student Bike Checkout"
          : "Student Bike Return",
        detail: evt.message,
        standId: evt.stand_id,
        severity: isPick || isDrop ? "warning" : "success",
      });
    });
  }

  const timePrefix = String(selectedHour).padStart(2, "0");

  // 1. Rebalancing steps if available
  if (rebalancing?.route_steps && rebalancing.route_steps.length > 0) {
    const standMap = new Map(stands.map((s) => [s.id, s]));
    rebalancing.route_steps.forEach((step, idx) => {
      const stand = standMap.get(step.stand_id);
      const isPick = step.action.toLowerCase().includes("pickup");
      const isDrop = step.action.toLowerCase().includes("drop");
      const timeMin = String((idx * 7) % 60).padStart(2, "0");

      const bikesCount = Math.abs(step.bikes_change);
      events.push({
        id: `van-step-${idx}`,
        time: `${timePrefix}:${timeMin}`,
        type: "van",
        title: isPick
          ? `Van Pickup (${bikesCount} bikes)`
          : isDrop
          ? `Van Drop-off (${bikesCount} bikes)`
          : `Van Visit`,
        detail: stand ? `${stand.name} (${stand.zone})` : `Stand #${step.stand_id}`,
        standId: step.stand_id,
        severity: isPick ? "normal" : "success",
      });
    });
  } else {
    // Default simulated van dispatch log for current hour
    events.push({
      id: "van-standby",
      time: `${timePrefix}:05`,
      type: "van",
      title: "Rebalancing Van #1 En Route",
      detail: stands[0]
        ? `Calibrating inventory balance at ${stands[0].name}`
        : "Standby for demand surge",
      standId: stands[0]?.id,
      severity: "normal",
    });
  }

  // 2. Starved and Full alerts for current hour
  stands.forEach((s) => {
    const bikes = hourlyInventories[s.id]?.[selectedHour] ?? 0;
    if (bikes === 0) {
      events.push({
        id: `alert-starved-${s.id}`,
        time: `${timePrefix}:12`,
        type: "alert",
        title: "Stockout / Starvation Alert",
        detail: `${s.name} has 0 bikes available for departure.`,
        standId: s.id,
        severity: "critical",
      });
    } else if (bikes >= s.dock_capacity) {
      events.push({
        id: `alert-full-${s.id}`,
        time: `${timePrefix}:18`,
        type: "alert",
        title: "Dock Saturation Warning",
        detail: `${s.name} is 100% full (${s.dock_capacity}/${s.dock_capacity} docks).`,
        standId: s.id,
        severity: "warning",
      });
    }
  });

  // 3. Transit Route updates
  if (transitRoutes && transitRoutes.length > 0) {
    transitRoutes.forEach((route, idx) => {
      events.push({
        id: `transit-${route.id}`,
        time: `${timePrefix}:${String(20 + idx * 12).padStart(2, "0")}`,
        type: "shuttle",
        title: `${route.name} Shuttle`,
        detail: `${route.vehicle_type} operating at ${route.headway_minutes}-min headway across ${route.stops.length} campus stops.`,
        severity: "normal",
      });
    });
  }

  // 4. System telemetry note
  events.push({
    id: "system-sync",
    time: `${timePrefix}:00`,
    type: "system",
    title: "Hourly Telemetry Synchronized",
    detail: `SimPy discrete-event calibrated for ${stands.length} stations.`,
    severity: "normal",
  });

  // Filter events
  const filteredEvents = events.filter((e) => {
    if (filter === "van") return e.type === "van";
    if (filter === "alerts") return e.type === "alert";
    return true;
  });

  return (
    <div className="bg-[#b8b8bc] rounded-2xl p-3.5 border border-zinc-300/60 shadow-sm flex flex-col">
      {/* Section Header */}
      <div className="flex items-center justify-between mb-2.5">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-emerald-600/20 text-emerald-800 flex items-center justify-center">
            <Radio className="w-3.5 h-3.5 text-emerald-700 animate-pulse" />
          </div>
          <div>
            <h3 className="font-bold text-xs text-zinc-900 leading-tight">
              Fleet & Dispatch Feed
            </h3>
            <span className="text-[10px] font-mono text-zinc-600">
              Live @ {timePrefix}:00 • {events.length} events
            </span>
          </div>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1 bg-zinc-300/70 p-0.5 rounded-lg text-[9px] font-medium">
          <button
            type="button"
            onClick={() => setFilter("all")}
            className={`px-2 py-0.5 rounded-md transition ${
              filter === "all"
                ? "bg-white text-zinc-900 font-bold shadow-xs"
                : "text-zinc-600 hover:text-zinc-900"
            }`}
          >
            All
          </button>
          <button
            type="button"
            onClick={() => setFilter("van")}
            className={`px-2 py-0.5 rounded-md transition ${
              filter === "van"
                ? "bg-white text-zinc-900 font-bold shadow-xs"
                : "text-zinc-600 hover:text-zinc-900"
            }`}
          >
            Vans
          </button>
          <button
            type="button"
            onClick={() => setFilter("alerts")}
            className={`px-2 py-0.5 rounded-md transition ${
              filter === "alerts"
                ? "bg-rose-500 text-white font-bold shadow-xs"
                : "text-zinc-600 hover:text-zinc-900"
            }`}
          >
            Alerts
          </button>
        </div>
      </div>

      {/* Events Stream */}
      <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
        {filteredEvents.length === 0 ? (
          <div className="py-6 text-center text-xs text-zinc-600 font-mono">
            No events found for this filter.
          </div>
        ) : (
          filteredEvents.map((evt) => {
            const isAlert = evt.severity === "critical" || evt.severity === "warning";
            const isSuccess = evt.severity === "success";

            return (
              <div
                key={evt.id}
                className={`p-2 rounded-xl text-xs transition border flex items-start gap-2 ${
                  isAlert
                    ? "bg-rose-50/80 border-rose-300/80 text-rose-950"
                    : isSuccess
                    ? "bg-emerald-50/70 border-emerald-300/70 text-emerald-950"
                    : "bg-white/80 border-zinc-200/80 text-zinc-900"
                }`}
              >
                {/* Event Icon Badge */}
                <div
                  className={`w-5 h-5 rounded-md flex items-center justify-center shrink-0 mt-0.5 ${
                    evt.type === "alert"
                      ? "bg-rose-500 text-white"
                      : evt.type === "van"
                      ? "bg-sky-600 text-white"
                      : evt.type === "shuttle"
                      ? "bg-emerald-600 text-white"
                      : "bg-zinc-700 text-white"
                  }`}
                >
                  {evt.type === "alert" && <AlertTriangle className="w-3 h-3" />}
                  {evt.type === "van" && <Truck className="w-3 h-3" />}
                  {evt.type === "shuttle" && <Bus className="w-3 h-3" />}
                  {evt.type === "system" && <Zap className="w-3 h-3" />}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-1 mb-0.5">
                    <span className="font-bold text-[11px] truncate">
                      {evt.title}
                    </span>
                    <span className="text-[9px] font-mono text-zinc-500 shrink-0">
                      {evt.time}
                    </span>
                  </div>
                  <p className="text-[10px] leading-tight text-zinc-700 line-clamp-2">
                    {evt.detail}
                  </p>

                  {/* Quick Action to Focus on Map if Stand attached */}
                  {evt.standId && onSelectStand && (
                    <button
                      type="button"
                      onClick={() => onSelectStand(evt.standId!)}
                      className="mt-1 inline-flex items-center gap-1 text-[9px] font-bold text-sky-700 hover:text-sky-900 hover:underline"
                    >
                      <MapPin className="w-2.5 h-2.5" />
                      <span>Focus Stand on Map</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
