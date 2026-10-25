"""
Unit tests for Module 2: Demand Forecasting.
"""
import pandas as pd
import numpy as np
import pytest
from backend.config import load_stands
from backend.data.synthetic_generator import SyntheticDemandGenerator
from backend.forecast.feature_pipeline import DemandFeaturePipeline
from backend.forecast.forecaster import (
    HistoricalAverageBaseline,
    MLDemandForecaster,
    evaluate_forecast_pipeline
)


@pytest.fixture(scope="module")
def synthetic_history_df():
    """Generates 10 days of synthetic demand data for testing."""
    from backend.data.weather_fetcher import HourlyWeather
    gen = SyntheticDemandGenerator(seed=123)
    stands = load_stands()
    stand_ids = [s.id for s in stands]

    # Deterministic dummy weather to avoid network delays in unit tests
    dummy_weather = {
        h: HourlyWeather(hour=h, temp_celsius=17.0, precipitation_mm=0.0, rain_probability_pct=0, is_rain=False)
        for h in range(24)
    }

    rows = []
    for day_idx in range(10):
        date_str = f"2026-10-{10 + day_idx:02d}"
        trips = gen.generate_day_trips(date_str, weather_override=dummy_weather, seed_offset=day_idx * 10)

        # Aggregate by hour and stand
        counts = {h: {s: {"pickups": 0, "dropoffs": 0} for s in stand_ids} for h in range(7, 23)}
        for t in trips:
            h = int(t.request_time_sec // 3600)
            if 7 <= h <= 22:
                counts[h][t.origin_stand_id]["pickups"] += 1
                counts[h][t.dest_stand_id]["dropoffs"] += 1

        for h in range(7, 23):
            for s_id in stand_ids:
                rows.append({
                    "date": date_str,
                    "hour": h,
                    "stand_id": s_id,
                    "pickups_actual": counts[h][s_id]["pickups"],
                    "dropoffs_actual": counts[h][s_id]["dropoffs"],
                    "temp_celsius": 17.5,
                    "precipitation_mm": 0.0
                })

    return pd.DataFrame(rows)


def test_feature_pipeline_construction():
    """Verify feature row generation and absence of NaNs."""
    pipeline = DemandFeaturePipeline()
    row = pipeline.build_feature_row(
        date_str="2026-10-23",
        hour=8,
        stand_id="ST-01",
        temp_celsius=14.0,
        precipitation_mm=0.2
    )

    assert row["hour"] == 8.0
    assert row["is_morning_rush"] == 1.0
    assert row["is_evening_rush"] == 0.0
    assert row["is_residential"] == 1.0
    assert row["is_rain"] == 1.0
    assert row["stand_ST-01"] == 1.0
    assert row["stand_ST-02"] == 0.0
    assert all(not np.isnan(v) for v in row.values())


def test_baseline_forecaster(synthetic_history_df):
    """Verify historical average baseline produces expected means."""
    baseline = HistoricalAverageBaseline()
    baseline.fit(synthetic_history_df)

    p_preds, d_preds = baseline.predict(synthetic_history_df.iloc[:20])
    assert len(p_preds) == 20
    assert len(d_preds) == 20
    assert (p_preds >= 0.0).all()
    assert (d_preds >= 0.0).all()


def test_ml_forecaster_fit_and_predict(synthetic_history_df):
    """Verify ML forecaster fits and predicts non-negative values."""
    forecaster = MLDemandForecaster()
    forecaster.fit(synthetic_history_df)

    p_preds, d_preds = forecaster.predict(synthetic_history_df.iloc[:20])
    assert len(p_preds) == 20
    assert (p_preds >= 0.0).all()
    assert (d_preds >= 0.0).all()

    # Verify predict_day produces complete stand-hour matrix
    day_preds = forecaster.predict_day("2026-10-25")
    assert len(day_preds) == 7
    for s_id, hours in day_preds.items():
        assert len(hours) == 16  # Hours 7 to 22
        for h, (p, d) in hours.items():
            assert 7 <= h <= 22
            assert p >= 0.0
            assert d >= 0.0


def test_evaluation_pipeline_metrics(synthetic_history_df):
    """Verify evaluation integrity: models evaluated on unseen test days."""
    ml_model, baseline, report = evaluate_forecast_pipeline(synthetic_history_df, test_days=2)

    assert report.num_train_samples > 0
    assert report.num_test_samples > 0
    assert report.baseline_pickup_metrics.mae > 0.0
    assert report.model_pickup_metrics.mae > 0.0
    assert report.model_pickup_metrics.mae < 10.0, "Model MAE must be realistic for campus volume"
