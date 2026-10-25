"""
Unit tests for Module 6: Comparative Evaluation Engine.
"""
import pytest
from backend.config import load_stands
from backend.data.campus_graph import build_geodesic_fallback_network
from backend.evaluation.evaluator import PolicyEvaluator, compute_confidence_interval


def test_confidence_interval_math():
    """Verify Student's t confidence interval bounds are computed accurately."""
    samples = [10.0, 12.0, 11.0, 10.5, 11.5]
    ci = compute_confidence_interval(samples, confidence_level=0.95)

    assert ci.mean == 11.0
    assert ci.std_dev > 0.0
    assert ci.ci_lower < ci.mean < ci.ci_upper
    assert ci.ci_lower >= 0.0


def test_paired_monte_carlo_evaluation():
    """Verify multi-seed paired evaluation produces complete comparative statistical report."""
    stands = load_stands()
    network = build_geodesic_fallback_network(stands, bike_speed_kmh=12.0)
    evaluator = PolicyEvaluator(stands=stands, campus_network=network)

    report = evaluator.evaluate(
        replications=3,
        fleet_size=100,
        seed_list=[42, 101, 202]
    )

    assert report.replications == 3
    assert report.fleet_size == 100
    assert len(report.seeds_evaluated) == 3
    assert len(report.baseline_run_metrics) == 3
    assert len(report.optimized_run_metrics) == 3

    # Check core KPIs including rides per vehicle per day and peak hour utilization
    for metric in [
        report.unmet_demand_pct,
        report.avg_wait_time_min,
        report.fleet_utilization_pct,
        report.rides_per_vehicle_per_day,
        report.peak_hour_utilization_pct,
    ]:
        assert metric.baseline.mean >= 0.0
        assert metric.optimized.mean >= 0.0
        assert metric.baseline.ci_lower <= metric.baseline.mean <= metric.baseline.ci_upper
        assert metric.optimized.ci_lower <= metric.optimized.mean <= metric.optimized.ci_upper
        assert 0.0 <= metric.p_value <= 1.0
        assert isinstance(metric.is_statistically_significant, bool)

    # Check hourly stand curves and unmet demand by stand and hour
    assert len(report.stand_hourly_baseline) == 7
    assert len(report.stand_hourly_optimized) == 7
    assert len(report.unmet_by_stand_hour_baseline) == 7
    assert len(report.unmet_by_stand_hour_optimized) == 7
    for s_id in report.stand_hourly_baseline:
        assert len(report.stand_hourly_baseline[s_id]) == 16  # Hours 7 to 22
        assert len(report.unmet_by_stand_hour_baseline[s_id]) == 16

    # Verify JSON serialization
    report_dict = report.to_dict()
    assert isinstance(report_dict, dict)
    assert "unmet_demand_pct" in report_dict
    assert "rides_per_vehicle_per_day" in report_dict
    assert "peak_hour_utilization_pct" in report_dict
    assert "unmet_by_stand_hour_baseline" in report_dict

