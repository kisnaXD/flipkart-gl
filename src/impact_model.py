"""Impact scoring and tier classification."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from src.config import MODEL_DIR
from src.features import build_impact_features, corridor_congestion_index, score_to_tier


FEATURE_COLS = [
    "type_weight",
    "corridor_index",
    "corridor_capacity",
    "time_factor",
    "closure_flag",
    "priority_high",
    "is_planned",
    "is_weekend",
    "attendance_proxy",
    "impact_score_raw",
]


class ImpactModel:
    def __init__(self) -> None:
        self.corridor_index: dict[str, float] = {}
        self.tier_model: GradientBoostingClassifier | None = None
        self.tier_encoder = LabelEncoder()

    def fit(self, df: pd.DataFrame) -> dict:
        self.corridor_index = corridor_congestion_index(df)
        feats = build_impact_features(df, self.corridor_index)
        labeled = df["impact_tier"].notna()
        X = feats.loc[labeled, FEATURE_COLS].fillna(0)
        y = self.tier_encoder.fit_transform(df.loc[labeled, "impact_tier"])

        if len(np.unique(y)) < 2 or len(X) < 20:
            self.tier_model = None
            return {"tier_accuracy": None, "note": "insufficient labeled data for classifier"}

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=42, stratify=y
        )
        self.tier_model = GradientBoostingClassifier(random_state=42)
        self.tier_model.fit(X_train, y_train)
        preds = self.tier_model.predict(X_test)
        acc = accuracy_score(y_test, preds)
        report = classification_report(
            y_test, preds, target_names=self.tier_encoder.classes_, output_dict=True
        )
        return {"tier_accuracy": round(acc, 3), "classification_report": report}

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        feats = build_impact_features(df, self.corridor_index)
        out = df[["id", "event_type", "event_cause", "corridor", "latitude", "longitude"]].copy()
        out["impact_score"] = feats["impact_score"]
        out["predicted_tier"] = feats["impact_score"].map(score_to_tier)

        if self.tier_model is not None:
            X = feats[FEATURE_COLS].fillna(0)
            ml_tier = self.tier_encoder.inverse_transform(self.tier_model.predict(X))
            out["ml_tier"] = ml_tier
            out["predicted_tier"] = out["ml_tier"]

        return out

    def save(self, path: Path | None = None) -> Path:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        path = path or MODEL_DIR / "impact_model.joblib"
        joblib.dump(
            {
                "corridor_index": self.corridor_index,
                "tier_model": self.tier_model,
                "tier_encoder": self.tier_encoder,
            },
            path,
        )
        meta = MODEL_DIR / "impact_metrics.json"
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "ImpactModel":
        path = path or MODEL_DIR / "impact_model.joblib"
        obj = cls()
        if path.exists():
            data = joblib.load(path)
            obj.corridor_index = data["corridor_index"]
            obj.tier_model = data["tier_model"]
            obj.tier_encoder = data["tier_encoder"]
        return obj


def save_metrics(metrics: dict) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_DIR / "impact_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
