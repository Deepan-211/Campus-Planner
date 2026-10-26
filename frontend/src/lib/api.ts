import {
  CampusInfo,
  Stand,
  CampusMatrix,
  ForecastResponse,
  ForecastEvalResponse,
  AllocationResponse,
  RebalancingResponse,
  EvaluationResponse,
  DataSourceInfo,
  ConfigSummary,
  TripOptionsResponse,
  CampusLiveAvailabilityResponse,
  TransitRoute,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const AUTH_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace("/api/v1", "/api/auth");
const TOKEN_KEY = "campusride_jwt_token";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export async function fetchCampusList(): Promise<CampusInfo[]> {
  const res = await fetch(`${API_BASE}/campus/list`);
  if (!res.ok) throw new Error("Failed to fetch campus list");
  return res.json();
}

export async function fetchStands(campusId?: string): Promise<Stand[]> {
  const url = campusId ? `${API_BASE}/campus/stands?campus_id=${campusId}` : `${API_BASE}/campus/stands`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch campus stands");
  return res.json();
}

export async function fetchMatrix(campusId?: string): Promise<CampusMatrix> {
  const url = campusId ? `${API_BASE}/campus/matrix?campus_id=${campusId}` : `${API_BASE}/campus/matrix`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch campus distance matrix");
  return res.json();
}

export async function fetchDataSource(campusId?: string): Promise<DataSourceInfo> {
  const url = campusId ? `${API_BASE}/data/source?campus_id=${campusId}` : `${API_BASE}/data/source`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch data source info");
  return res.json();
}

export async function fetchAssumptions(campusId?: string): Promise<ConfigSummary> {
  const url = campusId ? `${API_BASE}/config/assumptions?campus_id=${campusId}` : `${API_BASE}/config/assumptions`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch assumptions");
  return res.json();
}

export async function fetchForecast(date: string = "2026-10-23", campusId?: string): Promise<ForecastResponse> {
  const url = campusId
    ? `${API_BASE}/forecast/predict?date=${date}&campus_id=${campusId}`
    : `${API_BASE}/forecast/predict?date=${date}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch demand forecast");
  return res.json();
}

export async function fetchForecastEval(campusId?: string): Promise<ForecastEvalResponse> {
  const url = campusId ? `${API_BASE}/forecast/evaluate?campus_id=${campusId}` : `${API_BASE}/forecast/evaluate`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch forecast evaluation");
  return res.json();
}

export async function optimizeAllocation(
  fleetSize?: number,
  campusId?: string
): Promise<AllocationResponse> {
  const url = campusId ? `${API_BASE}/allocation/optimize?campus_id=${campusId}` : `${API_BASE}/allocation/optimize`;
  const body = fleetSize !== undefined ? { fleet_size: fleetSize } : {};
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to optimize fleet allocation");
  return res.json();
}

export async function planRebalancing(
  currentInventory?: Record<string, number>,
  targetInventory?: Record<string, number>,
  campusId?: string
): Promise<RebalancingResponse> {
  const url = campusId ? `${API_BASE}/rebalancing/plan?campus_id=${campusId}` : `${API_BASE}/rebalancing/plan`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      current_inventory: currentInventory,
      target_inventory: targetInventory,
    }),
  });
  if (!res.ok) throw new Error("Failed to plan rebalancing routes");
  return res.json();
}

export async function runEvaluation(
  replications: number = 5,
  fleetSize?: number,
  campusId?: string
): Promise<EvaluationResponse> {
  const url = campusId ? `${API_BASE}/simulation/evaluate?campus_id=${campusId}` : `${API_BASE}/simulation/evaluate`;
  const body: any = { replications, test_date: "2026-10-23" };
  if (fleetSize !== undefined) body.fleet_size = fleetSize;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to evaluate simulation policies");
  return res.json();
}

export async function fetchTripOptions(params: {
  campus_id?: string;
  origin_stand_id?: string;
  origin_coords?: [number, number];
  origin_name?: string;
  dest_stand_id?: string;
  dest_coords?: [number, number];
  dest_name?: string;
  departure_hour?: number;
  departure_minute?: number;
}): Promise<TripOptionsResponse> {
  const res = await fetch(`${API_BASE}/trip/options`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error("Failed to calculate trip options");
  return res.json();
}

export async function fetchStandsLiveAvailability(
  campusId?: string,
  hour: number = 8
): Promise<CampusLiveAvailabilityResponse> {
  const url = campusId
    ? `${API_BASE}/stands/live_availability?campus_id=${campusId}&hour=${hour}`
    : `${API_BASE}/stands/live_availability?hour=${hour}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch stand live availability");
  return res.json();
}

export async function fetchTransitRoutes(campusId?: string): Promise<TransitRoute[]> {
  const url = campusId
    ? `${API_BASE}/transit/routes?campus_id=${campusId}`
    : `${API_BASE}/transit/routes`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch transit routes");
  return res.json();
}
