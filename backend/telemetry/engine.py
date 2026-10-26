"""
Real-time continuous telemetry and physics simulation engine for CampusRide Planner.
Simulates moving rebalancing vans along OR-Tools CVRP routes with GPS interpolation,
realistic dwell times, dock stock levels, and live rider check-out/return events.
"""
import math
import random
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

from backend.config import load_config, load_stands, StandDefinition
from backend.data.campus_graph import load_or_build_campus_network, haversine_distance
from backend.rebalancing.router import RebalancingRouter


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate compass bearing in degrees (0-360) from point 1 to point 2."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    bearing_rad = math.atan2(y, x)
    return round((math.degrees(bearing_rad) + 360.0) % 360.0, 1)


class CampusTelemetryEngine:
    """
    Simulates real-time digital twin state for a campus, advancing time,
    van coordinates, station inventory levels, and discrete rider trips.
    """

    def __init__(self, campus_id: str = "vsb_karur"):
        self.campus_id = campus_id
        self.config = load_config(campus_id=campus_id)
        self.stands = load_stands(campus_id=campus_id)
        self.stand_lookup: Dict[str, StandDefinition] = {s.id: s for s in self.stands}
        self.network = load_or_build_campus_network(campus_id=campus_id)

        # Simulation clock: starts at 08:00:00 (28800 sec from midnight)
        self.sim_second: float = 8.0 * 3600.0
        self.is_paused: bool = False
        self.speed_multiplier: float = 2.0  # default 2x speed for good visual pacing

        # Initialize stand inventories
        f_size = self.config.fleet.total_bikes
        self.inventories: Dict[str, int] = {}
        for s in self.stands:
            # Baseline realistic 08:00 AM distribution
            target = max(1, min(s.dock_capacity, int(s.origin_weight * f_size * 1.1)))
            self.inventories[s.id] = target

        # Plan initial CVRP route for the van
        self._init_rebalancing_plan()

        # Telemetry event log
        self.event_counter: int = 1000
        self.recent_events: List[Dict[str, Any]] = []

    def _init_rebalancing_plan(self):
        """Solve or load CVRP plan and flatten waypoints for continuous path tracking."""
        router = RebalancingRouter(
            stands=self.stands,
            campus_network=self.network,
            campus_id=self.campus_id
        )

        curr = self.inventories.copy()
        f_size = self.config.fleet.total_bikes
        target = {
            s.id: min(s.dock_capacity, max(1, int(s.destination_weight * f_size * 0.95)))
            for s in self.stands
        }

        self.plan = router.plan_rebalancing(curr, target)
        self.route_steps = self.plan.route_steps

        # Flatten geometry segments into a continuous waypoint list
        self.waypoints: List[Tuple[float, float]] = []
        if self.plan.route_geometry:
            for seg in self.plan.route_geometry:
                for pt in seg:
                    if not self.waypoints or self.waypoints[-1] != (pt[0], pt[1]):
                        self.waypoints.append((pt[0], pt[1]))

        # Fallback to straight lines between steps if geometry is empty
        if len(self.waypoints) < 2:
            self.waypoints = [
                (self.stand_lookup[s.stand_id].latitude, self.stand_lookup[s.stand_id].longitude)
                for s in self.route_steps
                if s.stand_id in self.stand_lookup
            ]

        # Calculate cumulative distances along waypoints
        self.cum_dists: List[float] = [0.0]
        for i in range(1, len(self.waypoints)):
            d = haversine_distance(
                self.waypoints[i-1][0], self.waypoints[i-1][1],
                self.waypoints[i][0], self.waypoints[i][1]
            )
            self.cum_dists.append(self.cum_dists[-1] + max(1.0, d))
        self.total_path_distance_m = self.cum_dists[-1] if self.cum_dists else 1000.0

        # Van tracking physics
        self.van_dist_m: float = 0.0
        self.van_speed_kmh: float = 24.0  # 24 km/h cruising speed inside campus
        self.van_load: int = 0
        self.van_capacity: int = self.config.rebalancing.van_capacity or 15
        self.van_status: str = "EN_ROUTE"  # EN_ROUTE or AT_STOP
        self.current_stop_idx: int = 0
        self.dwell_timer_sec: float = 0.0
        self.van_bearing: float = 0.0

    def set_speed(self, multiplier: float):
        """Set simulation speed multiplier (1x, 2x, 5x, 10x)."""
        self.speed_multiplier = max(0.5, min(20.0, multiplier))

    def set_pause(self, paused: bool):
        """Pause or resume the simulation."""
        self.is_paused = paused

    def tick(self, real_delta_sec: float = 1.0) -> Dict[str, Any]:
        """
        Advance state by real_delta_sec * speed_multiplier seconds.
        Returns the updated digital twin telemetry payload.
        """
        if not self.is_paused:
            sim_dt = real_delta_sec * self.speed_multiplier
            self.sim_second += sim_dt

            # 1. Update Van physics and movement
            self._update_van(sim_dt)

            # 2. Simulate random student rides
            self._simulate_rider_activity(sim_dt)

        return self.get_telemetry_snapshot()

    def _update_van(self, sim_dt: float):
        """Advance the rebalancing van along its CVRP waypoints."""
        if not self.waypoints or len(self.waypoints) < 2:
            return

        # Check if currently loading/unloading at a station
        if self.van_status == "AT_STOP":
            self.dwell_timer_sec -= sim_dt
            if self.dwell_timer_sec <= 0:
                # Finished work at current stop, depart toward next
                self.van_status = "EN_ROUTE"
                self.current_stop_idx = (self.current_stop_idx + 1) % max(1, len(self.route_steps))
            return

        # Advance along path
        speed_mps = (self.van_speed_kmh * 1000.0) / 3600.0
        self.van_dist_m += speed_mps * sim_dt

        # Loop path if reached destination
        if self.van_dist_m >= self.total_path_distance_m:
            self.van_dist_m = 0.0
            self.current_stop_idx = 0

        # Check proximity to the target stop
        if self.route_steps and self.current_stop_idx < len(self.route_steps):
            target_step = self.route_steps[self.current_stop_idx]
            target_stand = self.stand_lookup.get(target_step.stand_id)
            if target_stand:
                curr_lat, curr_lon = self._get_interpolated_coords(self.van_dist_m)
                dist_to_stand = haversine_distance(
                    curr_lat, curr_lon, target_stand.latitude, target_stand.longitude
                )

                # Within 18 meters -> arrive at stand
                if dist_to_stand < 20.0 and self.van_status == "EN_ROUTE":
                    self.van_status = "AT_STOP"
                    self.dwell_timer_sec = 25.0  # 25 seconds dwell time

                    # Apply inventory change
                    bikes_delta = target_step.bikes_change
                    if target_step.action == "PICKUP":
                        actual_pickup = min(abs(bikes_delta), self.inventories[target_stand.id])
                        self.inventories[target_stand.id] -= actual_pickup
                        self.van_load = min(self.van_capacity, self.van_load + actual_pickup)
                        self._add_event(
                            event_type="REBALANCE_PICKUP",
                            stand_id=target_stand.id,
                            message=f"🚐 Van #1 picked up {actual_pickup} bikes from {target_stand.name} (Van load: {self.van_load}/{self.van_capacity})"
                        )
                    elif target_step.action in ("DROPOFF", "DELIVER"):
                        actual_drop = min(abs(bikes_delta), self.van_load)
                        actual_drop = min(actual_drop, target_stand.dock_capacity - self.inventories[target_stand.id])
                        self.inventories[target_stand.id] += actual_drop
                        self.van_load = max(0, self.van_load - actual_drop)
                        self._add_event(
                            event_type="REBALANCE_DROPOFF",
                            stand_id=target_stand.id,
                            message=f"🚐 Van #1 dropped off {actual_drop} bikes at {target_stand.name} (Van load: {self.van_load}/{self.van_capacity})"
                        )

    def _get_interpolated_coords(self, dist_m: float) -> Tuple[float, float]:
        """Interpolate current GPS coordinates along waypoints based on cumulative distance."""
        if not self.waypoints:
            return (0.0, 0.0)
        if dist_m <= 0:
            return self.waypoints[0]
        if dist_m >= self.total_path_distance_m:
            return self.waypoints[-1]

        # Find waypoint segment
        idx = 0
        for i in range(1, len(self.cum_dists)):
            if self.cum_dists[i] >= dist_m:
                idx = i - 1
                break

        seg_start_dist = self.cum_dists[idx]
        seg_len = max(0.1, self.cum_dists[idx + 1] - seg_start_dist)
        alpha = max(0.0, min(1.0, (dist_m - seg_start_dist) / seg_len))

        p1 = self.waypoints[idx]
        p2 = self.waypoints[idx + 1]

        lat = p1[0] + alpha * (p2[0] - p1[0])
        lon = p1[1] + alpha * (p2[1] - p1[1])

        # Update bearing
        self.van_bearing = calculate_bearing(p1[0], p1[1], p2[0], p2[1])
        return (round(lat, 6), round(lon, 6))

    def _simulate_rider_activity(self, sim_dt: float):
        """Simulate realistic stochastic bike checkouts and returns from students."""
        # Roughly 1 trip event every 4-8 seconds
        prob = 0.18 * (sim_dt / 1.0)
        if random.random() < prob and self.stands:
            action = random.choice(["CHECKOUT", "RETURN"])
            stand = random.choice(self.stands)
            curr = self.inventories[stand.id]

            if action == "CHECKOUT" and curr > 1:
                self.inventories[stand.id] -= 1
                bike_num = random.randint(10, 99)
                student_id = random.randint(101, 350)
                self._add_event(
                    event_type="RENTAL",
                    stand_id=stand.id,
                    message=f"🚴 Student #{student_id} checked out Bike #{bike_num} from {stand.name}"
                )
            elif action == "RETURN" and curr < stand.dock_capacity:
                self.inventories[stand.id] += 1
                bike_num = random.randint(10, 99)
                student_id = random.randint(101, 350)
                self._add_event(
                    event_type="RETURN",
                    stand_id=stand.id,
                    message=f"🚲 Student #{student_id} returned Bike #{bike_num} to {stand.name}"
                )

    def _add_event(self, event_type: str, stand_id: str, message: str):
        """Record an event in the sliding window log."""
        self.event_counter += 1
        hours = int((self.sim_second // 3600) % 24)
        minutes = int((self.sim_second % 3600) // 60)
        seconds = int(self.sim_second % 60)
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        stand = self.stand_lookup.get(stand_id)
        evt = {
            "id": f"evt-{self.event_counter}",
            "type": event_type,
            "stand_id": stand_id,
            "stand_name": stand.name if stand else stand_id,
            "time": time_str,
            "message": message,
            "bikes_available_after": self.inventories.get(stand_id, 0),
        }
        self.recent_events.insert(0, evt)
        if len(self.recent_events) > 30:
            self.recent_events.pop()

    def get_telemetry_snapshot(self) -> Dict[str, Any]:
        """Compile complete JSON telemetry frame."""
        hours = int((self.sim_second // 3600) % 24)
        minutes = int((self.sim_second % 3600) // 60)
        seconds = int(self.sim_second % 60)
        sim_time_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        curr_lat, curr_lon = self._get_interpolated_coords(self.van_dist_m)

        # Target stop information
        target_stand_id = ""
        target_stand_name = "Base Depot"
        eta_sec = 0
        current_action = "Patrolling Campus Mobility Grid"

        if self.route_steps and self.current_stop_idx < len(self.route_steps):
            step = self.route_steps[self.current_stop_idx]
            target_stand_id = step.stand_id
            target_stand_name = step.stand_name
            current_action = f"{step.action} {abs(step.bikes_change)} bikes at {step.stand_name}"

            # Calculate remaining distance to that stop
            target_stand = self.stand_lookup.get(step.stand_id)
            if target_stand:
                rem_m = haversine_distance(curr_lat, curr_lon, target_stand.latitude, target_stand.longitude)
                speed_mps = max(1.0, (self.van_speed_kmh * 1000.0) / 3600.0)
                eta_sec = int(rem_m / speed_mps)

        # Stand telemetry map
        stand_statuses = []
        for s in self.stands:
            bikes = self.inventories.get(s.id, 0)
            fill_pct = round((bikes / s.dock_capacity) * 100, 1)
            urgency = "BALANCED"
            if fill_pct <= 20:
                urgency = "STARVED"
            elif fill_pct >= 85:
                urgency = "SURPLUS"

            stand_statuses.append({
                "id": s.id,
                "name": s.name,
                "zone": s.zone,
                "bikes": bikes,
                "docks_free": s.dock_capacity - bikes,
                "capacity": s.dock_capacity,
                "fill_pct": fill_pct,
                "status": urgency,
            })

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "campus_id": self.campus_id,
            "sim_time": sim_time_formatted,
            "sim_second": round(self.sim_second, 1),
            "is_paused": self.is_paused,
            "speed_multiplier": self.speed_multiplier,
            "van": {
                "id": "VAN-01",
                "name": "Fleet Dispatch Van #1",
                "status": self.van_status,
                "latitude": curr_lat,
                "longitude": curr_lon,
                "bearing": self.van_bearing,
                "speed_kmh": 0.0 if self.van_status == "AT_STOP" else self.van_speed_kmh,
                "load": self.van_load,
                "capacity": self.van_capacity,
                "target_stand_id": target_stand_id,
                "target_stand_name": target_stand_name,
                "current_action": current_action,
                "eta_seconds": eta_sec,
                "dwell_remaining_sec": round(max(0.0, self.dwell_timer_sec), 1),
            },
            "stands": stand_statuses,
            "live_inventory": self.inventories,
            "recent_events": self.recent_events[:12],
        }


# Global registry of active campus engines
_engines: Dict[str, CampusTelemetryEngine] = {}

def get_telemetry_engine(campus_id: str = "vsb_karur") -> CampusTelemetryEngine:
    """Retrieve or initialize the campus telemetry engine instance."""
    cid = campus_id or "vsb_karur"
    if cid not in _engines:
        _engines[cid] = CampusTelemetryEngine(campus_id=cid)
    return _engines[cid]
