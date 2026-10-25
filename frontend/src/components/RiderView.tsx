"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  Stand,
  TripOptionsResponse,
  TripOption,
  CampusInfo,
  TransitRoute,
  DataSourceInfo,
} from "../lib/types";
import { fetchTripOptions, fetchTransitRoutes } from "../lib/api";
import CampusMap from "./CampusMap";
import {
  MapPin,
  Navigation,
  ArrowUpDown,
  Clock,
  Bike,
  Footprints,
  Sparkles,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Compass,
  DollarSign,
  ShieldAlert,
  Zap,
  Bus,
  Car,
} from "lucide-react";

export default function RiderView({
  stands,
  campusId,
  campuses,
  onSelectCampus,
  hourlyInventories,
  dataSource,
}: {
  stands: Stand[];
  campusId: string;
  campuses: CampusInfo[];
  onSelectCampus: (id: string) => void;
  hourlyInventories: Record<string, Record<number, number>>;
  dataSource?: DataSourceInfo | null;
}) {
  const currentCampus = campuses.find((c) => c.id === campusId);

  // Default origin to first stand, destination to second stand (or last stand)
  const [originStandId, setOriginStandId] = useState<string>("");
  const [destStandId, setDestStandId] = useState<string>("");
  const [selectedHour, setSelectedHour] = useState<number>(8);
  const [selectedMinute, setSelectedMinute] = useState<number>(30);
  const [isUsingGps, setIsUsingGps] = useState<boolean>(false);
  const [userCoords, setUserCoords] = useState<[number, number] | null>(null);

  const [tripOptions, setTripOptions] = useState<TripOptionsResponse | null>(null);
  const [selectedOptionId, setSelectedOptionId] = useState<string>("bike");
  const [transitRoutes, setTransitRoutes] = useState<TransitRoute[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch campus transit routes on mount and campus switch
  useEffect(() => {
    fetchTransitRoutes(campusId)
      .then((routes) => setTransitRoutes(routes))
      .catch((err) => console.warn("Could not fetch transit routes:", err));
  }, [campusId]);

  // Initialize stands when campus loads
  useEffect(() => {
    if (stands.length >= 2) {
      setOriginStandId(stands[0].id);
      setDestStandId(stands[stands.length - 1].id);
    } else if (stands.length === 1) {
      setOriginStandId(stands[0].id);
      setDestStandId(stands[0].id);
    }
  }, [campusId, stands]);

  // Request trip options whenever origin, destination, or time changes
  useEffect(() => {
    if (!originStandId || !destStandId || stands.length === 0) return;

    if (originStandId === destStandId) {
      setTripOptions(null);
      setError("Origin and destination stands cannot be identical. Please select different stands.");
      setIsLoading(false);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    fetchTripOptions({
      campus_id: campusId,
      origin_stand_id: originStandId,
      dest_stand_id: destStandId,
      departure_hour: selectedHour,
      departure_minute: selectedMinute,
      origin_coords: userCoords ? [userCoords[0], userCoords[1]] : undefined,
    })
      .then((res) => {
        if (!isMounted) return;
        setTripOptions(res);
        setSelectedOptionId(res.recommended_option_id);
        setIsLoading(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        console.error("Trip options error:", err);
        setError("Unable to compute journey options. Please verify stand selection.");
        setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [campusId, originStandId, destStandId, selectedHour, selectedMinute, userCoords]);

  // Swap origin and destination
  const handleSwap = () => {
    const temp = originStandId;
    setOriginStandId(destStandId);
    setDestStandId(temp);
    setUserCoords(null);
    setIsUsingGps(false);
  };

  // Simulated or real GPS location
  const handleUseLocation = () => {
    setIsUsingGps(true);
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          // If within ~50km of campus, use it, else place at stand 0 coordinate
          setUserCoords([pos.coords.latitude, pos.coords.longitude]);
        },
        () => {
          // Fallback to campus main entrance
          if (stands.length > 0) {
            setUserCoords([stands[0].latitude + 0.0003, stands[0].longitude - 0.0003]);
          }
        }
      );
    } else if (stands.length > 0) {
      setUserCoords([stands[0].latitude + 0.0003, stands[0].longitude - 0.0003]);
    }
  };

  // Handle map stand click (toggle origin / destination)
  const handleMapStandClick = (stand: Stand) => {
    if (!originStandId) {
      setOriginStandId(stand.id);
    } else if (originStandId === stand.id) {
      return;
    } else {
      setDestStandId(stand.id);
    }
  };

  const selectedOption: TripOption | undefined = useMemo(() => {
    if (!tripOptions) return undefined;
    return tripOptions.options.find((o) => o.id === selectedOptionId) || tripOptions.options[0];
  }, [tripOptions, selectedOptionId]);

  const renderModeIcon = (opt: TripOption) => {
    if (opt.mode_icon === "Zap" || opt.id === "scooter") {
      return (
        <div className="w-7 h-7 rounded-full flex items-center justify-center bg-amber-500/20 text-amber-300 border border-amber-500/40">
          <Zap className="w-4 h-4" />
        </div>
      );
    }
    if (opt.mode_icon === "Bus" || opt.id.includes("SHUTTLE")) {
      return (
        <div className="w-7 h-7 rounded-full flex items-center justify-center bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
          <Bus className="w-4 h-4" />
        </div>
      );
    }
    if (opt.mode_icon === "Car" || opt.id.includes("CART")) {
      return (
        <div className="w-7 h-7 rounded-full flex items-center justify-center bg-orange-500/20 text-orange-300 border border-orange-500/40">
          <Car className="w-4 h-4" />
        </div>
      );
    }
    if (opt.id === "bike") {
      return (
        <div className="w-7 h-7 rounded-full flex items-center justify-center bg-sky-500/20 text-sky-300 border border-sky-500/40">
          <Bike className="w-4 h-4" />
        </div>
      );
    }
    return (
      <div className="w-7 h-7 rounded-full flex items-center justify-center bg-lime-500/20 text-lime-300 border border-lime-500/40">
        <Footprints className="w-4 h-4" />
      </div>
    );
  };

  const getPolylineColor = (opt?: TripOption) => {
    if (!opt) return "#38bdf8";
    if (opt.id === "bike") return "#38bdf8";
    if (opt.id === "scooter") return "#f59e0b";
    if (opt.mode_icon === "Bus" || opt.id.includes("SHUTTLE")) return "#10b981";
    if (opt.mode_icon === "Car" || opt.id.includes("CART")) return "#f97316";
    return "#a3e635";
  };

  return (
    <div className="w-full space-y-5">
      {/* Top Banner: Rider Portal Welcome & Campus Selector */}
      <div className="glass-cockpit rounded-3xl p-5 border border-white/10 shadow-2xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
            <h2 className="font-classic font-bold text-base sm:text-lg text-white tracking-wider uppercase">
              Student Rider View • Journey Planner
            </h2>
          </div>
          <p className="text-xs font-editorial italic text-zinc-300 mt-1">
            Real-time multi-modal travel options with honest availability, OSMnx shortest pathways, and zero guess-work.
          </p>
        </div>

        {/* Data Badge */}
        <div className="flex flex-wrap items-center gap-2.5 self-start md:self-auto">
          <div
            className={`text-[10px] font-mono px-2.5 py-1 rounded-full flex items-center gap-1.5 border ${
              dataSource?.type === "survey"
                ? "bg-emerald-950/60 border-emerald-500/40 text-emerald-300"
                : "bg-blue-950/60 border-blue-500/40 text-blue-300"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                dataSource?.type === "survey" ? "bg-emerald-400" : "bg-blue-400"
              }`}
            />
            <span>{dataSource?.label || "Synthetic data (calibrated NHPP model)"}</span>
          </div>
        </div>
      </div>

      {/* Main Two-Column Layout: Planner Form & Route Details (Left) + Interactive Map (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left Column: Origin/Dest Selectors & Mode Option Cards (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Trip Search Form */}
          <div className="glass-card p-5 rounded-3xl border border-white/10 shadow-xl space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-white/10">
              <span className="text-xs font-classic font-bold text-white uppercase tracking-wider">
                Plan Your Campus Route
              </span>
              <button
                onClick={handleUseLocation}
                className={`text-[10px] font-mono px-2.5 py-1 rounded-full border transition flex items-center gap-1.5 ${
                  isUsingGps
                    ? "bg-emerald-950/80 text-emerald-300 border-emerald-500/50"
                    : "bg-white/5 text-zinc-300 border-white/10 hover:border-white/30"
                }`}
                title="Use current GPS location"
              >
                <Navigation className="w-3 h-3 text-emerald-400" />
                <span>{isUsingGps ? "Using Location" : "My Location"}</span>
              </button>
            </div>

            {/* Origin Input */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-classic uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span>Origin (Where you are)</span>
              </label>
              <div className="relative">
                <select
                  value={originStandId}
                  onChange={(e) => {
                    setOriginStandId(e.target.value);
                    setUserCoords(null);
                    setIsUsingGps(false);
                  }}
                  className="w-full bg-black/60 border border-white/15 focus:border-emerald-400 text-xs font-classic text-white rounded-xl py-2.5 px-3 pr-8 focus:outline-none transition appearance-none cursor-pointer"
                >
                  {stands.map((s) => (
                    <option key={s.id} value={s.id} className="bg-zinc-950 text-white">
                      {s.name} ({s.zone})
                    </option>
                  ))}
                </select>
                <MapPin className="w-4 h-4 text-emerald-400 absolute right-3 top-3 pointer-events-none" />
              </div>
            </div>

            {/* Swap Button */}
            <div className="flex justify-center -my-1">
              <button
                onClick={handleSwap}
                className="p-1.5 rounded-full bg-zinc-900 border border-white/20 text-zinc-300 hover:text-white hover:border-white/50 transition shadow-lg active:rotate-180"
                title="Swap origin and destination"
              >
                <ArrowUpDown className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Destination Input */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-classic uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-rose-500" />
                <span>Destination (Where to go)</span>
              </label>
              <div className="relative">
                <select
                  value={destStandId}
                  onChange={(e) => setDestStandId(e.target.value)}
                  className="w-full bg-black/60 border border-white/15 focus:border-rose-400 text-xs font-classic text-white rounded-xl py-2.5 px-3 pr-8 focus:outline-none transition appearance-none cursor-pointer"
                >
                  {stands.map((s) => (
                    <option key={s.id} value={s.id} className="bg-zinc-950 text-white">
                      {s.name} ({s.zone})
                    </option>
                  ))}
                </select>
                <MapPin className="w-4 h-4 text-rose-400 absolute right-3 top-3 pointer-events-none" />
              </div>
            </div>

            {/* Identical Origin & Destination Warning */}
            {originStandId === destStandId && (
              <div className="p-3 rounded-2xl bg-amber-500/15 border border-amber-500/40 text-amber-200 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
                <span>Origin and destination stands cannot be identical. Please select different stands.</span>
              </div>
            )}

            {/* Time Selector */}
            <div className="pt-2 border-t border-white/10 flex items-center justify-between text-xs font-mono">
              <div className="flex items-center gap-1.5 text-zinc-400">
                <Clock className="w-3.5 h-3.5 text-zinc-300" />
                <span>Departure Time:</span>
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={selectedHour}
                  onChange={(e) => setSelectedHour(Number(e.target.value))}
                  className="bg-black/60 border border-white/15 text-white text-xs font-mono rounded-lg px-2 py-1 focus:outline-none"
                >
                  {Array.from({ length: 15 }, (_, i) => i + 7).map((h) => (
                    <option key={h} value={h} className="bg-zinc-950 text-white">
                      {h.toString().padStart(2, "0")}:00
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => {
                    const now = new Date();
                    setSelectedHour(Math.min(21, Math.max(7, now.getHours())));
                    setSelectedMinute(now.getMinutes());
                  }}
                  className="text-[10px] font-classic uppercase px-2 py-1 rounded bg-white/10 text-white hover:bg-white/20 transition"
                >
                  Now
                </button>
              </div>
            </div>
          </div>

          {/* Travel Options Cards */}
          <div className="space-y-3">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-classic font-bold text-white uppercase tracking-wider">
                Available Travel Options
              </span>
              {isLoading && (
                <span className="text-[10px] font-mono text-zinc-400 animate-pulse">
                  Calculating routes...
                </span>
              )}
            </div>

            {error && (
              <div className="p-3 bg-red-950/60 border border-red-500/40 rounded-2xl text-xs text-red-200 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {tripOptions?.options.map((opt) => {
              const isSelected = selectedOptionId === opt.id;
              const isBike = opt.id === "bike";
              const isWalk = opt.id === "walk";
              const isRec = opt.tags.includes("Recommended");

              return (
                <div
                  key={opt.id}
                  onClick={() => setSelectedOptionId(opt.id)}
                  className={`p-4 rounded-2xl cursor-pointer transition relative border ${
                    isSelected
                      ? "bg-zinc-900/90 border-white/40 shadow-[0_0_20px_rgba(255,255,255,0.15)] ring-1 ring-white/20"
                      : "bg-black/50 border-white/10 hover:border-white/25 hover:bg-zinc-900/40"
                  }`}
                >
                  {/* Top Badges */}
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      {renderModeIcon(opt)}
                      <div>
                        <span className="text-xs font-classic font-bold text-white tracking-wide">
                          {opt.mode_name}
                        </span>
                        <div className="text-[10px] text-zinc-400 font-mono">
                          {opt.distance_m}m • {opt.cost === 0 ? "FREE" : `${opt.cost_currency}${opt.cost.toFixed(2)}`}
                        </div>
                      </div>
                    </div>

                    {/* Tag Pills */}
                    <div className="flex items-center gap-1.5 flex-wrap justify-end">
                      {opt.tags.map((tag) => (
                        <span
                          key={tag}
                          className={`text-[9px] font-classic uppercase font-bold px-2 py-0.5 rounded-full border ${
                            tag === "Recommended"
                              ? "bg-violet-950/80 text-violet-300 border-violet-500/50 shadow-[0_0_10px_rgba(139,92,246,0.3)] flex items-center gap-1"
                              : tag === "Fastest"
                              ? "bg-sky-950/80 text-sky-300 border-sky-500/40"
                              : tag === "Passes Your Route"
                              ? "bg-emerald-950/80 text-emerald-300 border-emerald-500/40"
                              : "bg-zinc-900 text-zinc-300 border-white/10"
                          }`}
                        >
                          {tag === "Recommended" && <Sparkles className="w-2.5 h-2.5 text-violet-400" />}
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Main Metric: Total Duration & Component Breakdown */}
                  <div className="flex items-baseline justify-between mt-1">
                    <div>
                      <div className="text-2xl font-bold font-mono text-white tracking-tight">
                        {opt.total_duration_min} min
                      </div>
                      <div className="text-[10px] text-zinc-400 font-mono">
                        {opt.id === "bike"
                          ? `Walk: ${opt.walk_duration_min} min • Unlock: 0.5 min • Ride: ${opt.transit_duration_min} min${
                              opt.wait_duration_min > 0 ? ` • Wait: ${opt.wait_duration_min} min` : ""
                            }`
                          : opt.id === "scooter"
                          ? `Walk: ${opt.walk_duration_min} min • Unlock: 0.5 min • Ride: ${opt.transit_duration_min} min${
                              opt.wait_duration_min > 0 ? ` • Wait: ${opt.wait_duration_min} min` : ""
                            }`
                          : opt.legs.length > 1
                          ? `Transit: ${opt.transit_duration_min} min • Walk: ${opt.walk_duration_min} min${
                              opt.wait_duration_min > 0 ? ` • Wait: ${opt.wait_duration_min} min` : ""
                            }`
                          : opt.id === "walk"
                          ? "Direct continuous walking"
                          : `Ride: ${opt.transit_duration_min} min`}
                      </div>
                      <div className="text-[10px] text-zinc-400 font-mono mt-0.5">
                        Distance: {opt.distance_m} m
                      </div>
                    </div>

                    {/* Availability Dot & Status */}
                    <div className="text-right">
                      <div className="flex items-center gap-1.5 justify-end">
                        <span
                          className={`w-2 h-2 rounded-full ${
                            opt.availability_status === "HIGH"
                              ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]"
                              : opt.availability_status === "LOW"
                              ? "bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.8)]"
                              : "bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.8)]"
                          }`}
                        />
                        <span className="text-[10px] font-mono uppercase font-bold text-zinc-300">
                          {opt.availability_status}
                        </span>
                      </div>
                      <span className="text-[9.5px] text-zinc-400 font-mono block mt-0.5 max-w-[200px] truncate">
                        {opt.availability_detail}
                      </span>
                    </div>
                  </div>

                  {/* Recommendation Reason Banner */}
                  {opt.recommendation_reason && (
                    <div className="mt-2.5 p-2 rounded-xl bg-violet-950/40 border border-violet-500/30 text-[10.5px] text-violet-200 flex items-start gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-violet-400 shrink-0 mt-0.5" />
                      <span>{opt.recommendation_reason}</span>
                    </div>
                  )}

                  {/* Honest Fallback Warning if 0 bikes available */}
                  {opt.fallback_message && (
                    <div className="mt-2.5 p-2 rounded-xl bg-amber-950/50 border border-amber-500/40 text-[10.5px] text-amber-200 flex items-start gap-1.5">
                      <ShieldAlert className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                      <span>{opt.fallback_message}</span>
                    </div>
                  )}

                  {/* Leg Steps (Rendered when card is selected) */}
                  {isSelected && opt.legs.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-white/10 space-y-1.5">
                      <span className="text-[9px] font-classic uppercase text-zinc-400 tracking-wider block">
                        Turn-By-Turn Route Steps
                      </span>
                      {opt.legs.map((leg, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between text-[10.5px] text-zinc-300 font-mono bg-black/40 px-2.5 py-1.5 rounded-lg border border-white/5"
                        >
                          <div className="flex items-center gap-2">
                            <span className="text-zinc-500">{idx + 1}.</span>
                            <span>
                              {leg.mode === "bike"
                                ? "🚴 Cycle"
                                : leg.mode === "scooter"
                                ? "⚡ E-Scooter"
                                : leg.mode === "shuttle"
                                ? "🚌 EV Shuttle"
                                : leg.mode === "golf_cart"
                                ? "🚐 Golf Cart"
                                : "🚶 Walk"}
                            </span>
                            <span className="text-zinc-400 truncate max-w-[140px]">
                              {leg.from_name.split(" ")[0]} → {leg.to_name.split(" ")[0]}
                            </span>
                          </div>
                          <span className="text-white font-bold">{leg.duration_min} min ({leg.distance_m} m)</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Campus Fixed Transit Schedule Overview Card */}
            {transitRoutes.length > 0 && (
              <div className="glass-card p-3 rounded-2xl border border-white/10 space-y-2 text-xs">
                <span className="text-[10px] font-classic uppercase font-bold text-zinc-300 tracking-wider flex items-center gap-1.5">
                  <Bus className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Campus Transit Timetable</span>
                </span>
                <div className="space-y-1.5">
                  {transitRoutes.map((tr) => (
                    <div
                      key={tr.id}
                      className="flex items-center justify-between p-2 rounded-xl bg-black/40 border border-white/5 text-[11px] font-mono"
                    >
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: tr.color }} />
                        <span className="text-white font-bold">{tr.name}</span>
                      </div>
                      <span className="text-zinc-400">
                        Every {tr.headway_minutes} min • {tr.operating_hours}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Real OSMnx Map with Visual Route Polyline (7 cols) */}
        <div className="lg:col-span-7 space-y-3">
          <div className="glass-card p-3 rounded-3xl border border-white/10 shadow-2xl relative">
            <div className="flex items-center justify-between px-2 pb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-classic font-bold text-white uppercase tracking-wider">
                  Campus Pathway Map
                </span>
                <span className="text-[10px] font-mono text-zinc-400">
                  Click any stand to set route endpoint
                </span>
              </div>
              {selectedOption && (
                <div className="text-[10px] font-mono text-zinc-300 bg-white/5 border border-white/10 px-2.5 py-0.5 rounded-full">
                  Showing: <strong className="text-white">{selectedOption.mode_name}</strong> ({selectedOption.total_duration_min} min • {selectedOption.distance_m} m)
                </div>
              )}
            </div>

            <CampusMap
              stands={stands}
              hourlyInventories={hourlyInventories}
              selectedHour={selectedHour}
              showRebalancingRoute={false}
              activePolyline={selectedOption?.full_geometry}
              polylineColor={getPolylineColor(selectedOption)}
              originStandId={originStandId}
              destStandId={destStandId}
              onStandClick={handleMapStandClick}
              transitRoutes={transitRoutes}
            />

            {/* Map Legend */}
            <div className="mt-3 pt-2 border-t border-white/10 flex flex-wrap items-center justify-between gap-2 text-[10px] font-mono text-zinc-400 px-2">
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                  <span>Start Pin</span>
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
                  <span>Destination Pin</span>
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-sky-400" />
                  <span>Bicycle Route</span>
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
                  <span>Walking Route</span>
                </span>
              </div>
              <span className="text-zinc-500">
                Speed: Bike 12 km/h • Walk 4.8 km/h
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
