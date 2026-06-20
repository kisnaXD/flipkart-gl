"""Feature engineering for impact and forecast models."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import CORRIDOR_CAPACITY, TYPE_WEIGHTS


def corridor_congestion_index(df: pd.DataFrame) -> dict[str, float]:
    counts = df.groupby("corridor").size()
    max_count = counts.max() or 1
    return (counts / max_count).to_dict()


def time_of_day_factor(hour: int) -> float:
    peak_hours = {8, 9, 17, 18, 19, 20}
    if hour in peak_hours:
        return 1.0
    if 10 <= hour <= 16:
        return 0.7
    return 0.4


def corridor_capacity_factor(corridor: str) -> float:
    tier = CORRIDOR_CAPACITY.get(corridor, "medium")
    return {"high": 1.0, "medium": 0.75, "low": 0.5}.get(tier, 0.75)


def attendance_proxy(row: pd.Series) -> float:
    cause = row.get("event_cause", "")
    desc = str(row.get("description", "") or "").lower()
    if cause == "public_event":
        if any(k in desc for k in ("stadium", "cricket", "match", "concert")):
            return 1.0
        return 0.85
    if cause in ("procession", "protest"):
        return 0.9
    if cause == "vip_movement":
        return 0.8
    return 0.3


def build_impact_features(df: pd.DataFrame, corridor_index: dict[str, float] | None = None) -> pd.DataFrame:
    if corridor_index is None:
        corridor_index = corridor_congestion_index(df)

    feats = pd.DataFrame(index=df.index)
    feats["type_weight"] = df["event_cause"].map(TYPE_WEIGHTS).fillna(0.4)
    feats["corridor_index"] = df["corridor"].map(corridor_index).fillna(0.3)
    feats["corridor_capacity"] = df["corridor"].map(corridor_capacity_factor)
    feats["time_factor"] = df["hour_of_day"].map(time_of_day_factor)
    feats["closure_flag"] = df["requires_road_closure"].astype(float)
    feats["priority_high"] = (df["priority"] == "High").astype(float)
    feats["is_planned"] = (df["event_type"] == "planned").astype(float)
    feats["is_weekend"] = df["is_weekend"]
    feats["attendance_proxy"] = df.apply(attendance_proxy, axis=1)

    feats["impact_score_raw"] = (
        0.25 * feats["type_weight"]
        + 0.20 * feats["corridor_index"]
        + 0.15 * feats["time_factor"]
        + 0.15 * feats["closure_flag"]
        + 0.10 * feats["priority_high"]
        + 0.10 * feats["attendance_proxy"]
        + 0.05 * feats["corridor_capacity"]
    )
    feats["impact_score"] = (feats["impact_score_raw"] * 100).round(1)
    return feats


def score_to_tier(score: float) -> str:
    if score >= 75:
        return "Critical"
    if score >= 55:
        return "High"
    if score >= 35:
        return "Medium"
    return "Low"


def spillover_count(df: pd.DataFrame, window_hours: float = 2.0) -> pd.Series:
    """Count co-occurring events in same geohash within time window."""
    counts = pd.Series(0, index=df.index, dtype=int)
    if "geohash" not in df.columns:
        return counts

    sorted_df = df.sort_values("start_datetime")
    for geohash, group in sorted_df.groupby("geohash"):
        if geohash is None or (isinstance(geohash, float) and np.isnan(geohash)):
            continue
        times = group["start_datetime"].values
        idx = group.index.values
        for i, t in enumerate(times):
            window = pd.Timedelta(hours=window_hours)
            nearby = sum(
                1
                for j, other in enumerate(times)
                if i != j and abs(pd.Timestamp(other) - pd.Timestamp(t)) <= window
            )
            counts[idx[i]] = nearby
    return counts


def model_feature_matrix(df: pd.DataFrame, corridor_index: dict[str, float]) -> pd.DataFrame:
    impact = build_impact_features(df, corridor_index)
    spill = spillover_count(df)
    impact["spillover_count"] = spill
    impact["duration_hours"] = df["duration_hours"].fillna(df["duration_hours"].median())
    impact["event_cause"] = df["event_cause"]
    impact["corridor"] = df["corridor"]
    impact["hour_of_day"] = df["hour_of_day"]
    impact["day_of_week"] = df["day_of_week"]
    return impact
