"""Load and clean Astram event data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import EVENT_DRIVEN_CAUSES, PROCESSED_DIR, RAW_CSV


def _parse_dt(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")


def _duration_hours(start: pd.Series, end: pd.Series) -> pd.Series:
    delta = (end - start).dt.total_seconds() / 3600.0
    return delta.where(delta >= 0)


def _geohash(lat: float, lon: float, precision: int = 6) -> str | None:
    if pd.isna(lat) or pd.isna(lon) or lat == 0 or lon == 0:
        return None
    base32 = "0123456789bcdefghjkmnpqrstuvwxyz"
    lat_interval = [-90.0, 90.0]
    lon_interval = [-180.0, 180.0]
    geohash = []
    bits = [16, 8, 4, 2, 1]
    bit = 0
    ch = 0
    even = True
    while len(geohash) < precision:
        if even:
            mid = (lon_interval[0] + lon_interval[1]) / 2
            if lon > mid:
                ch |= bits[bit]
                lon_interval[0] = mid
            else:
                lon_interval[1] = mid
        else:
            mid = (lat_interval[0] + lat_interval[1]) / 2
            if lat > mid:
                ch |= bits[bit]
                lat_interval[0] = mid
            else:
                lat_interval[1] = mid
        even = not even
        if bit < 4:
            bit += 1
        else:
            geohash.append(base32[ch])
            bit = 0
            ch = 0
    return "".join(geohash)


def load_raw() -> pd.DataFrame:
    return pd.read_csv(RAW_CSV, low_memory=False)


def clean_events(df: pd.DataFrame | None = None) -> pd.DataFrame:
    if df is None:
        df = load_raw()

    out = df.copy()
    for col in [
        "start_datetime",
        "end_datetime",
        "created_date",
        "modified_datetime",
        "closed_datetime",
        "resolved_datetime",
    ]:
        if col in out.columns:
            out[col] = _parse_dt(out[col])

    out["latitude"] = pd.to_numeric(out["latitude"], errors="coerce")
    out["longitude"] = pd.to_numeric(out["longitude"], errors="coerce")
    out["endlatitude"] = pd.to_numeric(out.get("endlatitude"), errors="coerce")
    out["endlongitude"] = pd.to_numeric(out.get("endlongitude"), errors="coerce")

    out["requires_road_closure"] = (
        out["requires_road_closure"].astype(str).str.upper().eq("TRUE")
    )
    out["corridor"] = out["corridor"].fillna("Non-corridor")
    out["event_cause"] = out["event_cause"].fillna("others")
    out["event_type"] = out["event_type"].fillna("unplanned")
    out["priority"] = out["priority"].fillna("Low")
    out["zone"] = out["zone"].fillna("Unknown")
    out["junction"] = out["junction"].fillna("Unknown")

    end_time = out["end_datetime"].fillna(out["closed_datetime"]).fillna(out["resolved_datetime"])
    out["duration_hours"] = _duration_hours(out["start_datetime"], end_time)

    out["hour_of_day"] = out["start_datetime"].dt.hour
    out["day_of_week"] = out["start_datetime"].dt.dayofweek
    out["is_weekend"] = out["day_of_week"].isin([5, 6]).astype(int)
    out["month"] = out["start_datetime"].dt.month

    out["geohash"] = [
        _geohash(lat, lon) for lat, lon in zip(out["latitude"], out["longitude"])
    ]

    out["is_event_driven"] = out["event_cause"].isin(EVENT_DRIVEN_CAUSES)
    out["impact_tier"] = _derive_impact_tier(out)

    return out


def _derive_impact_tier(df: pd.DataFrame) -> pd.Series:
    score = pd.Series(0.0, index=df.index)
    score += df["priority"].map({"High": 2.0, "Low": 0.5}).fillna(0.5)
    score += df["requires_road_closure"].astype(float) * 2.0
    score += df["event_cause"].map(
        {
            "public_event": 2.5,
            "procession": 2.2,
            "protest": 2.0,
            "vip_movement": 1.8,
            "congestion": 1.5,
            "construction": 1.0,
        }
    ).fillna(0.5)

    dur = df["duration_hours"].fillna(0)
    score += dur.clip(upper=24) / 6.0

    tiers = pd.cut(
        score,
        bins=[-1, 2.5, 4.5, 6.5, 100],
        labels=["Low", "Medium", "High", "Critical"],
    )
    return tiers.astype(str)


def save_processed(df: pd.DataFrame) -> Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / "events_clean.parquet"
    df.to_parquet(path, index=False)
    event_driven = df[df["is_event_driven"]].copy()
    event_driven.to_parquet(PROCESSED_DIR / "events_event_driven.parquet", index=False)
    return path
