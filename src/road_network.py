"""OpenStreetMap road network for barricade placement and diversions."""

from __future__ import annotations

import logging
import math
from functools import lru_cache

import networkx as nx

from src.config import ROOT

logger = logging.getLogger(__name__)

GRAPH_DIR = ROOT / "data" / "graphs"
GRAPH_DIR.mkdir(parents=True, exist_ok=True)

# Radius around each event to fetch driveable roads (~2km covers barricade + diversion zone)
LOCAL_GRAPH_RADIUS_M = 1400


@lru_cache(maxsize=64)
def get_local_graph(lat: float, lon: float, radius_m: int = LOCAL_GRAPH_RADIUS_M):
    """
    Load or download a drive network around the event.
    Cached per ~1.1km grid cell so nearby scenarios reuse the same graph.
    """
    import osmnx as ox

    ox.settings.timeout = 90
    ox.settings.overpass_url = "https://overpass.kumi.systems/api/interpreter"

    grid_lat = round(lat, 2)
    grid_lon = round(lon, 2)
    cache_path = GRAPH_DIR / f"local_{grid_lat}_{grid_lon}_{radius_m}.graphml"

    if cache_path.exists():
        return ox.load_graphml(cache_path)

    logger.info("Downloading road network near (%.2f, %.2f)...", lat, lon)
    G = ox.graph_from_point(
        (lat, lon),
        dist=radius_m,
        network_type="drive",
        simplify=True,
        retain_all=False,
    )
    ox.save_graphml(G, cache_path)
    logger.info("Cached %s nodes at %s", G.number_of_nodes(), cache_path.name)
    return G


