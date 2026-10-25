# CampusRide Planner - System Specification (docs/spec.md)

## 1. System Overview & Objectives
**CampusRide Planner** is an end-to-end digital twin and decision-support platform for university campus micromobility (docked bicycles). The platform integrates real-world campus geography, spatiotemporal demand forecasting, linear programming allocation, vehicle routing optimization, and discrete-event simulation to solve the twin challenges of micromobility: **stockouts** (empty stands) and **overflows** (full stands during rush hours).

Every metric displayed in the dashboard is derived from real data, physical network routing, mathematical optimizers, or reproducible Monte Carlo simulations.

---

## 2. Campus Topology & Fleet Specifications (UC Berkeley)
### 2.1 Geographic Domain
- **Campus**: University of California, Berkeley, CA.
- **Bounding Box**: North: 37.8765, South: 37.8650, West: -122.2660, East: -122.2500.

### 2.2 Phase 1 MVP Stand Network (7 Anchor Stands)
| Stand ID | Stand Name | Zone / Category | Latitude | Longitude | Dock Capacity ($C_k$) |
|---|---|---|---|---|---|
| `ST-01` | Unit 1 Residence Halls | Residential (South) | 37.8675 | -122.2555 | 25 |
| `ST-02` | Unit 2 Residence Halls | Residential (South) | 37.8658 | -122.2552 | 25 |
| `ST-03` | Foothill / Stern Halls | Residential (North Hills) | 37.8748 | -122.2541 | 20 |
| `ST-04` | Soda & Cory Halls (EECS) | Academic (North) | 37.8756 | -122.2588 | 25 |
| `ST-05` | Dwinelle & Wheeler Halls | Academic (Central) | 37.8706 | -122.2605 | 30 |
| `ST-06` | Moffitt & Doe Libraries | Central Hub | 37.8724 | -122.2608 | 25 |
| `ST-07` | Haas School of Business | Academic (East) | 37.8715 | -122.2533 | 20 |

**Totals**: 7 Stands, 170 Total Docks, Standard Fleet Size $F = 100$ bicycles (58.8% network fill ratio).

---

## 3. Module Specifications & Functional Requirements

### Module 1: Data Engine (`backend/data`)
- **1.1 Campus Graph Builder (`campus_graph.py`)**:
  - Downloads pedestrian and cycling network for UC Berkeley using `osmnx.graph_from_bbox`.
  - Computes edge impedance (distance in meters + average cycling speed of $12\text{ km/h} \approx 3.33\text{ m/s}$).
  - Computes $7 \times 7$ pairwise shortest path distance matrix $D_{ij}$ and travel time matrix $T_{ij}$ using Dijkstra's algorithm.
  - Caches graph to `config/campus_graph.graphml` and distance matrices to `config/travel_matrices.json`.
- **1.2 Weather Ingestion (`weather_fetcher.py`)**:
  - Fetches hourly temperature, precipitation probability, and precipitation amount from Open-Meteo free API (`api.open-meteo.com`).
  - Implements local SQLite caching with TTL (24h) to operate completely offline once cached.
- **1.3 Survey Ingestion & Anonymization (`survey_loader.py`)**:
  - Validates CSV survey responses: preferred commute hours, home stand, primary destination stand, willingness to cycle in rain, acceptable walking distance.
  - Anonymizes records (strips any email/timestamp identifiers).
- **1.4 Synthetic Demand Generator (`synthetic_generator.py`)**:
  - Calibrated by survey preferences and lecture bell schedules.
  - Generates realistic trip records $(t_{req}, \text{origin\_id}, \text{dest\_id}, \text{user\_type}, \text{max\_wait\_min})$.
  - Models class rush bursts (10-minute bell transitions at :50 to :05).
  - Explicitly tags dataset with `is_synthetic: true` in metadata and DB records.

---

### Module 2: Demand Forecaster (`backend/forecast`)
- **Input**: Historical hourly origin-destination demand matrix $Y_{k, t}$ over past $D$ days, with calendar features (hour of day, day of week) and weather features (temperature, rain mm).
- **Model Architecture**:
  - Baseline 1: Historical Mean (Average trips for stand $k$ at hour $h$).
  - Baseline 2: Rolling 7-day median.
  - Primary Model: Regularized Gradient Boosting / Ridge Regression with one-hot temporal encodings and weather interactions.
- **Output**: Forecasted pickups $\hat{\lambda}_{k, h}^{out}$ and dropoffs $\hat{\lambda}_{k, h}^{in}$ for all stands $k \in \{1,\dots,7\}$ and hours $h \in [7, 22]$.
- **Evaluation**: Mean Absolute Error (MAE) and Root Mean Squared Error (RMSE) on unseen test days.

---

### Module 3: SimPy Discrete-Event Simulator (`backend/simulator`)
- **Process Dynamics**:
  1. **Rider Arrival**: Individual rider arrives at origin stand $s_i$ at time $t_{arr}$ following a Poisson process.
  2. **Bike Checkout**: Rider requests 1 bike from $s_i$.
     - If $b_i > 0$: Rider instantly claims bike, decreases stand bike count, departs. Wait time = 0.
     - If $b_i = 0$ (Stockout): Rider enters wait queue. If wait time exceeds $\tau_{max} \approx 5\text{ mins}$, rider balks (unmet demand).
  3. **Transit**: Rider traverses shortest path from $s_i \to s_j$. Transit time $\sim \text{LogNormal}(\mu=T_{ij}, \sigma=0.15 \cdot T_{ij})$.
  4. **Dock Return**: Rider arrives at destination stand $s_j$.
     - If empty docks $d_j = C_j - b_j > 0$: Rider docks bike, completes trip.
     - If $d_j = 0$ (Overflow): Rider is rerouted to nearest available stand $s_{alt}$ via graph distance, adding rerouting time penalty.
