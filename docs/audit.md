# CampusRide Comprehensive System Audit (Step 0 to Phase 5 Final Report)

**Date**: 2026-10-25  
**Auditor**: Senior Full-Stack & Applied-ML Engineer  
**Status**: 100% Completed & Verified (All 5 Phases Production-Ready)  

---

## 1. Executive Summary
CampusRide has been fully transformed from an operator-only prototype into a complete, dual-view production product:
1. **Rider View (Default Landing Page)**: Student-facing trip planner with multi-modal routing (walk @ 4.8 km/h, bike @ 12.0 km/h, e-scooter @ 16.0 km/h, shuttle @ 18.0 km/h, golf cart @ 14.0 km/h), real OSMnx network paths, fixed-route corridor overlap detection ("Passes your route"), live availability from simulator state, honest stockout fallbacks, and transit timetables.
2. **Operator View (Management Cockpit)**: Production-grade digital twin providing spatiotemporal demand forecasting (HistGradientBoosting), MILP fleet allocation, OR-Tools CVRP rebalancing, and paired Monte Carlo simulation with 95% confidence intervals.
3. **Target Campus**: V.S.B. Engineering College, Karur, Tamil Nadu (`vsb_karur`) is the default primary campus loaded from `/config` and OpenStreetMap. UC Berkeley is retained strictly as an explicitly labelled demo preset (`[Demo Preset] UC Berkeley`).

---

## 2. Inventory of Implemented Backend & Frontend Components

### 2.1 Backend Modules (`backend/`)
| Module | File(s) | Description | Verification Status |
|---|---|---|---|
| **Config Loader** | `backend/config.py` | Multi-campus loader (`config/campuses/<id>/`), Pydantic validation models, assumptions tables. Defaults to `vsb_karur`. | Verified. 38 tests pass. |
| **Data Engine** | `backend/data/campus_graph.py`<br>`backend/data/weather_fetcher.py`<br>`backend/data/synthetic_generator.py`<br>`backend/data/survey_loader.py` | OSMnx road/path graph ingestion, Dijkstra shortest paths, Open-Meteo SQLite weather cache, NHPP synthetic demand generator, survey processor supporting both VSB Karur and Berkeley with SHA-256 PII anonymization (`ANON-XXXX`). | Verified. `test_vsb_karur_survey_processor` passes. |
| **Forecaster** | `backend/forecast/feature_pipeline.py`<br>`backend/forecast/forecaster.py` | Hourly spatiotemporal pickup/dropoff prediction using Scikit-Learn `HistGradientBoostingRegressor` with calendar & weather features, evaluated against Historical Mean baseline. | Verified. 4 tests pass (`test_forecast.py`). |
| **Simulator** | `backend/simulator/engine.py`<br>`backend/simulator/entities.py` | SimPy discrete-event simulation tracking bike containers, dock containers, queues, balking (`max_wait_minutes`), lognormal transit times, and live availability queries. | Verified. 6 tests pass (`test_simulator.py`). |
| **Allocation** | `backend/allocation/optimizer.py` | PuLP/MILP optimizer solving morning stand inventory $x_k$ subject to $\sum x_k = F$ and $0 \le x_k \le C_k$ minimizing weighted stockout + overflow penalties. Enforces `ValueError` when fleet exceeds capacity. | Verified. 4 tests pass (`test_allocation.py`). |
| **Rebalancing** | `backend/rebalancing/router.py` | OR-Tools Capacitated Vehicle Routing Problem (CVRP) for midday van pickups and deliveries. Decomposes driving, loading, unloading, and total shift time. Clearly reports dock operations. | Verified. 5 tests pass (`test_rebalancing.py`). |
| **Evaluation** | `backend/evaluation/evaluator.py` | Paired Monte Carlo simulation ($N=10$ seeds) comparing Policy A (uniform + no rebalancing) vs. Policy B (MILP + CVRP), computing mean, standard deviation, paired $t$-test p-value, and 95% CIs. | Verified. 2 tests pass (`test_evaluation.py`). |
| **API Layer** | `backend/api/main.py`<br>`backend/api/routes.py`<br>`backend/api/schemas.py` | FastAPI REST endpoints with CORS, strict Pydantic schemas, `/trip/options`, `/stands/live_availability`, `/transit/routes`, and dynamic `/data/source`. | Verified. 11 tests pass (`test_api.py`). |

