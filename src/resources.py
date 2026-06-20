"""Manpower and barricade recommendation engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from src.config import CORRIDOR_CAPACITY


@dataclass
class ResourcePlan:
    impact_tier: str
    constables: int
    inspectors: int
    sector_officers: int
    barricades: int
    cones: int
    staging_points: int
    notes: str

    def to_dict(self) -> dict:
        return asdict(self)


TIER_BASE = {
    "Low": ResourcePlan("Low", 3, 0, 0, 1, 4, 1, "Single junction monitoring"),
    "Medium": ResourcePlan("Medium", 8, 1, 0, 6, 12, 2, "Partial lane block on corridor segment"),
    "High": ResourcePlan("High", 20, 1, 1, 15, 25, 3, "Full lane control with diversion support"),
    "Critical": ResourcePlan("Critical", 35, 2, 2, 30, 40, 4, "Multi-sector route seal and crowd management"),
}

CAUSE_MULTIPLIER = {
    "public_event": 1.3,
    "procession": 1.25,
    "protest": 1.2,
    "vip_movement": 1.15,
    "congestion": 1.0,
    "construction": 0.9,
}


def recommend_resources(
    impact_tier: str,
    event_cause: str,
    corridor: str,
    requires_road_closure: bool = False,
) -> ResourcePlan:
    base = TIER_BASE.get(impact_tier, TIER_BASE["Medium"])
    mult = CAUSE_MULTIPLIER.get(event_cause, 1.0)
    cap = CORRIDOR_CAPACITY.get(corridor, "medium")
    cap_mult = {"high": 1.15, "medium": 1.0, "low": 0.85}.get(cap, 1.0)

    constables = max(2, int(base.constables * mult * cap_mult))
    barricades = base.barricades
    cones = base.cones
    if requires_road_closure:
        barricades = max(barricades, int(barricades * 1.4))
        cones = max(cones, int(cones * 1.3))

    notes = base.notes
    if event_cause == "public_event":
        notes += "; Pre-position near venue exits and parking ingress"
    elif event_cause == "procession":
        notes += "; Deploy along procession route at 200m intervals"
    elif event_cause == "construction":
        notes += "; Focus on merge points and U-turn alternatives"

    return ResourcePlan(
        impact_tier=impact_tier,
        constables=constables,
        inspectors=base.inspectors,
        sector_officers=base.sector_officers,
        barricades=barricades,
        cones=cones,
        staging_points=base.staging_points,
        notes=notes,
    )