- **Key Output Metrics**:
  - **Unmet Demand Rate (%)**: $\frac{\text{Balked Trips}}{\text{Total Requested Trips}} \times 100$
  - **Average Wait / Search Time (minutes)**: Across all riders (0 for instant checkouts, wait time for queued riders, diversion time for overflows).
  - **Fleet Utilization (%)**: Average percentage of the 100 bikes actively in transit across the operating day (07:00 - 22:00).

---

### Module 4: Morning Fleet Allocation Optimizer (`backend/allocation`)
- **Objective**: Determine initial bike inventory $x_k \in \mathbb{Z}_{\ge 0}$ for each stand $k \in \{1,\dots, K\}$ at 07:00 AM before morning rush (08:00 - 10:00 AM).
- **Mathematical Formulation (MILP)**:
  $$\min \sum_{k=1}^K \left( w_{stock} \cdot \max(0, \hat{D}_k^{out} - x_k) + w_{over} \cdot \max(0, x_k + \hat{D}_k^{in} - C_k) \right)$$
  Subject to:
  $$\sum_{k=1}^K x_k = F \quad (\text{Total Fleet Size})$$
  $$0 \le x_k \le C_k \quad \forall k \in \{1,\dots, K\}$$
  Where:
  - $\hat{D}_k^{out}$: Forecasted morning peak outbound trips from stand $k$.
  - $\hat{D}_k^{in}$: Forecasted morning peak inbound trips to stand $k$.
  - $w_{stock} = 1.0$, $w_{over} = 0.7$ (penalty weights).
- **Baseline Allocation**: Equal distribution ($x_k = \lfloor F / K \rfloor$, with remainder placed at largest capacity stands).

---

### Module 5: Midday Rebalancing Router (`backend/rebalancing`)
- **Problem**: At 11:30 AM (post-morning rush), academic stands are overflowing while residential stands are drained.
- **Service Van Constraints**:
  - 1 campus operations van, capacity $Q = 15$ bikes.
  - Base depot located at campus operations facility (e.g., near Haas/Stadium or Central Plant).
  - Loading/unloading time: 1.5 minutes per bike moved.
  - Driver shift limit: 90 minutes total operating window (11:30 AM - 1:00 PM).
- **Formulation**: Capacitated Vehicle Routing Problem with Pickup and Delivery (CVRPPD) solved using Google OR-Tools.
- **Output Route**: Ordered sequence of stops $[depot \to s_a \to s_b \to \dots \to depot]$ with exact pickup $(+q)$ and dropoff $(-q)$ amounts at each stop, total travel distance (km), and route duration (mins).

---

### Module 6: Comparative Evaluation Engine (`backend/evaluation`)
- **Protocol**:
  - Runs $N=10$ independent simulation replications under identical random seed sets for both policies:
    - **Policy A (Baseline)**: Uniform initial vehicle allocation, zero midday rebalancing.
    - **Policy B (Optimized)**: MILP initial vehicle allocation + OR-Tools CVRP midday rebalancing.
  - Computes sample mean, standard deviation, and two-sided 95% Confidence Interval (Student's $t$ with $df=9$).
  - Outputs a clear comparative statistical summary table.

---

### Module 7: Backend REST API (`backend/api`)
- Fast, async endpoints built with FastAPI and strict Pydantic schemas:
  - `GET /api/v1/campus/stands`: List all 7 stands with coordinates, dock capacities, and current status.
  - `GET /api/v1/campus/graph`: GeoJSON of stands and connecting bikeable path network.
  - `GET /api/v1/forecast/hourly`: Predicted hourly origin/destination demand for selected date/weather.
  - `POST /api/v1/allocation/optimize`: Solves initial allocation for fleet size $F$.
  - `POST /api/v1/rebalancing/plan`: Computes van routing plan given stand inventory imbalances.
  - `POST /api/v1/simulation/run`: Runs SimPy simulation for baseline vs. optimized policy and streams/returns metrics.

---

### Module 8: Interactive Digital Twin Dashboard (`frontend`)
- **Stack**: Next.js 14+ (App Router), TypeScript, Tailwind CSS, shadcn/ui components.
- **Map Visualizer**: MapLibre GL / Leaflet rendering the UC Berkeley campus with custom SVG stand markers displaying current bike fill level / capacity gauges ($x_k / C_k$).
- **Timeline & Hour Slider**: Scrub from 07:00 to 22:00 to watch bike inventory rise and fall dynamically.
- **Rebalancing Route Overlay**: Visualized as a highlighted path on the road network with numbered stop badges and load/unload callouts.
- **KPI Comparison Grid**:
  - Unmet Demand Rate: Baseline vs. Optimized (with 95% CI error bars).
  - Average Wait Time: Baseline vs. Optimized.
  - Fleet Utilization Rate: Baseline vs. Optimized.
- **Synthetic Data Disclaimer Badge**: Prominently displayed in header and footer.
