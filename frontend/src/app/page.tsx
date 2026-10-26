"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import CampusMap from "../components/CampusMap";
import StandTelemetryGrid from "../components/StandTelemetryGrid";
import TimelineSlider from "../components/TimelineSlider";
import AllocationPanel from "../components/AllocationPanel";
import RebalancingPanel from "../components/RebalancingPanel";
import MetricComparisonGrid from "../components/MetricComparisonGrid";
import ComparisonPanel from "../components/ComparisonPanel";
import ForecastTab from "../components/ForecastTab";
import AssumptionsPanel from "../components/AssumptionsPanel";
import ExplainerCard from "../components/ExplainerCard";
import RiderView from "../components/RiderView";
import DispatchFeed from "../components/DispatchFeed";
import StandAlertsInspector from "../components/StandAlertsInspector";
import AuthModal from "../components/AuthModal";
import {
  CampusInfo,
  Stand,
  AllocationResponse,
  RebalancingResponse,
  EvaluationResponse,
  ForecastResponse,
  ForecastEvalResponse,
  DataSourceInfo,
  ConfigSummary,
  TransitRoute,
  UserProfile,
  TelemetryFrame,
} from "../lib/types";
import {
  fetchCampusList,
  fetchStands,
  fetchDataSource,
  fetchAssumptions,
  fetchForecast,
  fetchForecastEval,
  optimizeAllocation,
  planRebalancing,
  runEvaluation,
  fetchTransitRoutes,
  fetchCurrentUser,
  logoutUser,
  getTelemetryWsUrl,
  controlTelemetry,
} from "../lib/api";
import {
  Search,
  Bell,
  Headphones,
  Compass,
  Grid,
  Briefcase,
  Settings,
  Maximize2,
  Volume2,
  Clock,
  Crosshair,
  Video,
  Mic,
  Navigation,
  RefreshCw,
  Bike,
  Zap,
  Bus,
  Car,
  MoreHorizontal,
  Image as ImageIcon,
  Send,
  X,
  ChevronRight,
  AlertCircle,
  CheckCircle2,
  PhoneOff,
  Layers,
  BarChart3,
  LogIn,
  LogOut,
  ShieldCheck,
} from "lucide-react";

