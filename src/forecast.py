"""Planned and unplanned forecasting pipelines."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

from src.config import EVENT_DRIVEN_CAUSES, MODEL_DIR
from src.features import corridor_congestion_index


PLANNED_FEATURES = [
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "closure_flag",
    "priority_high",
    "corridor_index",
    "type_weight",
]


class ForecastEngine:
    def __init__(self) -> None:
        self.duration_model: GradientBoostingRegressor | None = None
        self.corridor_index: dict[str, float] = {}
        self.hotspot_table: pd.DataFrame | None = None
        self.type_weights = {
            "public_event": 0.95,
            "procession": 0.90,
            "protest": 0.88,
            "vip_movement": 0.85,
            "congestion": 0.75,
            "construction": 0.55,
        }

    def _planned_features(self, df: pd.DataFrame) -> pd.DataFrame:
        feats = pd.DataFrame(index=df.index)
        feats["hour_of_day"] = df["hour_of_day"]
        feats["day_of_week"] = df["day_of_week"]
        feats["is_weekend"] = df["is_weekend"]
        feats["closure_flag"] = df["requires_road_closure"].astype(float)
        feats["priority_high"] = (df["priority"] == "High").astype(float)
        feats["corridor_index"] = df["corridor"].map(self.corridor_index).fillna(0.3)
        feats["type_weight"] = df["event_cause"].map(self.type_weights).fillna(0.4)
        return feats

    def fit(self, df: pd.DataFrame) -> dict:
        self.corridor_index = corridor_congestion_index(df)
        metrics: dict = {}

        planned = df[
            (df["event_type"] == "planned") | df["event_cause"].isin(EVENT_DRIVEN_CAUSES)
        ].copy()
        planned = planned[planned["duration_hours"].notna() & (planned["duration_hours"] > 0)]
        planned = planned[planned["duration_hours"] <= 72]

        if len(planned) >= 30:
            X = self._planned_features(planned)
            y = planned["duration_hours"]
            split = int(len(X) * 0.75)
            self.duration_model = GradientBoostingRegressor(random_state=42)
            self.duration_model.fit(X.iloc[:split], y.iloc[:split])
            preds = self.duration_model.predict(X.iloc[split:])
            mae = mean_absolute_error(y.iloc[split:], preds)
            metrics["duration_mae_hours"] = round(float(mae), 2)
        else:
            metrics["duration_mae_hours"] = None

        unplanned = df[df["event_type"] == "unplanned"].copy()
        self.hotspot_table = (
            unplanned.groupby(["corridor", "hour_of_day"])
            .size()
            .reset_index(name="event_count")
            .sort_values("event_count", ascending=False)
        )
        top5 = self.hotspot_table.head(5)
        test_week = unplanned[
            unplanned["start_datetime"] >= unplanned["start_datetime"].quantile(0.8)
        ]
        if len(test_week) > 0 and len(top5) > 0:
            captured = test_week["corridor"].isin(top5["corridor"]).mean()
            metrics["hotspot_recall_top5"] = round(float(captured), 3)
        else:
            metrics["hotspot_recall_top5"] = None

        return metrics

    def predict_duration(self, event: dict) -> float:
        row = pd.DataFrame([event])
        if self.duration_model is None:
            cause = event.get("event_cause", "construction")
            defaults = {
                "public_event": 8.0,
                "procession": 4.0,
                "construction": 6.0,
                "vip_movement": 2.0,
                "protest": 3.0,
                "congestion": 2.0,
            }
            return defaults.get(cause, 3.0)

        row["requires_road_closure"] = event.get("requires_road_closure", False)
        row["priority"] = event.get("priority", "Low")
        row["corridor"] = event.get("corridor", "Non-corridor")
        row["event_cause"] = event.get("event_cause", "construction")
        row["hour_of_day"] = event.get("hour_of_day", 12)
        row["day_of_week"] = event.get("day_of_week", 0)
        row["is_weekend"] = event.get("is_weekend", 0)
        X = self._planned_features(row)
        return float(max(0.5, self.duration_model.predict(X)[0]))

    def predict_hotspots(self, hour: int | None = None, top_n: int = 5) -> list[dict]:
        if self.hotspot_table is None or self.hotspot_table.empty:
            return []
        table = self.hotspot_table
        if hour is not None:
            table = table[table["hour_of_day"] == hour]
        top = table.nlargest(top_n, "event_count")
        return [
            {
                "corridor": row["corridor"],
                "hour_of_day": int(row["hour_of_day"]),
                "expected_events": int(row["event_count"]),
                "risk_score": round(row["event_count"] / max(table["event_count"].max(), 1) * 100, 1),
            }
            for _, row in top.iterrows()
        ]

    def save(self) -> Path:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        path = MODEL_DIR / "forecast_engine.joblib"
        joblib.dump(
            {
                "duration_model": self.duration_model,
                "corridor_index": self.corridor_index,
                "hotspot_table": self.hotspot_table,
            },
            path,
        )
        return path

    @classmethod
    def load(cls) -> "ForecastEngine":
        obj = cls()
        path = MODEL_DIR / "forecast_engine.joblib"
        if path.exists():
            data = joblib.load(path)
            obj.duration_model = data["duration_model"]
            obj.corridor_index = data["corridor_index"]
            obj.hotspot_table = data["hotspot_table"]
        return obj


def save_forecast_metrics(metrics: dict) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_DIR / "forecast_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
