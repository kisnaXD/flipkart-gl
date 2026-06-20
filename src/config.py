from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = ROOT / "Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv"
PROCESSED_DIR = ROOT / "data" / "processed"
MODEL_DIR = ROOT / "data" / "models"
OUTCOMES_DIR = ROOT / "data" / "outcomes"

EVENT_DRIVEN_CAUSES = [
    "construction",
    "public_event",
    "procession",
    "protest",
    "vip_movement",
    "congestion",
]

TYPE_WEIGHTS = {
    "public_event": 0.95,
    "procession": 0.90,
    "protest": 0.88,
    "vip_movement": 0.85,
    "congestion": 0.75,
    "construction": 0.55,
}

CORRIDOR_CAPACITY = {
    "ORR East 1": "high",
    "ORR East 2": "high",
    "ORR West 1": "high",
    "ORR West 2": "high",
    "Bellary Road 1": "high",
    "Bellary Road 2": "high",
    "Mysore Road": "high",
    "Tumkur Road": "high",
    "Old Madras Road": "medium",
    "CBD 1": "medium",
    "CBD 2": "medium",
    "Non-corridor": "low",
}

BENGALURU_CENTER = (12.9716, 77.5946)
