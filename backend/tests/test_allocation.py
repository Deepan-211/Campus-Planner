"""
Unit tests for Module 4: Fleet Allocation Optimizer (MILP).
"""
import pytest
from backend.config import load_stands
from backend.allocation.optimizer import FleetAllocationOptimizer


@pytest.fixture
def optimizer():
    stands = load_stands()
    return FleetAllocationOptimizer(stands)


def test_baseline_allocation_properties(optimizer):
    """Verify uniform baseline allocation respects fleet size and dock capacities."""
    alloc = optimizer.compute_baseline_allocation(fleet_size=100)

    assert sum(alloc.values()) == 100
    for s in optimizer.stands:
        assert 0 <= alloc[s.id] <= s.dock_capacity


def test_milp_optimization_feasibility(optimizer):
    """Verify MILP optimizer produces an optimal, capacity-bounded integer distribution."""
    # Morning rush scenario: High pickups from residential (ST-01, ST-02, ST-03), high dropoffs at academic (ST-04, ST-05)
    d_out = {
        "ST-01": 25.0,
        "ST-02": 24.0,
        "ST-03": 18.0,
        "ST-04": 2.0,
        "ST-05": 3.0,
        "ST-06": 4.0,
        "ST-07": 2.0
    }
    d_in = {
        "ST-01": 2.0,
        "ST-02": 1.0,
        "ST-03": 2.0,
        "ST-04": 22.0,
        "ST-05": 28.0,
        "ST-06": 15.0,
        "ST-07": 8.0
    }

    result = optimizer.optimize(morning_demand_out=d_out, morning_demand_in=d_in, fleet_size=100)

    assert result.solver_status in ["OPTIMAL", "Optimal"]
    assert sum(result.optimized_allocation.values()) == 100

    # Every stand must satisfy 0 <= x_k <= C_k
    for s in optimizer.stands:
        bikes = result.optimized_allocation[s.id]
        assert isinstance(bikes, int)
        assert 0 <= bikes <= s.dock_capacity

    # Solve time must be well within SLA (< 200ms)
    assert result.solve_time_ms < 200.0


def test_optimization_beats_baseline(optimizer):
    """Verify that MILP allocation strictly beats uniform baseline under asymmetric demand."""
    d_out = {
        "ST-01": 24.0,
        "ST-02": 24.0,
        "ST-03": 18.0,
        "ST-04": 1.0,
        "ST-05": 2.0,
        "ST-06": 2.0,
        "ST-07": 1.0
    }
    d_in = {
        "ST-01": 1.0,
        "ST-02": 1.0,
        "ST-03": 1.0,
        "ST-04": 20.0,
        "ST-05": 25.0,
        "ST-06": 18.0,
        "ST-07": 7.0
    }

    result = optimizer.optimize(morning_demand_out=d_out, morning_demand_in=d_in, fleet_size=100)

    # Optimized cost must be lower than baseline cost
    assert result.optimized_cost < result.baseline_cost
    assert result.cost_improvement_pct > 15.0, "Expected significant improvement under peak commute tide"

    # Residential stands must receive more bikes in optimized plan than in uniform baseline
    assert result.optimized_allocation["ST-01"] > result.baseline_allocation["ST-01"]
    assert result.optimized_allocation["ST-02"] > result.baseline_allocation["ST-02"]


def test_fleet_overflow_rejection(optimizer):
    """Verify that fleet sizes exceeding total capacity raise ValueError."""
    with pytest.raises(ValueError, match="exceeds total dock capacity"):
        optimizer.compute_baseline_allocation(fleet_size=200)

    with pytest.raises(ValueError, match="exceeds total dock capacity"):
        optimizer.optimize(morning_demand_out={}, morning_demand_in={}, fleet_size=200)
