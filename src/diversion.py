"""Diversion and barricade placement using OpenStreetMap road network."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

from geopy.distance import geodesic

logger = logging.getLogger(__name__)


@dataclass
class DiversionPlan:
    affected_radius_m: float
    barricade_points: list[dict]
    alternate_routes: list[dict]
    estimated_delay_minutes: float
    notes: str
    road_network_used: bool = False
    planner_mode: str = "unknown"
    snapped_event: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _radius_for_event(event_cause: str, requires_closure: bool) -> float:
    if requires_closure:
        return 800.0
    return {
        "public_event": 1000.0,
        "procession": 600.0,
        "protest": 500.0,
        "vip_movement": 400.0,
        "construction": 300.0,
        "congestion": 350.0,
    }.get(event_cause, 300.0)


def _estimate_delay(impact_tier: str, requires_closure: bool, corridor: str, route_count: int) -> float:
    tier_delay = {"Low": 5, "Medium": 12, "High": 22, "Critical": 35}.get(impact_tier, 12)
    closure_delay = 8 if requires_closure else 0
    cap_factor = 1.2 if corridor.startswith("ORR") else 1.0
    route_factor = 0.9 if route_count >= 2 else 1.1
    return round((tier_delay + closure_delay) * cap_factor * route_factor, 1)


def _plan_with_osm(
    latitude: float,
    longitude: float,
    corridor: str,
    event_cause: str,
    requires_road_closure: bool,
    impact_tier: str,
    radius: float,
) -> DiversionPlan:
    from src.road_network import find_barricade_points, find_diversion_routes, snap_to_road

    snapped = snap_to_road(latitude, longitude)
    snap_lat, snap_lon = snapped["latitude"], snapped["longitude"]

    min_dist = 150 if event_cause in ("construction", "congestion") else 200
    max_dist = min(radius * 0.75, 700)

    barricade_points = find_barricade_points(
        snap_lat, snap_lon, min_dist_m=min_dist, max_dist_m=max_dist
    )
    if not barricade_points:
        raise ValueError("No road intersections found")

    disruption_radius = min(radius * 0.45, 450)
    alternate_routes = find_diversion_routes(
        snap_lat, snap_lon, barricade_points, disruption_radius_m=disruption_radius
    )

    streets = ", ".join({b["street_name"] for b in barricade_points if b.get("street_name")})
    return DiversionPlan(
        affected_radius_m=radius,
        barricade_points=barricade_points,
        alternate_routes=alternate_routes,
        estimated_delay_minutes=_estimate_delay(
            impact_tier, requires_road_closure, corridor, len(alternate_routes)
        ),
        notes=(
            f"OpenStreetMap drive network: event on {snapped['street_name']}. "
            f"Barricades at road intersections ({streets}). "
            f"Diversions follow actual road geometry, avoiding {int(disruption_radius)}m disruption zone."
        ),
        road_network_used=True,
        planner_mode="osm",
        snapped_event=snapped,
    )


def _plan_with_history(
    latitude: float,
    longitude: float,
    corridor: str,
    event_cause: str,
    requires_road_closure: bool,
    impact_tier: str,
    radius: float,
) -> DiversionPlan:
    from src.road_proxy import (
        find_barricades_from_history,
        find_routes_from_barricades,
        snap_to_historical_road,
    )

    snapped = snap_to_historical_road(latitude, longitude)
    min_dist = 150 if event_cause in ("construction", "congestion") else 200
    max_dist = min(radius * 0.75, 650)

    barricade_points = find_barricades_from_history(
        snapped["latitude"], snapped["longitude"], min_dist, max_dist
    )
    alternate_routes = find_routes_from_barricades(
        barricade_points, snapped["latitude"], snapped["longitude"]
    )

    streets = ", ".join({b["street_name"] for b in barricade_points})
    return DiversionPlan(
        affected_radius_m=radius,
        barricade_points=barricade_points,
        alternate_routes=alternate_routes,
        estimated_delay_minutes=_estimate_delay(
            impact_tier, requires_road_closure, corridor, len(alternate_routes)
        ),
        notes=(
            f"Historical road proxy: snapped to nearest past incident on {snapped['street_name']}. "
            f"Barricades placed at real past incident coordinates ({streets}) — known road locations, not water."
        ),
        road_network_used=True,
        planner_mode="historical_proxy",
        snapped_event=snapped,
    )


def _osm_cached(lat: float, lon: float) -> bool:
    from src.road_network import GRAPH_DIR, LOCAL_GRAPH_RADIUS_M

    path = GRAPH_DIR / f"local_{round(lat, 2)}_{round(lon, 2)}_{LOCAL_GRAPH_RADIUS_M}.graphml"
    return path.exists()


def plan_diversion(
    latitude: float,
    longitude: float,
    corridor: str,
    event_cause: str,
    requires_road_closure: bool = False,
    impact_tier: str = "Medium",
) -> DiversionPlan:
    radius = _radius_for_event(event_cause, requires_road_closure)

    if _osm_cached(latitude, longitude):
        try:
            return _plan_with_osm(
                latitude, longitude, corridor, event_cause,
                requires_road_closure, impact_tier, radius,
            )
        except Exception as osm_exc:
            logger.warning("Cached OSM planner failed: %s", osm_exc)

    try:
        return _plan_with_history(
            latitude, longitude, corridor, event_cause,
            requires_road_closure, impact_tier, radius,
        )
    except Exception as hist_exc:
        logger.warning("Historical proxy failed: %s", hist_exc)
        return DiversionPlan(
            affected_radius_m=radius,
            barricade_points=[],
            alternate_routes=[],
            estimated_delay_minutes=_estimate_delay(impact_tier, requires_road_closure, corridor, 0),
            notes=f"Planner unavailable: {hist_exc}",
            road_network_used=False,
            planner_mode="failed",
        )
