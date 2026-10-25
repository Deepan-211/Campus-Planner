"""
Pydantic Schemas for CampusRide Planner REST API.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# --- Campus & Topography ---
class CampusInfo(BaseModel):
    id: str
    name: str
    city: str


class StandResponse(BaseModel):
    id: str
    name: str
    zone: str
    latitude: float
    longitude: float
    dock_capacity: int
    origin_weight: float
    destination_weight: float


class CampusMatrixResponse(BaseModel):
    source: str
    stands: List[str]
    distance_matrix: Dict[str, Dict[str, float]]
    travel_time_matrix: Dict[str, Dict[str, float]]


# --- Demand Forecasting ---
class HourlyPredictionItem(BaseModel):
    stand_id: str
    hour: int
    predicted_pickups: float
    predicted_dropoffs: float


class ForecastResponse(BaseModel):
    forecast_date: str
    model_name: str
    predictions: List[HourlyPredictionItem]


class ForecastMetricsSchema(BaseModel):
    mae: float
    rmse: float


class ForecastEvalResponse(BaseModel):
    model_name: str
    baseline_pickup_metrics: ForecastMetricsSchema
    model_pickup_metrics: ForecastMetricsSchema
    pickup_mae_improvement_pct: float
    baseline_dropoff_metrics: ForecastMetricsSchema
    model_dropoff_metrics: ForecastMetricsSchema
    dropoff_mae_improvement_pct: float
    num_train_samples: int
    num_test_samples: int


# --- Allocation Optimization ---
class AllocationWeightsSchema(BaseModel):
    stockout_penalty: float = 1.0
    overflow_penalty: float = 0.7


class AllocationRequest(BaseModel):
    fleet_size: Optional[int] = Field(default=None, ge=1, le=500)
    target_hour: Optional[int] = Field(default=7, ge=0, le=23)
    weights: Optional[AllocationWeightsSchema] = None


class AllocationResponse(BaseModel):
    fleet_size: int
    baseline_allocation: Dict[str, int]
    optimized_allocation: Dict[str, int]
    baseline_cost: float
    optimized_cost: float
    cost_improvement_pct: float
    solver_status: str
    solve_time_ms: float


# --- Vehicle Rebalancing ---
class RebalancingRequest(BaseModel):
    van_capacity: Optional[int] = Field(default=15, ge=1, le=50)
    current_inventory: Optional[Dict[str, int]] = None
    target_inventory: Optional[Dict[str, int]] = None


class RouteStepResponse(BaseModel):
    stop_order: int
    stand_id: str
    stand_name: str
    action: str
    bikes_change: int
    van_load_after: int
    arrival_time_min: float
    departure_time_min: float
    trip_number: int = 1


class RebalancingResponse(BaseModel):
    status: str
    total_distance_km: float
    total_time_minutes: float
    bikes_moved: int
    route_steps: List[RouteStepResponse]
    van_trips: int = 1
    unserviced_surplus: int
    unserviced_deficit: int
    route_geometry: Optional[List[List[List[float]]]] = None  # [[lat, lon], ...] per segment
    driving_time_minutes: float = 0.0
    loading_time_minutes: float = 0.0
    unloading_time_minutes: float = 0.0
    total_operations: int = 0


class RoutePathResponse(BaseModel):
    from_stand: str
    to_stand: str
    distance_m: float
    travel_time_sec: float
    geometry: List[List[float]]


# --- Comparative Simulation & Evaluation ---
class ConfidenceIntervalSchema(BaseModel):
    mean: float
    std_dev: float
    ci_lower: float
    ci_upper: float


class MetricComparisonSchema(BaseModel):
    name: str
    baseline: ConfidenceIntervalSchema
    optimized: ConfidenceIntervalSchema
    absolute_improvement: float
    pct_improvement: float
    p_value: float
    is_statistically_significant: bool


class EvaluationRequest(BaseModel):
    replications: Optional[int] = Field(default=30, ge=1, le=100)
    fleet_size: Optional[int] = Field(default=None, ge=1, le=500)
    test_date: Optional[str] = "2026-10-23"


class EvaluationResponse(BaseModel):
    replications: int
    fleet_size: int
    confidence_level: float
    seeds_evaluated: List[int]
    unmet_demand_pct: MetricComparisonSchema
    avg_wait_time_min: MetricComparisonSchema
    fleet_utilization_pct: MetricComparisonSchema
    rides_per_vehicle_per_day: MetricComparisonSchema
    peak_hour_utilization_pct: MetricComparisonSchema
    stand_hourly_baseline: Dict[str, Dict[int, float]]
    stand_hourly_optimized: Dict[str, Dict[int, float]]
    unmet_by_stand_hour_baseline: Optional[Dict[str, Dict[int, float]]] = None
    unmet_by_stand_hour_optimized: Optional[Dict[str, Dict[int, float]]] = None



# --- Data Source ---
class DataSourceResponse(BaseModel):
    type: str  # "synthetic" or "survey"
    label: str  # human-readable label
    count: Optional[int] = None  # number of survey records if survey


# --- Config / Assumptions ---
class AssumptionItem(BaseModel):
    parameter: str
    value: str
    units: str
    source: str
    config_key: str


class ConfigSummaryResponse(BaseModel):
    campus_id: str
    campus_name: str
    total_bikes: int
    total_docks: int
    num_stands: int
    van_capacity: int
    operating_hours: str
    assumptions: List[AssumptionItem]


# --- Rider View: Trip Planning & Routing ---
class TripOptionRequest(BaseModel):
    campus_id: Optional[str] = None
    origin_stand_id: Optional[str] = None
    origin_coords: Optional[List[float]] = None  # [lat, lon]
    origin_name: Optional[str] = None
    dest_stand_id: Optional[str] = None
    dest_coords: Optional[List[float]] = None  # [lat, lon]
    dest_name: Optional[str] = None
    departure_hour: Optional[int] = 8
    departure_minute: Optional[int] = 0


class TripLeg(BaseModel):
    mode: str  # "walk" | "bike"
    from_name: str
    to_name: str
    distance_m: float
    duration_min: float
    geometry: List[List[float]]  # [[lat, lon], ...]


class TripOption(BaseModel):
    id: str  # "walk" | "bike"
    mode_name: str
    mode_icon: str  # "Footprints" | "Bike"
    total_duration_min: float
    transit_duration_min: float
    walk_duration_min: float
    wait_duration_min: float
    distance_m: float
    cost: float
    cost_currency: str  # "₹" or "$"
    is_available: bool
    availability_status: str  # "HIGH" | "LOW" | "UNAVAILABLE"
    availability_detail: str
    tags: List[str]  # ["Fastest", "Recommended"]
    recommendation_reason: Optional[str] = None
    fallback_message: Optional[str] = None
    origin_stand_id: Optional[str] = None
    dest_stand_id: Optional[str] = None
    legs: List[TripLeg]
    full_geometry: List[List[float]]


class TripOptionsResponse(BaseModel):
    campus_id: str
    campus_name: str
    departure_time: str
    origin_name: str
    dest_name: str
    options: List[TripOption]
    recommended_option_id: str


class StandLiveAvailability(BaseModel):
    stand_id: str
    stand_name: str
    zone: str
    latitude: float
    longitude: float
    dock_capacity: int
    bikes_available: int
    docks_free: int
    fill_pct: int
    status: str  # "NORMAL" | "STARVED" | "FULL"


class CampusLiveAvailabilityResponse(BaseModel):
    campus_id: str
    campus_name: str
    hour: int
    stands: List[StandLiveAvailability]


class TransitStop(BaseModel):
    stand_id: str
    name: str
    latitude: float
    longitude: float
    stop_order: int


class TransitRouteResponse(BaseModel):
    id: str
    name: str
    type: str  # "shuttle" | "golf_cart"
    vehicle_type: str
    color: str
    operating_hours: str
    headway_minutes: int
    speed_kmh: float
    cost: float
    currency: str
    stops: List[TransitStop]
