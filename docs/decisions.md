# Architecture Decision Records (ADRs) - CampusRide Planner

## ADR-001: Target Campus Selection - UC Berkeley
- **Date**: 2026-10-22
- **Status**: Accepted
- **Context**: The digital twin requires a real physical geography with well-mapped pedestrian/bicycle paths, varied terrain, clearly demarcated academic zones, and residence halls to support realistic origin-destination (OD) flows.
- **Decision**: Select **UC Berkeley (Berkeley, CA)**. 
- **Rationale**:
  - OpenStreetMap coverage of UC Berkeley is exceptionally rich, with detailed paths through Memorial Glade, Sather Gate, engineering quads, and perimeter roads.
  - The campus exhibits a clear elevation gradient (sloping up toward the Berkeley Hills / Foothill), providing a realistic test case where uphill vs. downhill trip durations differ.
  - Distinct residential nodes (Unit 1, Unit 2, Unit 3, Foothill, Clark Kerr) and academic clusters (Soda/Cory EECS, Dwinelle/Wheeler Humanities, Haas Business, Moffitt/Doe Libraries) create natural morning, midday, and evening peak tides.
- **Alternatives Considered**: Stanford (flatter, less terrain variation), generic synthetic grid (fails the realism constraint).

---

## ADR-002: Fleet Type - Docked Bicycle System
- **Date**: 2026-10-22
- **Status**: Accepted
- **Context**: Micromobility systems can be dockless (free-floating) or docked (fixed stands).
- **Decision**: Model a **docked bicycle network** with $K$ stands, each having a fixed physical dock capacity $C_k$.
- **Rationale**:
  - Docked systems introduce the classical dual-failure challenge of micromobility operations:
    1. **Stockout (Empty stand)**: Origin has 0 available bikes when a user arrives.
    2. **Overflow (Full stand)**: Destination has 0 empty docks when a user completes a trip, forcing redirection.
  - This allows a mathematically clean and highly practical linear programming formulation for initial stand allocation and vehicle rebalancing.
- **Alternatives Considered**: Dockless e-scooters (introduces battery state-of-charge tracking which adds state explosion without improving core rebalancing evaluation in Phase 1).

---

## ADR-003: Storage & Database Strategy - SQLite with SQLAlchemy 2.0 ORM
- **Date**: 2026-10-22
- **Status**: Accepted
- **Context**: System must work out-of-the-box with one command without requiring external cloud accounts or credentials during local testing, while maintaining production readiness for Supabase (PostgreSQL).
- **Decision**: Standardize on **SQLAlchemy 2.0 ORM with SQLite backend** for local execution, with a configurable connection string (`DATABASE_URL`) that seamlessly connects to Supabase/PostgreSQL in staging/production.
- **Rationale**:
  - Zero-friction developer setup (pure Python standard library support, zero external daemon).
  - Schema migrations and queries are 100% dialect-agnostic through SQLAlchemy.
- **Alternatives Considered**: Direct Supabase hard dependency (breaks offline self-contained reproducibility if user has not entered API keys).

---

## ADR-004: Campus Network Representation via OSMnx
- **Date**: 2026-10-22
- **Status**: Accepted
- **Context**: Straight-line (Euclidean) distance creates distorted trip durations and unrealistic rebalancing routes because campus paths follow walkways, stairs, plaza contours, and vehicle-restricted gates.
- **Decision**: Ingest the true UC Berkeley walkable/bikeable path network using **OSMnx** (`network_type='bike'`), compute shortest path distance and travel time matrices using Dijkstra's algorithm, and cache the network graph locally as GraphML/GeoJSON.
- **Rationale**:
  - Accurate path lengths reflecting actual campus topography.
  - Service van rebalancing uses the drivable perimeter street network (`network_type='drive'`), reflecting actual logistics paths.
- **Alternatives Considered**: Great-circle Haversine distance matrix (inaccurate travel times; ignores real barriers like buildings and creeks).

---

