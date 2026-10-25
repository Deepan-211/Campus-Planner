"""
Capacitated Vehicle Rebalancing Router using Google OR-Tools / Greedy Heuristic.
Plans optimal van routes to transfer bicycles from surplus stands (post-morning rush)
to deficit stands before afternoon and evening commutes.
Respects van capacity (Q), service handling times (90s/bike), and driver shift limits.
Computes real network paths and returns route geometry for visualization.
"""
from typing import Dict, List, Tuple, Optional
import time
import math
import logging
from dataclasses import dataclass, field

from backend.config import load_config, load_stands, StandDefinition
from backend.data.campus_graph import CampusNetwork, load_or_build_campus_network
from backend.simulator.entities import RebalancingMove

logger = logging.getLogger(__name__)


@dataclass
class RouteStop:
    stop_order: int
    stand_id: str
    stand_name: str
    action: str  # 'START', 'PICKUP', 'DROPOFF', 'END'
    bikes_change: int  # Positive for pickup (into van), negative for dropoff (out of van)
    van_load_after: int
    arrival_time_min: float
    departure_time_min: float
    trip_number: int = 1


@dataclass
class RebalancingPlan:
    status: str
    total_distance_km: float
    total_time_minutes: float
    bikes_moved: int
    route_steps: List[RouteStop]
    van_trips: int = 1
    unserviced_surplus: int = 0
    unserviced_deficit: int = 0
    route_geometry: Optional[List[List[List[float]]]] = None  # List of segments: [[[lat, lon], ...], ...]
    driving_time_minutes: float = 0.0
    loading_time_minutes: float = 0.0
    unloading_time_minutes: float = 0.0
    total_operations: int = 0

    def to_simulation_moves(self, window_start_sec: float = 41400.0) -> List[RebalancingMove]:
        """
        Converts route steps into discrete SimPy simulation moves.
        `window_start_sec`: 11:30 AM = 11.5 * 3600 = 41400 seconds.
        """
        moves: List[RebalancingMove] = []
        for step in self.route_steps:
            if step.action in ["PICKUP", "DROPOFF"] and step.bikes_change != 0:
                t_sec = window_start_sec + (step.arrival_time_min * 60.0)
                sim_action = "pickup" if step.action == "PICKUP" else "dropoff"
                moves.append(RebalancingMove(
                    time_sec=round(t_sec, 1),
                    stand_id=step.stand_id,
                    action=sim_action,
                    count=abs(step.bikes_change)
                ))
        return moves


