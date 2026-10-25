"""
Unit tests for Module 3: SimPy Discrete-Event Simulation Engine.
"""
import pytest
from backend.config import load_stands
from backend.data.synthetic_generator import SyntheticTrip
from backend.data.campus_graph import build_geodesic_fallback_network
from backend.simulator.entities import RebalancingMove
from backend.simulator.engine import CampusSimulator


@pytest.fixture
def test_network():
    stands = load_stands()
    return build_geodesic_fallback_network(stands, bike_speed_kmh=12.0)


def test_empty_stand_stockouts(test_network):
    """Verify that riders arriving at a 0-bike stand encounter stockouts and balk."""
    stands = load_stands()
    # Allocate 0 bikes to ST-01, 20 bikes to others
    alloc = {s.id: (0 if s.id == "ST-01" else 20) for s in stands}

    trips = [
        SyntheticTrip(
            request_time_sec=25200 + i * 60,
            origin_stand_id="ST-01",
            dest_stand_id="ST-05",
            user_type="student",
            max_wait_minutes=1.0,
            is_synthetic=True
        )
        for i in range(5)
    ]

    sim = CampusSimulator(stands=stands, campus_network=test_network, random_seed=42)
    results = sim.run(trips, alloc)

    assert results.total_trips_requested == 5
    assert results.total_balked_stockouts == 5
    assert results.unmet_demand_pct == 100.0
    assert results.stand_metrics["ST-01"]["stockouts"] == 5


def test_full_stand_overflow_diversion(test_network):
    """Verify that riders returning to a full stand are diverted to an alternative."""
    stands = load_stands()
    # Make ST-05 completely full (30 bikes out of 30 capacity)
    # ST-01 has 1 bike, other stands have empty docks
    alloc = {
        "ST-01": 1,
        "ST-02": 5,
        "ST-03": 5,
        "ST-04": 5,
        "ST-05": 30,  # Full
        "ST-06": 5,
        "ST-07": 5
    }

    # Trip heading into full ST-05
    trip = SyntheticTrip(
        request_time_sec=25250,
        origin_stand_id="ST-01",
        dest_stand_id="ST-05",
        user_type="student",
        max_wait_minutes=5.0,
        is_synthetic=True
    )

    sim = CampusSimulator(stands=stands, campus_network=test_network, random_seed=42)
    results = sim.run([trip], alloc)

    assert results.total_trips_completed == 1
    assert results.total_diverted_overflows == 1
    assert results.stand_metrics["ST-05"]["overflows"] == 1
    # Check that trip docked at a stand other than ST-05
    log = results.trip_logs[0]
    assert log.status == "diverted_overflow"
    assert log.actual_dest_id != "ST-05"


def test_rebalancing_move_injection(test_network):
    """Verify that scheduled rebalancing van moves inject bikes into deficit stands."""
    stands = load_stands()
    # ST-01 starts with 0 bikes, ST-05 has 25 bikes
    alloc = {s.id: (0 if s.id == "ST-01" else 15) for s in stands}

    # At 25200 (07:00), ST-01 is empty. At 25300 (07:01:40), van delivers 5 bikes to ST-01.
    moves = [
        RebalancingMove(time_sec=25300, stand_id="ST-01", action="dropoff", count=5)
    ]

    # Trip arrives at 25400 (after rebalancing delivery)
    trip = SyntheticTrip(
        request_time_sec=25400,
        origin_stand_id="ST-01",
        dest_stand_id="ST-04",
        user_type="student",
        max_wait_minutes=5.0,
        is_synthetic=True
    )

    sim = CampusSimulator(stands=stands, campus_network=test_network, random_seed=42)
    results = sim.run([trip], alloc, rebalancing_schedule=moves)

    assert results.total_trips_completed == 1
    assert results.total_balked_stockouts == 0
    assert results.trip_logs[0].status == "completed"


def test_baseline_day_simulation_run(test_network):
    """Verify a complete full-day baseline simulation generates all KPI outputs and snapshots."""
    stands = load_stands()
    # Equal baseline allocation (14-15 bikes per stand = 100 bikes)
    equal_alloc = {
        "ST-01": 15, "ST-02": 15, "ST-03": 14,
        "ST-04": 14, "ST-05": 14, "ST-06": 14, "ST-07": 14
    }

    # Generate 50 trips distributed across the day
    trips = []
    for i in range(50):
        t_sec = 25200 + (i * 900)  # Spread across 12.5 hours
        orig = stands[i % 7].id
        dest = stands[(i + 3) % 7].id
        trips.append(SyntheticTrip(
            request_time_sec=t_sec,
            origin_stand_id=orig,
            dest_stand_id=dest,
            user_type="student",
            max_wait_minutes=5.0,
            is_synthetic=True
        ))

    sim = CampusSimulator(stands=stands, campus_network=test_network, random_seed=42)
    results = sim.run(trips, equal_alloc)

    assert results.total_trips_requested == 50
    assert results.total_trips_completed > 0
    assert 0.0 <= results.unmet_demand_pct <= 100.0
    assert results.avg_wait_time_min >= 0.0
    assert 0.0 <= results.fleet_utilization_pct <= 100.0

    # Hourly snapshots
    assert len(results.stand_hourly_inventory) == 7
    for s_id, snaps in results.stand_hourly_inventory.items():
        assert len(snaps) > 0
