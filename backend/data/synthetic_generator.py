"""
Synthetic Demand Generator for CampusRide Planner.
Generates realistic, calibrated micromobility trip events for UC Berkeley.
Models Non-Homogeneous Poisson Processes (NHPP) with:
1. Academic bell schedule surges (10-min window before class hours).
2. Diurnal origin-destination tides (morning residential->academic, evening reverse).
3. Weather attenuation factors.
4. Mandatory synthetic data labeling (`is_synthetic: True`).
"""
from typing import Dict, List, Optional
import math
import random
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from backend.config import load_config, load_stands, StandDefinition
from backend.data.weather_fetcher import WeatherFetcher, HourlyWeather
from backend.db.session import SessionLocal, init_db
from backend.db.models import TripRecordModel, HourlyDemandModel

logger = logging.getLogger(__name__)


@dataclass
class SyntheticTrip:
    request_time_sec: float
    origin_stand_id: str
    dest_stand_id: str
    user_type: str
    max_wait_minutes: float
    is_synthetic: bool = True


class SyntheticDemandGenerator:
    """
    Simulates spatiotemporal campus rider trip demand.
    Explicitly tags all records as synthetic.
    """

    def __init__(self, seed: Optional[int] = 42, campus_id: Optional[str] = None):
        self.config = load_config(campus_id=campus_id)
        self.stands = load_stands(campus_id=campus_id)
        self.stand_ids = [s.id for s in self.stands]
        self.seed = seed
        self.rng = random.Random(seed)
        self.weather_fetcher = WeatherFetcher()

        # Categorize stands by primary role
        self.residential_stands = [s.id for s in self.stands if s.zone == "Residential"]
        self.academic_stands = [s.id for s in self.stands if s.zone in ["Academic", "Hub"]]

    def _get_base_hourly_rate(self, hour: int) -> float:
        """Baseline hourly campus ride requests."""
        # Diurnal pattern: peaks at 08:00-09:00, 12:00-13:00, 17:00-18:00
        rates = {
            7: 15.0,
            8: 65.0,   # Morning rush 1
            9: 55.0,   # Morning rush 2
            10: 40.0,
            11: 45.0,
            12: 60.0,  # Lunch peak
            13: 50.0,
            14: 45.0,
            15: 45.0,
            16: 55.0,
            17: 68.0,  # Evening rush
            18: 50.0,
            19: 35.0,
            20: 25.0,
            21: 15.0,
            22: 8.0,
        }
        return rates.get(hour, 5.0)

    def _is_bell_transition(self, minute_of_hour: int) -> bool:
        """Classes transition between :50 and :00 (+5 mins into the next hour)."""
        return minute_of_hour >= 50 or minute_of_hour <= 5

    def _get_od_probabilities(self, hour: int) -> Dict[str, Dict[str, float]]:
        """
        Compute origin-destination transition probabilities matrix for a given hour.
        Morning: Residential -> Academic
        Midday: Academic -> Academic / Hub
        Evening: Academic -> Residential
        """
        p_matrix = {o: {d: 0.0 for d in self.stand_ids} for o in self.stand_ids}

        for o in self.stand_ids:
            for d in self.stand_ids:
                if o == d:
                    continue  # Zero intra-stand bike trips

                o_is_res = o in self.residential_stands
                d_is_acad = d in self.academic_stands

                if 7 <= hour <= 10:
                    # Morning tide
                    if o_is_res and d_is_acad:
                        weight = 5.0
                    elif not o_is_res and d_is_acad:
                        weight = 1.0
                    else:
                        weight = 0.2
                elif 11 <= hour <= 15:
                    # Midday campus circulation
                    if d_is_acad:
                        weight = 2.5
                    else:
                        weight = 1.0
                elif 16 <= hour <= 19:
                    # Evening return tide
                    if not o_is_res and not d_is_acad:
                        weight = 5.0
                    elif d in self.residential_stands:
                        weight = 4.0
                    else:
                        weight = 1.0
                else:
                    # Night
                    weight = 2.0 if d in self.residential_stands else 0.5

                p_matrix[o][d] = weight

            # Normalize row
            total = sum(p_matrix[o].values())
            if total > 0:
                for d in self.stand_ids:
                    p_matrix[o][d] /= total

        return p_matrix

    def generate_day_trips(
        self,
        date_str: str,
        weather_override: Optional[Dict[int, HourlyWeather]] = None,
        seed_offset: int = 0
    ) -> List[SyntheticTrip]:
        """
        Generate list of individual rider requests across the full operational day (07:00 to 22:00).
        """
        local_rng = random.Random(self.seed + seed_offset if self.seed is not None else None)
        weather_map = weather_override or self.weather_fetcher.get_hourly_weather(date_str)

        start_hour = self.config.simulation.operating_hours.start_hour
        end_hour = self.config.simulation.operating_hours.end_hour
        rain_penalty = self.config.weather.rain_penalty_factor

        trips: List[SyntheticTrip] = []

        for hour in range(start_hour, end_hour + 1):
            weather = weather_map.get(hour)
            base_rate = self._get_base_hourly_rate(hour)

            # Apply weather attenuation
            if weather and weather.is_rain:
                base_rate *= rain_penalty

            # Split hour into 60 1-minute Poisson slots
            od_probs = self._get_od_probabilities(hour)

            # Determine origin weights for this hour
            if 7 <= hour <= 10:
                orig_weights = [0.8 if s.zone == "Residential" else 0.2 for s in self.stands]
            elif 16 <= hour <= 19:
                orig_weights = [0.2 if s.zone == "Residential" else 0.8 for s in self.stands]
            else:
                orig_weights = [1.0 for _ in self.stands]
            
            orig_sum = sum(orig_weights)
            orig_weights = [w / orig_sum for w in orig_weights]

            for minute in range(60):
                # Class transition surge multiplier
                multiplier = 2.8 if self._is_bell_transition(minute) else 0.7
                # Minute rate lambda
                minute_lambda = (base_rate / 60.0) * multiplier

                # Poisson number of arrivals in this minute
                num_arrivals = 0
                L = math.exp(-minute_lambda)
                k = 0
                p = 1.0
                while p > L:
                    k += 1
                    p *= local_rng.random()
                num_arrivals = k - 1

                time_base_sec = (hour * 3600) + (minute * 60)

                for _ in range(num_arrivals):
                    sec_offset = local_rng.uniform(0.0, 59.9)
                    req_time = round(time_base_sec + sec_offset, 1)

                    # Pick origin stand
                    origin_id = local_rng.choices(self.stand_ids, weights=orig_weights)[0]

                    # Pick destination stand from transition matrix
                    dest_ids = [d for d in self.stand_ids if d != origin_id]
                    dest_weights = [od_probs[origin_id][d] for d in dest_ids]
                    dest_id = local_rng.choices(dest_ids, weights=dest_weights)[0]

                    user_type = local_rng.choices(["student", "faculty", "staff"], weights=[0.85, 0.10, 0.05])[0]
                    max_wait = local_rng.choice([3.0, 5.0, 7.0, 10.0])

                    trips.append(SyntheticTrip(
                        request_time_sec=req_time,
                        origin_stand_id=origin_id,
                        dest_stand_id=dest_id,
                        user_type=user_type,
                        max_wait_minutes=max_wait,
                        is_synthetic=True
                    ))

        # Sort trips chronologically
        trips.sort(key=lambda x: x.request_time_sec)
        logger.info("Generated %d synthetic trips for %s (seed=%s)", len(trips), date_str, self.seed)
        return trips

    def populate_database_history(self, start_date: str = "2026-10-01", num_days: int = 14):
        """
        Populates the database with historical synthetic training/test data.
        Labels all rows with `is_synthetic = True`.
        """
        init_db()
        db = SessionLocal()
        dt_start = datetime.strptime(start_date, "%Y-%m-%d")

        try:
            for day_idx in range(num_days):
                curr_date = (dt_start + timedelta(days=day_idx)).strftime("%Y-%m-%d")
                trips = self.generate_day_trips(curr_date, seed_offset=day_idx * 100)

                # Persist trips
                trip_models = [
                    TripRecordModel(
                        date=curr_date,
                        request_time_sec=t.request_time_sec,
                        origin_stand_id=t.origin_stand_id,
                        dest_stand_id=t.dest_stand_id,
                        user_type=t.user_type,
                        max_wait_minutes=t.max_wait_minutes,
                        is_synthetic=True
                    )
                    for t in trips
                ]
                db.bulk_save_objects(trip_models)

                # Aggregate into hourly demand
                weather = self.weather_fetcher.get_hourly_weather(curr_date)
                hourly_counts: Dict[int, Dict[str, Dict[str, int]]] = {
                    h: {s: {"pickups": 0, "dropoffs": 0} for s in self.stand_ids}
                    for h in range(24)
                }

                for t in trips:
                    h = int(t.request_time_sec // 3600)
                    if 0 <= h < 24:
                        hourly_counts[h][t.origin_stand_id]["pickups"] += 1
                        hourly_counts[h][t.dest_stand_id]["dropoffs"] += 1

                demand_models = []
                for h in range(7, 23):
                    w = weather.get(h)
                    for s_id in self.stand_ids:
                        demand_models.append(HourlyDemandModel(
                            date=curr_date,
                            hour=h,
                            stand_id=s_id,
                            pickups_actual=hourly_counts[h][s_id]["pickups"],
                            dropoffs_actual=hourly_counts[h][s_id]["dropoffs"],
                            temp_celsius=w.temp_celsius if w else 16.0,
                            precipitation_mm=w.precipitation_mm if w else 0.0
                        ))

                db.bulk_save_objects(demand_models)
                db.commit()

            logger.info("Successfully populated %d days of synthetic history in database.", num_days)
        finally:
            db.close()
