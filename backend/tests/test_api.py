"""
Unit tests for Module 7: FastAPI REST API.
"""
import pytest
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def test_health_endpoint():
    """Verify healthcheck endpoint returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["campus"] == "UC Berkeley"


def test_get_campus_list():
    """Verify available campus locations endpoint."""
    response = client.get("/api/v1/campus/list")
    assert response.status_code == 200
    campuses = response.json()
    assert len(campuses) >= 2
    campus_ids = {c["id"] for c in campuses}
    assert "berkeley" in campus_ids
    assert "vsb_karur" in campus_ids


def test_get_campus_stands():
    """Verify stands endpoint returns all 7 anchor stands for Berkeley and 6 for VSB."""
    response_b = client.get("/api/v1/campus/stands?campus_id=berkeley")
    assert response_b.status_code == 200
    stands_b = response_b.json()
    assert len(stands_b) == 7

    response_v = client.get("/api/v1/campus/stands?campus_id=vsb_karur")
    assert response_v.status_code == 200
    stands_v = response_v.json()
    assert len(stands_v) == 6
    assert any(s["id"] == "VSB-01" for s in stands_v)


def test_get_campus_matrix():
    """Verify travel distance and duration matrices endpoint."""
    response = client.get("/api/v1/campus/matrix")
    assert response.status_code == 200
    data = response.json()
    assert len(data["stands"]) == 7
    assert "distance_matrix" in data
    assert "travel_time_matrix" in data


def test_get_route_path():
    """Verify node-by-node path route endpoint."""
    response = client.get("/api/v1/campus/route_path?from=ST-01&to=ST-04&campus_id=berkeley")
    assert response.status_code == 200
    data = response.json()
    assert data["from_stand"] == "ST-01"
    assert data["to_stand"] == "ST-04"
    assert data["distance_m"] > 0
    assert len(data["geometry"]) >= 2


def test_data_source_badge():
    """Verify data source badge endpoint."""
    response = client.get("/api/v1/data/source")
    assert response.status_code == 200
    data = response.json()
    assert "type" in data
    assert "label" in data

    # V.S.B. Karur demand data was audited and verified to be generated synthetic data
    res_vsb = client.get("/api/v1/data/source?campus_id=vsb_karur")
    assert res_vsb.status_code == 200
    data_vsb = res_vsb.json()
    assert data_vsb["type"] == "synthetic"
    assert data_vsb["count"] == 250
    assert "Synthetic" in data_vsb["label"]



def test_forecast_predict_endpoint():
    """Verify hourly demand forecasting endpoint."""
    response = client.get("/api/v1/forecast/predict?date=2026-10-23")
    assert response.status_code == 200
    data = response.json()
    assert data["forecast_date"] == "2026-10-23"
    assert len(data["predictions"]) > 0
    first_pred = data["predictions"][0]
    assert first_pred["predicted_pickups"] >= 0.0
    assert first_pred["predicted_dropoffs"] >= 0.0


def test_forecast_evaluate_endpoint():
    """Verify forecast evaluation endpoint comparing ML against baseline."""
    response = client.get("/api/v1/forecast/evaluate?campus_id=berkeley")
    assert response.status_code == 200
    data = response.json()
    assert "model_name" in data
    assert "baseline_pickup_metrics" in data
    assert "model_pickup_metrics" in data
    assert data["num_test_samples"] > 0


def test_allocation_optimize_endpoint():
    """Verify MILP fleet allocation endpoint."""
    payload = {"fleet_size": 100}
    response = client.post("/api/v1/allocation/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["fleet_size"] == 100
    assert data["solver_status"] in ["OPTIMAL", "Optimal"]
    assert sum(data["optimized_allocation"].values()) == 100


def test_rebalancing_plan_endpoint():
    """Verify midday rebalancing routing endpoint with route geometry."""
    payload = {
        "van_capacity": 15,
        "current_inventory": {"ST-01": 2, "ST-05": 28},
        "target_inventory": {"ST-01": 15, "ST-05": 15}
    }
    response = client.post("/api/v1/rebalancing/plan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["OPTIMAL", "FEASIBLE"]
    assert len(data["route_steps"]) >= 2
    assert data["bikes_moved"] > 0
    assert "route_geometry" in data


def test_simulation_evaluate_endpoint():
    """Verify multi-run Monte Carlo evaluation endpoint."""
    payload = {
        "replications": 2,
        "fleet_size": 100,
        "test_date": "2026-10-23"
    }
    response = client.post("/api/v1/simulation/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["replications"] == 2
    assert "unmet_demand_pct" in data
    assert "avg_wait_time_min" in data
    assert "fleet_utilization_pct" in data
    assert "stand_hourly_baseline" in data
    assert "stand_hourly_optimized" in data


def test_config_assumptions_endpoint():
    """Verify assumptions and parameters endpoint."""
    response = client.get("/api/v1/config/assumptions?campus_id=vsb_karur")
    assert response.status_code == 200
    data = response.json()
    assert data["campus_id"] == "vsb_karur"
    assert data["campus_name"] == "V.S.B. Engineering College"
    assert data["total_bikes"] == 50
    assert len(data["assumptions"]) > 5


def test_stands_live_availability_endpoint():
    """Verify stand-level real-time inventory and availability endpoint."""
    response = client.get("/api/v1/stands/live_availability?campus_id=vsb_karur&hour=8")
    assert response.status_code == 200
    data = response.json()
    assert data["campus_id"] == "vsb_karur"
    assert data["hour"] == 8
    assert len(data["stands"]) > 0
    stand = data["stands"][0]
    assert "stand_id" in stand
    assert "bikes_available" in stand
    assert "docks_free" in stand
    assert "fill_pct" in stand


def test_trip_options_endpoint():
    """Verify rider multi-modal trip options routing endpoint."""
    payload = {
        "campus_id": "vsb_karur",
        "origin_stand_id": "VSB-01",
        "dest_stand_id": "VSB-03",
        "departure_hour": 8,
        "departure_minute": 30
    }
    response = client.post("/api/v1/trip/options", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["campus_id"] == "vsb_karur"
    assert len(data["options"]) >= 3  # walk, bike, scooter, plus fixed transit
    mode_ids = {opt["id"] for opt in data["options"]}
    assert "walk" in mode_ids
    assert "bike" in mode_ids
    assert "scooter" in mode_ids
    assert data["recommended_option_id"] in mode_ids

    # Verify only one option gets each tag (Fastest, Cheapest)
    fastest_count = sum(1 for opt in data["options"] if "Fastest" in opt["tags"])
    cheapest_count = sum(1 for opt in data["options"] if "Cheapest" in opt["tags"])
    assert fastest_count <= 1, "Only one option may get the 'Fastest' tag"
    assert cheapest_count == 1, "Exactly one option must get the 'Cheapest' tag"

    for opt in data["options"]:
        assert opt["total_duration_min"] > 0
        assert opt["distance_m"] > 0
        assert len(opt["full_geometry"]) > 0


def test_trip_options_rejects_identical_origin_destination():
    """Verify that selecting identical origin and destination stands is rejected with HTTP 400."""
    payload = {
        "campus_id": "vsb_karur",
        "origin_stand_id": "VSB-01",
        "dest_stand_id": "VSB-01",
        "departure_hour": 8,
        "departure_minute": 0
    }
    response = client.post("/api/v1/trip/options", json=payload)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "identical" in detail.lower()


def test_availability_changes_with_departure_time_and_matches_simulator():
    """Verify stand availability changes with departure time and matches the simulator state at that time."""
    from backend.api.routes import get_simulator_hourly_inventory

    sim_state = get_simulator_hourly_inventory(campus_id="vsb_karur")
    assert len(sim_state) > 0

    # Test hours across morning rush, midday rebalancing, and evening peak
    hours_to_test = [8, 13, 17]
    observed_availabilities = []

    for h in hours_to_test:
        res = client.get(f"/api/v1/stands/live_availability?campus_id=vsb_karur&hour={h}")
        assert res.status_code == 200
        data = res.json()
        assert data["hour"] == h

        stand_counts = {s["stand_id"]: s["bikes_available"] for s in data["stands"]}
        observed_availabilities.append(stand_counts)

        # Verify exact match with simulator state
        for s_id, count in stand_counts.items():
            expected = sim_state[s_id][h]
            assert count == expected, f"Stand {s_id} at hour {h} expected {expected} from simulator, got {count}"

    # Verify availability changes across departure times
    assert observed_availabilities[0] != observed_availabilities[1] or observed_availabilities[1] != observed_availabilities[2], (
        "Availability should dynamically change between morning, midday, and evening departure times"
    )



def test_transit_routes_endpoint():
    """Verify GET /api/v1/transit/routes returns campus fixed transit lines."""
    # V.S.B. Karur
    res_vsb = client.get("/api/v1/transit/routes?campus_id=vsb_karur")
    assert res_vsb.status_code == 200
    vsb_routes = res_vsb.json()
    assert len(vsb_routes) >= 2
    route_ids = [r["id"] for r in vsb_routes]
    assert "VSB-SHUTTLE-01" in route_ids
    assert "VSB-CART-01" in route_ids

    shuttle = vsb_routes[0]
    assert len(shuttle["stops"]) >= 4
    assert shuttle["stops"][0]["stand_id"] == "VSB-01"

    # UC Berkeley
    res_ucb = client.get("/api/v1/transit/routes?campus_id=berkeley")
    assert res_ucb.status_code == 200
    ucb_routes = res_ucb.json()
    assert len(ucb_routes) >= 1
    assert ucb_routes[0]["id"] == "UCB-SHUTTLE-P"
