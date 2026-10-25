"""
Unit tests for Module 5: Rebalancing Router.
"""
import pytest
from backend.config import load_stands
from backend.data.campus_graph import build_geodesic_fallback_network
from backend.rebalancing.router import RebalancingRouter


@pytest.fixture
def test_network():
    stands = load_stands()
    return build_geodesic_fallback_network(stands, bike_speed_kmh=12.0)


@pytest.fixture
def router(test_network):
    stands = load_stands()
    return RebalancingRouter(stands=stands, campus_network=test_network)


def test_zero_imbalance_idle_route(router):
    """Verify that when stands are already balanced, an idle route is returned."""
    balanced_inv = {s.id: 15 for s in router.stands}
    plan = router.plan_rebalancing(current_inventory=balanced_inv, target_inventory=balanced_inv)

    assert plan.status == "OPTIMAL"
    assert plan.bikes_moved == 0
    assert plan.total_distance_km == 0.0
    assert len(plan.route_steps) == 2
    assert plan.route_steps[0].action == "START"
    assert plan.route_steps[1].action == "END"


def test_capacity_and_time_bounded_rebalancing(router):
    """Verify van route strictly respects Q=15 capacity and 90-minute shift constraints."""
    # Midday scenario: Academic stands have surplus (+12), residential have deficit (-12)
    current_inv = {
        "ST-01": 2,   # Deficit of 12
        "ST-02": 3,   # Deficit of 12
        "ST-03": 10,
        "ST-04": 22,  # Surplus of 12
        "ST-05": 26,  # Surplus of 12
        "ST-06": 15,
        "ST-07": 10
    }
    target_inv = {
        "ST-01": 14,
        "ST-02": 15,
        "ST-03": 10,
        "ST-04": 10,
        "ST-05": 14,
        "ST-06": 15,
        "ST-07": 10
    }

    plan = router.plan_rebalancing(current_inventory=current_inv, target_inventory=target_inv)

    assert plan.status in ["OPTIMAL", "FEASIBLE"]
    assert plan.bikes_moved > 0
    assert plan.total_time_minutes <= 90.0
    assert plan.total_distance_km > 0.0

    # Verify physical van load bounds: 0 <= van_load <= 15 at every step
    for step in plan.route_steps:
        assert 0 <= step.van_load_after <= router.van_capacity, f"Van capacity violated at step {step.stop_order}"
        assert step.arrival_time_min <= step.departure_time_min

    # Final step must be at depot with empty van
    assert plan.route_steps[-1].action == "END"
    assert plan.route_steps[-1].van_load_after == 0


def test_simulation_moves_generation(router):
    """Verify route steps convert into valid, chronologically ordered SimPy moves."""
    current_inv = {"ST-04": 20, "ST-01": 5}
    target_inv = {"ST-04": 10, "ST-01": 15}

    plan = router.plan_rebalancing(current_inventory=current_inv, target_inventory=target_inv)
    moves = plan.to_simulation_moves(window_start_sec=41400.0)

    assert len(moves) >= 2
    # Check that pickups and dropoffs are matched
    pickups = sum(m.count for m in moves if m.action == "pickup")
    dropoffs = sum(m.count for m in moves if m.action == "dropoff")
    assert pickups == dropoffs
    assert pickups > 0

    # Check timestamps: monotonic and starting after 11:30 AM (41400s)
    for m in moves:
        assert m.time_sec >= 41400.0
    times = [m.time_sec for m in moves]
    assert times == sorted(times)


def test_rebalancing_multiple_van_trips(router):
    """Verify van trips when bikes moved exceed van capacity."""
    # Move 30 bikes when van capacity is 15 (requires at least 2 van trips)
    current_inv = {"ST-04": 30, "ST-01": 0}
    target_inv = {"ST-04": 0, "ST-01": 30}

    plan = router.plan_rebalancing(current_inventory=current_inv, target_inventory=target_inv)
    assert plan.bikes_moved > router.van_capacity
    assert plan.van_trips >= 2
    trip_numbers = {step.trip_number for step in plan.route_steps}
    assert len(trip_numbers) >= 2, f"Expected multiple trip numbers, got {trip_numbers}"

