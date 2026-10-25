"""
FastAPI REST API Routes for CampusRide Planner.
Exposes endpoints for campus topography, demand forecasting,
fleet allocation optimization, rebalancing routing, and comparative evaluation.
Supports multi-campus configurations (UC Berkeley, VSB Karur).
"""
from pathlib import Path
from typing import Dict, List, Optional
import logging
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from backend.config import (
    load_stands,
    load_config,
    load_transit_routes,
    list_available_campuses,
    get_assumptions_table,
    PROJECT_ROOT,
)
from backend.data.campus_graph import (
    load_or_build_campus_network,
    haversine_distance,
    generate_path_waypoints,
)
from backend.data.weather_fetcher import WeatherFetcher
from backend.data.synthetic_generator import SyntheticDemandGenerator
from backend.forecast.forecaster import MLDemandForecaster, evaluate_forecast_pipeline
from backend.allocation.optimizer import FleetAllocationOptimizer
from backend.rebalancing.router import RebalancingRouter
from backend.simulator.engine import CampusSimulator
from backend.evaluation.evaluator import PolicyEvaluator
from backend.api.schemas import (
    CampusInfo,
    StandResponse,
    CampusMatrixResponse,
    RoutePathResponse,
    ForecastResponse,
    HourlyPredictionItem,
    ForecastEvalResponse,
    ForecastMetricsSchema,
    AllocationRequest,
    AllocationResponse,
    RebalancingRequest,
    RebalancingResponse,
    RouteStepResponse,
    EvaluationRequest,
    EvaluationResponse,
    DataSourceResponse,
    AssumptionItem,
    ConfigSummaryResponse,
    TripOptionRequest,
    TripOptionsResponse,
    TripOption,
    TripLeg,
    StandLiveAvailability,
    CampusLiveAvailabilityResponse,
    TransitStop,
    TransitRouteResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

# In-memory caches keyed by campus_id
_forecasters: Dict[str, MLDemandForecaster] = {}
_forecast_eval_cache: Dict[str, ForecastEvalResponse] = {}
_simulator_hourly_inventory_cache: Dict[str, Dict[str, Dict[int, int]]] = {}


def get_simulator_hourly_inventory(campus_id: Optional[str] = None) -> Dict[str, Dict[int, int]]:
    """
    Retrieves the stand hourly inventory state produced by the CampusSimulator for the given campus.
    Guarantees that real-time live availability and trip options dynamically match the simulated state across hours.
    """
    cfg = load_config(campus_id=campus_id)
    cid = cfg.campus.id
    if cid in _simulator_hourly_inventory_cache:
        return _simulator_hourly_inventory_cache[cid]

    stands = load_stands(campus_id=cid)
    net = load_or_build_campus_network(campus_id=cid)
    total_bikes = cfg.fleet.total_bikes

    allocator = FleetAllocationOptimizer(stands=stands, campus_id=cid)
    init_alloc = allocator.compute_baseline_allocation(fleet_size=total_bikes)



    gen = SyntheticDemandGenerator(seed=42, campus_id=cid)
    test_trips = gen.generate_day_trips("2026-10-23")

    sim = CampusSimulator(stands=stands, campus_network=net, random_seed=42)
    results = sim.run(trips=test_trips, initial_allocation=init_alloc)

    _simulator_hourly_inventory_cache[cid] = results.stand_hourly_inventory
    return results.stand_hourly_inventory


def get_campus_forecaster(campus_id: Optional[str] = None) -> MLDemandForecaster:
    cfg = load_config(campus_id=campus_id)
    cid = cfg.campus.id
    if cid not in _forecasters:
        stands = load_stands(campus_id=cid)
        forecaster = MLDemandForecaster(stands)
        gen = SyntheticDemandGenerator(seed=42, campus_id=cid)
        rows = []
        dummy_weather = WeatherFetcher()._generate_fallback_weather("2026-10-01")
        for d in range(7):
            d_str = f"2026-10-{d+1:02d}"
            trips = gen.generate_day_trips(d_str, weather_override=dummy_weather, seed_offset=d * 10)
            counts = {h: {s.id: {"p": 0, "d": 0} for s in stands} for h in range(7, 23)}
            for t in trips:
                h = int(t.request_time_sec // 3600)
                if 7 <= h <= 22:
                    counts[h][t.origin_stand_id]["p"] += 1
                    counts[h][t.dest_stand_id]["d"] += 1
            for h in range(7, 23):
                for s in stands:
                    rows.append({
                        "date": d_str,
                        "hour": h,
                        "stand_id": s.id,
                        "pickups_actual": counts[h][s.id]["p"],
                        "dropoffs_actual": counts[h][s.id]["d"],
                        "temp_celsius": 17.0,
                        "precipitation_mm": 0.0
                    })
        forecaster.fit(pd.DataFrame(rows))
        _forecasters[cid] = forecaster
    return _forecasters[cid]


# --- Campus & Topography ---
@router.get("/campus/list", response_model=List[CampusInfo])
def get_campus_list():
    """Retrieve list of configured campus locations."""
    campuses = list_available_campuses()
    return [CampusInfo(**c) for c in campuses]


@router.get("/campus/stands", response_model=List[StandResponse])
def get_campus_stands(campus_id: Optional[str] = Query(default=None)):
    """Retrieve physical micromobility stands for the specified campus."""
    stands = load_stands(campus_id=campus_id)
    return [
        StandResponse(
            id=s.id,
            name=s.name,
            zone=s.zone,
            latitude=s.latitude,
            longitude=s.longitude,
            dock_capacity=s.dock_capacity,
            origin_weight=s.origin_weight,
            destination_weight=s.destination_weight,
        )
        for s in stands
    ]


@router.get("/campus/matrix", response_model=CampusMatrixResponse)
def get_campus_matrix(campus_id: Optional[str] = Query(default=None)):
    """Retrieve shortest path distance (m) and travel time (sec) matrices."""
    net = load_or_build_campus_network(campus_id=campus_id)
    return CampusMatrixResponse(
        source=net.source,
        stands=[s.id for s in net.stands],
        distance_matrix=net.distance_matrix,
        travel_time_matrix=net.travel_time_matrix,
    )


@router.get("/campus/route_path", response_model=RoutePathResponse)
def get_route_path(
    from_stand: Optional[str] = Query(default=None, alias="from"),
    from_stand_alt: Optional[str] = Query(default=None, alias="from_stand"),
    to_stand: Optional[str] = Query(default=None, alias="to"),
    to_stand_alt: Optional[str] = Query(default=None, alias="to_stand"),
    campus_id: Optional[str] = Query(default=None),
):
    """Retrieve node-by-node path coordinates along the campus road network between two stands."""
    origin = from_stand or from_stand_alt
    dest = to_stand or to_stand_alt
    if not origin or not dest:
        raise HTTPException(status_code=400, detail="Both from and to stand IDs are required.")

    net = load_or_build_campus_network(campus_id=campus_id)
    if origin not in net.stand_map or dest not in net.stand_map:
        raise HTTPException(status_code=404, detail=f"Stand ID not found: {origin} or {dest}")

    geometry = net.get_route_geometry(origin, dest)
    dist_m = net.get_distance(origin, dest)
    time_s = net.get_travel_time(origin, dest)

    return RoutePathResponse(
        from_stand=origin,
        to_stand=dest,
        distance_m=dist_m,
        travel_time_sec=time_s,
        geometry=geometry,
    )


# --- Data Source Badge ---
@router.get("/data/source", response_model=DataSourceResponse)
def get_data_source(campus_id: Optional[str] = Query(default=None)):
    """Return whether the current dataset is empirical survey data or calibrated synthetic data."""
    cfg = load_config(campus_id=campus_id)
    cid = cfg.campus.id

    candidate_files = [
        PROJECT_ROOT / "config" / "campuses" / cid / "survey_responses.csv",
        PROJECT_ROOT / "data" / f"{cid}_survey_responses.csv",
        PROJECT_ROOT / "data" / "survey_responses.csv",
    ]

    for survey_file in candidate_files:
        if survey_file.exists():
            try:
                df = pd.read_csv(survey_file)
                count = len(df)
                return DataSourceResponse(
                    type="synthetic",
                    label=f"Synthetic (n={count})",
                    count=count,
                )
            except Exception:
                pass

    return DataSourceResponse(
        type="synthetic",
        label="Synthetic Data (Calibrated NHPP)",
        count=None,
    )



# --- Demand Forecasting ---
@router.get("/forecast/predict", response_model=ForecastResponse)
def predict_demand(
    date: str = Query(default="2026-10-23", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    campus_id: Optional[str] = Query(default=None),
):
    """Forecast hourly pickups and dropoffs per stand for the specified date."""
    forecaster = get_campus_forecaster(campus_id=campus_id)
    weather_fetcher = WeatherFetcher()
    weather_map = weather_fetcher.get_hourly_weather(date)

    day_preds = forecaster.predict_day(date, weather_map)

    items = []
    for s_id, hours in day_preds.items():
        for h, (p, d) in hours.items():
            items.append(HourlyPredictionItem(
                stand_id=s_id,
                hour=h,
                predicted_pickups=p,
                predicted_dropoffs=d,
            ))

    return ForecastResponse(
        forecast_date=date,
        model_name=forecaster.model_name,
        predictions=items,
    )


@router.get("/forecast/evaluate", response_model=ForecastEvalResponse)
def evaluate_forecast(campus_id: Optional[str] = Query(default=None)):
    """Evaluate demand forecasting model against historical average baseline on held-out test data."""
    cfg = load_config(campus_id=campus_id)
    cid = cfg.campus.id
    if cid in _forecast_eval_cache:
        return _forecast_eval_cache[cid]

    stands = load_stands(campus_id=cid)
    gen = SyntheticDemandGenerator(seed=42, campus_id=cid)
    dummy_weather = WeatherFetcher()._generate_fallback_weather("2026-10-01")

    rows = []
    for d in range(8):
        d_str = f"2026-10-{d+1:02d}"
        trips = gen.generate_day_trips(d_str, weather_override=dummy_weather, seed_offset=d * 7)
        counts = {h: {s.id: {"p": 0, "d": 0} for s in stands} for h in range(7, 23)}
        for t in trips:
            h = int(t.request_time_sec // 3600)
            if 7 <= h <= 22:
                counts[h][t.origin_stand_id]["p"] += 1
                counts[h][t.dest_stand_id]["d"] += 1
        for h in range(7, 23):
            for s in stands:
                rows.append({
                    "date": d_str,
                    "hour": h,
                    "stand_id": s.id,
                    "pickups_actual": counts[h][s.id]["p"],
                    "dropoffs_actual": counts[h][s.id]["d"],
                    "temp_celsius": 17.0,
                    "precipitation_mm": 0.0,
                })

    df_all = pd.DataFrame(rows)
    _, _, report = evaluate_forecast_pipeline(df_all, test_days=2, stands=stands)

    resp = ForecastEvalResponse(
        model_name=report.model_name,
        baseline_pickup_metrics=ForecastMetricsSchema(
            mae=report.baseline_pickup_metrics.mae,
            rmse=report.baseline_pickup_metrics.rmse,
        ),
        model_pickup_metrics=ForecastMetricsSchema(
            mae=report.model_pickup_metrics.mae,
            rmse=report.model_pickup_metrics.rmse,
        ),
        pickup_mae_improvement_pct=report.pickup_mae_improvement_pct,
        baseline_dropoff_metrics=ForecastMetricsSchema(
            mae=report.baseline_dropoff_metrics.mae,
            rmse=report.baseline_dropoff_metrics.rmse,
        ),
        model_dropoff_metrics=ForecastMetricsSchema(
            mae=report.model_dropoff_metrics.mae,
            rmse=report.model_dropoff_metrics.rmse,
        ),
        dropoff_mae_improvement_pct=report.dropoff_mae_improvement_pct,
        num_train_samples=report.num_train_samples,
        num_test_samples=report.num_test_samples,
    )
    _forecast_eval_cache[cid] = resp
    return resp


# --- Allocation Optimizer ---
@router.post("/allocation/optimize", response_model=AllocationResponse)
def optimize_allocation(
    req: AllocationRequest,
    campus_id: Optional[str] = Query(default=None),
):
    """Solve MILP morning fleet allocation across all stands."""
    cfg = load_config(campus_id=campus_id)
    cid = cfg.campus.id
    stands = load_stands(campus_id=cid)
    optimizer = FleetAllocationOptimizer(stands, campus_id=cid)

    fleet_size = req.fleet_size or cfg.fleet.total_bikes

    # Default morning rush distributions
    if cid == "berkeley":
        morning_out = {
            "ST-01": 25.0, "ST-02": 24.0, "ST-03": 18.0,
            "ST-04": 2.0, "ST-05": 3.0, "ST-06": 3.0, "ST-07": 2.0,
        }
        morning_in = {
            "ST-01": 2.0, "ST-02": 1.0, "ST-03": 1.0,
            "ST-04": 22.0, "ST-05": 28.0, "ST-06": 16.0, "ST-07": 8.0,
        }
    else:
        morning_out = {s.id: max(1.0, round(s.origin_weight * fleet_size * 0.8, 1)) for s in stands}
        morning_in = {s.id: max(1.0, round(s.destination_weight * fleet_size * 0.8, 1)) for s in stands}

    w_s = req.weights.stockout_penalty if req.weights else 1.0
    w_o = req.weights.overflow_penalty if req.weights else 0.7

    try:
        res = optimizer.optimize(
            morning_demand_out=morning_out,
            morning_demand_in=morning_in,
            fleet_size=fleet_size,
            w_stockout=w_s,
            w_overflow=w_o,
        )
        return AllocationResponse(
            fleet_size=res.fleet_size,
            baseline_allocation=res.baseline_allocation,
            optimized_allocation=res.optimized_allocation,
            baseline_cost=res.baseline_cost,
            optimized_cost=res.optimized_cost,
            cost_improvement_pct=res.cost_improvement_pct,
            solver_status=res.solver_status,
            solve_time_ms=res.solve_time_ms,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Rebalancing Router ---
@router.post("/rebalancing/plan", response_model=RebalancingResponse)
def plan_rebalancing(
    req: RebalancingRequest,
    campus_id: Optional[str] = Query(default=None),
):
    """Solve Capacitated Vehicle Routing Problem for midday van rebalancing with OSMnx paths."""
    cfg = load_config(campus_id=campus_id)
    cid = cfg.campus.id
    stands = load_stands(campus_id=cid)
    net = load_or_build_campus_network(campus_id=cid)
    router_engine = RebalancingRouter(stands=stands, campus_network=net, campus_id=cid)

    if req.current_inventory:
        curr = req.current_inventory
    elif cid == "berkeley":
        curr = {
            "ST-01": 3, "ST-02": 2, "ST-03": 4,
            "ST-04": 22, "ST-05": 28, "ST-06": 23, "ST-07": 18,
        }
    else:
        f_size = cfg.fleet.total_bikes
        curr = {s.id: min(s.dock_capacity, max(1, int(s.destination_weight * f_size * 1.1))) for s in stands}

    if req.target_inventory:
        target = req.target_inventory
    elif cid == "berkeley":
        target = {
            "ST-01": 15, "ST-02": 15, "ST-03": 12,
            "ST-04": 12, "ST-05": 16, "ST-06": 16, "ST-07": 14,
        }
    else:
        f_size = cfg.fleet.total_bikes
        target = {s.id: min(s.dock_capacity, max(1, int(s.origin_weight * f_size * 0.9))) for s in stands}

    plan = router_engine.plan_rebalancing(current_inventory=curr, target_inventory=target)

    steps = [
        RouteStepResponse(
            stop_order=s.stop_order,
            stand_id=s.stand_id,
            stand_name=s.stand_name,
            action=s.action,
            bikes_change=s.bikes_change,
            van_load_after=s.van_load_after,
            arrival_time_min=s.arrival_time_min,
            departure_time_min=s.departure_time_min,
            trip_number=s.trip_number,
        )
        for s in plan.route_steps
    ]

    return RebalancingResponse(
        status=plan.status,
        total_distance_km=plan.total_distance_km,
        total_time_minutes=plan.total_time_minutes,
        bikes_moved=plan.bikes_moved,
        route_steps=steps,
        van_trips=plan.van_trips,
        unserviced_surplus=plan.unserviced_surplus,
        unserviced_deficit=plan.unserviced_deficit,
        route_geometry=plan.route_geometry,
        driving_time_minutes=plan.driving_time_minutes,
        loading_time_minutes=plan.loading_time_minutes,
        unloading_time_minutes=plan.unloading_time_minutes,
        total_operations=plan.total_operations,
    )


# --- Simulation Evaluation Engine ---
@router.post("/simulation/evaluate", response_model=EvaluationResponse)
def evaluate_policies(
    req: EvaluationRequest,
    campus_id: Optional[str] = Query(default=None),
):
    """Run paired Monte Carlo simulations comparing Baseline vs. Optimized policies with 95% CIs."""
    cfg = load_config(campus_id=campus_id)
    cid = cfg.campus.id
    stands = load_stands(campus_id=cid)
    net = load_or_build_campus_network(campus_id=cid)
    evaluator = PolicyEvaluator(stands=stands, campus_network=net, campus_id=cid)

    fleet_size = req.fleet_size or cfg.fleet.total_bikes
    report = evaluator.evaluate(
        replications=req.replications,
        fleet_size=fleet_size,
        test_date=req.test_date or "2026-10-23",
    )

    report_dict = report.to_dict()
    return EvaluationResponse(
        replications=report_dict["replications"],
        fleet_size=report_dict["fleet_size"],
        confidence_level=report_dict["confidence_level"],
        seeds_evaluated=report_dict["seeds_evaluated"],
        unmet_demand_pct=report_dict["unmet_demand_pct"],
        avg_wait_time_min=report_dict["avg_wait_time_min"],
        fleet_utilization_pct=report_dict["fleet_utilization_pct"],
        rides_per_vehicle_per_day=report_dict["rides_per_vehicle_per_day"],
        peak_hour_utilization_pct=report_dict["peak_hour_utilization_pct"],
        stand_hourly_baseline=report_dict["stand_hourly_baseline"],
        stand_hourly_optimized=report_dict["stand_hourly_optimized"],
        unmet_by_stand_hour_baseline=report_dict.get("unmet_by_stand_hour_baseline"),
        unmet_by_stand_hour_optimized=report_dict.get("unmet_by_stand_hour_optimized"),
    )



# --- Assumptions & Config Summary ---
@router.get("/config/assumptions", response_model=ConfigSummaryResponse)
def get_assumptions(campus_id: Optional[str] = Query(default=None)):
    """Retrieve operational assumptions, parameter justifications, and source references."""
    cfg = load_config(campus_id=campus_id)
    cid = cfg.campus.id
    stands = load_stands(campus_id=cid)
    total_docks = sum(s.dock_capacity for s in stands)
    assumptions_raw = get_assumptions_table(campus_id=cid)

    items = [AssumptionItem(**item) for item in assumptions_raw]

    return ConfigSummaryResponse(
        campus_id=cid,
        campus_name=cfg.campus.name,
        total_bikes=cfg.fleet.total_bikes,
        total_docks=total_docks,
        num_stands=len(stands),
        van_capacity=cfg.rebalancing.van_capacity,
        operating_hours=f"{cfg.simulation.operating_hours.start_hour}:00–{cfg.simulation.operating_hours.end_hour}:00",
        assumptions=items,
    )


# --- Stand Live Availability (for Rider & Operator Views) ---
@router.get("/stands/live_availability", response_model=CampusLiveAvailabilityResponse)
def get_stands_live_availability(
    hour: int = Query(default=8, ge=7, le=22),
    campus_id: Optional[str] = Query(default=None),
):
    """Returns stand-level real-time inventory and availability for a given hour."""
    cfg = load_config(campus_id=campus_id)
    cid = cfg.campus.id
    stands = load_stands(campus_id=cid)
    f_size = cfg.fleet.total_bikes
    hourly_inv = get_simulator_hourly_inventory(campus_id=cid)
    clamped_hour = max(7, min(22, hour))

    stand_items = []
    for s in stands:
        bikes = hourly_inv.get(s.id, {}).get(
            clamped_hour,
            max(0, min(s.dock_capacity, int(round(s.origin_weight * f_size))))
        )
        free_docks = max(0, s.dock_capacity - bikes)
        fill_pct = int(round((bikes / s.dock_capacity) * 100)) if s.dock_capacity > 0 else 0
        status = "STARVED" if bikes == 0 else ("FULL" if free_docks == 0 else "NORMAL")


        stand_items.append(StandLiveAvailability(
            stand_id=s.id,
            stand_name=s.name,
            zone=s.zone,
            latitude=s.latitude,
            longitude=s.longitude,
            dock_capacity=s.dock_capacity,
            bikes_available=bikes,
            docks_free=free_docks,
            fill_pct=fill_pct,
            status=status,
        ))

    return CampusLiveAvailabilityResponse(
        campus_id=cid,
        campus_name=cfg.campus.name,
        hour=hour,
        stands=stand_items,
    )


# --- Campus Fixed Transit Routes (Shuttle & Golf Cart) ---
@router.get("/transit/routes", response_model=List[TransitRouteResponse])
def get_transit_routes(campus_id: Optional[str] = Query(default=None)):
    """Return available campus shuttle and transit lines for the given campus."""
    cfg = load_config(campus_id=campus_id)
    cid = cfg.campus.id
    raw_routes = load_transit_routes(campus_id=cid)
    result = []
    for r in raw_routes:
        stops = [TransitStop(**s) for s in r.get("stops", [])]
        result.append(
            TransitRouteResponse(
                id=r["id"],
                name=r["name"],
                type=r.get("type", "shuttle"),
                vehicle_type=r.get("vehicle_type", "Electric Shuttle"),
                color=r.get("color", "#10b981"),
                operating_hours=r.get("operating_hours", "08:00–18:00"),
                headway_minutes=r.get("headway_minutes", 15),
                speed_kmh=r.get("speed_kmh", 18.0),
                cost=r.get("cost", 0.0),
                currency=r.get("currency", "₹" if cid == "vsb_karur" else "$"),
                stops=stops,
            )
        )
    return result


# --- Rider View Trip Options ---
@router.post("/trip/options", response_model=TripOptionsResponse)
def get_trip_options(req: TripOptionRequest):
    """
    Rider-facing multi-modal routing engine.
    Calculates exact walking, bicycle, e-scooter, and fixed transit (shuttle / golf cart) journey options
    with live stand availability, OSMnx path geometry, realistic travel times, fares, and honest comparison tags.
    """
    cfg = load_config(campus_id=req.campus_id)
    cid = cfg.campus.id
    stands = load_stands(campus_id=cid)
    stand_map = {s.id: s for s in stands}
    net = load_or_build_campus_network(campus_id=cid)

    walk_speed_mps = (cfg.simulation.walk_speed_kmh * 1000.0) / 3600.0
    bike_speed_mps = (cfg.simulation.bike_speed_kmh * 1000.0) / 3600.0
    currency = "₹" if cid == "vsb_karur" else "$"
    dep_hour = req.departure_hour or 8
    dep_min = req.departure_minute or 0
    f_size = cfg.fleet.total_bikes

    # 1. Resolve Origin Point and Closest Stand
    if req.origin_stand_id and req.origin_stand_id in stand_map:
        orig_stand = stand_map[req.origin_stand_id]
        orig_lat, orig_lon = orig_stand.latitude, orig_stand.longitude
        orig_name = req.origin_name or orig_stand.name
        user_at_orig_stand = True
    elif req.origin_coords and len(req.origin_coords) == 2:
        orig_lat, orig_lon = req.origin_coords[0], req.origin_coords[1]
        orig_stand = min(stands, key=lambda s: haversine_distance(orig_lat, orig_lon, s.latitude, s.longitude))
        orig_name = req.origin_name or f"Pin ({orig_lat:.4f}, {orig_lon:.4f})"
        user_at_orig_stand = haversine_distance(orig_lat, orig_lon, orig_stand.latitude, orig_stand.longitude) < 25.0
    else:
        orig_stand = stands[0]
        orig_lat, orig_lon = orig_stand.latitude, orig_stand.longitude
        orig_name = orig_stand.name
        user_at_orig_stand = True

    # 2. Resolve Destination Point and Closest Stand
    if req.dest_stand_id and req.dest_stand_id in stand_map:
        dest_stand = stand_map[req.dest_stand_id]
        dest_lat, dest_lon = dest_stand.latitude, dest_stand.longitude
        dest_name = req.dest_name or dest_stand.name
        dest_is_stand = True
    elif req.dest_coords and len(req.dest_coords) == 2:
        dest_lat, dest_lon = req.dest_coords[0], req.dest_coords[1]
        dest_stand = min(stands, key=lambda s: haversine_distance(dest_lat, dest_lon, s.latitude, s.longitude))
        dest_name = req.dest_name or f"Pin ({dest_lat:.4f}, {dest_lon:.4f})"
        dest_is_stand = haversine_distance(dest_lat, dest_lon, dest_stand.latitude, dest_stand.longitude) < 25.0
    else:
        dest_stand = stands[1] if len(stands) > 1 else stands[0]
        dest_lat, dest_lon = dest_stand.latitude, dest_stand.longitude
        dest_name = dest_stand.name
        dest_is_stand = True

    # Reject identical origin and destination
    if orig_stand.id == dest_stand.id and user_at_orig_stand and dest_is_stand:
        raise HTTPException(
            status_code=400,
            detail="Origin and destination stands cannot be identical. Please select different stands to plan a journey.",
        )
    if req.origin_stand_id and req.dest_stand_id and req.origin_stand_id == req.dest_stand_id:
        raise HTTPException(
            status_code=400,
            detail="Origin and destination stands cannot be identical. Please select different stands to plan a journey.",
        )

    # 3. Live Inventory for Origin and Dest Stands matching simulator state at departure time
    hourly_inv = get_simulator_hourly_inventory(campus_id=cid)
    clamped_hour = max(7, min(22, dep_hour))
    orig_bikes = hourly_inv.get(orig_stand.id, {}).get(
        clamped_hour, max(0, min(orig_stand.dock_capacity, int(round(orig_stand.origin_weight * f_size))))
    )
    dest_bikes = hourly_inv.get(dest_stand.id, {}).get(
        clamped_hour, max(0, min(dest_stand.dock_capacity, int(round(dest_stand.destination_weight * f_size))))
    )
    dest_free_docks = max(0, dest_stand.dock_capacity - dest_bikes)


    # 4. Mode 1: Walking
    direct_dist_m = haversine_distance(orig_lat, orig_lon, dest_lat, dest_lon)
    walk_path_dist_m = round(direct_dist_m * 1.25, 1)
    walk_duration_min = round(walk_path_dist_m / walk_speed_mps / 60.0, 1)
    walk_geom = generate_path_waypoints(orig_lat, orig_lon, dest_lat, dest_lon, num_waypoints=5)

    walk_option = TripOption(
        id="walk",
        mode_name="Walking",
        mode_icon="Footprints",
        total_duration_min=walk_duration_min,
        transit_duration_min=walk_duration_min,
        walk_duration_min=walk_duration_min,
        wait_duration_min=0.0,
        distance_m=walk_path_dist_m,
        cost=0.0,
        cost_currency=currency,
        is_available=True,
        availability_status="HIGH",
        availability_detail="Always 100% available with zero waiting time",
        tags=["Cheapest", "Zero Wait"],
        recommendation_reason=None,
        fallback_message=None,
        legs=[
            TripLeg(
                mode="walk",
                from_name=orig_name,
                to_name=dest_name,
                distance_m=walk_path_dist_m,
                duration_min=walk_duration_min,
                geometry=walk_geom,
            )
        ],
        full_geometry=walk_geom,
    )

    # 5. Mode 2: Docked Bicycle
    legs: List[TripLeg] = []
    full_geom: List[List[float]] = []

    # Leg A: Walk to origin stand (if not already at stand)
    walk_to_stand_dist = haversine_distance(orig_lat, orig_lon, orig_stand.latitude, orig_stand.longitude)
    walk_to_stand_min = round(walk_to_stand_dist / walk_speed_mps / 60.0, 1) if not user_at_orig_stand else 0.0
    if not user_at_orig_stand and walk_to_stand_dist > 15.0:
        leg_a_geom = [[orig_lat, orig_lon], [orig_stand.latitude, orig_stand.longitude]]
        legs.append(TripLeg(
            mode="walk",
            from_name=orig_name,
            to_name=orig_stand.name,
            distance_m=round(walk_to_stand_dist, 1),
            duration_min=walk_to_stand_min,
            geometry=leg_a_geom,
        ))
        full_geom.extend(leg_a_geom)

    # Leg B: Bike ride between stands
    bike_dist_m = net.get_distance(orig_stand.id, dest_stand.id)
    bike_duration_min = round(net.get_travel_time(orig_stand.id, dest_stand.id) / 60.0, 1)
    bike_geom = net.get_route_geometry(orig_stand.id, dest_stand.id)
    legs.append(TripLeg(
        mode="bike",
        from_name=orig_stand.name,
        to_name=dest_stand.name,
        distance_m=round(bike_dist_m, 1),
        duration_min=bike_duration_min,
        geometry=bike_geom,
    ))
    full_geom.extend(bike_geom)

    # Leg C: Walk from destination stand to final pin (if not stand)
    walk_from_stand_dist = haversine_distance(dest_stand.latitude, dest_stand.longitude, dest_lat, dest_lon)
    walk_from_stand_min = round(walk_from_stand_dist / walk_speed_mps / 60.0, 1) if not dest_is_stand else 0.0
    if not dest_is_stand and walk_from_stand_dist > 15.0:
        leg_c_geom = [[dest_stand.latitude, dest_stand.longitude], [dest_lat, dest_lon]]
        legs.append(TripLeg(
            mode="walk",
            from_name=dest_stand.name,
            to_name=dest_name,
            distance_m=round(walk_from_stand_dist, 1),
            duration_min=walk_from_stand_min,
            geometry=leg_c_geom,
        ))
        full_geom.extend(leg_c_geom)

    bike_is_avail = orig_bikes > 0
    if orig_bikes > 3:
        bike_avail_status = "HIGH"
        bike_avail_detail = f"{orig_bikes} bikes at {orig_stand.name} • {dest_free_docks} docks free at {dest_stand.name}"
        bike_fallback = None
    elif orig_bikes in [1, 2, 3]:
        bike_avail_status = "LOW"
        bike_avail_detail = f"Low stock: only {orig_bikes} bike(s) remaining at {orig_stand.name}"
        bike_fallback = None
    else:
        bike_avail_status = "UNAVAILABLE"
        bike_avail_detail = f"Stand empty: 0 bikes available at {orig_stand.name}"
        bike_fallback = f"No bikes available at {orig_stand.name}. Walking is recommended or wait for van rebalancing."

    unlock_min = 0.5
    wait_min = 0.0 if bike_is_avail else 5.0
    dock_min = 0.5
    total_bike_dist = round(walk_to_stand_dist + bike_dist_m + walk_from_stand_dist, 1)
    total_bike_duration = round(walk_to_stand_min + unlock_min + wait_min + bike_duration_min + dock_min + walk_from_stand_min, 1)
    bike_fare = 0.0  # Included with student ID pass
    bike_tags: List[str] = []

    bike_option = TripOption(
        id="bike",
        mode_name="Campus Bicycle",
        mode_icon="Bike",
        total_duration_min=total_bike_duration,
        transit_duration_min=bike_duration_min,
        walk_duration_min=round(walk_to_stand_min + walk_from_stand_min, 1),
        wait_duration_min=wait_min,
        distance_m=total_bike_dist,
        cost=bike_fare,
        cost_currency=currency,
        is_available=bike_is_avail,
        availability_status=bike_avail_status,
        availability_detail=bike_avail_detail,
        tags=bike_tags,

        recommendation_reason=None,
        fallback_message=bike_fallback,
        origin_stand_id=orig_stand.id,
        dest_stand_id=dest_stand.id,
        legs=legs,
        full_geometry=full_geom if full_geom else bike_geom,
    )

    # 6. Mode 3: Campus E-Scooter
    scooter_stands = {"VSB-01", "VSB-02", "VSB-04", "VSB-06"} if cid == "vsb_karur" else {"ST-01", "ST-02", "ST-04", "ST-06"}
    scooter_at_orig = orig_stand.id in scooter_stands
    scooter_at_dest = dest_stand.id in scooter_stands
    scooter_speed_mps = (16.0 * 1000.0) / 3600.0
    scooter_dist_m = round(direct_dist_m * 1.15, 1)
    scooter_ride_min = round(scooter_dist_m / scooter_speed_mps / 60.0, 1)
    scooter_unlock_min = 0.5
    scooter_avail = scooter_at_orig and scooter_at_dest and (8 <= dep_hour <= 20)
    scooter_wait_min = 0.0 if scooter_avail else 3.0
    scooter_total_min = round(walk_to_stand_min + scooter_unlock_min + scooter_wait_min + scooter_ride_min + walk_from_stand_min, 1)
    scooter_fare = 5.0 if cid == "vsb_karur" else 2.0

    scooter_tags = ["Nimble"]

    scooter_option = TripOption(
        id="scooter",
        mode_name="Campus E-Scooter",
        mode_icon="Zap",
        total_duration_min=scooter_total_min,
        transit_duration_min=scooter_ride_min,
        walk_duration_min=round(walk_to_stand_min + walk_from_stand_min, 1),
        wait_duration_min=scooter_wait_min,
        distance_m=scooter_dist_m,
        cost=scooter_fare,

        cost_currency=currency,
        is_available=scooter_avail,
        availability_status="HIGH" if scooter_avail else "UNAVAILABLE",
        availability_detail=f"Docked at designated scooter hubs ({', '.join(sorted(scooter_stands))})" if scooter_avail else "Not deployed at this stand",
        tags=scooter_tags,
        recommendation_reason=None,
        fallback_message="E-scooters are deployed at Main Entrance, Admin, Library & Hostel." if not scooter_avail else None,
        origin_stand_id=orig_stand.id,
        dest_stand_id=dest_stand.id,
        legs=[
            TripLeg(
                mode="scooter",
                from_name=orig_stand.name,
                to_name=dest_stand.name,
                distance_m=scooter_dist_m,
                duration_min=scooter_ride_min,
                geometry=bike_geom or walk_geom,
            )
        ],
        full_geometry=bike_geom or walk_geom,
    )

    # 7. Mode 4+: Fixed Campus Transit (EV Shuttle & Golf Cart)
    transit_options: List[TripOption] = []
    raw_transit = load_transit_routes(campus_id=cid)

    for r in raw_transit:
        stops = r.get("stops", [])
        if len(stops) < 2:
            continue

        board_candidates = [
            (idx, s, haversine_distance(orig_lat, orig_lon, s["latitude"], s["longitude"]))
            for idx, s in enumerate(stops)
        ]
        alight_candidates = [
            (idx, s, haversine_distance(dest_lat, dest_lon, s["latitude"], s["longitude"]))
            for idx, s in enumerate(stops)
        ]

        best_board = min(board_candidates, key=lambda x: x[2])
        best_alight = min(alight_candidates, key=lambda x: x[2])

        # Transit is viable if origin and destination are reasonably close to stops (<= 200m) and distinct
        if best_board[2] <= 200.0 and best_alight[2] <= 200.0 and best_board[1]["stand_id"] != best_alight[1]["stand_id"]:
            b_idx = best_board[0]
            a_idx = best_alight[0]

            if a_idx > b_idx:
                path_stops = stops[b_idx:a_idx + 1]
            else:
                path_stops = stops[b_idx:] + stops[1:a_idx + 1]

            transit_dist = 0.0
            for i in range(len(path_stops) - 1):
                transit_dist += haversine_distance(
                    path_stops[i]["latitude"], path_stops[i]["longitude"],
                    path_stops[i + 1]["latitude"], path_stops[i + 1]["longitude"],
                )

            transit_speed_mps = (r.get("speed_kmh", 18.0) * 1000.0) / 3600.0
            dwell_time_min = (len(path_stops) - 2) * 0.35 if len(path_stops) > 2 else 0.0
            transit_ride_min = round((transit_dist / transit_speed_mps / 60.0) + dwell_time_min, 1)

            headway = r.get("headway_minutes", 15)
            wait_min = float((headway - (dep_min % headway)) % headway)
            if wait_min == 0.0:
                wait_min = 1.0

            walk_to_board_min = round(best_board[2] / walk_speed_mps / 60.0, 1)
            walk_from_alight_min = round(best_alight[2] / walk_speed_mps / 60.0, 1)
            transit_total_min = round(walk_to_board_min + wait_min + transit_ride_min + walk_from_alight_min, 1)

            transit_geom = [[s["latitude"], s["longitude"]] for s in path_stops]
            in_service = 8 <= dep_hour <= 18

            shuttle_tags = ["Free Transit", "Passes Your Route"]
            if transit_total_min <= walk_duration_min:
                shuttle_tags.append("Zero Effort")

            transit_options.append(
                TripOption(
                    id=r["id"],
                    mode_name=r["name"],
                    mode_icon="Bus" if r.get("type") == "shuttle" else "Car",
                    total_duration_min=transit_total_min,
                    transit_duration_min=transit_ride_min,
                    walk_duration_min=round(walk_to_board_min + walk_from_alight_min, 1),
                    wait_duration_min=wait_min if in_service else 0.0,
                    distance_m=round(transit_dist + best_board[2] + best_alight[2], 1),
                    cost=float(r.get("cost", 0.0)),
                    cost_currency=currency,
                    is_available=in_service,
                    availability_status="HIGH" if in_service else "UNAVAILABLE",
                    availability_detail=f"Next departure in ~{int(wait_min)} min • Every {headway}m ({r.get('operating_hours', '08:00–18:00')})" if in_service else "Out of operating service hours",
                    tags=shuttle_tags,
                    recommendation_reason=None,
                    fallback_message=f"{r['name']} runs between {r.get('operating_hours', '08:00–18:00')}." if not in_service else None,
                    origin_stand_id=best_board[1]["stand_id"],
                    dest_stand_id=best_alight[1]["stand_id"],
                    legs=[
                        TripLeg(
                            mode="walk",
                            from_name=orig_name,
                            to_name=best_board[1]["name"],
                            distance_m=round(best_board[2], 1),
                            duration_min=walk_to_board_min,
                            geometry=[[orig_lat, orig_lon], [best_board[1]["latitude"], best_board[1]["longitude"]]],
                        ),
                        TripLeg(
                            mode=r.get("type", "shuttle"),
                            from_name=best_board[1]["name"],
                            to_name=best_alight[1]["name"],
                            distance_m=round(transit_dist, 1),
                            duration_min=transit_ride_min,
                            geometry=transit_geom,
                        ),
                        TripLeg(
                            mode="walk",
                            from_name=best_alight[1]["name"],
                            to_name=dest_name,
                            distance_m=round(best_alight[2], 1),
                            duration_min=walk_from_alight_min,
                            geometry=[[best_alight[1]["latitude"], best_alight[1]["longitude"]], [dest_lat, dest_lon]],
                        ),
                    ],
                    full_geometry=transit_geom,
                )
            )

    # 8. Intelligent Multi-Modal Recommendation
    # Determine the single best option
    fastest_transit = min([t for t in transit_options if t.is_available], key=lambda t: t.total_duration_min, default=None)

    if bike_is_avail and (walk_duration_min - total_bike_duration) >= 1.5:
        recommended_id = "bike"
        time_saved = round(walk_duration_min - total_bike_duration, 1)
        bike_option.tags.append("Recommended")
        bike_option.recommendation_reason = f"Bicycle saves {time_saved} min over walking ({orig_bikes} bikes ready at stand)."
    elif fastest_transit and fastest_transit.total_duration_min <= walk_duration_min:
        recommended_id = fastest_transit.id
        fastest_transit.tags.append("Recommended")
        fastest_transit.recommendation_reason = f"Passes directly by your route; arrives in {fastest_transit.total_duration_min} min with zero effort."
    elif not bike_is_avail:
        recommended_id = "walk"
        walk_option.tags.append("Recommended")
        walk_option.recommendation_reason = f"Walking is recommended because {orig_stand.name} currently has 0 bikes."
    else:
        recommended_id = "walk"
        walk_option.tags.append("Recommended")
        walk_option.recommendation_reason = "Short trip distance; direct walking avoids unlock/docking overhead."

    all_options = [bike_option, walk_option, scooter_option] + transit_options

    # Enforce tag rule: ONLY ONE option gets each tag (Fastest, Cheapest)
    for opt in all_options:
        opt.tags = [t for t in opt.tags if t not in ["Fastest", "Cheapest"]]

    # 1. Fastest: exactly one available option
    available_opts = [o for o in all_options if o.is_available]
    if available_opts:
        fastest_opt = min(available_opts, key=lambda o: o.total_duration_min)
        if "Fastest" not in fastest_opt.tags:
            fastest_opt.tags.append("Fastest")

    # 2. Cheapest: exactly one option (breaking ties by lowest total duration)
    cheapest_opt = min(all_options, key=lambda o: (o.cost, o.total_duration_min))
    if "Cheapest" not in cheapest_opt.tags:
        cheapest_opt.tags.append("Cheapest")

    all_options.sort(key=lambda o: (0 if o.id == recommended_id else 1, 0 if o.is_available else 1, o.total_duration_min))

    return TripOptionsResponse(
        campus_id=cid,
        campus_name=cfg.campus.name,
        departure_time=f"{dep_hour:02d}:{dep_min:02d}",
        origin_name=orig_name,
        dest_name=dest_name,
        options=all_options,
        recommended_option_id=recommended_id,
    )