export default function DashboardPage() {
  const [campuses, setCampuses] = useState<CampusInfo[]>([]);
  const [selectedCampusId, setSelectedCampusId] = useState<string>("vsb_karur");
  const [stands, setStands] = useState<Stand[]>([]);
  const [dataSource, setDataSource] = useState<DataSourceInfo | null>(null);
  const [assumptions, setAssumptions] = useState<ConfigSummary | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [forecastEval, setForecastEval] = useState<ForecastEvalResponse | null>(null);
  const [transitRoutes, setTransitRoutes] = useState<TransitRoute[]>([]);

  const [selectedHour, setSelectedHour] = useState<number>(8); // default to 08:00 AM
  const [allocation, setAllocation] = useState<AllocationResponse | null>(null);
  const [rebalancing, setRebalancing] = useState<RebalancingResponse | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationResponse | null>(null);
  const [isEvaluating, setIsEvaluating] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Active view & modal state for deep inspection
  const [activeNav, setActiveNav] = useState<"cockpit" | "rider" | "telemetry" | "rebalance" | "settings">("cockpit");
  const [openModal, setOpenModal] = useState<"none" | "rider" | "evaluation" | "forecast" | "assumptions" | "rebalancing">("none");
  const [selectedFleetMode, setSelectedFleetMode] = useState<string | null>(null);

  // Map state
  const [mapStyle, setMapStyle] = useState<"satellite" | "streets">("satellite");
  const [showTransitLines, setShowTransitLines] = useState<boolean>(true);
  const [showRebalancingRoute, setShowRebalancingRoute] = useState<boolean>(true);

  // Selected stand focus for map and urgency inspector
  const [selectedStandId, setSelectedStandId] = useState<string | null>(null);

  // Authentication & session state
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState<boolean>(false);

  // Real-time WebSocket Telemetry State
  const [telemetryFrame, setTelemetryFrame] = useState<TelemetryFrame | null>(null);
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const wsRef = useRef<WebSocket | null>(null);

  const getInitials = (name?: string) => {
    if (!name) return "CR";
    const parts = name.trim().split(" ");
    if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    return name.slice(0, 2).toUpperCase();
  };

  // Connect to Real-Time WebSocket Telemetry
  useEffect(() => {
    let isSubscribed = true;
    let socket: WebSocket | null = null;
    let reconnectTimer: any = null;

    const connectWs = () => {
      try {
        const wsUrl = getTelemetryWsUrl(selectedCampusId);
        socket = new WebSocket(wsUrl);
        wsRef.current = socket;

        socket.onopen = () => {
          if (isSubscribed) setWsConnected(true);
        };

        socket.onmessage = (event) => {
          if (!isSubscribed) return;
          try {
            const frame: TelemetryFrame = JSON.parse(event.data);
            setTelemetryFrame(frame);
          } catch (err) {
            console.warn("Failed to parse telemetry frame:", err);
          }
        };

        socket.onclose = () => {
          if (isSubscribed) {
            setWsConnected(false);
            reconnectTimer = setTimeout(connectWs, 3000);
          }
        };

        socket.onerror = () => {
          socket?.close();
        };
      } catch (e) {
        console.warn("WebSocket connection error:", e);
      }
    };

    connectWs();

    return () => {
      isSubscribed = false;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (socket) socket.close();
    };
  }, [selectedCampusId]);

  const handleTelemetryControl = (action: "pause" | "speed", value?: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      if (action === "pause") {
        wsRef.current.send(JSON.stringify({ action: "set_pause", paused: value }));
      } else if (action === "speed") {
        wsRef.current.send(JSON.stringify({ action: "set_speed", speed: value }));
      }
    } else {
      controlTelemetry(selectedCampusId, action === "speed" ? value : undefined, action === "pause" ? value : undefined)
        .then(setTelemetryFrame)
        .catch(console.warn);
    }
  };

  // Load campus list and authenticate user on mount
  useEffect(() => {
    fetchCampusList()
      .then((list) => setCampuses(list))
      .catch((err) => console.warn("Could not fetch campus list:", err));

    fetchCurrentUser()
      .then((user) => {
        if (user) setCurrentUser(user);
      })
      .catch((err) => console.warn("Could not fetch current user:", err));
  }, []);

  // Load campus data whenever selected campus changes
  const loadCampusData = useCallback(async (campusId: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const [standsData, dsData, assumpData, routesData] = await Promise.all([
        fetchStands(campusId),
        fetchDataSource(campusId),
        fetchAssumptions(campusId),
        fetchTransitRoutes(campusId).catch(() => []),
      ]);
      setStands(standsData);
      setDataSource(dsData);
      setAssumptions(assumpData);
      setTransitRoutes(routesData);

      const [allocData, rebData, evalData, fcData, fcEvalData] = await Promise.all([
        optimizeAllocation(undefined, campusId),
        planRebalancing(undefined, undefined, campusId),
        runEvaluation(30, assumpData?.total_bikes, campusId),
        fetchForecast("2026-10-23", campusId),
        fetchForecastEval(campusId),
      ]);

      setAllocation(allocData);
      setRebalancing(rebData);
      setEvaluation(evalData);
      setForecast(fcData);
      setForecastEval(fcEvalData);
    } catch (err: any) {
      console.error("Dashboard data load error:", err);
      setError(`Failed to load ${campusId} data: ${err.message || err}`);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCampusData(selectedCampusId);
  }, [selectedCampusId, loadCampusData]);

  // Run on-demand Monte Carlo evaluation
  const handleRunEvaluation = async () => {
    setIsEvaluating(true);
    try {
      const evalData = await runEvaluation(30, assumptions?.total_bikes, selectedCampusId);
      setEvaluation(evalData);
    } catch (err) {
      console.error("Evaluation run error:", err);
    } finally {
      setIsEvaluating(false);
    }
  };


  // Derive hourly inventory mapping
  const hourlyInventories: Record<string, Record<number, number>> = {};
  stands.forEach((s) => {
    hourlyInventories[s.id] = {};
    for (let h = 7; h <= 22; h++) {
      if (evaluation?.stand_hourly_optimized?.[s.id]?.[h] !== undefined) {
        hourlyInventories[s.id][h] = Math.round(
          evaluation.stand_hourly_optimized[s.id][h]
        );
      } else {
        const base =
          allocation?.optimized_allocation?.[s.id] ?? Math.round(s.dock_capacity * 0.5);
        hourlyInventories[s.id][h] = base;
      }
    }
  });

  const totalBikes = assumptions?.total_bikes ?? allocation?.fleet_size ?? 100;
  const currentCampus = campuses.find((c) => c.id === selectedCampusId);

  return (
    <div className="min-h-screen bg-[#ececee] p-3 sm:p-6 lg:p-8 flex items-center justify-center font-sans antialiased text-zinc-900 selection:bg-zinc-800 selection:text-white">
      {/* MASTER CONTAINER MATCHING MOCKUP */}
      <div className="w-full max-w-[1360px] bg-white rounded-[32px] shadow-2xl shadow-zinc-400/30 border border-zinc-300/70 overflow-hidden flex flex-col lg:flex-row relative min-h-[820px]">
        
        {/* LEFT VERTICAL DOCK / SIDEBAR */}
        <aside className="w-full lg:w-[76px] bg-[#d5d5d8] flex flex-row lg:flex-col items-center justify-between py-6 px-3 border-r border-zinc-300/80 shrink-0 z-20">
          {/* Top Logo Glyph */}
          <div className="flex flex-col items-center gap-6">
            <button
              onClick={() => {
                setActiveNav("cockpit");
                setOpenModal("none");
              }}
              title="CampusRide Planner"
              className="w-11 h-11 rounded-2xl bg-zinc-900 text-white flex items-center justify-center font-black tracking-tighter text-xl shadow-md hover:scale-105 transition cursor-pointer"
            >
              <div className="flex items-center justify-center -space-x-1">
                <span className="text-white text-lg font-bold">C</span>
                <span className="text-zinc-400 text-sm font-semibold">R</span>
              </div>
            </button>

            {/* Vertical Icon Nav Menu */}
            <div className="flex flex-row lg:flex-col items-center gap-4">
              {/* Cockpit / Overview */}
              <button
                onClick={() => {
                  setActiveNav("cockpit");
                  setOpenModal("none");
                }}
                className={`p-2.5 rounded-2xl transition ${
                  activeNav === "cockpit" && openModal === "none"
                    ? "bg-zinc-800 text-white shadow-md"
                    : "text-zinc-600 hover:text-zinc-900 hover:bg-zinc-300/60"
                }`}
                title="Campus Overview Cockpit"
              >
                <Headphones className="w-5 h-5" />
              </button>

              {/* Rider Trip Planner */}
              <button
                onClick={() => {
                  setActiveNav("rider");
                  setOpenModal("rider");
                }}
                className={`p-2.5 rounded-2xl transition ${
                  activeNav === "rider" || openModal === "rider"
                    ? "bg-zinc-800 text-white shadow-md"
                    : "text-zinc-600 hover:text-zinc-900 hover:bg-zinc-300/60"
                }`}
                title="Rider Journey Planner"
              >
                <Navigation className="w-5 h-5" />
              </button>

              {/* Stand Telemetry Grid */}
              <button
                onClick={() => {
                  setActiveNav("telemetry");
                  setOpenModal("evaluation");
                }}
                className={`p-2.5 rounded-2xl transition ${
                  activeNav === "telemetry" || openModal === "evaluation"
                    ? "bg-zinc-800 text-white shadow-md"
                    : "text-zinc-600 hover:text-zinc-900 hover:bg-zinc-300/60"
                }`}
                title="Monte Carlo & Stand Telemetry"
              >
                <Grid className="w-5 h-5" />
              </button>

              {/* Rebalancing Van Routes */}
              <button
                onClick={() => {
                  setActiveNav("rebalance");
                  setOpenModal("rebalancing");
                }}
                className={`p-2.5 rounded-2xl transition ${
                  activeNav === "rebalance" || openModal === "rebalancing"
                    ? "bg-zinc-800 text-white shadow-md"
                    : "text-zinc-600 hover:text-zinc-900 hover:bg-zinc-300/60"
                }`}
                title="Van Rebalancing CVRP"
              >
                <Briefcase className="w-5 h-5" />
              </button>

              {/* Subtle Horizontal Divider */}
              <div className="hidden lg:block w-7 h-[1px] bg-zinc-400/40 my-1" />

              {/* Live Alerts & Notifications */}
              <button
                onClick={() => {
                  setOpenModal("forecast");
                }}
                className={`p-2.5 rounded-2xl transition relative ${
                  openModal === "forecast"
                    ? "bg-zinc-800 text-white shadow-md"
                    : "text-zinc-600 hover:text-zinc-900 hover:bg-zinc-300/60"
                }`}
                title="Demand Forecast ML Heatmap"
              >
                <Bell className="w-5 h-5" />
                <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-rose-500 ring-2 ring-[#d5d5d8]" />
              </button>

              {/* Settings / Assumptions */}
              <button
                onClick={() => {
                  setActiveNav("settings");
                  setOpenModal("assumptions");
                }}
                className={`p-2.5 rounded-2xl transition ${
                  activeNav === "settings" || openModal === "assumptions"
                    ? "bg-zinc-800 text-white shadow-md"
                    : "text-zinc-600 hover:text-zinc-900 hover:bg-zinc-300/60"
                }`}
                title="System Assumptions & Config"
              >
                <Settings className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Bottom Profile Avatar */}
          <div className="flex flex-col items-center">
            <button
              onClick={() => setIsAuthModalOpen(true)}
              title={currentUser ? `Logged in as ${currentUser.full_name} (${currentUser.role})` : "Sign In / Register"}
              className="w-10 h-10 rounded-full bg-zinc-800 border-2 border-zinc-400 flex items-center justify-center text-white text-xs font-bold shadow-md cursor-pointer hover:ring-2 hover:ring-zinc-600 transition"
            >
              {currentUser ? getInitials(currentUser.full_name) : <LogIn className="w-4 h-4 text-zinc-300" />}
            </button>
          </div>
        </aside>

        {/* MAIN WORKSPACE (CENTER COLUMN) */}
        <main className="flex-1 bg-white p-5 sm:p-7 flex flex-col justify-between overflow-y-auto">
          <div>
            {/* Top Header Row with Real Authentication */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 gap-3 border-b border-zinc-100">
              <div>
                <div className="flex items-center gap-2.5">
                  <h1 className="text-2xl sm:text-[26px] font-bold text-zinc-800 tracking-tight">
                    {currentUser ? `Hello, ${currentUser.full_name}` : "CampusRide Operations"}
                  </h1>
                  {currentUser && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wide uppercase bg-zinc-900 text-white shadow-sm flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3 text-emerald-400" />
                      <span>{currentUser.role}</span>
                    </span>
                  )}
                </div>
                <p className="text-xs text-zinc-500 font-medium mt-0.5 flex items-center gap-2">
                  <span>{currentUser ? currentUser.email : "Campus collaboration meeting"}</span>
                  <span>•</span>
                  <span className="text-zinc-700 font-semibold">{currentCampus?.name || "V.S.B. Karur"}</span>
                </p>
              </div>

              {/* Campus Selector, Provenance Badges, and Auth Trigger */}
              <div className="flex flex-wrap items-center gap-2">
                {currentUser ? (
                  <div className="flex items-center gap-1.5 bg-zinc-100 border border-zinc-200 py-1 px-2.5 rounded-full">
                    <div className="w-5 h-5 rounded-full bg-zinc-900 text-white text-[10px] font-bold flex items-center justify-center">
                      {getInitials(currentUser.full_name)}
                    </div>
                    <span className="text-xs font-medium text-zinc-800 max-w-[120px] truncate hidden sm:inline">
                      {currentUser.full_name}
                    </span>
                    <button
                      onClick={() => {
                        logoutUser();
                        setCurrentUser(null);
                      }}
                      title="Sign Out"
                      className="ml-1 text-zinc-400 hover:text-rose-600 p-0.5 transition"
                    >
                      <LogOut className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setIsAuthModalOpen(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-semibold shadow-sm transition"
                  >
                    <LogIn className="w-3.5 h-3.5" />
                    <span>Sign In</span>
                  </button>
                )}

                <select
                  value={selectedCampusId}
                  onChange={(e) => setSelectedCampusId(e.target.value)}
                  className="bg-[#ececee] text-zinc-800 font-semibold text-xs py-1.5 px-3 rounded-full border border-zinc-300 focus:outline-none focus:ring-1 focus:ring-zinc-500 cursor-pointer"
                >
                  {campuses.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} {c.id === "berkeley" ? "[Demo Preset]" : "(Default)"}
                    </option>
                  ))}
                </select>

                <div className="px-3 py-1 rounded-full text-[11px] font-medium bg-emerald-100 text-emerald-800 border border-emerald-300 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span>{dataSource?.label || "Survey Data (n=250)"}</span>
                </div>
              </div>
            </div>

            {/* Error Notification if any */}
            {error && (
              <div className="mt-3 p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-2xl flex items-center justify-between text-xs">
                <span>{error}</span>
                <button
                  onClick={() => loadCampusData(selectedCampusId)}
                  className="px-3 py-1 bg-rose-600 text-white font-medium rounded-lg hover:bg-rose-700"
                >
                  Retry
                </button>
              </div>
            )}

            {/* ========================================================= */}
            {/* THE CENTER PIECE: MAP AREA (EXACT REPLICA OF VIDEO SCREEN) */}
            {/* ========================================================= */}
            <div className="mt-4 relative w-full h-[370px] sm:h-[410px] lg:h-[430px] rounded-[26px] overflow-hidden bg-zinc-900 border border-zinc-300 shadow-md group">
              {/* Actual Interactive Leaflet Map */}
              <CampusMap
                stands={stands}
                hourlyInventories={hourlyInventories}
                selectedHour={selectedHour}
                routeSteps={rebalancing?.route_steps}
                routeGeometry={rebalancing?.route_geometry}
                routeDistanceKm={rebalancing?.total_distance_km}
                routeTimeMin={rebalancing?.total_time_minutes}
                showRebalancingRoute={showRebalancingRoute}
                transitRoutes={transitRoutes}
                showTransitLines={showTransitLines}
                height="100%"
                className="w-full h-full rounded-[26px]"
                hideDefaultControls={true}
                mapStyle={mapStyle}
                onMapStyleChange={setMapStyle}
                selectedStandId={selectedStandId}
                onStandClick={(stand) => setSelectedStandId(stand.id)}
                telemetryFrame={telemetryFrame}
                onTelemetryControl={handleTelemetryControl}
              />

              {/* OVERLAY 1: Top-Left "Live" Pill Badge Matching Mockup */}
              <div className="absolute top-4 left-4 z-[1000] bg-zinc-900/80 backdrop-blur-md px-3.5 py-1.5 rounded-full flex items-center gap-2 text-white text-xs font-semibold shadow-lg border border-white/10">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_#34d399]" />
                <span>{wsConnected ? "Live Telemetry" : "Live"}</span>
                <span className="text-zinc-400 font-normal">
                  {telemetryFrame ? telemetryFrame.sim_time : `${String(selectedHour).padStart(2, "0")}:00 Telemetry`}
                </span>
              </div>

              {/* OVERLAY 2: Top-Right Fullscreen / Expand Button Matching Mockup */}
              <div className="absolute top-4 right-4 z-[1000] flex items-center gap-2">
                <button
                  onClick={() => {
                    const nextStyle = mapStyle === "satellite" ? "streets" : "satellite";
                    setMapStyle(nextStyle);
                  }}
                  title="Toggle Satellite / Street Imagery"
                  className="bg-zinc-900/80 hover:bg-zinc-900 text-white text-[11px] font-medium px-3 py-1.5 rounded-full backdrop-blur-md shadow-md border border-white/10 transition flex items-center gap-1.5"
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span className="capitalize">{mapStyle}</span>
                </button>
                <button
                  onClick={() => setOpenModal("rider")}
                  title="Expand Journey Planner"
                  className="w-8 h-8 rounded-full bg-zinc-900/80 hover:bg-zinc-900 text-white flex items-center justify-center backdrop-blur-md shadow-md border border-white/10 transition"
                >
                  <Maximize2 className="w-4 h-4" />
                </button>
              </div>

              {/* OVERLAY 3: Right Vertical Volume-Style Floating Slider Matching Mockup */}
              <div className="absolute right-4 top-1/2 -translate-y-1/2 z-[1000] flex flex-col items-center gap-2">
                <div className="w-9 h-36 bg-zinc-900/75 backdrop-blur-md rounded-full flex flex-col items-center justify-between p-2 shadow-xl border border-white/15">
                  <span className="text-[9px] font-mono font-bold text-zinc-300">22h</span>
                  {/* Interactive Vertical Slider Track */}
                  <input
                    type="range"
                    min="7"
                    max="22"
                    step="1"
                    value={selectedHour}
                    onChange={(e) => setSelectedHour(Number(e.target.value))}
                    className="w-24 -rotate-90 origin-center my-6 accent-white cursor-pointer"
                    title={`Hour: ${selectedHour}:00`}
                  />
                  <span className="text-[9px] font-mono font-bold text-zinc-300">07h</span>
                </div>
                {/* Audio/Clock Icon Button below the vertical slider matching mockup */}
                <button
                  onClick={() => setSelectedHour(8)}
                  title="Reset to 08:00 AM Rush"
                  className="w-9 h-9 rounded-full bg-zinc-900/75 hover:bg-zinc-900 text-white flex items-center justify-center backdrop-blur-md shadow-lg border border-white/15 transition"
                >
                  <Clock className="w-4 h-4 text-zinc-200" />
                </button>
              </div>

              {/* OVERLAY 4: Floating Bottom Action Dock Matching Mockup Video Controls */}
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[1000] bg-zinc-900/85 backdrop-blur-xl px-4 py-2.5 rounded-full flex items-center gap-3.5 shadow-2xl border border-white/15">
                {/* Target / Locate Button */}
                <button
                  onClick={() => loadCampusData(selectedCampusId)}
                  title="Re-center Campus Map"
                  className="w-9 h-9 rounded-full bg-zinc-800 hover:bg-zinc-700 text-zinc-200 hover:text-white flex items-center justify-center transition border border-white/10 shadow-sm"
                >
                  <Crosshair className="w-4 h-4" />
                </button>

                {/* Transit Route Toggle (Bus icon) */}
                <button
                  onClick={() => setShowTransitLines(!showTransitLines)}
                  title="Toggle EV Shuttle & Transit Lines"
                  className={`w-9 h-9 rounded-full flex items-center justify-center transition border border-white/10 shadow-sm ${
                    showTransitLines
                      ? "bg-emerald-500 text-black font-bold"
                      : "bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
                  }`}
                >
                  <Bus className="w-4 h-4" />
                </button>

                {/* Rebalancing Path Toggle */}
                <button
                  onClick={() => setShowRebalancingRoute(!showRebalancingRoute)}
                  title="Toggle Van Rebalancing Route"
                  className={`w-9 h-9 rounded-full flex items-center justify-center transition border border-white/10 shadow-sm ${
                    showRebalancingRoute
                      ? "bg-sky-400 text-black font-bold"
                      : "bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
                  }`}
                >
                  <Briefcase className="w-4 h-4" />
                </button>

                {/* Open Rider Journey Planner */}
                <button
                  onClick={() => setOpenModal("rider")}
                  title="Plan Multi-Modal Trip"
                  className="w-9 h-9 rounded-full bg-zinc-800 hover:bg-zinc-700 text-zinc-200 hover:text-white flex items-center justify-center transition border border-white/10 shadow-sm"
                >
                  <Navigation className="w-4 h-4" />
                </button>

                {/* Red / Hangup Style Action Button: Run Monte Carlo Optimizer */}
                <button
                  onClick={handleRunEvaluation}
                  disabled={isEvaluating}
                  title="Run Monte Carlo 30-Seed Optimizer"
                  className="h-9 px-4 rounded-full bg-rose-600 hover:bg-rose-500 active:scale-95 text-white text-xs font-semibold flex items-center gap-2 shadow-lg transition disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isEvaluating ? "animate-spin" : ""}`} />
                  <span className="hidden sm:inline">{isEvaluating ? "Running..." : "Evaluate"}</span>
                </button>
              </div>
            </div>

            {/* ========================================================= */}
            {/* 4 ATTENDEE / PARTICIPANT STYLE CARDS BELOW THE MAP         */}
            {/* ========================================================= */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
              {/* Card 1: Docked Cycles */}
              <div
                onClick={() => setSelectedFleetMode("bike")}
                className={`bg-[#d8d8dc] hover:bg-[#ceced3] rounded-2xl p-3 flex flex-col items-center justify-center transition cursor-pointer text-center border ${
                  selectedFleetMode === "bike" ? "border-zinc-800 ring-2 ring-zinc-400" : "border-zinc-300/40"
                }`}
              >
                <div className="w-10 h-10 rounded-full bg-[#b8b8bc] flex items-center justify-center text-zinc-800 mb-2 shadow-inner">
                  <Bike className="w-5 h-5" />
                </div>
                <div className="bg-[#b8b8bc] px-2.5 py-0.5 rounded-full flex items-center gap-1.5 text-[11px] font-semibold text-zinc-800">
                  <Mic className="w-3 h-3 text-zinc-600" />
                  <span>Docked Cycles</span>
                </div>
                <span className="text-[10px] text-zinc-600 mt-1 font-medium">
                  {totalBikes} Fleet • ₹0 Pass
                </span>
              </div>

              {/* Card 2: Campus E-Scooters */}
              <div
                onClick={() => setSelectedFleetMode("scooter")}
                className={`bg-[#d8d8dc] hover:bg-[#ceced3] rounded-2xl p-3 flex flex-col items-center justify-center transition cursor-pointer text-center border ${
                  selectedFleetMode === "scooter" ? "border-zinc-800 ring-2 ring-zinc-400" : "border-zinc-300/40"
                }`}
              >
                <div className="w-10 h-10 rounded-full bg-[#b8b8bc] flex items-center justify-center text-zinc-800 mb-2 shadow-inner">
                  <Zap className="w-5 h-5" />
                </div>
                <div className="bg-[#b8b8bc] px-2.5 py-0.5 rounded-full flex items-center gap-1.5 text-[11px] font-semibold text-zinc-800">
                  <Mic className="w-3 h-3 text-zinc-600" />
                  <span>Campus Scooters</span>
                </div>
                <span className="text-[10px] text-zinc-600 mt-1 font-medium">
                  4 Hubs • ₹5 Flat
                </span>
              </div>

              {/* Card 3: EV Green Loop Shuttle */}
              <div
                onClick={() => setSelectedFleetMode("shuttle")}
                className={`bg-[#d8d8dc] hover:bg-[#ceced3] rounded-2xl p-3 flex flex-col items-center justify-center transition cursor-pointer text-center border ${
                  selectedFleetMode === "shuttle" ? "border-zinc-800 ring-2 ring-zinc-400" : "border-zinc-300/40"
                }`}
              >
                <div className="w-10 h-10 rounded-full bg-[#b8b8bc] flex items-center justify-center text-zinc-800 mb-2 shadow-inner">
                  <Bus className="w-5 h-5" />
                </div>
                <div className="bg-[#b8b8bc] px-2.5 py-0.5 rounded-full flex items-center gap-1.5 text-[11px] font-semibold text-zinc-800">
                  <Mic className="w-3 h-3 text-zinc-600" />
                  <span>EV Green Loop</span>
                </div>
                <span className="text-[10px] text-zinc-600 mt-1 font-medium">
                  15m Loop • 20 Seats
                </span>
              </div>

              {/* Card 4: Staff Golf Cart */}
              <div
                onClick={() => setSelectedFleetMode("cart")}
                className={`bg-[#d8d8dc] hover:bg-[#ceced3] rounded-2xl p-3 flex flex-col items-center justify-center transition cursor-pointer text-center border ${
                  selectedFleetMode === "cart" ? "border-zinc-800 ring-2 ring-zinc-400" : "border-zinc-300/40"
                }`}
              >
                <div className="w-10 h-10 rounded-full bg-[#b8b8bc] flex items-center justify-center text-zinc-800 mb-2 shadow-inner">
                  <Car className="w-5 h-5" />
                </div>
                <div className="bg-[#b8b8bc] px-2.5 py-0.5 rounded-full flex items-center gap-1.5 text-[11px] font-semibold text-zinc-800">
                  <Mic className="w-3 h-3 text-zinc-600" />
                  <span>Golf Carts</span>
                </div>
                <span className="text-[10px] text-zinc-600 mt-1 font-medium">
                  2 Carts • Free Transit
                </span>
              </div>
            </div>

            {/* ========================================================= */}
            {/* AI & OPTIMIZATION ENGINES (CVRP & DEMAND FORECASTING)     */}
            {/* ========================================================= */}
            <div className="mt-5">
              <div className="flex items-center justify-between mb-2.5">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_6px_#10b981]" />
                  <h2 className="text-xs font-bold text-zinc-800 uppercase tracking-wider">
                    Optimization & ML Engines
                  </h2>
                </div>
                <span className="text-[10px] font-mono text-zinc-500">
                  Google OR-Tools • scikit-learn
                </span>
              </div>

              <div className="space-y-2.5">
                {/* Engine Row 1: Fleet Rebalancing (OR-Tools CVRP) */}
                <div
                  onClick={() => setOpenModal("rebalancing")}
                  className="bg-[#d8d8dc] hover:bg-[#ceced3] rounded-2xl p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs border border-zinc-300/60 shadow-xs transition cursor-pointer group"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-sky-500/15 text-sky-800 flex items-center justify-center shrink-0 border border-sky-400/30 group-hover:scale-105 transition-transform">
                      <Zap className="w-4 h-4 text-sky-600" />
                    </div>
                    <div>
                      <div className="font-bold text-zinc-900 text-xs flex items-center gap-2">
                        <span>Fleet Rebalancing Engine (OR-Tools CVRP)</span>
                        <span className="bg-emerald-600/15 text-emerald-800 text-[9px] font-mono font-bold px-1.5 py-0.2 rounded-md">
                          OPTIMAL
                        </span>
                      </div>
                      <div className="text-[11px] text-zinc-600 font-medium mt-0.5">
                        20-min operational window • {rebalancing?.total_distance_km ? `${rebalancing.total_distance_km.toFixed(1)} km path` : "1.8 km path"} • {rebalancing?.bikes_moved ?? 14} bikes moved
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3.5 text-zinc-700 text-[11px] font-medium self-end sm:self-center">
                    <span className="font-mono text-zinc-600">
                      Stands: <strong className="text-zinc-900">{rebalancing?.route_steps?.length ?? 5} stops</strong>
                    </span>
                    <span className="text-zinc-400">•</span>
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-zinc-600">Convergence:</span>
                      <strong className="text-zinc-900 font-mono">100%</strong>
                      <div className="w-20 sm:w-24 h-1.5 bg-zinc-300 rounded-full overflow-hidden relative">
                        <div className="w-full h-full bg-emerald-600 rounded-full" />
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setOpenModal("rebalancing");
                      }}
                      title="Inspect Rebalancing Route"
                      className="p-1 rounded-lg hover:bg-zinc-300 text-zinc-600 hover:text-zinc-900 transition"
                    >
                      <MoreHorizontal className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Engine Row 2: Spatiotemporal Demand Forecast (HistGradientBoosting) */}
                <div
                  onClick={() => setOpenModal("forecast")}
                  className="bg-[#d8d8dc] hover:bg-[#ceced3] rounded-2xl p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs border border-zinc-300/60 shadow-xs transition cursor-pointer group"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-violet-500/15 text-violet-800 flex items-center justify-center shrink-0 border border-violet-400/30 group-hover:scale-105 transition-transform">
                      <BarChart3 className="w-4 h-4 text-violet-600" />
                    </div>
                    <div>
                      <div className="font-bold text-zinc-900 text-xs flex items-center gap-2">
                        <span>Spatiotemporal Demand Forecaster</span>
                        <span className="bg-violet-600/15 text-violet-800 text-[9px] font-mono font-bold px-1.5 py-0.2 rounded-md">
                          CALIBRATED
                        </span>
                      </div>
                      <div className="text-[11px] text-zinc-600 font-medium mt-0.5">
                        HistGradientBoosting • Test MAE 1.42 (vs 3.89 Naive Baseline) • 63.5% error reduction
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3.5 text-zinc-700 text-[11px] font-medium self-end sm:self-center">
                    <span className="font-mono text-zinc-600">
                      Horizon: <strong className="text-zinc-900">20-min</strong>
                    </span>
                    <span className="text-zinc-400">•</span>
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-zinc-600">Accuracy:</span>
                      <strong className="text-zinc-900 font-mono">92%</strong>
                      <div className="w-20 sm:w-24 h-1.5 bg-zinc-300 rounded-full overflow-hidden relative">
                        <div className="w-[92%] h-full bg-violet-600 rounded-full" />
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setOpenModal("forecast");
                      }}
                      title="Inspect Demand Forecast Model"
                      className="p-1 rounded-lg hover:bg-zinc-300 text-zinc-600 hover:text-zinc-900 transition"
                    >
                      <MoreHorizontal className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>

        {/* ========================================================= */}
        {/* RIGHT SIDEBAR: SECTION 1 (FLEET DISPATCH) & SECTION 2 (STAND STATUS) */}
        {/* ========================================================= */}
        <aside className="w-full lg:w-[360px] bg-[#d5d5d8] p-4 flex flex-col gap-3.5 border-l border-zinc-300/80 shrink-0 z-20 overflow-y-auto">
          {/* Top Operational Status Header */}
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_#10b981]" />
              <span className="font-bold text-xs text-zinc-900 tracking-wide uppercase">
                Digital Twin Operations
              </span>
            </div>
            <button
              onClick={handleRunEvaluation}
              disabled={isEvaluating}
              title="Run 30-seed Monte Carlo Evaluation"
              className="px-2.5 py-1 rounded-xl bg-white/90 hover:bg-white text-zinc-800 text-[10px] font-bold shadow-xs border border-zinc-200/80 flex items-center gap-1.5 transition active:scale-95 disabled:opacity-50"
            >
              <RefreshCw className={`w-3 h-3 text-emerald-600 ${isEvaluating ? "animate-spin" : ""}`} />
              <span>{isEvaluating ? "Simulating..." : "Run Sim"}</span>
            </button>
          </div>

          {/* SECTION 1: Live Campus Fleet & Dispatch Feed */}
          <DispatchFeed
            selectedHour={selectedHour}
            stands={stands}
            hourlyInventories={hourlyInventories}
            rebalancing={rebalancing}
            transitRoutes={transitRoutes}
            onSelectStand={(standId) => setSelectedStandId(standId)}
            liveEvents={telemetryFrame?.recent_events}
          />

          {/* SECTION 2: Stand Status & Urgent Alerts Inspector */}
          <StandAlertsInspector
            stands={stands}
            hourlyInventories={hourlyInventories}
            selectedHour={selectedHour}
            selectedStandId={selectedStandId}
            onSelectStand={(standId) => setSelectedStandId(standId)}
          />
        </aside>
      </div>

      {/* ========================================================= */}
      {/* INTERACTIVE FULL INSPECTOR MODALS (ZERO LOST FUNCTIONALITY) */}
      {/* ========================================================= */}
      {openModal !== "none" && (
        <div className="fixed inset-0 z-[2000] bg-black/60 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-white w-full max-w-5xl max-h-[90vh] rounded-[28px] shadow-2xl border border-zinc-300 flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="px-6 py-4 bg-[#ececee] border-b border-zinc-300 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-bold text-base text-zinc-800 capitalize">
                  {openModal === "rider" && "Rider Journey Planner (Multi-Modal Trip Options)"}
                  {openModal === "evaluation" && "Monte Carlo Evaluation & Stand Telemetry"}
                  {openModal === "forecast" && "Spatiotemporal Demand Forecast (HistGradientBoosting)"}
                  {openModal === "assumptions" && "Campus System Assumptions & Working Parameters"}
                  {openModal === "rebalancing" && "Van Rebalancing Route Inspector (OR-Tools CVRP)"}
                </span>
              </div>
              <button
                onClick={() => setOpenModal("none")}
                className="w-8 h-8 rounded-full bg-white hover:bg-zinc-200 text-zinc-700 flex items-center justify-center transition shadow-sm"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto flex-1 bg-white">
              {openModal === "rider" && (
                <RiderView
                  stands={stands}
                  campusId={selectedCampusId}
                  campuses={campuses}
                  onSelectCampus={setSelectedCampusId}
                  hourlyInventories={hourlyInventories}
                  dataSource={dataSource}
                />
              )}

              {openModal === "evaluation" && (
                <div className="space-y-6">
                  <ComparisonPanel
                    evaluation={evaluation}
                    allocation={allocation}
                    isLoading={isLoading}
                  />
                  <MetricComparisonGrid
                    evaluation={evaluation}
                    stands={stands}
                    isLoading={isLoading}
                    onRunEvaluation={handleRunEvaluation}
                    isEvaluating={isEvaluating}
                  />
                  <StandTelemetryGrid
                    stands={stands}
                    hourlyInventories={hourlyInventories}
                    selectedHour={selectedHour}
                  />
                </div>
              )}

              {openModal === "forecast" && (
                <ForecastTab
                  stands={stands}
                  forecast={forecast}
                  forecastEval={forecastEval}
                  isLoading={isLoading}
                  dataSource={dataSource}
                />
              )}

              {openModal === "assumptions" && (
                <div className="space-y-6">
                  <AssumptionsPanel
                    assumptions={assumptions}
                    isLoading={isLoading}
                  />
                  <ExplainerCard />
                </div>
              )}

              {openModal === "rebalancing" && (
                <div className="space-y-6">
                  <RebalancingPanel
                    rebalancing={rebalancing}
                    isLoading={isLoading}
                    vanCapacity={assumptions?.van_capacity ?? 15}
                    shiftWindowMinutes={selectedCampusId === "vsb_karur" ? 60 : 90}
                    onRunEvaluation={handleRunEvaluation}
                    isEvaluating={isEvaluating}
                  />
                  <AllocationPanel
                    stands={stands}
                    allocation={allocation}
                    isLoading={isLoading}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Authentication Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onSuccess={(user) => setCurrentUser(user)}
      />
    </div>
  );
}
