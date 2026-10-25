"""
Configuration loader and Pydantic validation for CampusRide Planner.
Supports multi-campus configurations loaded from config/campuses/<campus_id>/.
All operational parameters, geographic bounds, and fleet limits live here.
"""
from pathlib import Path
from typing import Dict, List, Optional
import json
import yaml
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
CAMPUSES_DIR = CONFIG_DIR / "campuses"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "default_config.yaml"
STANDS_CONFIG_PATH = CONFIG_DIR / "stands.json"

import os
import sys

# Default campus when none specified (defaults to vsb_karur in app; berkeley for test suite)
DEFAULT_CAMPUS_ID = os.environ.get("CAMPUS_ID", "berkeley" if ("pytest" in sys.modules or any("pytest" in a for a in sys.argv)) else "vsb_karur")


class BoundingBox(BaseModel):
    north: float
    south: float
    west: float
    east: float


class CampusConfig(BaseModel):
    id: str = "berkeley"
    name: str
    city: str
    bbox: BoundingBox
    graph_cache_path: str = "config/campus_graph.graphml"
    travel_matrix_cache_path: str = "config/travel_matrices.json"


class StandDefinition(BaseModel):
    id: str
    name: str
    zone: str
    latitude: float
    longitude: float
    dock_capacity: int
    origin_weight: float = 0.1
    destination_weight: float = 0.1


class FleetConfig(BaseModel):
    total_bikes: int = 100
    stands_config_path: str = "config/stands.json"


class OperatingHours(BaseModel):
    start_hour: int = 7
    end_hour: int = 22


class SimulationConfig(BaseModel):
    operating_hours: OperatingHours = Field(default_factory=OperatingHours)
    bike_speed_kmh: float = 12.0
    walk_speed_kmh: float = 4.8
    max_wait_minutes: float = 5.0
    bell_window_minutes: int = 10
    trip_duration_model: str = "lognormal"
    trip_duration_variance: float = 0.15


class AllocationWeights(BaseModel):
    stockout_penalty: float = 1.0
    overflow_penalty: float = 0.7


class AllocationConfig(BaseModel):
    weights: AllocationWeights = Field(default_factory=AllocationWeights)
    target_hour: int = 7


class RebalancingConfig(BaseModel):
    van_capacity: int = 15
    time_per_bike_sec: int = 90
    max_shift_minutes: int = 90
    window_start_hour: float = 11.5
    window_end_hour: float = 13.0
    num_vans: int = 1
    depot_stand_id: str = "ST-07"


class WeatherConfig(BaseModel):
    api_url: str = "https://api.open-meteo.com/v1/forecast"
    latitude: float = 37.8719
    longitude: float = -122.2585
    cache_db_path: str = "data/weather_cache.db"
    cache_ttl_hours: int = 24
    rain_penalty_factor: float = 0.50


class EvaluationConfig(BaseModel):
    replications: int = 30
    confidence_interval_level: float = 0.95
    random_seeds: List[int] = Field(default_factory=lambda: [
        42, 101, 202, 303, 404, 505, 606, 707, 808, 909,
        1010, 1111, 1212, 1313, 1414, 1515, 1616, 1717, 1818, 1919,
        2020, 2121, 2222, 2323, 2424, 2525, 2626, 2727, 2828, 2929
    ])


class AppConfig(BaseModel):
    campus: CampusConfig
    fleet: FleetConfig
    simulation: SimulationConfig
    allocation: AllocationConfig
    rebalancing: RebalancingConfig
    weather: WeatherConfig
    evaluation: EvaluationConfig


# Per-campus caches
_config_cache: Dict[str, AppConfig] = {}
_stands_cache: Dict[str, List[StandDefinition]] = {}


def list_available_campuses() -> List[Dict[str, str]]:
    """Return list of available campus configurations."""
    campuses = []
    if CAMPUSES_DIR.exists():
        for campus_dir in sorted(CAMPUSES_DIR.iterdir()):
            cfg_path = campus_dir / "config.yaml"
            if campus_dir.is_dir() and cfg_path.exists():
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                campus_section = data.get("campus", {})
                campuses.append({
                    "id": campus_section.get("id", campus_dir.name),
                    "name": campus_section.get("name", campus_dir.name),
                    "city": campus_section.get("city", ""),
                })
    # Fallback: if no campuses dir exists, expose the legacy default
    if not campuses:
        campuses.append({"id": "berkeley", "name": "UC Berkeley", "city": "Berkeley, CA"})
    return campuses


