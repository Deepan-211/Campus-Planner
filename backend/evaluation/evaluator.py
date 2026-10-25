"""
Comparative Policy Evaluation Engine for CampusRide Planner.
Runs multi-replication Monte Carlo simulations to statistically compare:
Policy A (Baseline: Uniform initial allocation, zero rebalancing)
vs.
Policy B (Optimized: MILP morning allocation + OR-Tools CVRP midday rebalancing).

Computes sample means, standard deviations, paired Student's t-test p-values,
and two-sided 95% confidence intervals across identical random seeds.
Enforces strict evaluation integrity: the optimizer and forecaster never see
the simulator's hidden true stochastic realizations.
"""
from typing import Dict, List, Tuple, Optional
import math
import logging
from dataclasses import dataclass, asdict
import numpy as np
import scipy.stats as stats

from backend.config import load_config, load_stands, StandDefinition
from backend.data.campus_graph import CampusNetwork, load_or_build_campus_network
from backend.data.synthetic_generator import SyntheticDemandGenerator, SyntheticTrip
from backend.data.weather_fetcher import HourlyWeather
from backend.allocation.optimizer import FleetAllocationOptimizer
from backend.rebalancing.router import RebalancingRouter
from backend.simulator.engine import CampusSimulator, SimulationResults

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceInterval:
    mean: float
    std_dev: float
    ci_lower: float
    ci_upper: float


@dataclass
class MetricComparison:
    name: str
    baseline: ConfidenceInterval
    optimized: ConfidenceInterval
    absolute_improvement: float
    pct_improvement: float
    p_value: float
    is_statistically_significant: bool  # p < 0.05


@dataclass
class EvaluationReport:
    replications: int
    fleet_size: int
    confidence_level: float
    seeds_evaluated: List[int]
    unmet_demand_pct: MetricComparison
    avg_wait_time_min: MetricComparison
    fleet_utilization_pct: MetricComparison
    rides_per_vehicle_per_day: MetricComparison
    peak_hour_utilization_pct: MetricComparison
    baseline_run_metrics: List[dict]
    optimized_run_metrics: List[dict]
    stand_hourly_baseline: Dict[str, Dict[int, float]]
    stand_hourly_optimized: Dict[str, Dict[int, float]]
    unmet_by_stand_hour_baseline: Dict[str, Dict[int, float]]
    unmet_by_stand_hour_optimized: Dict[str, Dict[int, float]]

    def to_dict(self) -> dict:
        return asdict(self)



def compute_confidence_interval(samples: List[float], confidence_level: float = 0.95) -> ConfidenceInterval:
    """
    Computes sample mean, standard deviation, and Student's t confidence interval.
    """
    n = len(samples)
    if n == 0:
        return ConfidenceInterval(0.0, 0.0, 0.0, 0.0)
    if n == 1:
        val = float(samples[0])
        return ConfidenceInterval(val, 0.0, val, val)

    arr = np.array(samples, dtype=float)
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1))
    se = std / math.sqrt(n)

    t_crit = float(stats.t.ppf(1.0 - (1.0 - confidence_level) / 2.0, df=n - 1))
    moe = t_crit * se

    ci_lower = max(0.0, mean - moe)
    ci_upper = mean + moe

    return ConfidenceInterval(
        mean=round(mean, 2),
        std_dev=round(std, 2),
        ci_lower=round(ci_lower, 2),
        ci_upper=round(ci_upper, 2)
    )


