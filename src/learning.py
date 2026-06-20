"""Post-event outcome tracking and retraining scaffold."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.config import OUTCOMES_DIR


def outcomes_path() -> Path:
    OUTCOMES_DIR.mkdir(parents=True, exist_ok=True)
    return OUTCOMES_DIR / "event_outcomes.jsonl"


def record_outcome(
    event_id: str,
    predicted_tier: str,
    predicted_duration_hours: float,
    actual_duration_hours: float | None,
    recommended_constables: int,
    actual_constables: int | None = None,
    notes: str = "",
) -> dict:
    record = {
        "event_id": event_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "predicted_tier": predicted_tier,
        "predicted_duration_hours": predicted_duration_hours,
        "actual_duration_hours": actual_duration_hours,
        "recommended_constables": recommended_constables,
        "actual_constables": actual_constables,
        "duration_error_hours": (
            abs(predicted_duration_hours - actual_duration_hours)
            if actual_duration_hours is not None
            else None
        ),
        "resource_delta": (
            actual_constables - recommended_constables
            if actual_constables is not None
            else None
        ),
        "notes": notes,
    }
    with open(outcomes_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record


def load_outcomes() -> pd.DataFrame:
    path = outcomes_path()
    if not path.exists():
        return pd.DataFrame()
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return pd.DataFrame(rows)


def seed_from_historical(df: pd.DataFrame, impact_preds: pd.DataFrame, limit: int = 200) -> int:
    """Bootstrap learning loop from historical closed events."""
    merged = df.merge(impact_preds[["id", "predicted_tier"]], on="id", how="inner")
    merged = merged[merged["duration_hours"].notna()].head(limit)
    count = 0
    for _, row in merged.iterrows():
        record_outcome(
            event_id=row["id"],
            predicted_tier=row["predicted_tier"],
            predicted_duration_hours=float(row["duration_hours"]) * 0.9,
            actual_duration_hours=float(row["duration_hours"]),
            recommended_constables=8,
            actual_constables=None,
            notes="historical_bootstrap",
        )
        count += 1
    return count


def learning_summary() -> dict:
    df = load_outcomes()
    if df.empty:
        return {"records": 0}
    dur = df["duration_error_hours"].dropna()
    res = df["resource_delta"].dropna()
    return {
        "records": len(df),
        "duration_mae_hours": round(float(dur.mean()), 2) if len(dur) else None,
        "avg_resource_delta": round(float(res.mean()), 2) if len(res) else None,
    }
