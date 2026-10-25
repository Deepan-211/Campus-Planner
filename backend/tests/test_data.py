"""
Unit tests for Module 1: Data Ingestion and Generation.
"""
from pathlib import Path
import pytest
from backend.config import load_config, load_stands
from backend.data.campus_graph import load_or_build_campus_network, build_geodesic_fallback_network
from backend.data.weather_fetcher import WeatherFetcher
from backend.data.survey_loader import SurveyProcessor, generate_sample_survey_csv
from backend.data.synthetic_generator import SyntheticDemandGenerator


def test_config_loading():
    """Verify default YAML config and stands JSON load with proper schemas."""
    config = load_config()
    stands = load_stands()

    assert "UC Berkeley" in config.campus.name
    assert config.fleet.total_bikes == 100
    assert len(stands) == 7
    assert {s.id for s in stands} == {"ST-01", "ST-02", "ST-03", "ST-04", "ST-05", "ST-06", "ST-07"}
    total_capacity = sum(s.dock_capacity for s in stands)
    assert total_capacity == 170


def test_campus_network_matrices():
    """Verify travel distance and duration matrices properties."""
    stands = load_stands()
    net = build_geodesic_fallback_network(stands, bike_speed_kmh=12.0)

    for s1 in stands:
        for s2 in stands:
            dist = net.get_distance(s1.id, s2.id)
            tt = net.get_travel_time(s1.id, s2.id)
            if s1.id == s2.id:
                assert dist == 0.0
                assert tt == 0.0
            else:
                assert dist > 100.0, f"Distance between {s1.id} and {s2.id} too short"
                assert dist < 5000.0, f"Distance between {s1.id} and {s2.id} exceeds campus"
                assert tt > 20.0
                assert tt < 1800.0


def test_weather_fetcher(tmp_path):
    """Verify hourly weather lookup and local caching."""
    db_file = tmp_path / "test_weather.db"
    wf = WeatherFetcher(db_path=str(db_file))

    weather_data = wf.get_hourly_weather("2026-10-23")
    assert len(weather_data) == 24
    for hour, w in weather_data.items():
        assert 0 <= hour <= 23
        assert 5.0 <= w.temp_celsius <= 35.0
        assert w.precipitation_mm >= 0.0


def test_survey_processor(tmp_path):
    """Verify survey CSV parsing, alias mapping, and anonymization."""
    csv_file = tmp_path / "survey.csv"
    generate_sample_survey_csv(csv_file, num_responses=30)

    processor = SurveyProcessor()
    records = processor.parse_csv(csv_file)

    assert len(records) == 30
    for r in records:
        assert r["anonymized_id"].startswith("ANON-")
        assert "@" not in r["anonymized_id"], "Email PII must be stripped"
        assert r["home_stand_id"] in processor.valid_stand_ids
        assert r["primary_dest_stand_id"] in processor.valid_stand_ids
        assert 6 <= r["morning_commute_hour"] <= 12
        assert 14 <= r["evening_commute_hour"] <= 22


def test_synthetic_demand_generator():
    """Verify synthetic trip generation adheres to constraints and bell schedules."""
    gen1 = SyntheticDemandGenerator(seed=42)
    gen2 = SyntheticDemandGenerator(seed=42)

    trips1 = gen1.generate_day_trips("2026-10-23")
    trips2 = gen2.generate_day_trips("2026-10-23")

    # Seed reproducibility check
    assert len(trips1) == len(trips2)
    assert trips1[0].request_time_sec == trips2[0].request_time_sec

    assert len(trips1) > 200, "Should generate realistic trip volume for a campus day"

    # All trips must be explicitly labeled synthetic
    for t in trips1:
        assert t.is_synthetic is True
        assert 25200 <= t.request_time_sec <= (22 * 3600 + 3600)
        assert t.origin_stand_id != t.dest_stand_id

    # Check chronological ordering
    req_times = [t.request_time_sec for t in trips1]
    assert req_times == sorted(req_times), "Trips must be chronologically ordered"


def test_vsb_karur_survey_processor(tmp_path):
    """Verify V.S.B. Karur survey parsing, aliases, empirical transition matrix, and priors."""
    csv_file = tmp_path / "vsb_survey.csv"
    generate_sample_survey_csv(csv_file, num_responses=50, campus_id="vsb_karur")

    processor = SurveyProcessor(campus_id="vsb_karur")
    records = processor.parse_csv(csv_file)

    assert len(records) == 50
    for r in records:
        assert r["anonymized_id"].startswith("ANON-")
        assert "vsb.ac.in" not in r["anonymized_id"]
        assert r["home_stand_id"] in processor.valid_stand_ids
        assert r["primary_dest_stand_id"] in processor.valid_stand_ids
        assert r["home_stand_id"].startswith("VSB-")
        assert r["primary_dest_stand_id"].startswith("VSB-")

    od_matrix = processor.compute_empirical_od_matrix(records)
    for origin, dest_probs in od_matrix.items():
        if dest_probs:
            assert abs(sum(dest_probs.values()) - 1.0) < 1e-4

    commute_hours = processor.compute_empirical_commute_hours(records)
    assert "morning" in commute_hours and "evening" in commute_hours
    assert sum(commute_hours["morning"].values()) > 0.99

    rain_willingness = processor.compute_rain_willingness_pct(records)
    assert 0.0 <= rain_willingness <= 100.0


def test_validate_stand_coordinates_real_positions():
    """Verify that stand coordinates are strictly within real campus positions from config."""
    from backend.config import load_config, validate_stand_coordinates, StandDefinition

    for cid in ["vsb_karur", "berkeley"]:
        cfg = load_config(campus_id=cid)
        stands = load_stands(campus_id=cid)
        errors = validate_stand_coordinates(stands, cfg)
        assert len(errors) == 0, f"Coordinates out of bounds for {cid}: {errors}"

    # Verify that an out-of-bounds stand triggers validation errors
    cfg = load_config(campus_id="vsb_karur")
    bogus_stand = StandDefinition(
        id="BOGUS-01",
        name="Off-campus Stand",
        zone="Unknown",
        latitude=99.0,  # clearly outside south/north
        longitude=77.954,
        dock_capacity=10,
    )
    errors = validate_stand_coordinates([bogus_stand], cfg)
    assert len(errors) == 1
    assert "outside campus bbox" in errors[0]

