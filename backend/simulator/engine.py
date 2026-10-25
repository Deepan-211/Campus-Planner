"""
Discrete-Event Simulation Engine using SimPy.
Models rider arrivals, bike queueing/balking, network transit with lognormal variation,
dock returns, overflow diversion, and midday operations van rebalancing.
"""
from typing import Dict, List, Optional
import math
import random
import logging
from dataclasses import dataclass, field
import simpy

from backend.config import load_config, load_stands, StandDefinition
from backend.data.campus_graph import CampusNetwork, load_or_build_campus_network
from backend.data.synthetic_generator import SyntheticTrip
from backend.simulator.entities import StandState, RiderTripLog, RebalancingMove

logger = logging.getLogger(__name__)


@dataclass
class SimulationResults:
    total_trips_requested: int
    total_trips_completed: int
    total_balked_stockouts: int
    total_diverted_overflows: int
    unmet_demand_pct: float
    avg_wait_time_min: float
    avg_trip_duration_min: float
    fleet_utilization_pct: float
    rides_per_vehicle_per_day: float
    peak_hour_utilization_pct: float
    stand_hourly_inventory: Dict[str, Dict[int, int]]
    stand_hourly_unmet: Dict[str, Dict[int, int]]
    stand_metrics: Dict[str, dict]
    trip_logs: List[RiderTripLog] = field(default_factory=list)