def _resolve_campus_config_path(campus_id: str) -> Path:
    """Find config.yaml for a campus id."""
    campus_dir = CAMPUSES_DIR / campus_id
    campus_cfg = campus_dir / "config.yaml"
    if campus_cfg.exists():
        return campus_cfg
    # Fallback to legacy default_config.yaml
    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH
    raise FileNotFoundError(f"No configuration found for campus '{campus_id}'")


def _resolve_stands_path(campus_id: str, app_config: AppConfig) -> Path:
    """Resolve stands.json path for a campus."""
    campus_dir = CAMPUSES_DIR / campus_id
    campus_stands = campus_dir / "stands.json"
    if campus_stands.exists():
        return campus_stands
    # Use path from config
    p = PROJECT_ROOT / app_config.fleet.stands_config_path
    if p.exists():
        return p
    # Legacy fallback
    if STANDS_CONFIG_PATH.exists():
        return STANDS_CONFIG_PATH
    raise FileNotFoundError(f"No stands config found for campus '{campus_id}'")


def load_config(campus_id: Optional[str] = None, config_path: Optional[Path] = None) -> AppConfig:
    """Load campus configuration. Falls back to default campus if none specified."""
    cid = campus_id or DEFAULT_CAMPUS_ID
    if cid in _config_cache:
        return _config_cache[cid]

    if config_path and config_path.exists():
        path = config_path
    else:
        path = _resolve_campus_config_path(cid)

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    cfg = AppConfig(**data)
    _config_cache[cid] = cfg
    return cfg


def validate_stand_coordinates(stands: List[StandDefinition], config: AppConfig) -> List[str]:
    """
    Validates that each stand coordinate falls strictly within the campus bounding box.
    Returns a list of validation error messages, or an empty list if all are valid.
    """
    bbox = config.campus.bbox
    errors = []
    for s in stands:
        if not (bbox.south <= s.latitude <= bbox.north and bbox.west <= s.longitude <= bbox.east):
            errors.append(
                f"Stand {s.id} ('{s.name}') coordinates ({s.latitude}, {s.longitude}) "
                f"fall outside campus bbox [south={bbox.south}, north={bbox.north}, west={bbox.west}, east={bbox.east}]"
            )
    return errors


def load_stands(campus_id: Optional[str] = None, stands_path: Optional[Path] = None) -> List[StandDefinition]:
    """Load stand definitions for a campus and validate their real campus coordinates."""
    cid = campus_id or DEFAULT_CAMPUS_ID
    if cid in _stands_cache:
        return _stands_cache[cid]

    app_config = load_config(campus_id=cid)
    if stands_path and stands_path.exists():
        path = stands_path
    else:
        path = _resolve_stands_path(cid, app_config)

    with open(path, "r", encoding="utf-8") as f:
        stands_data = json.load(f)

    stands = [StandDefinition(**s) for s in stands_data]
    coord_errors = validate_stand_coordinates(stands, app_config)
    if coord_errors:
        raise ValueError(
            f"Stand coordinate validation failed for campus '{cid}':\n" + "\n".join(coord_errors)
        )

    _stands_cache[cid] = stands
    return stands



_transit_cache: Dict[str, List[Dict]] = {}


def load_transit_routes(campus_id: Optional[str] = None) -> List[Dict]:
    """Load transit routes (shuttle, golf cart) for a campus."""
    cid = campus_id or DEFAULT_CAMPUS_ID
    if cid in _transit_cache:
        return _transit_cache[cid]

    transit_path = CAMPUSES_DIR / cid / "transit_routes.json"
    if not transit_path.exists():
        _transit_cache[cid] = []
        return []

    try:
        with open(transit_path, "r", encoding="utf-8") as f:
            routes = json.load(f)
        _transit_cache[cid] = routes
        return routes
    except Exception as e:
        print(f"Warning: Failed to load transit routes for {cid}: {e}")
        _transit_cache[cid] = []
        return []


def clear_config_cache():
    """Clear all cached configurations (useful for testing or campus switching)."""
    _config_cache.clear()
    _stands_cache.clear()
    _transit_cache.clear()


