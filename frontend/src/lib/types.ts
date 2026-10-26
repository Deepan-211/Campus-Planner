export interface CampusInfo {
  id: string;
  name: string;
  city: string;
}

export interface Stand {
  id: string;
  name: string;
  zone: string;
  latitude: number;
  longitude: number;
  dock_capacity: number;
  origin_weight: number;
  destination_weight: number;
}

export interface CampusMatrix {
  source: string;
  stands: string[];
  distance_matrix: Record<string, Record<string, number>>;
  travel_time_matrix: Record<string, Record<string, number>>;
}

export interface RoutePath {
  from_stand: string;
  to_stand: string;
  distance_m: number;
  travel_time_sec: number;
  geometry: [number, number][];
}

export interface HourlyPredictionItem {
  stand_id: string;
  hour: number;
  predicted_pickups: number;
  predicted_dropoffs: number;
}

export interface ForecastResponse {
  forecast_date: string;
  model_name: string;
  predictions: HourlyPredictionItem[];
}

export interface ForecastMetrics {
  mae: number;
  rmse: number;
}

export interface ForecastEvalResponse {
  model_name: string;
  baseline_pickup_metrics: ForecastMetrics;
  model_pickup_metrics: ForecastMetrics;
  pickup_mae_improvement_pct: number;
  baseline_dropoff_metrics: ForecastMetrics;
  model_dropoff_metrics: ForecastMetrics;
  dropoff_mae_improvement_pct: number;
  num_train_samples: number;
  num_test_samples: number;
}

export interface AllocationResponse {
  fleet_size: number;
  baseline_allocation: Record<string, number>;
  optimized_allocation: Record<string, number>;
  baseline_cost: number;
  optimized_cost: number;
  cost_improvement_pct: number;
  solver_status: string;
  solve_time_ms: number;
}

export interface RouteStep {
  stop_order: number;
  stand_id: string;
  stand_name: string;
  action: "START" | "PICKUP" | "DROPOFF" | "END";
  bikes_change: number;
  van_load_after: number;
  arrival_time_min: number;
  departure_time_min: number;
  trip_number?: number;
}

export interface RebalancingResponse {
  status: string;
  total_distance_km: number;
  total_time_minutes: number;
  bikes_moved: number;
  van_trips?: number;
  route_steps: RouteStep[];
  unserviced_surplus: number;
  unserviced_deficit: number;
  route_geometry?: [number, number][][]; // list of segment coordinates [[lat, lon], ...]
  driving_time_minutes?: number;
  loading_time_minutes?: number;
  unloading_time_minutes?: number;
  total_operations?: number;
}

export interface ConfidenceInterval {
  mean: number;
  std_dev: number;
  ci_lower: number;
  ci_upper: number;
}

export interface MetricComparison {
  name: string;
  baseline: ConfidenceInterval;
  optimized: ConfidenceInterval;
  absolute_improvement: number;
  pct_improvement: number;
  p_value: number;
  is_statistically_significant: boolean;
}

export interface EvaluationResponse {
  replications: number;
  fleet_size: number;
  confidence_level: number;
  seeds_evaluated: number[];
  unmet_demand_pct: MetricComparison;
  avg_wait_time_min: MetricComparison;
  fleet_utilization_pct: MetricComparison;
  rides_per_vehicle_per_day?: MetricComparison;
  peak_hour_utilization_pct?: MetricComparison;
  stand_hourly_baseline: Record<string, Record<number, number>>;
  stand_hourly_optimized: Record<string, Record<number, number>>;
  unmet_by_stand_hour_baseline?: Record<string, Record<number, number>>;
  unmet_by_stand_hour_optimized?: Record<string, Record<number, number>>;
}

export interface DataSourceInfo {
  type: string;
  label: string;
  count?: number | null;
}

export interface AssumptionItem {
  parameter: string;
  value: string;
  units: string;
  source: string;
  config_key: string;
}

export interface ConfigSummary {
  campus_id: string;
  campus_name: string;
  total_bikes: number;
  total_docks: number;
  num_stands: number;
  van_capacity: number;
  operating_hours: string;
  assumptions: AssumptionItem[];
}

export interface TripLeg {
  mode: string;
  from_name: string;
  to_name: string;
  distance_m: number;
  duration_min: number;
  geometry: [number, number][];
}

export interface TripOption {
  id: string;
  mode_name: string;
  mode_icon: string;
  total_duration_min: number;
  transit_duration_min: number;
  walk_duration_min: number;
  wait_duration_min: number;
  distance_m: number;
  cost: number;
  cost_currency: string;
  is_available: boolean;
  availability_status: "HIGH" | "LOW" | "UNAVAILABLE";
  availability_detail: string;
  tags: string[];
  recommendation_reason?: string | null;
  fallback_message?: string | null;
  origin_stand_id?: string | null;
  dest_stand_id?: string | null;
  legs: TripLeg[];
  full_geometry: [number, number][];
}

export interface TripOptionsResponse {
  campus_id: string;
  campus_name: string;
  departure_time: string;
  origin_name: string;
  dest_name: string;
  options: TripOption[];
  recommended_option_id: string;
}

export interface StandLiveAvailability {
  stand_id: string;
  stand_name: string;
  zone: string;
  latitude: number;
  longitude: number;
  dock_capacity: number;
  bikes_available: number;
  docks_free: number;
  fill_pct: number;
  status: "NORMAL" | "STARVED" | "FULL";
}

export interface CampusLiveAvailabilityResponse {
  campus_id: string;
  campus_name: string;
  hour: number;
  stands: StandLiveAvailability[];
}

export interface TransitStop {
  stand_id: string;
  name: string;
  latitude: number;
  longitude: number;
  stop_order: number;
}

export interface TransitRoute {
  id: string;
  name: string;
  type: "shuttle" | "golf_cart" | string;
  vehicle_type: string;
  color: string;
  operating_hours: string;
  headway_minutes: number;
  speed_kmh: number;
  cost: number;
  currency: string;
  stops: TransitStop[];
}

export interface UserProfile {
  id: number;
  email: string;
  full_name: string;
  role: "admin" | "operator" | "student" | string;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}