class CampusSimulator:
    """
    Simulates a full operating day (07:00 to 22:00) of campus micromobility.
    """

    def __init__(
        self,
        stands: Optional[List[StandDefinition]] = None,
        campus_network: Optional[CampusNetwork] = None,
        random_seed: int = 42
    ):
        self.config = load_config()
        self.stands = stands or load_stands()
        self.stand_map = {s.id: s for s in self.stands}
        self.campus_network = campus_network or load_or_build_campus_network()
        self.random_seed = random_seed
        self.rng = random.Random(random_seed)

    def run(
        self,
        trips: List[SyntheticTrip],
        initial_allocation: Dict[str, int],
        rebalancing_schedule: Optional[List[RebalancingMove]] = None
    ) -> SimulationResults:
        """
        Executes the discrete-event simulation.
        `initial_allocation`: {stand_id: starting_bike_count}
        `rebalancing_schedule`: list of planned service van pickup/dropoff actions
        """
        # Start at 07:00 AM (25200 seconds)
        start_time_sec = float(self.config.simulation.operating_hours.start_hour * 3600)
        end_time_sec = float((self.config.simulation.operating_hours.end_hour + 1) * 3600)
        total_fleet = sum(initial_allocation.values())

        env = simpy.Environment(initial_time=start_time_sec)

        # Initialize stands
        stand_states: Dict[str, StandState] = {}
        for s in self.stands:
            init_bikes = initial_allocation.get(s.id, 0)
            stand_states[s.id] = StandState(
                env=env,
                stand_id=s.id,
                name=s.name,
                dock_capacity=s.dock_capacity,
                initial_bikes=init_bikes
            )

        trip_logs: List[RiderTripLog] = []
        active_bikes_samples: List[int] = []

        # 1. Background Monitor Process
        def monitor_process():
            while env.now <= end_time_sec:
                current_hour = int(env.now // 3600)
                # Snapshot stand inventories at the top of the hour
                if env.now % 3600 == 0:
                    for s_id, s_state in stand_states.items():
                        s_state.record_snapshot(current_hour)

                # Track active bikes in transit
                docked_bikes = sum(s.current_bikes for s in stand_states.values())
                in_transit = max(0, total_fleet - docked_bikes)
                active_bikes_samples.append(in_transit)

                # Sample every 5 minutes (300 seconds)
                yield env.timeout(300)

        env.process(monitor_process())

        # 2. Rebalancing Van Process
        if rebalancing_schedule:
            def rebalancing_process():
                # Sort moves chronologically
                sorted_moves = sorted(rebalancing_schedule, key=lambda m: m.time_sec)
                for move in sorted_moves:
                    if move.time_sec > env.now:
                        yield env.timeout(move.time_sec - env.now)

                    target_stand = stand_states.get(move.stand_id)
                    if not target_stand:
                        continue

                    if move.action == "pickup":
                        # Van removes surplus bikes from stand
                        take_qty = min(move.count, target_stand.current_bikes)
                        if take_qty > 0:
                            yield target_stand.bikes.get(take_qty)
                    elif move.action == "dropoff":
                        # Van drops bikes into deficit stand
                        give_qty = min(move.count, target_stand.current_empty_docks)
                        if give_qty > 0:
                            yield target_stand.bikes.put(give_qty)

            env.process(rebalancing_process())

        # 3. Individual Rider Processes
        def rider_process(trip_id: int, trip: SyntheticTrip):
            # Wait until trip request time
            if trip.request_time_sec > env.now:
                yield env.timeout(trip.request_time_sec - env.now)

            orig_stand = stand_states[trip.origin_stand_id]
            dest_stand = stand_states[trip.dest_stand_id]

            max_wait_sec = trip.max_wait_minutes * 60.0
            log = RiderTripLog(
                trip_id=trip_id,
                request_time_sec=trip.request_time_sec,
                origin_id=trip.origin_stand_id,
                dest_id=trip.dest_stand_id,
                actual_dest_id=trip.dest_stand_id
            )

            # Check for stockout at origin
            if orig_stand.current_bikes == 0:
                orig_stand.total_stockouts += 1

            # Request 1 bike from origin stand with timeout
            req = orig_stand.bikes.get(1)
            result = yield req | env.timeout(max_wait_sec)

            if req not in result:
                # Balked: Rider gave up and walked
                req.cancel()
                log.wait_time_sec = max_wait_sec
                log.status = "balked_stockout"
                trip_logs.append(log)
                return

            # Bike successfully checked out
            wait_time = max(0.0, env.now - trip.request_time_sec)
            orig_stand.total_pickups += 1
            log.wait_time_sec = wait_time

            # Calculate network transit duration with lognormal variation
            mean_tt = self.campus_network.get_travel_time(trip.origin_stand_id, trip.dest_stand_id)
            variance = self.config.simulation.trip_duration_variance
            # Sample travel time
            duration = max(30.0, self.rng.lognormvariate(math.log(max(10.0, mean_tt)), variance))
            log.transit_time_sec = round(duration, 1)

            yield env.timeout(duration)

            # Rider arrives at destination stand
            if dest_stand.current_empty_docks > 0:
                # Clean return
                yield dest_stand.bikes.put(1)
                dest_stand.total_dropoffs += 1
                log.status = "completed"
                log.actual_dest_id = dest_stand.id
            else:
                # Overflow: Dest stand is full! Reroute to nearest stand with available dock
                dest_stand.total_overflows += 1
                available_stands = [s for s in stand_states.values() if s.id != dest_stand.id and s.current_empty_docks > 0]

                if available_stands:
                    # Find nearest available stand by network distance
                    best_stand = min(
                        available_stands,
                        key=lambda s: self.campus_network.get_distance(dest_stand.id, s.id)
                    )
                    extra_tt = self.campus_network.get_travel_time(dest_stand.id, best_stand.id)
                    yield env.timeout(extra_tt)
                    yield best_stand.bikes.put(1)
                    best_stand.total_dropoffs += 1
                    log.actual_dest_id = best_stand.id
                    log.wait_time_sec += extra_tt  # Count diversion time as rider friction
                    log.status = "diverted_overflow"
                else:
                    # Rare: Entire campus has zero docks available, forced dock wait
                    yield dest_stand.bikes.put(1)
                    dest_stand.total_dropoffs += 1
                    log.status = "completed"

            trip_logs.append(log)

        # Spawn rider processes
        for t_idx, trip in enumerate(trips):
            env.process(rider_process(t_idx + 1, trip))

        # Run simulation to completion
        env.run(until=end_time_sec)

        # Calculate final KPIs
        total_requested = len(trip_logs)
        balked = sum(1 for t in trip_logs if t.status == "balked_stockout")
        diverted = sum(1 for t in trip_logs if t.status == "diverted_overflow")
        completed = total_requested - balked

        unmet_pct = round((balked / total_requested * 100.0) if total_requested > 0 else 0.0, 2)
        avg_wait = round(float(sum(t.wait_time_sec for t in trip_logs) / total_requested / 60.0) if total_requested > 0 else 0.0, 2)
        completed_trips = [t for t in trip_logs if t.status != "balked_stockout"]
        avg_dur = round(float(sum(t.transit_time_sec for t in completed_trips) / len(completed_trips) / 60.0) if completed_trips else 0.0, 2)

        avg_in_transit = (sum(active_bikes_samples) / len(active_bikes_samples)) if active_bikes_samples else 0.0
        utilization_pct = round((avg_in_transit / total_fleet * 100.0) if total_fleet > 0 else 0.0, 2)
        rides_per_veh = round((completed / total_fleet) if total_fleet > 0 else 0.0, 2)
        peak_in_transit = max(active_bikes_samples) if active_bikes_samples else 0
        peak_hour_util_pct = round((peak_in_transit / total_fleet * 100.0) if total_fleet > 0 else 0.0, 2)

        stand_hourly: Dict[str, Dict[int, int]] = {
            s_id: s.hourly_snapshots for s_id, s in stand_states.items()
        }
        stand_hourly_unmet: Dict[str, Dict[int, int]] = {
            s_id: {h: 0 for h in range(7, 23)} for s_id in stand_states.keys()
        }
        for t in trip_logs:
            if t.status == "balked_stockout":
                h = int(t.request_time_sec // 3600)
                if t.origin_id in stand_hourly_unmet and h in stand_hourly_unmet[t.origin_id]:
                    stand_hourly_unmet[t.origin_id][h] += 1

        stand_metrics = {
            s_id: {
                "dock_capacity": s.dock_capacity,
                "pickups": s.total_pickups,
                "stockouts": s.total_stockouts,
                "dropoffs": s.total_dropoffs,
                "overflows": s.total_overflows,
            }
            for s_id, s in stand_states.items()
        }

        return SimulationResults(
            total_trips_requested=total_requested,
            total_trips_completed=completed,
            total_balked_stockouts=balked,
            total_diverted_overflows=diverted,
            unmet_demand_pct=unmet_pct,
            avg_wait_time_min=avg_wait,
            avg_trip_duration_min=avg_dur,
            fleet_utilization_pct=utilization_pct,
            rides_per_vehicle_per_day=rides_per_veh,
            peak_hour_utilization_pct=peak_hour_util_pct,
            stand_hourly_inventory=stand_hourly,
            stand_hourly_unmet=stand_hourly_unmet,
            stand_metrics=stand_metrics,
            trip_logs=trip_logs
        )

