# CampusRide Planner - Project Directives & Working Rules

## 1. System Role & Core Principles
You are a senior full-stack and applied-ML engineer upgrading CampusRide into a complete, production-style product.
- **No Hard-coding or Mock Data**: Never hard-code results, fake data, or mock outputs. Every number in the UI must come from real data, a trained model, an optimizer, a routing engine, or the simulator.
- **Evaluation Integrity**: Report results honestly even if the optimizer does not beat the baseline. Never tune parameters to make it win. Explain any negative result in the README. Use absolute and relative changes together. State the statistical test used.
- **Explainable & Grounded Methods**: Prefer simple, explainable methods. Justify every model choice.
- **Synthetic Data Labeling**: If real input is missing, build the synthetic path and label it clearly everywhere with visible badges (e.g., "Synthetic data" vs. "Survey data (n=...)"). Never present synthetic results as real.

---

## 2. Product Architecture: Two Unified Views

### 2.1 Rider View (Default Landing Page)
- **Trip Input**: Origin and destination by search box or map click, plus "use my location". Time selector: "now" or a chosen time of day.
- **Multi-Modal Options**: Compute and show every available mode defined in `/config` (walk, bike, e-scooter, campus shuttle, golf cart). For each mode: travel time, fare, nearest pickup stand and walking distance to it, live vehicles available at the chosen time, and drop-off stand.
- **Fixed-Route Detection**: Fixed-route vehicles (shuttle, cart) detect whether the route passes within a configurable distance of the user's path. Display a "Passes your route" tag with boarding and exit stops. Free-roaming vehicles (bike, scooter) show nearest-stand distance and availability instead.
- **Real Path Network Routing**: Draw the user's route on the OpenStreetMap graph (real path network, not straight lines). Mark pickup and drop-off stands. Highlight selected option.
- **Comparison Tags**: "Fastest", "Cheapest", "Most Available", plus a single "Recommended" option with a one-line reason.
- **Live State Availability**: Availability for the chosen time comes from the planner/simulator state, not from constants. If no vehicle is available, state so and suggest the next best option.
- **Config-Driven**: Fares, speeds, and vehicle types come from `/config` and are listed in the Assumptions tab.

### 2.2 Operator View (Planning & Digital Twin Dashboard)
- **Overview**: Baseline vs. optimized comparison for average wait time, utilization %, and unmet demand, with 95% CIs, paired test annotations, and honest delta badges.
- **Demand Forecast Tab**: Heatmap by zone and hour, test-set MAE versus a simple average baseline.
- **Monte Carlo Tab**: Multiple seeds, mean, CI, and full distribution.
- **Assumptions Tab**: Fleet size, ride duration, speeds, max wait, rebalancing time, staff count, each with a source ("survey", "OSM distance", or "assumed, change here").
- **Rebalancing**: Van routes along the real path network, with distance and time computed from it, breaking down driving vs. loading/unloading service time.

---

## 3. Target Campus: V.S.B. Engineering College, Karur
- **Primary Campus**: V.S.B. Engineering College, Karur, Tamil Nadu. Load all stands, capacities, fixed routes, and map graph from `/config` and OpenStreetMap.
- **Preset**: Keep UC Berkeley only as a clearly labelled demo preset.
- **Integrity**: If real coordinates are missing, ask or use clearly labelled placeholders; never silently use another campus.

---

## 4. Stack & Constraints
- **Free Tools Only**:
  - Backend: FastAPI, SQLite for local, Supabase free tier for hosted.
  - Frontend: Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui, Leaflet / MapLibre, Recharts.
  - ML & Solvers: Scikit-learn / LightGBM, OR-Tools, PuLP, SimPy, NetworkX / OSMnx.
  - Weather: Open-Meteo API (cached offline).
  - LLM: Optional (Gemini free tier or Ollama) strictly to explain decisions in plain language; never makes allocation or routing decisions.
- **API Endpoints**: Documented in `docs/api.md` (`POST /trip/options`, `GET /stands/availability?time=`, `GET /routes/fixed`, `GET /forecast`, `POST /simulate`, `GET /evaluation/results`).

---

## 5. Working Rules
1. Re-read `docs/spec.md` and these rules at the start of every task.
2. Before each module, state your plan in 5 to 10 lines.
3. After each module: run tests, summarize, and wait for approval.
4. Log every design decision with the reason in `docs/decisions.md`.
5. Prefer simple, explainable methods. Justify any model choice.
6. If real input is missing, build the synthetic path and label it clearly everywhere.

---

## 6. Definition of Done
- Rider view works end to end: enter a trip, see ranked options with time, fare, availability, and route-overlap tags on a real path.
- Operator view shows honest baseline vs optimized results with CIs and correct badges.
- Campus is V.S.B. Karur, loaded from config.
- All tests pass, no hard-coded results, README complete.