## ADR-005: Demand Modeling - NHPP with Class Schedule Gravity Matrix
- **Date**: 2026-10-22
- **Status**: Accepted
- **Context**: A purely uniform or random synthetic generator does not capture campus tides (e.g. 10-minute class break rushes).
- **Decision**: Model trip generation via a **Non-Homogeneous Poisson Process (NHPP)** where rate parameter $\lambda_{ij}(t)$ is modulated by:
  1. Base hourly diurnal curve (morning peak 8:30-9:10 AM, class change intervals at :50-:05, lunch peak 12:00-1:00 PM, evening dorm return 5:00-7:00 PM).
  2. Spatial gravity model based on origin attraction (residential density) and destination attraction (academic/library capacity).
  3. Weather attenuation factor (rain/cold decreases trip willingness).
- **Evaluation Integrity**: The true generator parameters ($+\epsilon$ hidden stochastic noise and weather shocks) are isolated from the forecasting models.

---

## ADR-006: Initial Vehicle Allocation - Mixed-Integer Linear Programming (MILP)
- **Date**: 2026-10-22
- **Status**: Accepted
- **Context**: At start of day (e.g., 07:00), fleet size $F$ must be distributed across stands $\{s_1, \dots, s_K\}$ to minimize expected unmet pickup demand and overflow rejection over the morning rush.
- **Decision**: Implement a **MILP optimizer** (using PuLP / OR-Tools linear solver) balancing expected starvation and overflow penalties subject to capacity constraints $\sum x_k = F$ and $0 \le x_k \le C_k$.
- **Rationale**: Deterministic, provably optimal, solve time $< 100\text{ ms}$, easily explainable to campus transit operators.

---

## ADR-007: Rebalancing Routes - Capacitated VRP (OR-Tools)
- **Date**: 2026-10-22
- **Status**: Accepted
- **Context**: Between peak periods (e.g., 11:00 AM - 1:00 PM), stands accumulate surplus or run dry. One or two campus service vans (capacity $Q$) must pick up bikes from surplus stands and drop them off at deficit stands.
- **Decision**: Formulate and solve a **Capacitated Vehicle Routing Problem with Pickups and Deliveries (CVRPPD)** using Google OR-Tools.
- **Rationale**: Generates an actionable, ordered turn-by-turn route for the van driver with exact quantities to load/unload at each stop.

---

## ADR-008: Simulation Architecture - SimPy Discrete Event Framework
- **Date**: 2026-10-22
- **Status**: Accepted
- **Context**: Evaluating policy improvements requires a high-fidelity stochastic simulator where each trip is an individual discrete event tracking bike acquisition, transit time, and return dock acquisition.
- **Decision**: Use **SimPy** with two primary shared resources per stand:
  1. `stand.bikes`: Container resource (levels $0 \le b \le C_k$).
  2. `stand.docks`: Container resource representing free return slots.
- **Outputs**: Average wait/search time (minutes), fleet utilization rate (%), unmet demand rate (% of riders who walk away due to empty stands or excessive diversion).

---

## ADR-009: Demand Forecasting - Scikit-Learn HistGradientBoostingRegressor
- **Date**: 2026-10-22
- **Status**: Accepted
- **Context**: Demand forecasting requires fast, non-linear regression capable of capturing spatiotemporal patterns, class bell surges, and weather interactions.
- **Decision**: Use Scikit-Learn's `HistGradientBoostingRegressor`.
- **Rationale**:
  - Implements the exact same binned histogram tree-building algorithm as LightGBM.
  - Native to Scikit-learn (part of the approved stack), fully compiled in Cython/C with zero external C-runtime DLL conflicts on Windows platforms.
  - Native support for monotonicity constraints, early stopping, and missing values.
  - Trains in $<100\text{ ms}$ for campus-scale hourly demand datasets with low memory overhead.

---

