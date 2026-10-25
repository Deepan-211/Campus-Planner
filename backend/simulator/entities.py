"""
Entities and Data Structures for SimPy Discrete-Event Simulation.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import simpy


@dataclass
class RebalancingMove:
    time_sec: float
    stand_id: str
    action: str  # 'pickup' (van takes bikes from stand) or 'dropoff' (van puts bikes into stand)
    count: int


@dataclass
class RiderTripLog:
    trip_id: int
    request_time_sec: float
    origin_id: str
    dest_id: str
    actual_dest_id: str
    wait_time_sec: float = 0.0
    transit_time_sec: float = 0.0
    status: str = "completed"  # 'completed', 'balked_stockout', 'diverted_overflow'


class StandState:
    """
    State container for a physical micromobility stand during simulation.
    Uses SimPy Container for atomic bike allocation and return.
    """

    def __init__(self, env: simpy.Environment, stand_id: str, name: str, dock_capacity: int, initial_bikes: int):
        self.env = env
        self.id = stand_id
        self.name = name
        self.dock_capacity = dock_capacity
        # SimPy container bounds: 0 <= bikes <= dock_capacity
        self.bikes = simpy.Container(env, capacity=dock_capacity, init=min(initial_bikes, dock_capacity))

        # Metrics tracking
        self.total_pickups: int = 0
        self.total_stockouts: int = 0
        self.total_dropoffs: int = 0
        self.total_overflows: int = 0
        self.hourly_snapshots: Dict[int, int] = {}

    @property
    def current_bikes(self) -> int:
        return self.bikes.level

    @property
    def current_empty_docks(self) -> int:
        return self.dock_capacity - self.bikes.level

    def record_snapshot(self, hour: int):
        self.hourly_snapshots[hour] = self.bikes.level
