"use client";

import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polyline,
  useMap,
  useMapEvents,
} from "react-leaflet";
import { Stand, RouteStep, TransitRoute, TelemetryFrame, TelemetryVan } from "../lib/types";
import {
  Navigation,
  MapPin,
  Bus,
  Plus,
  Minus,
  Focus,
  Maximize2,
  ZoomIn,
  Truck,
  Play,
  Pause,
  Radio,
  Zap,
} from "lucide-react";

export interface CampusMapProps {
  stands: Stand[];
  hourlyInventories: Record<string, Record<number, number>>;
  selectedHour: number;
  routeSteps?: RouteStep[];
  routeGeometry?: [number, number][][];
  routeDistanceKm?: number;
  routeTimeMin?: number;
  showRebalancingRoute?: boolean;
  activePolyline?: [number, number][];
  polylineColor?: string;
  originStandId?: string | null;
  destStandId?: string | null;
  onStandClick?: (stand: Stand) => void;
  transitRoutes?: TransitRoute[];
  showTransitLines?: boolean;
  height?: string;
  className?: string;
  hideDefaultControls?: boolean;
  mapStyle?: "satellite" | "streets";
  onMapStyleChange?: (style: "satellite" | "streets") => void;
  selectedStandId?: string | null;
  telemetryFrame?: TelemetryFrame | null;
  onTelemetryControl?: (action: "pause" | "speed", value?: any) => void;
}

/**
 * Interactive Zoom HUD rendered inside Leaflet context
 */