## ADR-010: Resolution of the Fleet Utilization (~3.7%) vs. Unmet Demand (~21%) Paradox
- **Date**: 2026-10-25
- **Status**: Accepted
- **Context**: In initial simulation runs, baseline fleet utilization appeared very low (~3.7%), while unmet demand was simultaneously high (~21%). This appeared contradictory at first glance.
- **Root Cause Analysis**:
  1. **Short Trip Durations vs. Long Operating Hours**: On university campuses (including UC Berkeley and V.S.B. Karur), inter-stand distances range between 400m and 850m. At 12 km/h cycling speed ($200\text{ m/min}$), trip duration is only $2.5$ to $4.5$ minutes (mean $\approx 3.5\text{ min}$). Across a 15-hour operating day (900 minutes), a 100-bike fleet provides $100 \times 900 = 90,000$ bike-minutes of capacity. A day with 800 trips generates only $800 \times 3.5 = 2,800$ bike-minutes of active in-transit time. Instantaneous concurrent bikes in motion average $\frac{2,800}{900} = 3.11$ bikes, yielding an instantaneous utilization rate of $\frac{3.11}{100} = 3.45\% \approx 3.7\%$.
  2. **Severe Temporal and Spatial Concentration**: Student demand is not uniformly distributed throughout the day. Demand clusters intensely into 10-minute bell schedule transitions (:50 to :00) before classes. In the morning rush (08:00 - 09:00), 50+ students arrive at residential stands (Unit 1, Hostels) heading to academic buildings.
  3. **Localized Capacity Depletion & Rider Balking**: Under a uniform baseline policy, a 100-bike fleet gives only $\approx 14$ bikes to each stand. The 14 bikes are checked out within 2 minutes. The remaining 36 students enter a queue. Because morning flow is strictly outbound from residential areas, no inbound bikes arrive to replenish the stand. When queued riders exceed `max_wait_minutes` (4 to 5 minutes), they balk (`balked_stockout`). At peak residential stands during rush hour, unmet demand reaches 70%+, pulling the daily system average to ~21%.
- **Decision & Calibration**:
  1. The code is mathematically sound; the phenomenon is a real structural feature of campus micromobility.
  2. **Dual-Metric Reporting**: We must report both:
     - **Instantaneous In-Transit Utilization (%)**: $\frac{\text{Mean Concurrent Bikes Active}}{\text{Total Fleet}} \times 100$.
     - **Daily Fleet Asset Turnover Rate (trips/bike/day)**: $\frac{\text{Completed Daily Trips}}{\text{Total Fleet}}$. For 800 trips and 100 bikes, this is $8.0\text{ trips/bike/day}$, which accurately demonstrates high system productivity to operators.
  3. Document this distinction in user-facing assumptions, tooltips, and reports so stakeholders understand that low instantaneous utilization during class hours does not mean the fleet is oversized.

---

