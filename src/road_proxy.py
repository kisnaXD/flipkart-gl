"""Snap to roads using historical Astram event coordinates as proxy road points."""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
import pandas as pd

from src.config import PROCESSED_DIR


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@lru_cache(maxsize=1)
def _road_proxy_points() -> pd.DataFrame:
    path = PROCESSED_DIR / "events_clean.parquet"
    if not path.exists():
        return pd.DataFrame(columns=["latitude", "longitude", "corridor", "event_cause"])
    df = pd.read_parquet(path, columns=["latitude", "longitude", "corridor", "event_cause"])
    df = df.dropna(subset=["latitude", "longitude"])
    df = df[(df["latitude"] != 0) & (df["longitude"] != 0)]
    return df


def snap_to_historical_road(lat: float, lon: float) -> dict:
    df = _road_proxy_points()
    if df.empty:
        raise ValueError("No historical road proxy points")

    dists = df.apply(
        lambda r: _haversine_m(lat, lon, r["latitude"], r["longitude"]), axis=1
    )
    idx = dists.idxmin()
    row = df.loc[idx]
    return {
        "node_id": int(idx),
        "latitude": round(float(row["latitude"]), 6),
        "longitude": round(float(row["longitude"]), 6),
        "street_name": f"Near {row['corridor']} (historical incident point)",
        "highway_type": "proxy",
    }


def find_barricades_from_history(
    lat: float,
    lon: float,
    min_dist_m: float = 180,
    max_dist_m: float = 650,
    max_barricades: int = 4,
) -> list[dict]:
    df = _road_proxy_points()
    if df.empty:
        raise ValueError("No historical road proxy points")

    snap = snap_to_historical_road(lat, lon)
    s_lat, s_lon = snap["latitude"], snap["longitude"]

    df = df.copy()
    df["dist_from_event"] = df.apply(
        lambda r: _haversine_m(s_lat, s_lon, r["latitude"], r["longitude"]), axis=1
    )
    candidates = df[(df["dist_from_event"] >= min_dist_m) & (df["dist_from_event"] <= max_dist_m)]

    if candidates.empty:
        # Expand search slightly
        candidates = df[(df["dist_from_event"] >= min_dist_m * 0.7) & (df["dist_from_event"] <= max_dist_m * 1.3)]

    if candidates.empty:
        raise ValueError("No historical points in barricade range")

    candidates = candidates.sort_values("dist_from_event")

    # Spread by angle quadrant from event
    def bearing(row):
        return (math.degrees(math.atan2(
            row["longitude"] - s_lon,
            row["latitude"] - s_lat,
        )) + 360) % 360

    candidates = candidates.copy()
    candidates["bearing"] = candidates.apply(bearing, axis=1)
    candidates["quad"] = pd.cut(
        candidates["bearing"],
        bins=[0, 90, 180, 270, 360],
        labels=["N", "E", "S", "W"],
        include_lowest=True,
    )

    selected = []
    for quad in ["N", "E", "S", "W"]:
        sub = candidates[candidates["quad"] == quad]
        if not sub.empty:
            row = sub.iloc[0]
            selected.append(
                {
                    "node_id": int(sub.index[0]),
                    "latitude": round(float(row["latitude"]), 6),
                    "longitude": round(float(row["longitude"]), 6),
                    "network_distance_m": round(float(row["dist_from_event"]), 0),
                    "street_name": f"{row['corridor']} corridor",
                    "role": "intersection_control",
                    "quadrant": quad,
                }
            )

    for i, pt in enumerate(selected[:max_barricades]):
        pt["id"] = f"B{i + 1}"

    return selected[:max_barricades]


def find_routes_from_barricades(
    barricade_points: list[dict],
    event_lat: float,
    event_lon: float,
    max_routes: int = 2,
) -> list[dict]:
    """Build simple road-following proxy routes via historical corridor points."""
    df = _road_proxy_points()
    routes = []

    for i, barrier in enumerate(barricade_points[:max_routes]):
        sub = df.copy()
        sub["dist"] = sub.apply(
            lambda r: _haversine_m(barrier["latitude"], barrier["longitude"], r["latitude"], r["longitude"]),
            axis=1,
        )
        far = sub[sub["dist"] > 600].nsmallest(3, "dist")
        if far.empty:
            far = sub.nsmallest(1, "dist")

        target = far.iloc[-1]
        geometry = [
            [barrier["latitude"], barrier["longitude"]],
            [round(float(target["latitude"]), 6), round(float(target["longitude"]), 6)],
        ]
        length_m = _haversine_m(geometry[0][0], geometry[0][1], geometry[1][0], geometry[1][1])

        routes.append(
            {
                "route_id": f"ALT-{i + 1}",
                "corridor": str(target["corridor"]),
                "start": {"latitude": geometry[0][0], "longitude": geometry[0][1]},
                "end": {"latitude": geometry[1][0], "longitude": geometry[1][1]},
                "geometry": geometry,
                "length_m": round(length_m, 0),
                "instruction": f"Divert toward {target['corridor']} via known incident corridor ({int(length_m)}m)",
            }
        )

    return routes
