"""FastAPI application and map dashboard."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import json

from src.config import MODEL_DIR, PROCESSED_DIR
from src.diversion import plan_diversion
from src.features import build_impact_features, score_to_tier
from src.forecast import ForecastEngine
from src.impact_model import ImpactModel
from src.learning import learning_summary, load_outcomes, record_outcome
from src.resources import recommend_resources

APP_DIR = Path(__file__).resolve().parent

impact_model = ImpactModel.load()
forecast_engine = ForecastEngine.load()
SCENARIO_CACHE: list[dict] = []


class EventRequest(BaseModel):
    event_type: str = "planned"
    event_cause: str = "public_event"
    latitude: float = Field(..., ge=12.5, le=13.5)
    longitude: float = Field(..., ge=77.0, le=78.0)
    corridor: str = "CBD 2"
    priority: str = "High"
    requires_road_closure: bool = False
    hour_of_day: int = Field(18, ge=0, le=23)
    day_of_week: int = Field(5, ge=0, le=6)
    is_weekend: int = Field(1, ge=0, le=1)
    description: str = ""


class OutcomeRequest(BaseModel):
    event_id: str
    predicted_tier: str
    predicted_duration_hours: float
    actual_duration_hours: float | None = None
    recommended_constables: int
    actual_constables: int | None = None
    notes: str = ""


SCENARIOS = [
    {
        "name": "Cricket Match — Chinnaswamy Stadium",
        "request": EventRequest(
            event_type="planned",
            event_cause="public_event",
            latitude=12.9788,
            longitude=77.5995,
            corridor="CBD 2",
            priority="High",
            requires_road_closure=False,
            hour_of_day=14,
            description="Cricket Match at M Chinnaswamy Stadium",
        ),
    },
    {
        "name": "ORR Metro Construction",
        "request": EventRequest(
            event_type="planned",
            event_cause="construction",
            latitude=12.9694,
            longitude=77.7006,
            corridor="ORR East 2",
            priority="High",
            requires_road_closure=False,
            hour_of_day=9,
            description="Metro station pillar work",
        ),
    },
    {
        "name": "Procession — Town Hall",
        "request": EventRequest(
            event_type="planned",
            event_cause="procession",
            latitude=12.9643,
            longitude=77.5855,
            corridor="Mysore Road",
            priority="High",
            requires_road_closure=True,
            hour_of_day=17,
            description="Religious procession",
        ),
    },
    {
        "name": "VIP Movement — CBD",
        "request": EventRequest(
            event_type="planned",
            event_cause="vip_movement",
            latitude=12.9762,
            longitude=77.6017,
            corridor="Old Madras Road",
            priority="High",
            requires_road_closure=True,
            hour_of_day=10,
        ),
    },
    {
        "name": "Flash Congestion Cluster",
        "request": EventRequest(
            event_type="unplanned",
            event_cause="congestion",
            latitude=12.9219,
            longitude=77.6452,
            corridor="ORR East 1",
            priority="High",
            requires_road_closure=False,
            hour_of_day=18,
        ),
    },
]


def _load_events() -> pd.DataFrame:
    path = PROCESSED_DIR / "events_clean.parquet"
    if not path.exists():
        raise HTTPException(status_code=503, detail="Run pipeline first: python -m src.pipeline")
    return pd.read_parquet(path)


def _analyze_event(req: EventRequest) -> dict:
    row = pd.DataFrame([req.model_dump()])
    row["id"] = "LIVE-001"
    feats = build_impact_features(row, impact_model.corridor_index)
    score = float(feats["impact_score"].iloc[0])
    tier = score_to_tier(score)

    duration = forecast_engine.predict_duration(req.model_dump())
    resources = recommend_resources(
        tier, req.event_cause, req.corridor, req.requires_road_closure
    )
    diversion = plan_diversion(
        req.latitude,
        req.longitude,
        req.corridor,
        req.event_cause,
        req.requires_road_closure,
        tier,
    )

    return {
        "impact_score": score,
        "impact_tier": tier,
        "predicted_duration_hours": round(duration, 1),
        "peak_window": f"{req.hour_of_day:02d}:00 – {(int(req.hour_of_day + duration) % 24):02d}:00",
        "resources": resources.to_dict(),
        "diversion": diversion.to_dict(),
        "hotspots_next_hour": forecast_engine.predict_hotspots(req.hour_of_day, top_n=5),
    }


def _build_scenario_cache() -> list[dict]:
    return [
        {
            "name": s["name"],
            "request": s["request"].model_dump(),
            "analysis": _analyze_event(s["request"]),
        }
        for s in SCENARIOS
    ]


@asynccontextmanager
async def lifespan(application: FastAPI):
    global SCENARIO_CACHE
    SCENARIO_CACHE = _build_scenario_cache()
    yield


app = FastAPI(title="Gridlock Event Congestion Engine", version="1.3.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")


STITCH_DIR = APP_DIR / "templates" / "stitch"


def _serve_stitch(page: str) -> HTMLResponse:
    path = STITCH_DIR / f"{page}.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Page {page} not found")
    html = path.read_text(encoding="utf-8")
    shell_css = '<link rel="stylesheet" href="/static/css/gridlock-shell.css"/>'
    shell_js = '<script src="/static/js/gridlock-nav.js"></script>'
    if shell_css not in html:
        html = html.replace("</head>", f"{shell_css}\n</head>")
    if "gridlock-nav.js" not in html:
        html = html.replace(
            '<script src="/static/js/gridlock-app.js">',
            f"{shell_js}\n<script src=\"/static/js/gridlock-app.js\">",
        )
    return HTMLResponse(content=html)


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return _serve_stitch("command")


@app.get("/map", response_class=HTMLResponse)
def map_page():
    return _serve_stitch("map")


@app.get("/scenarios", response_class=HTMLResponse)
def scenarios_page():
    return _serve_stitch("scenarios")


@app.get("/hotspots", response_class=HTMLResponse)
def hotspots_page():
    return _serve_stitch("hotspots")


@app.get("/analytics", response_class=HTMLResponse)
def analytics_page():
    return _serve_stitch("analytics")


@app.get("/learning", response_class=HTMLResponse)
def learning_page():
    return _serve_stitch("learning")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "gridlock"}


@app.get("/api/analytics/summary")
def analytics_summary():
    summary_path = MODEL_DIR / "pipeline_summary.json"
    impact_path = MODEL_DIR / "impact_metrics.json"
    forecast_path = MODEL_DIR / "forecast_metrics.json"
    data = {
        "total_events": 8173,
        "event_driven_events": 807,
        "tier_accuracy": None,
        "duration_mae_hours": None,
    }
    if summary_path.exists():
        with open(summary_path, encoding="utf-8") as f:
            s = json.load(f)
        data["total_events"] = s.get("total_events", data["total_events"])
        data["event_driven_events"] = s.get("event_driven_events", data["event_driven_events"])
    if impact_path.exists():
        with open(impact_path, encoding="utf-8") as f:
            im = json.load(f)
        data["tier_accuracy"] = im.get("tier_accuracy")
    if forecast_path.exists():
        with open(forecast_path, encoding="utf-8") as f:
            fm = json.load(f)
        data["duration_mae_hours"] = fm.get("duration_mae_hours")
    return data


@app.get("/api/scenarios/full")
def scenarios_full():
    if not SCENARIO_CACHE:
        return _build_scenario_cache()
    return SCENARIO_CACHE


@app.get("/api/events/map-data")
def events_map_data(limit: int = 400):
    df = _load_events()
    subset = (
        df[df["is_event_driven"]]
        .dropna(subset=["latitude", "longitude"])
        .head(limit)
        .copy()
    )
    if subset.empty:
        return {"events": []}

    preds = impact_model.predict(subset)
    merged = subset.merge(preds[["id", "predicted_tier"]], on="id", how="left")

    events = []
    for _, row in merged.iterrows():
        when = row["start_datetime"]
        events.append(
            {
                "lat": float(row["latitude"]),
                "lon": float(row["longitude"]),
                "tier": row.get("predicted_tier") or row.get("impact_tier", "Medium"),
                "cause": row["event_cause"],
                "corridor": row["corridor"],
                "when": str(when)[:16] if pd.notna(when) else "Unknown",
            }
        )
    return {"events": events}


@app.post("/api/analyze")
def analyze(req: EventRequest):
    return _analyze_event(req)


@app.get("/api/hotspots")
def hotspots(hour: int | None = None, top_n: int = 5):
    return {"hotspots": forecast_engine.predict_hotspots(hour, top_n)}


@app.get("/api/events")
def list_events(limit: int = 50):
    df = _load_events()
    subset = df[df["is_event_driven"]].head(limit)
    cols = [
        "id", "event_type", "event_cause", "corridor", "latitude", "longitude",
        "start_datetime", "priority", "requires_road_closure", "impact_tier",
    ]
    return {"events": subset[cols].astype(str).to_dict(orient="records")}


@app.get("/api/scenarios")
def scenarios():
    if SCENARIO_CACHE:
        return [{"name": s["name"], "analysis": s["analysis"]} for s in SCENARIO_CACHE]
    return [{"name": s["name"], "analysis": _analyze_event(s["request"])} for s in SCENARIOS]


@app.post("/api/outcomes")
def post_outcome(req: OutcomeRequest):
    return record_outcome(**req.model_dump())


@app.get("/api/learning/summary")
def get_learning_summary():
    return learning_summary()


@app.get("/api/learning/outcomes")
def get_outcomes():
    df = load_outcomes()
    if df.empty:
        return {"outcomes": []}
    return {"outcomes": df.to_dict(orient="records")}