def graph_available() -> bool:
    try:
        get_local_graph(12.97, 77.59)
        return True
    except Exception as exc:
        logger.warning("Road graph unavailable: %s", exc)
        return False


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    d_lon = math.radians(lon2 - lon1)
    lat1r, lat2r = map(math.radians, [lat1, lat2])
    x = math.sin(d_lon) * math.cos(lat2r)
    y = math.cos(lat1r) * math.sin(lat2r) - math.sin(lat1r) * math.cos(lat2r) * math.cos(d_lon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _quadrant(bearing: float) -> str:
    if 45 <= bearing < 135:
        return "E"
    if 135 <= bearing < 225:
        return "S"
    if 225 <= bearing < 315:
        return "W"
    return "N"


def _node_latlon(G, node: int) -> tuple[float, float]:
    data = G.nodes[node]
    return float(data["y"]), float(data["x"])


def _street_name(G, node: int) -> str:
    names: set[str] = set()
    for _u, _v, data in G.edges(node, keys=True, data=True):
        name = data.get("name") or data.get("ref")
        if name:
            names.add(str(name))
    return ", ".join(sorted(names)[:2]) if names else "Unnamed road"


def snap_to_road(lat: float, lon: float) -> dict:
    """Snap a point to the nearest driveable road segment."""
    import osmnx as ox

    G = get_local_graph(lat, lon)
    node = ox.distance.nearest_nodes(G, lon, lat)
    nlat, nlon = _node_latlon(G, node)
    _u, _v, edge_key = ox.distance.nearest_edges(G, lon, lat)
    # nearest_edges returns u,v,key for multigraph
    edge_data = G.edges[_u, _v, edge_key]
    return {
        "node_id": int(node),
        "latitude": round(nlat, 6),
        "longitude": round(nlon, 6),
        "street_name": edge_data.get("name") or _street_name(G, node),
        "highway_type": edge_data.get("highway", "unknown"),
    }


def find_barricade_points(
    lat: float,
    lon: float,
    min_dist_m: float = 180,
    max_dist_m: float = 650,
    max_barricades: int = 4,
) -> list[dict]:
    """
    Place barricades on real road intersections upstream of the event.
    Uses network distance along driveable roads, not straight-line offsets.
    """
    import osmnx as ox

    G = get_local_graph(lat, lon)
    event_node = ox.distance.nearest_nodes(G, lon, lat)
    event_lat, event_lon = _node_latlon(G, event_node)

    dist_map = nx.single_source_dijkstra_path_length(
        G, event_node, cutoff=max_dist_m * 1.2, weight="length"
    )

    candidates: list[dict] = []
    for node, dist in dist_map.items():
        if dist < min_dist_m or dist > max_dist_m:
            continue
        degree = G.degree(node)
        if degree < 2:
            continue

        nlat, nlon = _node_latlon(G, node)
        bearing = _bearing(event_lat, event_lon, nlat, nlon)
        quad = _quadrant(bearing)
        street = _street_name(G, node)

        score = degree * 10 + (5 if street != "Unnamed road" else 0) + (8 if degree >= 3 else 0)
        role = "intersection_control" if degree >= 3 else "ingress_control"
        candidates.append(
            {
                "node_id": int(node),
                "latitude": round(nlat, 6),
                "longitude": round(nlon, 6),
                "network_distance_m": round(dist, 0),
                "street_name": street,
                "quadrant": quad,
                "role": role,
                "degree": degree,
                "score": score,
            }
        )

    selected: list[dict] = []
    for quad in ("N", "E", "S", "W"):
        quad_candidates = [c for c in candidates if c["quadrant"] == quad]
        if quad_candidates:
            selected.append(max(quad_candidates, key=lambda c: c["score"]))

    if len(selected) < max_barricades:
        used = {c["node_id"] for c in selected}
        remainder = sorted(
            [c for c in candidates if c["node_id"] not in used],
            key=lambda c: c["score"],
            reverse=True,
        )
        for c in remainder:
            if len(selected) >= max_barricades:
                break
            selected.append(c)

    for i, pt in enumerate(selected[:max_barricades]):
        pt["id"] = f"B{i + 1}"
        pt.pop("score", None)

    return selected[:max_barricades]


def _edges_near_node(G, center_node: int, radius_m: float) -> set[tuple]:
    dist_map = nx.single_source_dijkstra_path_length(
        G, center_node, cutoff=radius_m, weight="length"
    )
    affected: set[tuple] = set()
    for node in dist_map:
        for u, v, key in G.edges(node, keys=True):
            if u in dist_map and v in dist_map:
                affected.add((u, v, key))
    return affected


def find_diversion_routes(
    lat: float,
    lon: float,
    barricade_points: list[dict],
    disruption_radius_m: float = 400,
    max_routes: int = 2,
) -> list[dict]:
    """Compute alternate routes along roads, avoiding the disrupted zone."""
    import osmnx as ox

    G = get_local_graph(lat, lon)
    event_node = ox.distance.nearest_nodes(G, lon, lat)
    affected = _edges_near_node(G, event_node, disruption_radius_m)

    G2 = G.copy()
    for u, v, key in affected:
        if G2.has_edge(u, v, key):
            G2[u][v][key]["length"] = G2[u][v][key].get("length", 1) * 50

    routes: list[dict] = []
    used_targets: set[int] = set()

    for i, barrier in enumerate(barricade_points[:max_routes]):
        start_node = barrier.get("node_id") or ox.distance.nearest_nodes(
            G, barrier["longitude"], barrier["latitude"]
        )

        dist_from_event = nx.single_source_dijkstra_path_length(
            G, event_node, cutoff=2500, weight="length"
        )

        targets = []
        for node, dist in dist_from_event.items():
            if dist < 900 or node == start_node or node in used_targets:
                continue
            if G.degree(node) < 2:
                continue
            targets.append((node, dist, _street_name(G, node)))

        targets.sort(key=lambda t: t[1], reverse=True)
        if not targets:
            continue

        target_node, _, target_street = targets[0]
        used_targets.add(target_node)

        try:
            path = nx.shortest_path(G2, start_node, target_node, weight="length")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            try:
                path = nx.shortest_path(G, start_node, target_node, weight="length")
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue

        geometry = [
            [round(_node_latlon(G, n)[0], 6), round(_node_latlon(G, n)[1], 6)] for n in path
        ]
        if len(geometry) < 2:
            continue

        length_m = sum(
            G[path[j]][path[j + 1]][0].get("length", 0)
            for j in range(len(path) - 1)
            if G.has_edge(path[j], path[j + 1])
        )

        routes.append(
            {
                "route_id": f"ALT-{i + 1}",
                "corridor": target_street,
                "start": {"latitude": geometry[0][0], "longitude": geometry[0][1]},
                "end": {"latitude": geometry[-1][0], "longitude": geometry[-1][1]},
                "geometry": geometry,
                "length_m": round(length_m, 0),
                "instruction": f"Divert via {target_street} ({int(length_m)}m along roads)",
            }
        )

    return routes


def prefetch_scenario_graphs(scenarios: list[tuple[float, float]]) -> None:
    """Pre-download road graphs for known scenario locations."""
    for lat, lon in scenarios:
        try:
            get_local_graph(lat, lon)
        except Exception as exc:
            logger.warning("Prefetch failed for (%.4f, %.4f): %s", lat, lon, exc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    prefetch_scenario_graphs(
        [
            (12.9788, 77.5995),
            (12.9694, 77.7006),
            (12.9643, 77.5855),
            (12.9762, 77.6017),
            (12.9219, 77.6452),
        ]
    )
    print("Local road graphs cached in", GRAPH_DIR)
