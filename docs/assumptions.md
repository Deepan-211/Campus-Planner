# CampusRide Planner - Simulation Assumptions & Parameters (docs/assumptions.md)

Every assumption in this table is traceable to a specific real-world source or explicitly marked as an assumed parameter that can be tuned via `config/campuses/<campus_id>/config.yaml`.

---

## 1. V.S.B. Engineering College, Karur (`vsb_karur`) — Primary Target Campus

| Parameter Name | Value in System | Units | Justification & Stated Source | Configuration Key |
|---|---|---|---|---|
| **Campus Geographic Center** | V.S.B. Karur (10.9427, 78.1691) | Lat, Lon | V.S.B. Engineering College central campus coordinates from OpenStreetMap | `campus.bbox` |
| **Number of Key Stands** | 6 | Stands | Anchor stands covering main gate, mechanical, library, CSE tech quad, and hostels | `fleet.num_stands` |
| **Total Stand Capacity** | 80 | Docks | Sized to academic/residential quad density (10 to 16 docks per stand) | `stands[*].dock_capacity` |
| **Total Fleet Size ($F$)** | 50 | Bicycles | 62.5% network fill ratio (industry standard to prevent dock lockouts) | `fleet.total_bikes` |
| **Walking Pace** | 4.8 (1.33 m/s) | km/h | Standard pedestrian walking velocity for campus pathways | `modes.walk.speed_kmh` |
| **Docked Bicycle Speed** | 12.0 (3.33 m/s) | km/h | NACTO (National Association of City Transportation Officials) campus cycling standard | `modes.bicycle.speed_kmh` |
| **Campus E-Scooter Speed** | 16.0 (4.44 m/s) | km/h | Governed speed-limited campus electric scooter rate | `modes.escooter.speed_kmh` |
| **Green Loop EV Shuttle Speed** | 18.0 (5.00 m/s) | km/h | Campus electric minibus average road speed with speed-calming | `modes.shuttle.speed_kmh` |
| **Express Golf Cart Speed** | 14.0 (3.89 m/s) | km/h | Campus electric service cart speed along designated multi-use corridors | `modes.golf_cart.speed_kmh` |
| **Transit Corridor Buffer** | 180 | Meters | Maximum student walking access distance to an active transit corridor | `transit.buffer_meters` |
| **EV Shuttle Headway** | 15 | Minutes | Operating frequency (08:00 to 18:00) | `transit_routes[SHUTTLE-GL].headway_minutes` |
| **Express Golf Cart Headway** | 20 | Minutes | Operating frequency (08:30 to 17:30) | `transit_routes[CART-EXP].headway_minutes` |
| **Student Commute Survey Calibration** | $n=250$ | Responses | Real empirical survey at VSB Karur: 58% peak commute 08:00-09:00, 31.6% rain willingness | `survey.source` |
| **Max Wait Time Before Balking** | 5.0 | Minutes | Student willingness-to-wait threshold before walking or choosing alternate mode | `simulation.max_wait_minutes` |
| **Class Transition Surge Interval** | 10 | Minutes | Academic bell transition surge window (:50 to :00) | `demand.bell_window_minutes` |
| **Rebalancing Van Capacity ($Q$)** | 15 | Bicycles | Tata Winger / Force Traveller maintenance van | `rebalancing.van_capacity` |
| **Bike Load / Unload Time** | 90 | Seconds/bike | Time required for technician to unlock stand, load rack, or secure bike | `rebalancing.time_per_bike_sec` |
| **Rebalancing Operating Window** | 60 | Minutes | Midday lunch lull (12:30 PM to 1:30 PM) | `rebalancing.max_shift_minutes` |
| **Rain Demand Attenuation** | 0.50 (50% drop if $\ge 2\text{ mm/h}$) | Multiplier | Transportation Research Part A: micromobility precipitation elasticity | `weather.rain_penalty_factor` |
| **Random Evaluation Seeds** | 42, 101, 202, ..., 909 | Integer | Fixed seeds across 10 paired replications for strict reproducibility | `evaluation.random_seeds` |

---

## 2. [Demo Preset] UC Berkeley (`berkeley`)

| Parameter Name | Value in System | Units | Justification & Stated Source | Configuration Key |
|---|---|---|---|---|
| **Campus Geographic Center** | UC Berkeley (37.8719, -122.2585) | Lat, Lon | Central campus coordinates from OpenStreetMap | `campus.bbox` |
| **Number of Key Stands** | 7 | Stands | Anchor stands covering Unit 1, Unit 2, Foothill, Soda, Dwinelle, Moffitt, Haas | `fleet.num_stands` |
| **Total Stand Capacity** | 170 | Docks | Real-world bike station sizing (20 to 30 docks per station, Bay Wheels standard) | `stands[*].dock_capacity` |
| **Total Fleet Size ($F$)** | 100 | Bicycles | 58.8% network fill ratio | `fleet.total_bikes` |
| **Transit Corridor** | Bear Transit P-Line | Route | Perimeter campus shuttle connecting Hearst Mining, West Gate, Unit 1, Haas | `transit_routes[BEAR-P]` |
| **Rebalancing Operating Window** | 90 | Minutes | Midday lull (11:30 AM to 1:00 PM) | `rebalancing.max_shift_minutes` |
