"""End-to-end training and artifact generation."""

from __future__ import annotations

import json

from src.data_loader import clean_events, save_processed
from src.forecast import ForecastEngine, save_forecast_metrics
from src.impact_model import ImpactModel, save_metrics
from src.learning import learning_summary, seed_from_historical


def run() -> dict:
    df = clean_events()
    save_processed(df)

    impact = ImpactModel()
    impact_metrics = impact.fit(df)
    impact.save()
    save_metrics(impact_metrics)

    forecast = ForecastEngine()
    forecast_metrics = forecast.fit(df)
    forecast.save()
    save_forecast_metrics(forecast_metrics)

    impact_preds = impact.predict(df)
    seeded = seed_from_historical(df, impact_preds)

    summary = {
        "total_events": len(df),
        "event_driven_events": int(df["is_event_driven"].sum()),
        "impact_metrics": impact_metrics,
        "forecast_metrics": forecast_metrics,
        "learning_records_seeded": seeded,
        "learning_summary": learning_summary(),
    }

    from src.config import MODEL_DIR

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_DIR / "pipeline_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    print(json.dumps(summary, indent=2, default=str))
    return summary


if __name__ == "__main__":
    run()