class PolicyEvaluator:
    """
    Orchestrates comparative Monte Carlo evaluation across paired random seeds.
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

        self.optimizer = FleetAllocationOptimizer(self.stands, campus_id=self.campus_id)
        self.router = RebalancingRouter(self.stands, self.campus_network, campus_id=self.campus_id)

    def evaluate(
        self,
        replications: Optional[int] = None,
        fleet_size: Optional[int] = None,
        seed_list: Optional[List[int]] = None,
        test_date: str = "2026-10-23"
    ) -> EvaluationReport:
        """
        Runs paired simulation replications for Baseline vs. Optimized policies.
        """
        f_size = fleet_size or self.config.fleet.total_bikes
        reps = replications or self.config.evaluation.replications
        seeds = (seed_list or self.config.evaluation.random_seeds)[:reps]
        conf_level = self.config.evaluation.confidence_interval_level

        # Baseline allocation (uniform)
        baseline_alloc = self.optimizer.compute_baseline_allocation(f_size)

        # Expected morning rush demand: if ST-01 exists (Berkeley), use known empirical counts;
        # otherwise dynamically derive from stand weights and fleet size
        if "ST-01" in self.stand_map:
            expected_morning_out = {
                "ST-01": 24.0, "ST-02": 24.0, "ST-03": 18.0,
                "ST-04": 2.0, "ST-05": 3.0, "ST-06": 3.0, "ST-07": 2.0
            }
            expected_morning_in = {
                "ST-01": 2.0, "ST-02": 1.0, "ST-03": 1.0,
                "ST-04": 22.0, "ST-05": 28.0, "ST-06": 16.0, "ST-07": 8.0
            }
            midday_current = {
                "ST-01": 3, "ST-02": 2, "ST-03": 4,
                "ST-04": 22, "ST-05": 28, "ST-06": 23, "ST-07": 18
            }
            midday_target = {
                "ST-01": 15, "ST-02": 15, "ST-03": 12,
                "ST-04": 12, "ST-05": 16, "ST-06": 16, "ST-07": 14
            }
        else:
            expected_morning_out = {
                s.id: max(1.0, round(s.origin_weight * f_size * 0.8, 1))
                for s in self.stands
            }
            expected_morning_in = {
                s.id: max(1.0, round(s.destination_weight * f_size * 0.8, 1))
                for s in self.stands
            }
            # Midday: reverse flows (bikes accumulated at destination stands)
            midday_current = {
                s.id: min(s.dock_capacity, max(1, int(s.destination_weight * f_size * 1.1)))
                for s in self.stands
            }
            midday_target = {
                s.id: min(s.dock_capacity, max(1, int(s.origin_weight * f_size * 0.9)))
                for s in self.stands
            }

        # Solve morning allocation for Policy B
        opt_alloc_res = self.optimizer.optimize(
            morning_demand_out=expected_morning_out,
            morning_demand_in=expected_morning_in,
            fleet_size=f_size
        )
        optimized_alloc = opt_alloc_res.optimized_allocation

        rebalancing_plan = self.router.plan_rebalancing(midday_current, midday_target)
        rebalancing_moves = rebalancing_plan.to_simulation_moves(window_start_sec=41400.0)

        # Storage for paired runs
        base_unmet: List[float] = []
        base_wait: List[float] = []
        base_util: List[float] = []
        base_rides: List[float] = []
        base_peak: List[float] = []

        opt_unmet: List[float] = []
        opt_wait: List[float] = []
        opt_util: List[float] = []
        opt_rides: List[float] = []
        opt_peak: List[float] = []

        base_run_details: List[dict] = []
        opt_run_details: List[dict] = []

        hourly_base_accum: Dict[str, Dict[int, List[int]]] = {s.id: {h: [] for h in range(7, 23)} for s in self.stands}
        hourly_opt_accum: Dict[str, Dict[int, List[int]]] = {s.id: {h: [] for h in range(7, 23)} for s in self.stands}
        unmet_base_accum: Dict[str, Dict[int, List[int]]] = {s.id: {h: [] for h in range(7, 23)} for s in self.stands}
        unmet_opt_accum: Dict[str, Dict[int, List[int]]] = {s.id: {h: [] for h in range(7, 23)} for s in self.stands}

        # Deterministic dummy weather to keep multi-run simulations fast & offline
        dummy_weather = {
            h: HourlyWeather(hour=h, temp_celsius=17.0, precipitation_mm=0.0, rain_probability_pct=5, is_rain=False)
            for h in range(24)
        }

        for seed in seeds:
            # Generate stochastic trip realization with seed
            gen = SyntheticDemandGenerator(seed=seed, campus_id=self.campus_id)
            trips = gen.generate_day_trips(test_date, weather_override=dummy_weather)

            sim = CampusSimulator(stands=self.stands, campus_network=self.campus_network, random_seed=seed)

            # 1. Run Policy A (Baseline)
            res_base: SimulationResults = sim.run(trips=trips, initial_allocation=baseline_alloc, rebalancing_schedule=None)
            base_unmet.append(res_base.unmet_demand_pct)
            base_wait.append(res_base.avg_wait_time_min)
            base_util.append(res_base.fleet_utilization_pct)
            base_rides.append(res_base.rides_per_vehicle_per_day)
            base_peak.append(res_base.peak_hour_utilization_pct)
            base_run_details.append({
                "seed": seed,
                "unmet_demand_pct": res_base.unmet_demand_pct,
                "avg_wait_time_min": res_base.avg_wait_time_min,
                "fleet_utilization_pct": res_base.fleet_utilization_pct,
                "rides_per_vehicle_per_day": res_base.rides_per_vehicle_per_day,
                "peak_hour_utilization_pct": res_base.peak_hour_utilization_pct,
                "total_stockouts": res_base.total_balked_stockouts,
                "total_overflows": res_base.total_diverted_overflows,
            })

            # 2. Run Policy B (Optimized)
            res_opt: SimulationResults = sim.run(trips=trips, initial_allocation=optimized_alloc, rebalancing_schedule=rebalancing_moves)
            opt_unmet.append(res_opt.unmet_demand_pct)
            opt_wait.append(res_opt.avg_wait_time_min)
            opt_util.append(res_opt.fleet_utilization_pct)
            opt_rides.append(res_opt.rides_per_vehicle_per_day)
            opt_peak.append(res_opt.peak_hour_utilization_pct)
            opt_run_details.append({
                "seed": seed,
                "unmet_demand_pct": res_opt.unmet_demand_pct,
                "avg_wait_time_min": res_opt.avg_wait_time_min,
                "fleet_utilization_pct": res_opt.fleet_utilization_pct,
                "rides_per_vehicle_per_day": res_opt.rides_per_vehicle_per_day,
                "peak_hour_utilization_pct": res_opt.peak_hour_utilization_pct,
                "total_stockouts": res_opt.total_balked_stockouts,
                "total_overflows": res_opt.total_diverted_overflows,
            })

            # Accumulate hourly curves
            for s_id, snaps in res_base.stand_hourly_inventory.items():
                for h, val in snaps.items():
                    if h in hourly_base_accum[s_id]:
                        hourly_base_accum[s_id][h].append(val)

            for s_id, snaps in res_opt.stand_hourly_inventory.items():
                for h, val in snaps.items():
                    if h in hourly_opt_accum[s_id]:
                        hourly_opt_accum[s_id][h].append(val)

            # Accumulate unmet demand curves
            for s_id, snaps in res_base.stand_hourly_unmet.items():
                for h, val in snaps.items():
                    if h in unmet_base_accum[s_id]:
                        unmet_base_accum[s_id][h].append(val)

            for s_id, snaps in res_opt.stand_hourly_unmet.items():
                for h, val in snaps.items():
                    if h in unmet_opt_accum[s_id]:
                        unmet_opt_accum[s_id][h].append(val)

        # Average hourly trajectories
        avg_hourly_base = {
            s_id: {h: round(float(np.mean(vals)), 1) if vals else 0.0 for h, vals in hours.items()}
            for s_id, hours in hourly_base_accum.items()
        }
        avg_hourly_opt = {
            s_id: {h: round(float(np.mean(vals)), 1) if vals else 0.0 for h, vals in hours.items()}
            for s_id, hours in hourly_opt_accum.items()
        }

        # Average unmet demand trajectories by stand and hour
        avg_unmet_base = {
            s_id: {h: round(float(np.mean(vals)), 2) if vals else 0.0 for h, vals in hours.items()}
            for s_id, hours in unmet_base_accum.items()
        }
        avg_unmet_opt = {
            s_id: {h: round(float(np.mean(vals)), 2) if vals else 0.0 for h, vals in hours.items()}
            for s_id, hours in unmet_opt_accum.items()
        }

        # Statistical analysis
        ci_base_unmet = compute_confidence_interval(base_unmet, conf_level)
        ci_opt_unmet = compute_confidence_interval(opt_unmet, conf_level)
        diff_unmet = round(ci_base_unmet.mean - ci_opt_unmet.mean, 2)
        pct_imp_unmet = round((diff_unmet / ci_base_unmet.mean * 100.0) if ci_base_unmet.mean > 0 else 0.0, 2)
        p_val_unmet = float(stats.ttest_rel(base_unmet, opt_unmet).pvalue) if len(seeds) > 1 else 1.0

        ci_base_wait = compute_confidence_interval(base_wait, conf_level)
        ci_opt_wait = compute_confidence_interval(opt_wait, conf_level)
        diff_wait = round(ci_base_wait.mean - ci_opt_wait.mean, 2)
        pct_imp_wait = round((diff_wait / ci_base_wait.mean * 100.0) if ci_base_wait.mean > 0 else 0.0, 2)
        p_val_wait = float(stats.ttest_rel(base_wait, opt_wait).pvalue) if len(seeds) > 1 else 1.0

        ci_base_util = compute_confidence_interval(base_util, conf_level)
        ci_opt_util = compute_confidence_interval(opt_util, conf_level)
        diff_util = round(ci_opt_util.mean - ci_base_util.mean, 2)  # Utilization increase is desirable
        pct_imp_util = round((diff_util / ci_base_util.mean * 100.0) if ci_base_util.mean > 0 else 0.0, 2)
        p_val_util = float(stats.ttest_rel(base_util, opt_util).pvalue) if len(seeds) > 1 else 1.0

        # Rides per vehicle per day
        ci_base_rides = compute_confidence_interval(base_rides, conf_level)
        ci_opt_rides = compute_confidence_interval(opt_rides, conf_level)
        diff_rides = round(ci_opt_rides.mean - ci_base_rides.mean, 2)
        pct_imp_rides = round((diff_rides / ci_base_rides.mean * 100.0) if ci_base_rides.mean > 0 else 0.0, 2)
        p_val_rides = float(stats.ttest_rel(base_rides, opt_rides).pvalue) if len(seeds) > 1 else 1.0

        # Peak-hour utilization
        ci_base_peak = compute_confidence_interval(base_peak, conf_level)
        ci_opt_peak = compute_confidence_interval(opt_peak, conf_level)
        diff_peak = round(ci_opt_peak.mean - ci_base_peak.mean, 2)
        pct_imp_peak = round((diff_peak / ci_base_peak.mean * 100.0) if ci_base_peak.mean > 0 else 0.0, 2)
        p_val_peak = float(stats.ttest_rel(base_peak, opt_peak).pvalue) if len(seeds) > 1 else 1.0

        return EvaluationReport(
            replications=len(seeds),
            fleet_size=f_size,
            confidence_level=conf_level,
            seeds_evaluated=seeds,
            unmet_demand_pct=MetricComparison(
                name="Unmet Demand Rate (%)",
                baseline=ci_base_unmet,
                optimized=ci_opt_unmet,
                absolute_improvement=diff_unmet,
                pct_improvement=pct_imp_unmet,
                p_value=round(p_val_unmet, 5),
                is_statistically_significant=(p_val_unmet < 0.05)
            ),
            avg_wait_time_min=MetricComparison(
                name="Average Wait Time (min)",
                baseline=ci_base_wait,
                optimized=ci_opt_wait,
                absolute_improvement=diff_wait,
                pct_improvement=pct_imp_wait,
                p_value=round(p_val_wait, 5),
                is_statistically_significant=(p_val_wait < 0.05)
            ),
            fleet_utilization_pct=MetricComparison(
                name="Fleet Utilization (%)",
                baseline=ci_base_util,
                optimized=ci_opt_util,
                absolute_improvement=diff_util,
                pct_improvement=pct_imp_util,
                p_value=round(p_val_util, 5),
                is_statistically_significant=(p_val_util < 0.05)
            ),
            rides_per_vehicle_per_day=MetricComparison(
                name="Rides / Vehicle / Day",
                baseline=ci_base_rides,
                optimized=ci_opt_rides,
                absolute_improvement=diff_rides,
                pct_improvement=pct_imp_rides,
                p_value=round(p_val_rides, 5),
                is_statistically_significant=(p_val_rides < 0.05)
            ),
            peak_hour_utilization_pct=MetricComparison(
                name="Peak-Hour Utilization (%)",
                baseline=ci_base_peak,
                optimized=ci_opt_peak,
                absolute_improvement=diff_peak,
                pct_improvement=pct_imp_peak,
                p_value=round(p_val_peak, 5),
                is_statistically_significant=(p_val_peak < 0.05)
            ),
            baseline_run_metrics=base_run_details,
            optimized_run_metrics=opt_run_details,
            stand_hourly_baseline=avg_hourly_base,
            stand_hourly_optimized=avg_hourly_opt,
            unmet_by_stand_hour_baseline=avg_unmet_base,
            unmet_by_stand_hour_optimized=avg_unmet_opt,
        )