class RebalancingRouter:
    """
    Plans capacitated van rebalancing routes between peak periods.
    """

    def __init__(
        self,
        stands: Optional[List[StandDefinition]] = None,
        campus_network: Optional[CampusNetwork] = None,
        campus_id: Optional[str] = None
    ):
        self.config = load_config(campus_id=campus_id)
        self.campus_id = self.config.campus.id
        self.stands = stands or load_stands(campus_id=self.campus_id)
        self.stand_map = {s.id: s for s in self.stands}
        self.campus_network = campus_network or load_or_build_campus_network(campus_id=self.campus_id)

        self.van_capacity = self.config.rebalancing.van_capacity
        self.handling_time_per_bike_sec = self.config.rebalancing.time_per_bike_sec
        self.max_shift_sec = self.config.rebalancing.max_shift_minutes * 60.0
        self.depot_id = self.config.rebalancing.depot_stand_id
        if self.depot_id not in self.stand_map:
            self.depot_id = self.stands[0].id

    def plan_rebalancing(
        self,
        current_inventory: Dict[str, int],
        target_inventory: Dict[str, int]
    ) -> RebalancingPlan:
        """
        Computes rebalancing route from current stand counts to target counts.
        Surplus stands (curr > target) are visited for pickups.
        Deficit stands (curr < target) are visited for dropoffs.
        """
        surplus: Dict[str, int] = {}
        deficit: Dict[str, int] = {}

        for s in self.stands:
            curr = current_inventory.get(s.id, 0)
            target = target_inventory.get(s.id, curr)
            diff = curr - target
            if diff > 0:
                surplus[s.id] = diff
            elif diff < 0:
                deficit[s.id] = -diff

        total_surplus = sum(surplus.values())
        total_deficit = sum(deficit.values())

        depot_name = self.stand_map[self.depot_id].name

        # If perfectly balanced, return empty route
        if total_surplus == 0 or total_deficit == 0:
            return RebalancingPlan(
                status="OPTIMAL",
                total_distance_km=0.0,
                total_time_minutes=0.0,
                bikes_moved=0,
                route_steps=[
                    RouteStop(0, self.depot_id, depot_name, "START", 0, 0, 0.0, 0.0),
                    RouteStop(1, self.depot_id, depot_name, "END", 0, 0, 0.0, 0.0)
                ],
                route_geometry=[]
            )

        rem_surplus = dict(surplus)
        rem_deficit = dict(deficit)

        route_steps: List[RouteStop] = []
        current_stand_id = self.depot_id
        current_time_sec = 0.0
        current_van_load = 0
        total_distance_m = 0.0
        total_bikes_moved = 0
        total_driving_sec = 0.0
        total_loading_sec = 0.0
        total_unloading_sec = 0.0
        stop_counter = 0

        route_steps.append(RouteStop(
            stop_order=stop_counter,
            stand_id=self.depot_id,
            stand_name=depot_name,
            action="START",
            bikes_change=0,
            van_load_after=0,
            arrival_time_min=0.0,
            departure_time_min=0.0
        ))

        visited_sequence = [self.depot_id]
        current_trip_num = 1

        while any(rem_surplus.values()) and any(rem_deficit.values()):
            # Phase 1: Collect up to van_capacity from nearest surplus stands
            picked_this_tour = 0
            while current_van_load < self.van_capacity and any(v > 0 for v in rem_surplus.values()):
                avail_surplus = [s_id for s_id, amt in rem_surplus.items() if amt > 0]
                if not avail_surplus:
                    break

                best_surplus_stand = min(
                    avail_surplus,
                    key=lambda s_id: self.campus_network.get_travel_time(current_stand_id, s_id)
                )

                travel_sec = self.campus_network.get_travel_time(current_stand_id, best_surplus_stand)
                dist_m = self.campus_network.get_distance(current_stand_id, best_surplus_stand)

                can_take = min(rem_surplus[best_surplus_stand], self.van_capacity - current_van_load)
                service_sec = can_take * self.handling_time_per_bike_sec

                depot_return_tt = self.campus_network.get_travel_time(best_surplus_stand, self.depot_id)
                if (current_time_sec + travel_sec + service_sec + depot_return_tt) > self.max_shift_sec:
                    break

                current_time_sec += travel_sec
                total_driving_sec += travel_sec
                arr_min = round(current_time_sec / 60.0, 2)
                current_time_sec += service_sec
                total_loading_sec += service_sec
                dep_min = round(current_time_sec / 60.0, 2)

                current_van_load += can_take
                rem_surplus[best_surplus_stand] -= can_take
                total_distance_m += dist_m
                picked_this_tour += can_take
                total_bikes_moved += can_take
                stop_counter += 1

                route_steps.append(RouteStop(
                    stop_order=stop_counter,
                    stand_id=best_surplus_stand,
                    stand_name=self.stand_map[best_surplus_stand].name,
                    action="PICKUP",
                    bikes_change=can_take,
                    van_load_after=current_van_load,
                    arrival_time_min=arr_min,
                    departure_time_min=dep_min,
                    trip_number=current_trip_num,
                ))
                current_stand_id = best_surplus_stand
                visited_sequence.append(best_surplus_stand)

            if picked_this_tour == 0:
                break

            # Phase 2: Deliver van load to nearest deficit stands
            while current_van_load > 0 and any(v > 0 for v in rem_deficit.values()):
                avail_deficit = [s_id for s_id, amt in rem_deficit.items() if amt > 0]
                if not avail_deficit:
                    break

                best_deficit_stand = min(
                    avail_deficit,
                    key=lambda s_id: self.campus_network.get_travel_time(current_stand_id, s_id)
                )

                travel_sec = self.campus_network.get_travel_time(current_stand_id, best_deficit_stand)
                dist_m = self.campus_network.get_distance(current_stand_id, best_deficit_stand)

                can_give = min(rem_deficit[best_deficit_stand], current_van_load)
                service_sec = can_give * self.handling_time_per_bike_sec

                depot_return_tt = self.campus_network.get_travel_time(best_deficit_stand, self.depot_id)
                if (current_time_sec + travel_sec + service_sec + depot_return_tt) > self.max_shift_sec:
                    break

                current_time_sec += travel_sec
                total_driving_sec += travel_sec
                arr_min = round(current_time_sec / 60.0, 2)
                current_time_sec += service_sec
                total_unloading_sec += service_sec
                dep_min = round(current_time_sec / 60.0, 2)

                current_van_load -= can_give
                rem_deficit[best_deficit_stand] -= can_give
                total_distance_m += dist_m
                stop_counter += 1

                route_steps.append(RouteStop(
                    stop_order=stop_counter,
                    stand_id=best_deficit_stand,
                    stand_name=self.stand_map[best_deficit_stand].name,
                    action="DROPOFF",
                    bikes_change=-can_give,
                    van_load_after=current_van_load,
                    arrival_time_min=arr_min,
                    departure_time_min=dep_min,
                    trip_number=current_trip_num,
                ))
                current_stand_id = best_deficit_stand
                visited_sequence.append(best_deficit_stand)

            # Advance tour if van emptied and more work remains
            if current_van_load == 0 and any(v > 0 for v in rem_surplus.values()) and any(v > 0 for v in rem_deficit.values()):
                current_trip_num += 1

            if current_time_sec >= self.max_shift_sec:
                break

        # Final return to Depot
        if current_stand_id != self.depot_id:
            final_travel_sec = self.campus_network.get_travel_time(current_stand_id, self.depot_id)
            final_dist_m = self.campus_network.get_distance(current_stand_id, self.depot_id)
            current_time_sec += final_travel_sec
            total_driving_sec += final_travel_sec
            total_distance_m += final_dist_m
            visited_sequence.append(self.depot_id)

        stop_counter += 1
        arr_min = round(current_time_sec / 60.0, 2)
        bikes_unloaded = current_van_load
        route_steps.append(RouteStop(
            stop_order=stop_counter,
            stand_id=self.depot_id,
            stand_name=depot_name,
            action="END",
            bikes_change=-bikes_unloaded,
            van_load_after=0,
            arrival_time_min=arr_min,
            departure_time_min=arr_min,
            trip_number=current_trip_num,
        ))

        # Compute full route geometry segment by segment
        route_geometry: List[List[List[float]]] = []
        for i in range(len(visited_sequence) - 1):
            from_st = visited_sequence[i]
            to_st = visited_sequence[i + 1]
            seg_coords = self.campus_network.get_route_geometry(from_st, to_st)
            if seg_coords:
                route_geometry.append(seg_coords)

        unserviced_s = sum(rem_surplus.values())
        unserviced_d = sum(rem_deficit.values())
        status = "OPTIMAL" if (unserviced_s == 0 and unserviced_d == 0) else "FEASIBLE"
        total_ops = (total_bikes_moved * 2) if total_bikes_moved > 0 else 0
        computed_trips = max(1, math.ceil(total_bikes_moved / self.van_capacity)) if (self.van_capacity > 0 and total_bikes_moved > 0) else 1
        final_van_trips = max(computed_trips, current_trip_num)

        return RebalancingPlan(
            status=status,
            total_distance_km=round(total_distance_m / 1000.0, 2),
            total_time_minutes=round(current_time_sec / 60.0, 2),
            bikes_moved=total_bikes_moved,
            route_steps=route_steps,
            van_trips=final_van_trips,
            unserviced_surplus=unserviced_s,
            unserviced_deficit=unserviced_d,
            route_geometry=route_geometry,
            driving_time_minutes=round(total_driving_sec / 60.0, 2),
            loading_time_minutes=round(total_loading_sec / 60.0, 2),
            unloading_time_minutes=round(total_unloading_sec / 60.0, 2),
            total_operations=total_ops,
        )