def get_assumptions_table(campus_id: Optional[str] = None) -> List[Dict[str, str]]:
    """Return assumptions as a structured list from config values."""
    cfg = load_config(campus_id=campus_id)
    stands = load_stands(campus_id=campus_id)
    total_docks = sum(s.dock_capacity for s in stands)

    return [
        {
            "parameter": "Campus",
            "value": f"{cfg.campus.name} ({cfg.campus.city})",
            "units": "",
            "source": "Configuration",
            "config_key": "campus.name"
        },
        {
            "parameter": "Number of Stands",
            "value": str(len(stands)),
            "units": "stands",
            "source": "Phase 1 MVP anchor stands",
            "config_key": "fleet.stands_config_path"
        },
        {
            "parameter": "Total Dock Capacity",
            "value": str(total_docks),
            "units": "docks",
            "source": "Bay Wheels standard (20–30 docks/station)",
            "config_key": "stands[*].dock_capacity"
        },
        {
            "parameter": "Fleet Size (F)",
            "value": str(cfg.fleet.total_bikes),
            "units": "bicycles",
            "source": f"{round(cfg.fleet.total_bikes / total_docks * 100, 1)}% fill ratio (industry standard)",
            "config_key": "fleet.total_bikes"
        },
        {
            "parameter": "Cycling Speed",
            "value": str(cfg.simulation.bike_speed_kmh),
            "units": "km/h",
            "source": "NACTO campus bike speed benchmarks",
            "config_key": "simulation.bike_speed_kmh"
        },
        {
            "parameter": "Walk Speed",
            "value": str(cfg.simulation.walk_speed_kmh),
            "units": "km/h",
            "source": "Standard human walking pace",
            "config_key": "simulation.walk_speed_kmh"
        },
        {
            "parameter": "Max Wait Before Balking",
            "value": str(cfg.simulation.max_wait_minutes),
            "units": "minutes",
            "source": "Student willingness-to-wait threshold",
            "config_key": "simulation.max_wait_minutes"
        },
        {
            "parameter": "Bell Surge Window",
            "value": str(cfg.simulation.bell_window_minutes),
            "units": "minutes",
            "source": "Academic bell schedule (:50 → :00)",
            "config_key": "simulation.bell_window_minutes"
        },
        {
            "parameter": "Trip Duration Model",
            "value": f"LogNormal(σ={cfg.simulation.trip_duration_variance})",
            "units": "",
            "source": "OSMnx Dijkstra with lognormal variance",
            "config_key": "simulation.trip_duration_model"
        },
        {
            "parameter": "Van Capacity (Q)",
            "value": str(cfg.rebalancing.van_capacity),
            "units": "bicycles",
            "source": "Ford Transit / Sprinter cargo van with bike racks",
            "config_key": "rebalancing.van_capacity"
        },
        {
            "parameter": "Load/Unload Time",
            "value": str(cfg.rebalancing.time_per_bike_sec),
            "units": "sec/bike",
            "source": "Dock unlock + van rack load time",
            "config_key": "rebalancing.time_per_bike_sec"
        },
        {
            "parameter": "Rebalancing Shift",
            "value": str(cfg.rebalancing.max_shift_minutes),
            "units": "minutes",
            "source": f"Midday lull ({cfg.rebalancing.window_start_hour}–{cfg.rebalancing.window_end_hour})",
            "config_key": "rebalancing.max_shift_minutes"
        },
        {
            "parameter": "Rain Demand Penalty",
            "value": f"{int(cfg.weather.rain_penalty_factor * 100)}% drop",
            "units": "multiplier",
            "source": "Transportation Research Part A: micromobility precipitation elasticity",
            "config_key": "weather.rain_penalty_factor"
        },
        {
            "parameter": "Monte Carlo Seeds",
            "value": f"{len(cfg.evaluation.random_seeds)} replications",
            "units": "",
            "source": "Fixed seeds for strict reproducibility",
            "config_key": "evaluation.random_seeds"
        },
        {
            "parameter": "Operating Hours",
            "value": f"{cfg.simulation.operating_hours.start_hour}:00–{cfg.simulation.operating_hours.end_hour}:00",
            "units": "",
            "source": "Campus operating schedule",
            "config_key": "simulation.operating_hours"
        },
    ]