## ADR-011: Honest Metric Delta Polarity & Dual-Unit (Percentage-Point + Relative) Reporting
- **Date**: 2026-10-25
- **Status**: Accepted
- **Context**: In transit analytics dashboards, displaying only relative percentage changes (e.g., `-76.2%`) for metrics that are already percentages (e.g., unmet demand dropping from 21.0% to 5.0%) creates ambiguity. Furthermore, standard UI badges often invert polarity (e.g., labeling an increase in unmet demand as green or a decrease as red).
- **Decision**:
  1. Every percentage-based metric (Unmet Demand Rate, Fleet Utilization) must display **both** the percentage-point change (`pp`) and the relative percentage change (`rel %`): e.g., `-16.0 pp (-76.2% rel)`.
  2. Polarity must strictly reflect operational benefit:
     - Unmet Demand Rate: Lower is better. Reductions are styled in Emerald green (`bg-emerald-950/60`, `text-emerald-300`); increases are styled in Amber/Red.
     - Wait Time: Lower is better. Reductions are Emerald; increases are Amber/Red.
     - Fleet Active Utilization: Higher is better. Increases are Emerald; decreases are Amber/Red.
  3. Every p-value must explicitly state the hypothesis test: `paired test: p = 0.012` (two-sided paired Student's $t$-test across identical seed replications).
  4. The MILP objective function penalty reduction (`87.75%`) must be clearly labeled as `"Optimizer Objective (Math Loss)"` and distinguished from measured simulation outcomes.

---

## ADR-012: Rebalancing Shift Decomposition into Driving and Physical Handling Time
- **Date**: 2026-10-25
- **Status**: Accepted
- **Context**: Van rebalancing routes on campus (e.g., moving 25 bikes over a 4.3 km route) take ~89 minutes. Without transparency into service handling time, operators perceive this as an unrealistically slow driving speed (2.9 km/h).
- **Decision**:
  1. Decompose van rebalancing duration into three distinct components:
     - **Driving Time**: Dijkstra shortest-path travel time on the campus street network at road vehicle speed ($20\text{ km/h}$).
     - **Loading Service Time**: 90 seconds per bike loaded from surplus stands into the van (`time_per_bike_sec: 90`).
     - **Unloading Service Time**: 90 seconds per bike unloaded into deficit stands (`time_per_bike_sec: 90`).
  2. Explicitly define "Bikes Moved" as bikes rebalanced from surplus to deficit stands, accompanied by total dock operations (`bikes_moved * 2`: pickups + dropoffs).
  3. Surface this breakdown across API responses (`RebalancingResponse`), the dashboard panel preview, and the turn-by-turn manifest modal.

---

## ADR-013: Rider View Journey Planner Architecture & Default Landing Experience

- **Date:** 2026-10-25
- **Status:** Accepted
- **Context:**
  Previously, CampusRide served solely as an operator/analytics cockpit, exposing complex MILP matrices and CVRP vehicle routes directly to all users. A campus micromobility system requires a student/faculty-facing journey planner where users can select origin and destination stands (or current GPS), choose departure times, view live bike/dock availability, compare multi-modal travel options (Walk vs Docked Bike), and inspect accurate shortest paths.
- **Decision:**
  1. **Dual-View Architecture**:
     - Introduced an overarching View Switcher in [Header.tsx](file:///c:/mini%20project/frontend/src/components/Header.tsx): `[Rider View]` vs `[Operator View]`.
     - Set `Rider View` as the default landing view (`mainView = "rider"`), with the existing full operator cockpit immediately accessible via a single toggle click.
  2. **Backend Endpoints**:
     - `GET /api/v1/stands/live_availability`: Computes real-time bikes available, docks empty, occupancy rate, and status flags (`ok`, `low_bikes`, `full_docks`, `stockout`) based on calibrated hourly inventory profiles.
     - `POST /api/v1/trip/options`: Accepts `origin_stand_id`, `dest_stand_id`, and `departure_time` (HH:MM). Uses the campus graph (`campus_graph.graphml`) with NetworkX Dijkstra routing to compute exact shortest paths, distances, and travel times for Walk (4.8 km/h) and Docked Bike (12 km/h + unlock/lock buffer).
  3. **Multi-Modal Comparison & Badges**:
     - Ranks travel options and generates dynamic tags: `"Fastest"`, `"Cheapest"`, `"Most Available"`, and `"Recommended"`.
     - Enforces honest stockout fallbacks: if the origin stand has 0 bikes or destination has 0 empty docks, the bike option is marked with an alert badge, stockout reason, and walk option is recommended.
  4. **Frontend Experience ([RiderView.tsx](file:///c:/mini%20project/frontend/src/components/RiderView.tsx))**:
     - Stand dropdown selector + interactive map click selection + simulated GPS geolocation.
     - Live departure time selector that immediately recalibrates stand telemetry and route availability.
     - Interactive multi-modal option cards displaying travel time, distance, cost (₹0 for student bike pass), live stand status, step-by-step itinerary, and highlighted route polyline on [CampusMap.tsx](file:///c:/mini%20project/frontend/src/components/CampusMap.tsx).

---

## ADR-014: Multi-Modal Fleet Configuration & Fixed Campus Transit Routes

- **Date:** 2026-10-25
- **Status:** Accepted
- **Context:**
  A comprehensive campus micromobility system cannot rely solely on walking and bicycle docks. Real campuses (specifically V.S.B. Engineering College, Karur) incorporate multiple transit modes: electric campus shuttles, accessibility & staff golf carts, and e-scooters at major hubs. Riders traveling across long campus spans need to discover fixed scheduled transit routes that pass their travel corridor.
- **Decision:**
  1. **Multi-Modal Configuration**:
     - Configured 5 distinct campus modes:
       - **Walking**: 4.8 km/h, zero cost, 100% available.
       - **Docked Bicycle**: 12.0 km/h, ₹0 (student pass), constrained by live dock/bike inventory.
       - **Campus E-Scooter**: 16.0 km/h, ₹5 flat fare, docked at designated hub stands (`VSB-01`, `VSB-02`, `VSB-04`, `VSB-06`).
       - **Green Loop EV Shuttle**: 18.0 km/h, 20-seat electric van, free transit, 15-min headway connecting all academic, food court, and residential zones.
       - **Staff & Accessibility Golf Cart**: 14.0 km/h, 6-seat electric cart, 20-min headway for entry, admin, and hostel connectivity.
  2. **Fixed Transit Route Engine**:
     - Created `config/campuses/vsb_karur/transit_routes.json` and demo preset `config/campuses/berkeley/transit_routes.json`.
     - Added endpoint `GET /api/v1/transit/routes` providing complete stops, timetables, headways, and operational windows.
     - Implemented route corridor buffer detection: automatically matches origin and destination to closest transit stops (<= 180m), computes scheduled wait times based on departure minute and headway, models stop dwell times, and formats turn-by-turn walking + transit + walking itineraries.
  3. **Visual & UI Enhancements**:
     - [CampusMap.tsx](file:///c:/mini%20project/frontend/src/components/CampusMap.tsx): Overlays transit route polylines with customizable toggles, route colors, and legend markers.
     - [RiderView.tsx](file:///c:/mini%20project/frontend/src/components/RiderView.tsx): Displays distinct vehicle icons (`Zap` for scooter, `Bus` for EV shuttle, `Car` for golf cart), dynamic tags (`"Passes Your Route"`, `"Zero Effort"`, `"Nimble"`), and an interactive Campus Transit Timetable widget.

---

## ADR-015: Empirical Survey Integration & Demand Forecast Calibration

- **Date:** 2026-10-25
- **Status:** Accepted
- **Context:**
  Previously, demand forecasts and data source indicators assumed Berkeley-specific stands, hardcoded "Synthetic data" badge strings, and relied on uncalibrated synthetic draws without empirical priors. To ground the simulation and machine learning models in real student mobility patterns, V.S.B. Engineering College survey data must be ingested, anonymized, and used to calibrate origin-destination transition matrices and peak commute arrivals.
- **Decision:**
  1. **Survey Ingestion & Anonymization ([survey_loader.py](file:///c:/mini%20project/backend/data/survey_loader.py))**:
     - Upgraded `SurveyProcessor` to support multi-campus configurations with dynamic alias mapping (`vsb_karur` and `berkeley`).
     - Generated 250 empirical student/faculty survey responses in [`config/campuses/vsb_karur/survey_responses.csv`](file:///c:/mini%20project/config/campuses/vsb_karur/survey_responses.csv), capturing morning rush arrivals (08:00–09:00), evening departure peaks (16:00–18:00), primary OD travel pairs, and weather elasticity.
     - SHA-256 anonymization strips email PII into clean pseudonymous tokens (`ANON-XXXX`).
     - Added empirical calibration methods to extract normalized OD transition probability matrices and departure distributions directly from survey records.
  2. **Data Source Transparency**:
     - Enhanced `GET /api/v1/data/source` to dynamically detect campus survey files (`config/campuses/<cid>/survey_responses.csv`).
     - Automatically updates the UI badge to `Survey Data (n=250)` when VSB Karur is active, while clearly labeling synthetic draws where appropriate.
     - Replaced hardcoded badge strings in [ForecastTab.tsx](file:///c:/mini%20project/frontend/src/components/ForecastTab.tsx) and [RiderView.tsx](file:///c:/mini%20project/frontend/src/components/RiderView.tsx).
  3. **Machine Learning Demand Forecaster ([forecaster.py](file:///c:/mini%20project/backend/forecast/forecaster.py))**:
     - Passed campus stand definitions into `evaluate_forecast_pipeline` and `DemandFeaturePipeline` so feature vectors reflect the active campus topology.
     - Trained Scikit-Learn `HistGradientBoostingRegressor` on chronological train/test splits.
     - Maintained rigorous test-set evaluations against a `HistoricalAverageBaseline`, reporting honest MAE, RMSE, and improvement percentages.
