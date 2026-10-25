"""
Feature Engineering Pipeline for Campus Spatiotemporal Demand Forecasting.
Extracts cyclical temporal features, academic schedule indicators,
weather conditions, and stand geographic role interactions.
"""
from typing import List, Dict, Tuple, Optional
import math
from datetime import datetime
import pandas as pd
import numpy as np
from backend.config import load_stands, StandDefinition


class DemandFeaturePipeline:
    """
    Transforms raw hourly stand logs into machine-learning feature vectors.
    """

    def __init__(self, stands: Optional[List[StandDefinition]] = None):
        self.stands = stands or load_stands()
        self.stand_ids = [s.id for s in self.stands]
        self.stand_map = {s.id: s for s in self.stands}

    def build_feature_row(
        self,
        date_str: str,
        hour: int,
        stand_id: str,
        temp_celsius: float = 16.0,
        precipitation_mm: float = 0.0
    ) -> Dict[str, float]:
        """
        Builds a single feature dictionary for a stand at a given hour.
        """
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        weekday = dt.weekday()  # 0=Monday, 6=Sunday
        is_weekend = 1.0 if weekday >= 5 else 0.0

        # Cyclical hour encoding
        hour_rad = 2.0 * math.pi * hour / 24.0
        hour_sin = math.sin(hour_rad)
        hour_cos = math.cos(hour_rad)

        # Campus schedule indicators
        is_morning_rush = 1.0 if (8 <= hour <= 10) else 0.0
        is_lunch = 1.0 if (12 <= hour <= 13) else 0.0
        is_evening_rush = 1.0 if (16 <= hour <= 19) else 0.0
        is_night = 1.0 if (hour >= 21 or hour <= 6) else 0.0

        # Weather indicators
        is_rain = 1.0 if precipitation_mm > 0.1 else 0.0
        rain_rush_interaction = is_rain * (is_morning_rush + is_evening_rush)

        stand_def = self.stand_map.get(stand_id)
        is_residential = 1.0 if (stand_def and stand_def.zone == "Residential") else 0.0
        is_academic = 1.0 if (stand_def and stand_def.zone in ["Academic", "Hub"]) else 0.0

        features = {
            "hour": float(hour),
            "hour_sin": hour_sin,
            "hour_cos": hour_cos,
            "weekday": float(weekday),
            "is_weekend": is_weekend,
            "is_morning_rush": is_morning_rush,
            "is_lunch": is_lunch,
            "is_evening_rush": is_evening_rush,
            "is_night": is_night,
            "temp_celsius": float(temp_celsius),
            "precipitation_mm": float(precipitation_mm),
            "is_rain": is_rain,
            "rain_rush_interaction": rain_rush_interaction,
            "is_residential": is_residential,
            "is_academic": is_academic,
            "res_morning_surge": is_residential * is_morning_rush,
            "acad_evening_surge": is_academic * is_evening_rush,
            "res_evening_sink": is_residential * is_evening_rush,
            "acad_morning_sink": is_academic * is_morning_rush,
        }

        # One-hot stand ID
        for s_id in self.stand_ids:
            features[f"stand_{s_id}"] = 1.0 if stand_id == s_id else 0.0

        return features

    def transform_dataframe(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
        """
        Converts a dataframe with columns [date, hour, stand_id, temp_celsius, precipitation_mm, pickups_actual, dropoffs_actual]
        into (X, y_pickups, y_dropoffs).
        """
        feature_rows = []
        for _, row in df.iterrows():
            feat = self.build_feature_row(
                date_str=str(row["date"]),
                hour=int(row["hour"]),
                stand_id=str(row["stand_id"]),
                temp_celsius=float(row.get("temp_celsius", 16.0)),
                precipitation_mm=float(row.get("precipitation_mm", 0.0))
            )
            feature_rows.append(feat)

        X = pd.DataFrame(feature_rows)
        y_pickups = df["pickups_actual"].astype(float) if "pickups_actual" in df.columns else pd.Series()
        y_dropoffs = df["dropoffs_actual"].astype(float) if "dropoffs_actual" in df.columns else pd.Series()

        return X, y_pickups, y_dropoffs
