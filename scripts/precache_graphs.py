"""Pre-download OSM road graphs for demo scenario locations."""

from __future__ import annotations

from src.road_network import get_local_graph

SCENARIOS = [
    (12.9788, 77.5995, "Chinnaswamy Stadium"),
    (12.9694, 77.7006, "ORR Metro"),
    (12.9643, 77.5855, "Town Hall procession"),
    (12.9762, 77.6017, "VIP CBD"),
    (12.9219, 77.6452, "Flash cluster"),
]


def main() -> None:
    for lat, lon, name in SCENARIOS:
        print(f"Caching graph: {name} ({lat}, {lon})...")
        G = get_local_graph(lat, lon)
        print(f"  -> {G.number_of_nodes()} nodes")


if __name__ == "__main__":
    main()
