"""
Weather Ingestion Module using Open-Meteo Free API.
Fetches hourly temperature and precipitation for UC Berkeley, with local SQLite caching.
Includes deterministic Berkeley microclimate fallback for offline execution.
"""
from typing import Dict, Optional
import json
import sqlite3
import time
import math
import logging
from dataclasses import dataclass
import requests
from backend.config import load_config

logger = logging.getLogger(__name__)


@dataclass
class HourlyWeather:
    hour: int
    temp_celsius: float
    precipitation_mm: float
    rain_probability_pct: int
    is_rain: bool


class WeatherFetcher:
    """
    Fetches and caches hourly weather data from Open-Meteo.
    Zero paid API keys required.
    """

    def __init__(self, db_path: Optional[str] = None):
        config = load_config()
        self.api_url = config.weather.api_url
        self.lat = config.weather.latitude
        self.lon = config.weather.longitude
        self.ttl_seconds = config.weather.cache_ttl_hours * 3600
        self.db_path = db_path or config.weather.cache_db_path
        self._init_cache_db()

    def _init_cache_db(self):
        """Initialize local SQLite cache table for weather responses."""
        import os
        from pathlib import Path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS weather_cache (
                    date TEXT PRIMARY KEY,
                    payload JSON NOT NULL,
                    cached_at INTEGER NOT NULL
                )
            """)
        conn.close()

    def _get_from_cache(self, date_str: str) -> Optional[dict]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT payload, cached_at FROM weather_cache WHERE date = ?",
                (date_str,)
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                payload_json, cached_at = row
                if (time.time() - cached_at) < self.ttl_seconds:
                    return json.loads(payload_json)
        except Exception as e:
            logger.warning("Cache lookup error: %s", e)
        return None

    def _save_to_cache(self, date_str: str, payload: dict):
        try:
            conn = sqlite3.connect(self.db_path)
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO weather_cache (date, payload, cached_at) VALUES (?, ?, ?)",
                    (date_str, json.dumps(payload), int(time.time()))
                )
            conn.close()
        except Exception as e:
            logger.warning("Cache write error: %s", e)

    def get_hourly_weather(self, date_str: str) -> Dict[int, HourlyWeather]:
        """
        Fetch hourly weather for a specific YYYY-MM-DD date.
        Returns a dictionary mapping hour (0-23) to HourlyWeather dataclass.
        """
        # 1. Check local cache
        cached = self._get_from_cache(date_str)
        if cached:
            return self._parse_payload(cached, date_str)

        # 2. Query Open-Meteo free API
        try:
            params = {
                "latitude": self.lat,
                "longitude": self.lon,
                "hourly": "temperature_2m,precipitation_probability,precipitation",
                "timezone": "America/Los_Angeles",
                "start_date": date_str,
                "end_date": date_str
            }
            resp = requests.get(self.api_url, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                self._save_to_cache(date_str, data)
                return self._parse_payload(data, date_str)
        except Exception as e:
            logger.warning("Open-Meteo API request failed: %s. Using Berkeley microclimate model.", e)

        # 3. Fallback to calibrated Berkeley microclimate
        return self._generate_fallback_weather(date_str)

    def _parse_payload(self, data: dict, date_str: str) -> Dict[int, HourlyWeather]:
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        precips = hourly.get("precipitation", [])
        probs = hourly.get("precipitation_probability", [])

        result = {}
        for i, t in enumerate(times):
            hour = int(t.split("T")[1].split(":")[0])
            temp = float(temps[i]) if i < len(temps) else 16.0
            precip = float(precips[i]) if i < len(precips) else 0.0
            prob = int(probs[i]) if i < len(probs) else 0
            result[hour] = HourlyWeather(
                hour=hour,
                temp_celsius=temp,
                precipitation_mm=precip,
                rain_probability_pct=prob,
                is_rain=(precip > 0.1)
            )
        return result

    def _generate_fallback_weather(self, date_str: str) -> Dict[int, HourlyWeather]:
        """
        Calibrated diurnal temperature curve for Berkeley, CA (average highs ~18-21°C, lows ~10-12°C).
        """
        result = {}
        for hour in range(24):
            # Diurnal temperature cycle peaking at 15:00
            temp = 12.0 + 8.0 * max(0.0, math.sin(math.pi * (hour - 6) / 12)) if 6 <= hour <= 18 else 11.0
            result[hour] = HourlyWeather(
                hour=hour,
                temp_celsius=round(temp, 1),
                precipitation_mm=0.0,
                rain_probability_pct=5,
                is_rain=False
            )
        return result
