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
                    ┌─────────────────────────┐
                    │   Vercel (frontend/)    │
                    │   HTML + JS + CSS       │
                    └───────────┬─────────────┘
                                │ /api/* → nip.io (proxy)
                                ▼
Astram CSV → pipeline → models  │  EC2 FastAPI (API only)
                                │  /api/analyze, /api/scenarios, …
                                └─────────────────────────┘
```

- **Frontend:** `frontend/` — static Stitch UI, deployed to Vercel
- **Backend:** `app/main.py` — FastAPI API only, deployed to EC2

Rebuild frontend after UI changes:

```bash
python scripts/build_frontend.py
```

## Local development

**Backend (API):**

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m src.pipeline       # train once
python run.py                # → http://127.0.0.1:8000/api/health
```

**Frontend (static):**

```bash
python scripts/build_frontend.py
npx serve frontend           # → http://localhost:3000
```

Set `window.GRIDLOCK_API = "http://127.0.0.1:8000"` in browser console for local API, or edit `frontend/js/config.js`.

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

## Vercel deployment (frontend)

| Setting | Value |
|---------|--------|
| Framework Preset | **Other** |
| Root Directory | **`frontend`** |
| Build Command | *(empty)* |
| Output Directory | *(empty)* |

1. [vercel.com/new](https://vercel.com/new) → import repo
2. Set **Root Directory** to `frontend`
3. Deploy — no env vars required

API calls from `*.vercel.app` are proxied to `http://65.2.35.241.nip.io/api/*` via root `vercel.json` (avoids HTTPS→HTTP mixed-content blocking).

To call EC2 directly instead, set in `frontend/js/config.js`:

```js
window.GRIDLOCK_API = "https://65.2.35.241.nip.io";
```

(requires HTTPS on EC2)

## EC2 deployment (backend API)

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