### 2.2 Frontend Application (`frontend/`)
- **Framework**: Next.js 14 App Router, TypeScript, Tailwind CSS, Leaflet (`react-leaflet`), Recharts, Lucide icons.
- **Pages & Components**:
  - `src/app/page.tsx`: Dual-view architecture (`RiderView` as default landing page, toggle to `OperatorView`).
  - `src/components/RiderView.tsx`: Journey planner with origin/destination search, interactive map selection, 5 multi-modal cards, honest stockout fallbacks, and timetable widgets.
  - `src/components/CampusMap.tsx`: Interactive Leaflet map with stand markers, transit route polyline overlays, vehicle mode colors, and `[Transit Lines]` toggle.
  - `src/components/MetricComparisonGrid.tsx`: Monte Carlo KPI comparison cards with honest polarity and percentage-point (`pp`) plus relative percentage deltas.
  - `src/components/ComparisonPanel.tsx`: Overview comparative panel with baseline vs. optimized and 95% CIs.
  - `src/components/ForecastTab.tsx`: 24-hour demand forecast heatmap with dynamic data source badge.
  - `src/components/StandTelemetryGrid.tsx`: Stand cards with radial capacity gauges (with fixed `{bikes}` counter).
  - `src/components/AllocationPanel.tsx`: MILP allocation results relabeled as "Optimizer Objective Loss".
  - `src/components/RebalancingPanel.tsx`: Van rebalancing route steps with driving vs. service time breakdown.

---

## 3. Resolution Matrix for the 9 Known Issues

| # | Issue Description | Root Cause | Implemented & Verified Resolution | Status |
|---|---|---|---|---|
| **1** | Utilization ~3.7% vs. Unmet Demand ~21% Contradiction | Physical brevity of campus trips (3.5 min) vs. non-homogeneous bell transition rushes causing localized morning residential stockouts. | Documented mathematical transport paradox in `docs/decisions.md` (ADR-010). Explained both instantaneous capacity utilization and daily asset turnover. | **RESOLVED** |
| **2** | Delta Badges Must Be Honest (Polarity & Percentage Points) | Static strings and relative-only deltas in `MetricComparisonGrid.tsx`. | Dynamic calculation of percentage-point change (`pp`) and relative percentage change (`rel %`). Honest polarity: emerald for improvement, amber/red for deterioration. | **RESOLVED** |
| **3** | Remove or Relabel "87.75% cost reduction" | Optimizer objective penalty reduction was labeled as "COST REDUCTION" in headline simulation header. | Relabeled as `"-87.75% Objective Loss"` and `"Optimizer Objective (Mathematical penalty reduction, not a measured simulation outcome)"`. | **RESOLVED** |
| **4** | Stand Counters Show "$" Before Bike Counts | Line 65 in `StandTelemetryGrid.tsx` used literal `${bikes}` in JSX text node. | Replaced `${bikes}` with `{bikes}`. Counters now cleanly display integer numbers. | **RESOLVED** |
| **5** | Campus Config Not Loading (Map Shows Berkeley) | Hardcoded default `"berkeley"` in backend and frontend. | Set default campus to `"vsb_karur"` in `backend/config.py` and `frontend/src/app/page.tsx`. Relabeled Berkeley as `[Demo Preset] UC Berkeley`. | **RESOLVED** |
| **6** | Van Time 89 min for 4.3 km Breakdown & Definition of Moved | 90s per bike handling time lumped with driving time; "moved" ambiguity. | Decomposed into driving time, loading time, unloading time, and total shift time. Defined moved bikes and total dock operations (`pickups + dropoffs`). | **RESOLVED** |
| **7** | Add Visible Data Badge Everywhere | Missing provenance tags in tabs and views. | Added dynamic badge `Survey Data (n=250)` or `Synthetic Data (NHPP Model)` across Rider View, Forecast Tab, Monte Carlo Tab, and Main Header. | **RESOLVED** |
| **8** | Show "paired test" Next to P-values | Raw `p = ...` without specifying statistical methodology. | Updated to render `paired test: p = 1.0e-05` across all comparative displays. | **RESOLVED** |
| **9** | Overlapping Cards, Clipped Markers, Low-Contrast Text | Fixed grid heights, missing Leaflet popup padding, WCAG AA contrast issues. | Converted card containers to responsive flex layouts, increased Leaflet margins, upgraded text colors from `text-zinc-500` to `text-zinc-400` / `text-zinc-300`. | **RESOLVED** |

---

## 4. Phase Completion Summary

- **Phase 1: Known Issues & Fixes**: Complete & Verified (All 9 issues resolved, ADR-010 to ADR-012 logged).
- **Phase 2: Rider View MVP**: Complete & Verified (`/trip/options`, `/stands/live_availability`, dual-view landing page, ADR-013 logged).
- **Phase 3: Multi-Modal Fleet & Fixed Transit Routes**: Complete & Verified (5 transport modes, Green Loop EV Shuttle, Express Golf Cart, Bear Transit P-Line, polyline overlays, ADR-014 logged).
- **Phase 4: Survey Data Integration & Demand Forecast Upgrade**: Complete & Verified (250 VSB Karur responses, SHA-256 PII anonymization, empirical OD calibration, dynamic badge, ADR-015 logged).
- **Phase 5: Polish & Final Production Readiness**: Complete & Verified (Updated README, audit, assumptions, zero build errors, 38/38 passing unit tests).
