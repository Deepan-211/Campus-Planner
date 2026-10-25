"""
Mixed-Integer Linear Programming (MILP) Fleet Allocation Optimizer using Google OR-Tools.
Determines optimal initial bike distributions at 07:00 AM across all stands
to minimize expected stockouts and overflows during the morning peak (08:00 to 10:00 AM).
"""
from typing import Dict, List, Optional
import time
import logging
from dataclasses import dataclass
from ortools.linear_solver import pywraplp

from backend.config import load_config, load_stands, StandDefinition

logger = logging.getLogger(__name__)


@dataclass
class AllocationResult:
    fleet_size: int
    baseline_allocation: Dict[str, int]
    optimized_allocation: Dict[str, int]
    baseline_cost: float
    optimized_cost: float
    cost_improvement_pct: float
    solver_status: str
    solve_time_ms: float


class FleetAllocationOptimizer:
    """
    MILP optimizer for morning fleet distribution using Google OR-Tools.
    """

    def __init__(self, stands: Optional[List[StandDefinition]] = None, campus_id: Optional[str] = None):
        self.config = load_config(campus_id=campus_id)
        self.stands = stands or load_stands(campus_id=campus_id)
        self.stand_map = {s.id: s for s in self.stands}
        self.total_capacity = sum(s.dock_capacity for s in self.stands)

    def compute_baseline_allocation(self, fleet_size: int) -> Dict[str, int]:
        """
        Baseline policy: Uniform distribution across all stands.
        Remainder distributed to stands with largest dock capacity.
        """
        if fleet_size > self.total_capacity:
            raise ValueError(f"Fleet size {fleet_size} exceeds total dock capacity {self.total_capacity}")

        num_stands = len(self.stands)
        base_per_stand = fleet_size // num_stands
        remainder = fleet_size % num_stands

        sorted_stands = sorted(self.stands, key=lambda s: s.dock_capacity, reverse=True)
        alloc: Dict[str, int] = {}

        for idx, s in enumerate(sorted_stands):
            extra = 1 if idx < remainder else 0
            val = min(s.dock_capacity, base_per_stand + extra)
            alloc[s.id] = val

        allocated = sum(alloc.values())
        while allocated < fleet_size:
            for s in sorted_stands:
                if alloc[s.id] < s.dock_capacity and allocated < fleet_size:
                    alloc[s.id] += 1
                    allocated += 1

        return alloc

    def evaluate_cost(
        self,
        allocation: Dict[str, int],
        morning_demand_out: Dict[str, float],
        morning_demand_in: Dict[str, float],
        w_stockout: float = 1.0,
        w_overflow: float = 0.7
    ) -> float:
        """
        Calculates the expected objective cost for a given allocation:
        Cost = sum_k [ w_stock * max(0, D_out - x_k) + w_over * max(0, x_k + D_in - C_k) ]
        """
        cost = 0.0
        for s in self.stands:
            x_k = allocation.get(s.id, 0)
            c_k = s.dock_capacity
            d_out = morning_demand_out.get(s.id, 0.0)
            d_in = morning_demand_in.get(s.id, 0.0)

            stockout_shortfall = max(0.0, d_out - x_k)
            overflow_excess = max(0.0, x_k + d_in - c_k)

            cost += (w_stockout * stockout_shortfall) + (w_overflow * overflow_excess)

        return round(cost, 2)

    def optimize(
        self,
        morning_demand_out: Dict[str, float],
        morning_demand_in: Dict[str, float],
        fleet_size: Optional[int] = None,
        w_stockout: Optional[float] = None,
        w_overflow: Optional[float] = None
    ) -> AllocationResult:
        """
        Solves the MILP fleet allocation problem using Google OR-Tools CBC/SCIP solver.
        `morning_demand_out`: {stand_id: expected_pickups_between_8_and_10}
        `morning_demand_in`: {stand_id: expected_dropoffs_between_8_and_10}
        """
        f_size = fleet_size or self.config.fleet.total_bikes
        w_s = w_stockout if w_stockout is not None else self.config.allocation.weights.stockout_penalty
        w_o = w_overflow if w_overflow is not None else self.config.allocation.weights.overflow_penalty

        if f_size > self.total_capacity:
            raise ValueError(f"Requested fleet size {f_size} exceeds total dock capacity {self.total_capacity}")

        t0 = time.time()

        solver = pywraplp.Solver.CreateSolver("CBC")
        if not solver:
            solver = pywraplp.Solver.CreateSolver("SCIP")

        # Decision variables: x_k (integer bikes at stand k)
        x = {}
        # Slack variables: u_k (stockout shortfall), v_k (overflow excess)
        u = {}
        v = {}

        for s in self.stands:
            x[s.id] = solver.IntVar(0, s.dock_capacity, f"x_{s.id}")
            u[s.id] = solver.NumVar(0.0, solver.infinity(), f"u_{s.id}")
            v[s.id] = solver.NumVar(0.0, solver.infinity(), f"v_{s.id}")

        # Constraint 1: Total fleet size conservation
        solver.Add(solver.Sum([x[s.id] for s in self.stands]) == f_size)

        # Constraints 2 & 3: Linearized absolute shortfall and excess
        for s in self.stands:
            d_out = float(morning_demand_out.get(s.id, 0.0))
            d_in = float(morning_demand_in.get(s.id, 0.0))
            c_k = float(s.dock_capacity)

            # u_k >= D_k^out - x_k
            solver.Add(u[s.id] >= d_out - x[s.id])
            # v_k >= x_k + D_k^in - C_k
            solver.Add(v[s.id] >= x[s.id] + d_in - c_k)

        # Objective function: minimize weighted sum of slacks
        objective = solver.Objective()
        for s in self.stands:
            objective.SetCoefficient(u[s.id], float(w_s))
            objective.SetCoefficient(v[s.id], float(w_o))
        objective.SetMinimization()

        status = solver.Solve()
        solve_duration_ms = round((time.time() - t0) * 1000.0, 2)

        status_str = "OPTIMAL" if status == pywraplp.Solver.OPTIMAL else "FEASIBLE" if status == pywraplp.Solver.FEASIBLE else "INFEASIBLE"

        # Extract optimal allocation
        optimized_alloc: Dict[str, int] = {}
        for s in self.stands:
            val = int(round(x[s.id].solution_value()))
            optimized_alloc[s.id] = val

        # Baseline allocation and cost comparison
        baseline_alloc = self.compute_baseline_allocation(f_size)
        baseline_cost = self.evaluate_cost(baseline_alloc, morning_demand_out, morning_demand_in, w_s, w_o)
        optimized_cost = self.evaluate_cost(optimized_alloc, morning_demand_out, morning_demand_in, w_s, w_o)

        improvement_pct = round(((baseline_cost - optimized_cost) / baseline_cost * 100.0) if baseline_cost > 0 else 0.0, 2)

        return AllocationResult(
            fleet_size=f_size,
            baseline_allocation=baseline_alloc,
            optimized_allocation=optimized_alloc,
            baseline_cost=baseline_cost,
            optimized_cost=optimized_cost,
            cost_improvement_pct=improvement_pct,
            solver_status=status_str,
            solve_time_ms=solve_duration_ms
        )
