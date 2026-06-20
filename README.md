# Gridlock — Event-Driven Congestion Engine

Forecast event-related traffic impact and recommend manpower, barricading, and diversion plans for Bengaluru corridor operations.

**Live demo:** https://65.2.35.241.nip.io

## Problem

Political rallies, festivals, sports events, construction, and sudden gatherings create localized traffic breakdowns. Gridlock uses historical Astram event data plus live event parameters to:

1. **Score impact** — Low / Medium / High / Critical tiers
2. **Forecast duration** — planned event window estimates
3. **Predict hotspots** — unplanned cluster risk by corridor + hour
4. **Recommend resources** — constables, barricades, staging points
5. **Plan diversions** — OSM road-network barricades and alternate routes
6. **Learn post-event** — outcome logging for continuous improvement

## Architecture

```
Astram CSV → pipeline (train) → models (joblib)
                                      ↓
Live event → FastAPI /api/analyze → impact + forecast + resources + diversion
                                      ↓
                              Stitch command-center UI (map, scenarios, learning)
```

## Local development

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Train once
python -m src.pipeline

# Serve (no retrain)
python run.py
# → http://127.0.0.1:8000
```

To retrain on startup: `GRIDLOCK_TRAIN=true python run.py`

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check |
| `POST /api/analyze` | Full analysis for a live event |
| `GET /api/scenarios/full` | Pre-built demo scenarios |
| `GET /api/events/map-data` | Historical event-driven incidents |
| `GET /api/hotspots` | Next-hour hotspot forecast |
| `POST /api/outcomes` | Record post-event outcome |
| `GET /api/learning/summary` | Learning loop metrics |

## Model metrics (validation set)

| Metric | Value |
|--------|-------|
| Tier accuracy | 68.8% |
| Duration MAE | 7.8 h |
| Hotspot recall (top-5) | 38.1% |

## EC2 deployment

```bash
git clone https://github.com/kisnaXD/flipkart-gridlock.git
cd flipkart-gridlock
bash deploy/setup-ec2.sh
```

Requires Ubuntu EC2 with ports **80** and **443** open in the security group.

### AWS security group (required)

In EC2 → Security Groups → inbound rules, add:

| Type | Port | Source |
|------|------|--------|
| HTTP | 80 | 0.0.0.0/0 |
| HTTPS | 443 | 0.0.0.0/0 |

Then re-run SSL on the instance:

```bash
ssh -i your-key.pem ubuntu@65.2.35.241
sudo certbot --nginx -d 65.2.35.241.nip.io
```

Until ports are open, the app runs locally on the instance only (`curl http://127.0.0.1/api/health` works).

## Demo walkthrough

1. **Command Center** — select a scenario (e.g. Cricket Match at Chinnaswamy)
2. **Map** — historical incidents + barricade / diversion overlay
3. **Scenarios** — compare impact tiers and resource plans
4. **Hotspots** — unplanned congestion forecast
5. **Learning** — post-event feedback loop

## Team / data

Built for Flipkart Gridlock. Training data: anonymized Astram event records (Bengaluru).

## Optional: Vercel redirect URL

The UI is served from EC2 (FastAPI + templates). You do **not** need Vercel for the app to work.

If the submission form asks for a separate frontend URL, deploy this repo to [Vercel](https://vercel.com) — the included `vercel.json` redirects all traffic to the live EC2 demo.

1. Go to [vercel.com/new](https://vercel.com/new) → Import [kisnaXD/flipkart-gridlock](https://github.com/kisnaXD/flipkart-gridlock)
2. Framework preset: **Other**
3. Deploy (no env vars needed)
4. Submit your `*.vercel.app` URL — it forwards to `http://65.2.35.241.nip.io`

**Important:** Open EC2 ports 80/443 first so the redirect target is reachable.