function MapZoomHUD({
  stands,
  activePolyline,
  defaultCenter,
  defaultZoom,
}: {
  stands: Stand[];
  activePolyline?: [number, number][];
  defaultCenter: [number, number];
  defaultZoom: number;
}) {
  const map = useMap();
  const [currentZoom, setCurrentZoom] = useState<number>(() => map.getZoom());
  const controlRef = useRef<HTMLDivElement>(null);

  // Sync zoom state on map zoom events
  useMapEvents({
    zoomend: () => {
      setCurrentZoom(Math.round(map.getZoom()));
    },
    zoom: () => {
      setCurrentZoom(Math.round(map.getZoom()));
    },
  });

  // Stop Leaflet from stealing clicks/scrolls inside this control HUD
  useEffect(() => {
    if (controlRef.current) {
      L.DomEvent.disableClickPropagation(controlRef.current);
      L.DomEvent.disableScrollPropagation(controlRef.current);
    }
  }, []);

  const handleZoomIn = () => {
    map.zoomIn(1);
  };

  const handleZoomOut = () => {
    map.zoomOut(1);
  };

  const handleFitCampus = () => {
    if (stands.length > 0) {
      const bounds = L.latLngBounds(
        stands.map((s) => [s.latitude, s.longitude] as [number, number])
      );
      map.fitBounds(bounds, {
        padding: [60, 60],
        maxZoom: 19,
        animate: true,
        duration: 0.8,
      });
    } else {
      map.flyTo(defaultCenter, defaultZoom, { duration: 0.8 });
    }
  };

  const handleFitRoute = () => {
    if (activePolyline && activePolyline.length > 0) {
      const bounds = L.latLngBounds(activePolyline);
      map.fitBounds(bounds, {
        padding: [50, 50],
        maxZoom: 19,
        animate: true,
        duration: 0.8,
      });
    }
  };

  const handleSetZoomLevel = (targetZoom: number) => {
    map.setZoom(targetZoom, { animate: true });
  };

  return (
    <div
      ref={controlRef}
      className="leaflet-bottom leaflet-left !pointer-events-auto"
      style={{ marginBottom: "16px", marginLeft: "16px", zIndex: 1000 }}
    >
      <div className="flex flex-col items-start gap-1.5">
        {/* Main Glassmorphic Zoom Control Stack - Slim & Thin */}
        <div className="glass-cockpit p-1 rounded-xl flex flex-col items-center gap-0.5 shadow-xl border border-white/10 backdrop-blur-xl bg-zinc-950/85 w-8">
          {/* Zoom In Button */}
          <button
            type="button"
            onClick={handleZoomIn}
            className="w-7 h-7 rounded-lg bg-white/10 hover:bg-white/20 active:bg-white/30 text-white flex items-center justify-center transition-all duration-150 shadow-sm group cursor-pointer"
            title="Zoom In (+ or Scroll Up, up to 22x)"
            aria-label="Zoom in"
          >
            <Plus className="w-3.5 h-3.5 group-hover:scale-110 transition-transform" />
          </button>

          {/* Current Zoom Level Badge */}
          <div
            className="w-7 py-0.5 flex flex-col items-center justify-center text-center select-none"
            title={`Current Zoom Level: ${currentZoom} (Max: 22)`}
          >
            <span className="text-[10px] font-mono font-bold text-white tracking-tight leading-none">
              {currentZoom}x
            </span>
            <span className="text-[6.5px] uppercase font-mono text-zinc-400 mt-0.5 tracking-tighter leading-none">
              zoom
            </span>
          </div>

          {/* Zoom Out Button */}
          <button
            type="button"
            onClick={handleZoomOut}
            className="w-7 h-7 rounded-lg bg-white/10 hover:bg-white/20 active:bg-white/30 text-white flex items-center justify-center transition-all duration-150 shadow-sm group cursor-pointer"
            title="Zoom Out (- or Scroll Down)"
            aria-label="Zoom out"
          >
            <Minus className="w-3.5 h-3.5 group-hover:scale-110 transition-transform" />
          </button>

          {/* Divider */}
          <div className="w-5 h-px bg-white/15 my-0.5" />

          {/* Fit All Stands in View Button */}
          <button
            type="button"
            onClick={handleFitCampus}
            className="w-7 h-7 rounded-lg bg-white/10 hover:bg-emerald-500/25 hover:text-emerald-300 active:bg-emerald-500/40 text-zinc-200 flex items-center justify-center transition-all duration-150 shadow-sm group cursor-pointer"
            title="Auto-Fit Campus (Frames all stands)"
            aria-label="Fit all stands"
          >
            <Focus className="w-3.5 h-3.5 group-hover:scale-110 transition-transform" />
          </button>

          {/* Fit Active Route if available */}
          {activePolyline && activePolyline.length > 0 && (
            <button
              type="button"
              onClick={handleFitRoute}
              className="w-7 h-7 rounded-lg bg-sky-500/20 hover:bg-sky-500/35 text-sky-300 flex items-center justify-center transition-all duration-150 shadow-sm group cursor-pointer border border-sky-400/30"
              title="Fit Selected Route in View"
              aria-label="Fit route"
            >
              <Navigation className="w-3.5 h-3.5 group-hover:scale-110 transition-transform" />
            </button>
          )}
        </div>

        {/* Quick Zoom Level Preset Chips - Thin & Compact */}
        <div className="glass-cockpit px-1.5 py-0.5 rounded-lg flex items-center gap-0.5 shadow-lg border border-white/10 backdrop-blur-xl bg-zinc-950/80">
          <button
            type="button"
            onClick={() => handleSetZoomLevel(15)}
            className={`px-1.5 py-0.5 rounded text-[8.5px] font-mono font-medium transition ${
              currentZoom <= 15
                ? "bg-white text-black shadow-xs font-bold"
                : "text-zinc-400 hover:text-white"
            }`}
            title="Overview (15x)"
          >
            Area
          </button>
          <button
            type="button"
            onClick={() => handleSetZoomLevel(17)}
            className={`px-1.5 py-0.5 rounded text-[8.5px] font-mono font-medium transition ${
              currentZoom === 16 || currentZoom === 17
                ? "bg-white text-black shadow-xs font-bold"
                : "text-zinc-400 hover:text-white"
            }`}
            title="Campus Level (17x)"
          >
            Campus
          </button>
          <button
            type="button"
            onClick={() => handleSetZoomLevel(19)}
            className={`px-1.5 py-0.5 rounded text-[8.5px] font-mono font-medium transition ${
              currentZoom === 18 || currentZoom === 19
                ? "bg-white text-black shadow-xs font-bold"
                : "text-zinc-400 hover:text-white"
            }`}
            title="Stands Level (19x)"
          >
            Stands
          </button>
          <button
            type="button"
            onClick={() => handleSetZoomLevel(21)}
            className={`px-1.5 py-0.5 rounded text-[8.5px] font-mono font-medium transition ${
              currentZoom >= 20
                ? "bg-emerald-400 text-black shadow-xs font-bold"
                : "text-zinc-400 hover:text-emerald-300"
            }`}
            title="Deep Close-Up (21x)"
          >
            21x
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Helper to fly to stand on click
 */
function StandFlyHandler({ stand }: { stand: Stand | null }) {
  const map = useMap();
  useEffect(() => {
    if (stand) {
      map.flyTo([stand.latitude, stand.longitude], Math.max(map.getZoom(), 19), {
        animate: true,
        duration: 0.7,
      });
    }
  }, [stand, map]);
  return null;
}

export default function CampusMapLeaflet({
  stands,
  hourlyInventories,
  selectedHour,
  routeSteps,
  routeGeometry,
  routeDistanceKm,
  routeTimeMin,
  showRebalancingRoute = true,
  activePolyline,
  polylineColor = "#38bdf8",
  originStandId,
  destStandId,
  onStandClick,
  transitRoutes,
  showTransitLines = true,
  height,
  className,
  hideDefaultControls = false,
  mapStyle: controlledMapStyle,
  onMapStyleChange,
  selectedStandId,
  telemetryFrame,
  onTelemetryControl,
}: CampusMapProps) {
  const [internalMapStyle, setInternalMapStyle] = useState<"satellite" | "streets">(
    controlledMapStyle || "satellite"
  );
  const [showTransit, setShowTransit] = useState<boolean>(showTransitLines);
  const [inspectedStand, setInspectedStand] = useState<Stand | null>(null);

  useEffect(() => {
    if (selectedStandId) {
      const match = stands.find((s) => s.id === selectedStandId);
      if (match) {
        setInspectedStand(match);
      }
    }
  }, [selectedStandId, stands]);

  const activeMapStyle = controlledMapStyle || internalMapStyle;

  const handleStyleChange = (style: "satellite" | "streets") => {
    setInternalMapStyle(style);
    onMapStyleChange?.(style);
  };

  // Calculate dynamic center & zoom from stands coordinates
  const lats = stands.map((s) => s.latitude);
  const lons = stands.map((s) => s.longitude);
  const centerLat =
    lats.length > 0 ? lats.reduce((a, b) => a + b, 0) / lats.length : 10.95485;
  const centerLon =
    lons.length > 0 ? lons.reduce((a, b) => a + b, 0) / lons.length : 77.95463;
  const mapCenter: [number, number] = [centerLat, centerLon];

  // Detect if campus is VSB Karur vs Berkeley
  const isVsbCampus = centerLat < 20; // 10.95 for Karur, 37.87 for Berkeley
  const mapZoom = isVsbCampus ? 17 : 16;
  const campusLabel = isVsbCampus
    ? "V.S.B. Engineering College, Karur"
    : "UC Berkeley";

  // Stand Marker with high contrast and zero clipping
  const createStandIcon = (stand: Stand, bikes: number) => {
    const isOrigin = originStandId === stand.id;
    const isDest = destStandId === stand.id;
    const isStarved = bikes === 0;
    const isFull = bikes >= stand.dock_capacity;

    const ringBorder = isOrigin
      ? "#10b981" // emerald-500
      : isDest
      ? "#f43f5e" // rose-500
      : isStarved
      ? "#ef4444" // red-500 alert when starved
      : isFull
      ? "#3b82f6" // blue alert when full
      : "#ffffff"; // crisp white

    const glow = isOrigin
      ? "0 0 16px rgba(16, 185, 129, 0.95), 0 0 8px rgba(255, 255, 255, 0.8)"
      : isDest
      ? "0 0 16px rgba(244, 63, 94, 0.95), 0 0 8px rgba(255, 255, 255, 0.8)"
      : isStarved
      ? "0 0 14px rgba(239, 68, 68, 0.7)"
      : isFull
      ? "0 0 14px rgba(59, 130, 246, 0.7)"
      : "0 0 14px rgba(0, 0, 0, 0.9), 0 0 8px rgba(255, 255, 255, 0.6)";

    const pinBadge = isOrigin
      ? `<div style="position: absolute; top: -14px; background: #059669; color: white; font-size: 8px; font-weight: 800; padding: 1px 5px; border-radius: 9999px; letter-spacing: 0.05em; border: 1px solid rgba(255,255,255,0.4); box-shadow: 0 2px 6px rgba(0,0,0,0.8);">START</div>`
      : isDest
      ? `<div style="position: absolute; top: -14px; background: #e11d48; color: white; font-size: 8px; font-weight: 800; padding: 1px 5px; border-radius: 9999px; letter-spacing: 0.05em; border: 1px solid rgba(255,255,255,0.4); box-shadow: 0 2px 6px rgba(0,0,0,0.8);">END</div>`
      : "";

    const displayName =
      stand.name.length > 18 ? stand.name.slice(0, 16) + "…" : stand.name;

    const html = `
      <div style="
        width: 130px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        pointer-events: auto;
      ">
        <div style="
          position: relative;
          width: 44px;
          height: 44px;
          background: rgba(5, 5, 10, 0.94);
          border: 2.5px solid ${ringBorder};
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: ${glow};
          backdrop-filter: blur(12px);
        ">
          ${pinBadge}
          <span style="font-size: 15px; font-weight: 800; color: #ffffff; font-family: monospace;">
            ${bikes}
          </span>
          <div style="
            position: absolute;
            bottom: -6px;
            background: #09090b;
            border: 1px solid rgba(255, 255, 255, 0.4);
            padding: 0.5px 4.5px;
            border-radius: 9999px;
            font-size: 8.5px;
            font-weight: 700;
            color: #ffffff;
            font-family: monospace;
          ">
            /${stand.dock_capacity}
          </div>
        </div>
        <div style="
          margin-top: 6px;
          background: rgba(0, 0, 0, 0.9);
          border: 1px solid rgba(255, 255, 255, 0.35);
          backdrop-filter: blur(8px);
          padding: 2.5px 8px;
          border-radius: 6px;
          font-size: 9.5px;
          font-weight: 700;
          color: #ffffff;
          white-space: nowrap;
          letter-spacing: 0.03em;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.95);
        ">
          ${displayName}
        </div>
      </div>
    `;

    return L.divIcon({
      html,
      className: "custom-stand-marker-container",
      iconSize: [130, 80],
      iconAnchor: [65, 22],
    });
  };

  // Animated moving van icon with compass bearing heading and status badge
  const createVanIcon = (van: TelemetryVan) => {
    const isAtStop = van.status === "AT_STOP";
    const badgeColor = isAtStop ? "#10b981" : "#0284c7";
    const etaText = isAtStop
      ? `AT DOCK • ${Math.round(van.dwell_remaining_sec)}s`
      : `ETA ${Math.round(van.eta_seconds)}s ➔ ${van.target_stand_name.slice(0, 14)}`;

    const html = `
      <div style="
        position: relative;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        pointer-events: auto;
      ">
        <!-- Floating Van Status Pill -->
        <div style="
          margin-bottom: 5px;
          background: rgba(9, 13, 22, 0.95);
          border: 1px solid rgba(56, 189, 248, 0.7);
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.9), 0 0 12px rgba(56, 189, 248, 0.45);
          border-radius: 9999px;
          padding: 2px 8px;
          display: flex;
          align-items: center;
          gap: 5px;
          white-space: nowrap;
          backdrop-filter: blur(8px);
        ">
          <span style="
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: ${badgeColor};
            box-shadow: 0 0 6px ${badgeColor};
          "></span>
          <span style="font-size: 10px; font-weight: 800; color: #ffffff; letter-spacing: 0.02em;">
            VAN #1 (${van.load}/${van.capacity})
          </span>
          <span style="font-size: 9px; font-weight: 600; color: #94a3b8;">
            • ${etaText}
          </span>
        </div>

        <!-- Van Beacon Radar Body -->
        <div style="position: relative; width: 44px; height: 44px; display: flex; align-items: center; justify-content: center;">
          <div style="
            position: absolute;
            inset: 0;
            border-radius: 50%;
            background: rgba(56, 189, 248, 0.25);
            border: 1.5px solid #38bdf8;
            box-shadow: 0 0 16px rgba(56, 189, 248, 0.8);
          "></div>
          <div style="
            position: relative;
            z-index: 2;
            width: 32px;
            height: 32px;
            background: #090d16;
            border: 2px solid #38bdf8;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            transform: rotate(${van.bearing}deg);
            transition: transform 0.6s ease;
          ">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="12 2 19 21 12 17 5 21 12 2"></polygon>
            </svg>
          </div>
        </div>
      </div>
    `;

    return L.divIcon({
      html,
      className: "custom-van-marker-container",
      iconSize: [200, 80],
      iconAnchor: [100, 52],
    });
  };

  // Straight line fallback positions if routeGeometry is not supplied
  const fallbackRoutePositions: [number, number][] = [];
  if (showRebalancingRoute && routeSteps && routeSteps.length > 0) {
    const standLookup = new Map(stands.map((s) => [s.id, s]));
    routeSteps.forEach((step) => {
      const stand = standLookup.get(step.stand_id);
      if (stand) {
        fallbackRoutePositions.push([stand.latitude, stand.longitude]);
      }
    });
  }

  // Key change on MapContainer forces immediate clean re-centering when campus changes
  const containerKey = `${centerLat.toFixed(3)}_${centerLon.toFixed(3)}_${activeMapStyle}`;
  const containerHeight = height || "520px";

  const handleMarkerClick = (stand: Stand) => {
    setInspectedStand(stand);
    onStandClick?.(stand);
  };

  return (
    <div
      className={`w-full overflow-hidden relative shadow-md ${
        className || "h-[520px] rounded-2xl border border-white/10 bg-black"
      }`}
      style={{ height: containerHeight }}
    >
      <MapContainer
        key={containerKey}
        center={mapCenter}
        zoom={mapZoom}
        minZoom={3}
        maxZoom={22}
        zoomControl={false}
        scrollWheelZoom={true}
        doubleClickZoom={true}
        touchZoom={true}
        boxZoom={true}
        keyboard={true}
        style={{ height: "100%", width: "100%" }}
        className="w-full h-full"
      >
        {/* Realistic Satellite Imagery (Esri World Imagery) or OpenStreetMap */}
        {activeMapStyle === "satellite" ? (
          <TileLayer
            attribution="Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics"
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            maxNativeZoom={18}
            maxZoom={22}
          />
        ) : (
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            maxNativeZoom={19}
            maxZoom={22}
          />
        )}

        {/* Real Network Van Route Polylines (OSMnx road geometry) */}
        {showRebalancingRoute && routeGeometry && routeGeometry.length > 0 ? (
          routeGeometry.map((segment, idx) => (
            <Polyline
              key={`seg-${idx}`}
              positions={segment}
              pathOptions={{
                color: "#38bdf8", // Sky blue road line
                weight: 4,
                opacity: 0.95,
              }}
            />
          ))
        ) : (
          fallbackRoutePositions.length > 1 && (
            <Polyline
              positions={fallbackRoutePositions}
              pathOptions={{
                color: "#38bdf8",
                weight: 3.5,
                dashArray: "8, 8",
                opacity: 0.9,
              }}
            />
          )
        )}

        {/* Rider View Selected Route Polyline */}
        {activePolyline && activePolyline.length > 0 && (
          <Polyline
            positions={activePolyline}
            pathOptions={{
              color: polylineColor || "#38bdf8",
              weight: 5,
              opacity: 0.95,
            }}
          />
        )}

        {/* Campus Fixed Transit Routes (EV Shuttle & Golf Cart) */}
        {showTransit &&
          transitRoutes &&
          transitRoutes.map((tr) => {
            const stopPositions = tr.stops.map(
              (s) => [s.latitude, s.longitude] as [number, number]
            );
            return (
              <Polyline
                key={tr.id}
                positions={stopPositions}
                pathOptions={{
                  color: tr.color || "#10b981",
                  weight: 3.5,
                  dashArray: "6, 8",
                  opacity: 0.85,
                }}
              />
            );
          })}

        {/* Stand Markers */}
        {stands.map((stand) => {
          const bikes =
            telemetryFrame?.live_inventory?.[stand.id] ??
            hourlyInventories[stand.id]?.[selectedHour] ??
            Math.round(stand.dock_capacity * 0.5);
          const icon = createStandIcon(stand, bikes);

          return (
            <Marker
              key={stand.id}
              position={[stand.latitude, stand.longitude]}
              icon={icon}
              eventHandlers={{
                click: () => handleMarkerClick(stand),
              }}
            >
              <Popup className="custom-popup">
                <div className="p-3 bg-zinc-950 text-white rounded-xl border border-white/20 min-w-[210px] shadow-2xl font-sans">
                  <div className="font-classic font-bold text-sm text-white mb-0.5">
                    {stand.name}
                  </div>
                  <div className="text-[11px] text-zinc-400 mb-2 font-mono">
                    Zone: {stand.zone} • ID: {stand.id}
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs border-t border-white/10 pt-2 font-mono">
                    <div>
                      <span className="text-zinc-400 block text-[10px]">
                        BIKES AVAILABLE
                      </span>
                      <strong className="text-white text-sm">{bikes}</strong>
                    </div>
                    <div>
                      <span className="text-zinc-400 block text-[10px]">
                        FREE DOCKS
                      </span>
                      <strong className="text-zinc-200 text-sm">
                        {stand.dock_capacity - bikes}
                      </strong>
                    </div>
                    <div>
                      <span className="text-zinc-400 block text-[10px]">
                        TOTAL DOCKS
                      </span>
                      <span className="text-zinc-200">{stand.dock_capacity}</span>
                    </div>
                    <div>
                      <span className="text-zinc-400 block text-[10px]">
                        FILL LEVEL
                      </span>
                      <span className="text-white font-bold">
                        {Math.round((bikes / stand.dock_capacity) * 100)}%
                      </span>
                    </div>
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}

        {/* Animated Moving Rebalancing Van Marker */}
        {telemetryFrame?.van && (
          <Marker
            position={[telemetryFrame.van.latitude, telemetryFrame.van.longitude]}
            icon={createVanIcon(telemetryFrame.van)}
          >
            <Popup className="custom-popup">
              <div className="p-3 bg-zinc-950 text-white rounded-xl border border-sky-400/40 min-w-[240px] shadow-2xl font-sans">
                <div className="flex items-center justify-between border-b border-white/10 pb-2 mb-2">
                  <div className="flex items-center gap-1.5 font-bold text-sky-400 text-xs">
                    <span>🚐</span>
                    <span>{telemetryFrame.van.name}</span>
                  </div>
                  <span
                    className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${
                      telemetryFrame.van.status === "AT_STOP"
                        ? "bg-emerald-950 text-emerald-400 border border-emerald-500/40"
                        : "bg-sky-950 text-sky-400 border border-sky-500/40"
                    }`}
                  >
                    {telemetryFrame.van.status}
                  </span>
                </div>
                <div className="space-y-1.5 text-xs text-zinc-300 font-mono">
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Action:</span>
                    <span className="font-semibold text-white">{telemetryFrame.van.current_action}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Target Stop:</span>
                    <span className="text-white font-semibold">{telemetryFrame.van.target_stand_name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">ETA to Stop:</span>
                    <span className="text-emerald-400 font-bold">{Math.round(telemetryFrame.van.eta_seconds)}s</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Van Load:</span>
                    <span className="text-sky-300 font-bold">{telemetryFrame.van.load} / {telemetryFrame.van.capacity} bikes</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">Cruising Speed:</span>
                    <span>{telemetryFrame.van.speed_kmh} km/h</span>
                  </div>
                </div>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Dynamic Zoom & Navigation HUD */}
        <MapZoomHUD
          stands={stands}
          activePolyline={activePolyline}
          defaultCenter={mapCenter}
          defaultZoom={mapZoom}
        />

        {/* Stand Fly Handler for smooth zooms */}
        <StandFlyHandler stand={inspectedStand} />
      </MapContainer>

      {/* Default Controls if not hidden */}
      {!hideDefaultControls && (
        <>
          {/* Campus Location Chip in Top Left */}
          <div className="absolute top-4 left-4 z-[1000] glass-cockpit px-3 py-1.5 rounded-full flex items-center gap-2 shadow-2xl border border-white/10">
            <MapPin className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-xs font-classic font-semibold text-white tracking-wide">
              {campusLabel}
            </span>
            <span className="text-[10px] font-mono text-zinc-400">
              ({stands.length} stands)
            </span>
          </div>

          {/* Real-time Streaming Telemetry Control HUD in Top Center */}
          {telemetryFrame && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[1000] glass-cockpit px-3.5 py-1.5 rounded-full flex items-center gap-2.5 shadow-2xl border border-sky-400/30">
              <div className="flex items-center gap-1.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span className="text-[10px] font-bold text-emerald-400 tracking-wider uppercase font-mono">
                  Live Stream
                </span>
              </div>

              <span className="text-zinc-600">•</span>

              <span className="text-xs font-mono font-bold text-white flex items-center gap-1">
                <span>🕒</span>
                <span>{telemetryFrame.sim_time}</span>
              </span>

              <span className="text-zinc-600 hidden sm:inline">•</span>

              <div className="hidden md:flex items-center gap-1.5 text-[11px] font-mono text-zinc-300">
                <span className="text-sky-400 font-semibold">🚐 Van #1:</span>
                <span className="text-white truncate max-w-[130px]">
                  {telemetryFrame.van.status === "AT_STOP"
                    ? "At Dock"
                    : `ETA ${Math.round(telemetryFrame.van.eta_seconds)}s`}
                </span>
              </div>

              <span className="text-zinc-600">•</span>

              {/* Play/Pause & Speed Selector */}
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => onTelemetryControl?.("pause", !telemetryFrame.is_paused)}
                  className="p-1 rounded-md hover:bg-white/10 text-zinc-300 hover:text-white transition"
                  title={telemetryFrame.is_paused ? "Resume Simulation" : "Pause Simulation"}
                >
                  {telemetryFrame.is_paused ? (
                    <Play className="w-3.5 h-3.5 text-emerald-400 fill-emerald-400" />
                  ) : (
                    <Pause className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
                  )}
                </button>
                {[1, 2, 5].map((spd) => (
                  <button
                    key={spd}
                    type="button"
                    onClick={() => onTelemetryControl?.("speed", spd)}
                    className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-bold transition ${
                      telemetryFrame.speed_multiplier === spd
                        ? "bg-sky-500 text-black shadow-sm"
                        : "text-zinc-400 hover:text-white"
                    }`}
                  >
                    {spd}x
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Style Toggle Pill in top right */}
          <div className="absolute top-4 right-4 z-[1000] glass-cockpit p-1 rounded-full flex items-center gap-1 shadow-2xl">
            {transitRoutes && transitRoutes.length > 0 && (
              <button
                type="button"
                onClick={() => setShowTransit(!showTransit)}
                className={`px-3 py-1 rounded-full text-[10px] font-classic uppercase transition flex items-center gap-1 ${
                  showTransit
                    ? "bg-emerald-500 text-black font-bold shadow-md"
                    : "text-zinc-300 hover:text-white"
                }`}
                title="Toggle Campus Shuttle / Transit Lines"
              >
                <Bus className="w-3 h-3" />
                <span>Transit Lines</span>
              </button>
            )}
            <button
              type="button"
              onClick={() => handleStyleChange("satellite")}
              className={`px-3 py-1 rounded-full text-[10px] font-classic uppercase transition ${
                activeMapStyle === "satellite"
                  ? "bg-white text-black font-bold shadow-md"
                  : "text-zinc-300 hover:text-white"
              }`}
            >
              Realistic Satellite
            </button>
            <button
              type="button"
              onClick={() => handleStyleChange("streets")}
              className={`px-3 py-1 rounded-full text-[10px] font-classic uppercase transition ${
                activeMapStyle === "streets"
                  ? "bg-white text-black font-bold shadow-md"
                  : "text-zinc-300 hover:text-white"
              }`}
            >
              Streets
            </button>
          </div>
        </>
      )}

      {/* Route Info Badge & Legend Pill in Bottom Right */}
      <div className="absolute bottom-4 right-4 z-[1000] glass-cockpit px-3 py-2 rounded-xl text-[10px] flex items-center gap-3 shadow-2xl border border-white/10">
        {routeDistanceKm !== undefined && (
          <div className="flex items-center gap-1.5 text-sky-300 font-mono font-bold pr-2 border-r border-white/15">
            <Navigation className="w-3.5 h-3.5" />
            <span>
              OSM Route: {routeDistanceKm.toFixed(1)} km ({routeTimeMin?.toFixed(1)} min)
            </span>
          </div>
        )}
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-white shadow-[0_0_6px_white]" />
          <span className="text-zinc-200 font-classic">Stand</span>
        </div>
        <span className="text-zinc-500">•</span>
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-0.5 bg-sky-400" />
          <span className="text-zinc-300 font-classic">Van Path</span>
        </div>
        {transitRoutes && transitRoutes.length > 0 && showTransit && (
          <>
            <span className="text-zinc-500">•</span>
            <div className="flex items-center gap-1.5">
              <span className="w-3.5 h-0.5 bg-emerald-400 border-b border-dashed border-emerald-300" />
              <span className="text-emerald-300 font-classic">EV Shuttle</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
