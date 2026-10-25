"""
Demand Forecaster for CampusRide Planner.
Compares a gradient boosted regressor (LightGBM/Ridge) against a simple historical average baseline.
Evaluates on unseen test days only, reporting MAE and RMSE.
"""
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from backend.config import load_stands, StandDefinition
from backend.forecast.feature_pipeline import DemandFeaturePipeline

logger = logging.getLogger(__name__)


@dataclass
class ForecastMetrics:
    mae: float
    rmse: float


@dataclass
class ForecastComparisonReport:
    model_name: str
    baseline_pickup_metrics: ForecastMetrics
    model_pickup_metrics: ForecastMetrics
    pickup_mae_improvement_pct: float
    baseline_dropoff_metrics: ForecastMetrics
    model_dropoff_metrics: ForecastMetrics
    dropoff_mae_improvement_pct: float
    num_train_samples: int
    num_test_samples: int


class HistoricalAverageBaseline:
    """
    Baseline model that predicts the historical sample average
    for each (stand_id, hour) combination.
    """

    def __init__(self):
        self.pickup_lookup: Dict[Tuple[str, int], float] = {}
        self.dropoff_lookup: Dict[Tuple[str, int], float] = {}
        self.global_pickup_mean: float = 0.0
        self.global_dropoff_mean: float = 0.0

    def fit(self, df_train: pd.DataFrame):
        grouped = df_train.groupby(["stand_id", "hour"])[["pickups_actual", "dropoffs_actual"]].mean()
        self.pickup_lookup = grouped["pickups_actual"].to_dict()
        self.dropoff_lookup = grouped["dropoffs_actual"].to_dict()
        self.global_pickup_mean = float(df_train["pickups_actual"].mean()) if not df_train.empty else 0.0
        self.global_dropoff_mean = float(df_train["dropoffs_actual"].mean()) if not df_train.empty else 0.0

    def predict(self, df_test: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        preds_p = []
        preds_d = []
        for _, row in df_test.iterrows():
            key = (str(row["stand_id"]), int(row["hour"]))
            preds_p.append(self.pickup_lookup.get(key, self.global_pickup_mean))
            preds_d.append(self.dropoff_lookup.get(key, self.global_dropoff_mean))
        return np.array(preds_p), np.array(preds_d)


class MLDemandForecaster:
    """
    Trained spatiotemporal regressor for campus bike pickups and dropoffs.
    Uses Scikit-Learn HistGradientBoostingRegressor (LightGBM-style histogram gradient boosting).
    """

    def __init__(self, stands: Optional[List[StandDefinition]] = None):
        self.stands = stands or load_stands()
        self.pipeline = DemandFeaturePipeline(self.stands)
        self.model_pickups = None
        self.model_dropoffs = None
        self.model_name = "HistGradientBoosting"
        self._init_models()

    def _init_models(self):
        from sklearn.ensemble import HistGradientBoostingRegressor
        self.model_pickups = HistGradientBoostingRegressor(
            max_iter=100,
            learning_rate=0.08,
            max_depth=6,
            min_samples_leaf=5,
            random_state=42
        )
        self.model_dropoffs = HistGradientBoostingRegressor(
            max_iter=100,
            learning_rate=0.08,
            max_depth=6,
            min_samples_leaf=5,
            random_state=42
        )
        self.model_name = "HistGradientBoosting"

    def fit(self, df_train: pd.DataFrame):
        """Fit ML models on feature-engineered training set."""
        X_train, y_pickups, y_dropoffs = self.pipeline.transform_dataframe(df_train)
        self.model_pickups.fit(X_train, y_pickups)
        self.model_dropoffs.fit(X_train, y_dropoffs)
        logger.info("Successfully trained %s models for pickups and dropoffs.", self.model_name)

    def predict(self, df_input: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Predict pickups and dropoffs, clamping negative values to zero."""
        X, _, _ = self.pipeline.transform_dataframe(df_input)
        raw_p = self.model_pickups.predict(X)
        raw_d = self.model_dropoffs.predict(X)
        preds_p = np.clip(raw_p, 0.0, None)
        preds_d = np.clip(raw_d, 0.0, None)
        return preds_p, preds_d

    def predict_day(
        self,
        date_str: str,
        weather_map: Optional[dict] = None
    ) -> Dict[str, Dict[int, Tuple[float, float]]]:
        """
        Generate predictions for all stands and all operational hours (07:00 to 22:00) on a given date.
        Returns: {stand_id: {hour: (predicted_pickups, predicted_dropoffs)}}
        """
        rows = []
        for s in self.stands:
            for h in range(7, 23):
                temp = 16.0
                precip = 0.0
                if weather_map and h in weather_map:
                    w = weather_map[h]
                    temp = getattr(w, "temp_celsius", 16.0)
                    precip = getattr(w, "precipitation_mm", 0.0)

                rows.append({
                    "date": date_str,
                    "hour": h,
                    "stand_id": s.id,
                    "temp_celsius": temp,
                    "precipitation_mm": precip
                })

        df_query = pd.DataFrame(rows)
        preds_p, preds_d = self.predict(df_query)

        result: Dict[str, Dict[int, Tuple[float, float]]] = {s.id: {} for s in self.stands}
        for idx, row in df_query.iterrows():
            s_id = row["stand_id"]
            h = int(row["hour"])
            result[s_id][h] = (round(float(preds_p[idx]), 2), round(float(preds_d[idx]), 2))

        return result


def evaluate_forecast_pipeline(
    df_all: pd.DataFrame,
    test_days: int = 3,
    stands: Optional[List[StandDefinition]] = None,
) -> Tuple[MLDemandForecaster, HistoricalAverageBaseline, ForecastComparisonReport]:
    """
    Splits data chronologically: earlier days for training, last N days for unseen testing.
    Fits both models, evaluates performance, and outputs comparison metrics.
    """
    unique_dates = sorted(df_all["date"].unique())
    if len(unique_dates) <= test_days:
        split_idx = max(1, len(unique_dates) // 2)
    else:
        split_idx = len(unique_dates) - test_days

    train_dates = set(unique_dates[:split_idx])
    test_dates = set(unique_dates[split_idx:])

    df_train = df_all[df_all["date"].isin(train_dates)].reset_index(drop=True)
    df_test = df_all[df_all["date"].isin(test_dates)].reset_index(drop=True)

    # 1. Fit baseline
    baseline = HistoricalAverageBaseline()
    baseline.fit(df_train)
    b_pred_p, b_pred_d = baseline.predict(df_test)

    # 2. Fit ML model
    ml_model = MLDemandForecaster(stands=stands)
    ml_model.fit(df_train)
    m_pred_p, m_pred_d = ml_model.predict(df_test)

    # 3. Ground truth
    y_test_p = df_test["pickups_actual"].values
    y_test_d = df_test["dropoffs_actual"].values

    # 4. Metrics
    b_p_mae = float(mean_absolute_error(y_test_p, b_pred_p))
    b_p_rmse = float(root_mean_squared_error(y_test_p, b_pred_p))
    m_p_mae = float(mean_absolute_error(y_test_p, m_pred_p))
    m_p_rmse = float(root_mean_squared_error(y_test_p, m_pred_p))

    b_d_mae = float(mean_absolute_error(y_test_d, b_pred_d))
    b_d_rmse = float(root_mean_squared_error(y_test_d, b_pred_d))
    m_d_mae = float(mean_absolute_error(y_test_d, m_pred_d))
    m_d_rmse = float(root_mean_squared_error(y_test_d, m_pred_d))

    p_imp = round(((b_p_mae - m_p_mae) / b_p_mae) * 100.0, 2) if b_p_mae > 0 else 0.0
    d_imp = round(((b_d_mae - m_d_mae) / b_d_mae) * 100.0, 2) if b_d_mae > 0 else 0.0

    report = ForecastComparisonReport(
        model_name=ml_model.model_name,
        baseline_pickup_metrics=ForecastMetrics(mae=round(b_p_mae, 3), rmse=round(b_p_rmse, 3)),
        model_pickup_metrics=ForecastMetrics(mae=round(m_p_mae, 3), rmse=round(m_p_rmse, 3)),
        pickup_mae_improvement_pct=p_imp,
        baseline_dropoff_metrics=ForecastMetrics(mae=round(b_d_mae, 3), rmse=round(b_d_rmse, 3)),
        model_dropoff_metrics=ForecastMetrics(mae=round(m_d_mae, 3), rmse=round(m_d_rmse, 3)),
        dropoff_mae_improvement_pct=d_imp,
        num_train_samples=len(df_train),
        num_test_samples=len(df_test)
    )

    return ml_model, baseline, report
