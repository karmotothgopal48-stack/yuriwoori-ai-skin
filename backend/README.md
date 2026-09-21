# YuriWoori Backend

FastAPI service behind the YuriWoori AI Skin Analysis experience. It accepts a face photo, scores visible skin
characteristics with classical computer vision, and turns the result into product recommendations, an AM/PM
routine, ingredient-compatibility warnings, progress tracking, a Claude-powered skincare coach (RAG over the
product catalogue) and a Shopify checkout hand-off.

- **Framework:** FastAPI + SQLAlchemy 2, served by Uvicorn
- **Database:** PostgreSQL with the `pgvector` extension, migrations via Alembic
- **Skin analysis:** OpenCV heuristics (`heuristic-cv-v0`) — an honest baseline, *not* a trained model
- **AI coach:** Anthropic Claude (`claude-sonnet-4-6`) with retrieval from local sentence-transformer embeddings
- **Frontend:** the React app in the sibling [`../frontend`](../frontend) folder of this monorepo (CORS is preconfigured for it)

---

## Contents

1. [How it works](#how-it-works)
2. [Project structure](#project-structure)
3. [Prerequisites](#prerequisites)
4. [Setup](#setup)
5. [Configuration](#configuration)
6. [Running the server](#running-the-server)
7. [API reference](#api-reference)
8. [Scan flow (what the frontend calls)](#scan-flow-what-the-frontend-calls)
9. [Skin analysis metrics](#skin-analysis-metrics)
10. [Database](#database)
11. [Scripts](#scripts)
12. [Tests](#tests)
13. [Connecting the frontend](#connecting-the-frontend)
14. [Troubleshooting](#troubleshooting)
15. [Known limitations](#known-limitations)

---

## How it works

```
Browser (React, :2999)
   │  JSON over HTTP  (CORS allow-list from FRONTEND_ORIGIN)
   ▼
FastAPI  /v1/*  ──►  services/  ──►  PostgreSQL (+ pgvector)
                       │
                       ├─ cv_quality.py      frame quality gate (blur / lighting)
                       ├─ skin_analysis.py   OpenCV metrics → skin profile
                       ├─ recommendation.py  profile → matching products (database)
                       ├─ catalogue_csv.py   data/products_export.csv → catalogue + recommendations
                       ├─ routine_builder.py profile → AM / PM routine
                       ├─ ingredient_compatibility.py  routine → conflict flags
                       ├─ coach.py           RAG + Claude  (needs ANTHROPIC_API_KEY)
                       ├─ shopping_agent.py  budget → cart
                       └─ shopify_client.py  cart → checkout URL
```

Uploaded frames are written to `app/uploads/<scan_id>/<angle>.jpg`. Nothing is sent to a third party except the
coach's retrieved context + question (Anthropic) and the checkout cart (Shopify).

## Project structure

```
backend/
├── app/
│   ├── main.py                  FastAPI app, CORS, DB-error handler, mounts /v1
│   ├── schemas.py               Pydantic request/response models
│   ├── core/config.py           Settings loaded from .env
│   ├── db/
│   │   ├── models.py            SQLAlchemy models (see Database)
│   │   └── session.py           Engine, SessionLocal, get_db dependency
│   ├── api/v1/
│   │   ├── router.py            Registers all endpoint modules
│   │   └── endpoints/           health, scans, passport, products, catalogue,
│   │                            coach, progress, shopping_agent, shopify
│   ├── services/                Business logic (analysis, recommendations, RAG, …)
│   └── uploads/                 Saved scan frames (git-ignored)
├── alembic/ + alembic.ini       Database migrations
├── data/products_export.csv     Shopify product export: source of the catalogue API and DB seed
├── scripts/                     Catalogue import / sync / embeddings / seeding
├── tests/test_unit.py           Unit tests (no DB / network / OpenCV needed)
├── requirements.txt
├── .env.example
└── src/app/passport/page.tsx    Stray Next.js file, not used by this service
```

## Prerequisites

- **Python 3.11+** (developed on a recent 3.x with a local `venv`)
- **PostgreSQL 14+ with the `pgvector` extension** (Docker image `pgvector/pgvector:pg16` is the easiest route)
- An **Anthropic API key with available credits** (only needed for the coach)
- Optional: a **Shopify Storefront API token** (only needed for checkout)

## Setup

```bash
# 1. Start Postgres with pgvector (example)
docker run -d --name yuriwoori-db \
  -e POSTGRES_USER=yuriwoori_user -e POSTGRES_PASSWORD=<your-password> -e POSTGRES_DB=yuriwoori_db \
  -p 5432:5432 pgvector/pgvector:pg16

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # macOS / Linux

# 3. Install dependencies (includes torch + sentence-transformers, so the first install is large)
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env           # then edit .env (see Configuration)

# 5. Create / upgrade the database schema
alembic upgrade head

# 6. Load the catalogue and build search data (see Scripts)
python scripts/import_catalogue_csv.py
python scripts/seed_ingredient_interactions.py
python scripts/build_embeddings.py
```

> `requirements.txt` is saved as UTF-16. Recent `pip` reads it fine; if your tooling complains, re-save it as UTF-8.

## Configuration

Settings are read from `.env` (see `app/core/config.py`). Never commit `.env`.

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Yes | e.g. `postgresql://user:pass@localhost:5432/yuriwoori_db`. Without it the app still boots (`/v1/health`, `/docs`) but every DB route fails. |
| `FRONTEND_ORIGIN` | Yes | Comma-separated browser origins allowed by CORS. Default: `http://localhost:2999,http://127.0.0.1:2999,http://localhost:3000`. |
| `ANTHROPIC_API_KEY` | For chat | Powers `/v1/coach/message`. Missing key → `503`; billing/API failure → `502`. |
| `SHOPIFY_STORE_DOMAIN` | For checkout | Store domain, e.g. `your-store.myshopify.com`. |
| `SHOPIFY_STOREFRONT_ACCESS_TOKEN` | For checkout | Storefront API token. |
| `JWT_SECRET` | No | Reserved for future auth (unused). |
| `BACKEND_PORT`, `ENVIRONMENT` | No | Defaults `8000` / `development`. |

## Running the server

```bash
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- Interactive docs (Swagger UI): <http://localhost:8000/docs>
- Health check: <http://localhost:8000/v1/health> → `{"status":"ok","service":"yuriwoori-backend"}`
- The server speaks **plain HTTP**. Point clients at `http://`, not `https://`.
- Without `--reload`, code changes only apply after a manual restart.

## API reference

All routes are prefixed with `/v1`. Errors use FastAPI's `{"detail": "..."}` shape.

### Health
| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check. |

### Scans — `/scans`
| Method | Path | Description |
|---|---|---|
| POST | `/scans` | Create a scan → `{scan_id}`. |
| POST | `/scans/{scan_id}/frames` | Upload a frame `{angle, image_base64}` (JPEG, base64 or data URL, ≤ ~10 MB). Returns quality scores and `passed`. Only passed frames count toward analysis. |
| POST | `/scans/{scan_id}/analyze` | Run skin analysis on passed frames → skin profile. Idempotent per scan. `400` if no passed frame, `503` if OpenCV is unavailable. |
| GET | `/scans/{scan_id}` | Fetch the analyzed profile (`404` if not analyzed yet). |
| GET | `/scans/{scan_id}/recommendations` | Database-backed recommendations (uses the `products` table, so it needs the catalogue imported). Built once, then cached. The frontend uses `/catalogue/recommendations` instead. |
| GET | `/scans/{scan_id}/routine` | `{AM: [...], PM: [...]}` steps with product and reason. |
| GET | `/scans/{scan_id}/compatibility` | Ingredient conflict flags for the routine (call after `/routine`). |

### Products — `/products`
| Method | Path | Description |
|---|---|---|
| GET | `/products?category=` | Active catalogue, optionally filtered by category. |
| GET | `/products/{product_id}` | Detail: concern tags, chips, benefits, ingredients. |

### Catalogue (CSV) — `/catalogue`
Backed directly by `data/products_export.csv` (the Shopify product export, 37 active products). It is re-read
automatically whenever the file changes, so editing the CSV needs no restart or re-import. Bundles/kits are hidden
unless `include_bundles=true`.

| Method | Path | Description |
|---|---|---|
| GET | `/catalogue/products` | List products. Filters: `step` (cleanse, tone, treat, moisturize, protect, mask), `concern` (e.g. `hydration`), `q` (name search), `include_bundles`. |
| GET | `/catalogue/products/{handle}` | One product: price, image, description, concern tags, chips, ingredients, store URL. |
| GET | `/catalogue/recommendations` | **Recommended products for an analysis.** Pass `scan_id=<uuid>` (uses that scan's saved profile) *or* the metrics directly: `hydration`, `oiliness`, `redness`, `pigmentation`, `blemish_index`, `pore_visibility` (0–100). Optional `limit_per_step` (default 2). |

Recommendation response:

```json
{
  "scan_id": "…",
  "active_concerns": { "hydration": "boost hydration", "pore-visibility": "refine visible pores" },
  "recommendations": [
    { "rank": 1, "score": 20, "handle": "aloevera-facial-deep-cleansing-foam", "name": "…", "price": 855.0,
      "image_url": "…", "routine_step": "cleanse", "product_url": "https://yuriwoori.com/products/…",
      "matched_concerns": ["hydration", "pore-visibility"],
      "match_reason": "Matches your scan: helps boost hydration, refine visible pores.", "…": "…" }
  ]
}
```

How products are matched: a concern is *active* when its metric crosses a threshold (redness / pigmentation /
blemish / pores > 40, oiliness > 55, hydration < 45). A product is recommended only if its own concern tags overlap
an active concern; score = 10 per overlapping concern plus up to 10 more by severity, ties broken by name, and at most `limit_per_step` products per
routine step. The score adds up to 10 more per concern the worse it is, so a stronger reading ranks higher.
Balanced skin can legitimately return an empty list — check `active_concerns` to explain why.
Concern tags are derived by keyword-matching each product's title (plus chips/benefits/key-benefit when the export
includes them) — see `CONCERN_KEYWORDS` in `app/services/catalogue_csv.py`.

Try it without a scan: `GET /v1/catalogue/recommendations?hydration=30&redness=55&pore_visibility=60`.

### Coach — `/coach`
| Method | Path | Description |
|---|---|---|
| POST | `/coach/message` | `{message, conversation_id?}` → `{conversation_id, reply, cited_product_ids}`. Retrieves relevant products by vector similarity and asks Claude to answer only from them. |

### Passport, progress, shopping
| Method | Path | Description |
|---|---|---|
| POST | `/passport/save/{scan_id}` | Save a scan's summary (skin type, top concerns, score) to the guest passport. |
| GET | `/passport` | Read the guest passport. |
| GET | `/progress/{user_id}` | Snapshot series and "meaningful changes" over time. |
| POST | `/shopping-agent/build` | `{message, scan_id?}` — parses a budget ("₹2000", "2k") and builds a cart of real products that fits it. |
| POST | `/shopify/checkout/{cart_id}` | Creates a Shopify cart and returns `checkout_url` (+ `unresolved_products`). Needs Shopify config and resolved variant IDs. |

Users are not authenticated yet; scans are stored without a user and a fixed guest id represents them.

## Scan flow (what the frontend calls)

```
POST /scans                              → scan_id
POST /scans/{id}/frames  (front, JPEG)   → passed? (else ask the user to retake)
POST /scans/{id}/analyze                 → skin profile
GET  /catalogue/recommendations?scan_id={id} → products (from the CSV catalogue)
GET  /scans/{id}/routine                 → AM / PM
GET  /scans/{id}/compatibility           → warnings
```

The frame quality gate (`cv_quality.py`) is deliberately lightweight: it reads the JPEG header and byte statistics
(no pixel decode). A frame passes when sharpness ≥ 15, lighting ≥ 40 and the combined quality ≥ 55. Non-JPEG or
tiny/corrupt images always fail, so clients must send JPEG.

## Skin analysis metrics

`skin_analysis.py` first **finds the face** (OpenCV Haar cascades; the face must be near the centre of the frame),
trims hair and jaw, and keeps only **skin-coloured pixels** (YCrCb mask). Every metric is measured on that skin region
only, so walls, clothing and bystanders don't affect the result. If no centred face is found, `/analyze` returns
`422` asking for a retake. Metrics (HSV/LAB statistics, edge density, blob detection) are on a 0–100 scale:

| Field | Meaning |
|---|---|
| `hydration`, `texture` | Higher = better. Hydration is a *proxy* derived from texture and shine, not a real moisture reading. |
| `redness`, `oiliness`, `pigmentation`, `blemish_index`, `pore_visibility` | Higher = **more** of the trait (a concern level). |
| `skin_type` | `oily`, `dry`, `combination` or `normal`, from oiliness and hydration. |
| `overall_score` | Blend of hydration, texture and (100 − average concern). |

Recommendations trigger when a concern exceeds its threshold (redness/pigmentation/blemish/pores > 40, oiliness > 55,
hydration < 45) and match products by their real `concern_tags`. A well-balanced scan can return no recommendations.

## Database

Tables (`app/db/models.py`): `users`, `devices`, `scans`, `scan_frames`, `skin_profiles`, `skin_passports`,
`products`, `ingredients`, `product_ingredients`, `ingredient_interactions`, `routines`, `routine_steps`,
`recommendations`, `product_embeddings`, `ingredient_embeddings`, `coach_conversations`, `coach_messages`,
`progress_snapshots`, `carts`, `cart_items`.

Migrations live in `alembic/versions/`. Common commands:

```bash
alembic upgrade head                              # apply all migrations
alembic revision --autogenerate -m "message"      # create a migration after model changes
alembic current                                   # show applied revision
```

## Scripts

Run from the backend folder (they import `app.*` relative to the working directory).

| Script | What it does |
|---|---|
| `scripts/import_catalogue_csv.py` | Imports products and INCI ingredient lists from `data/products_export.csv` into the database (needed for routines, the coach and DB recommendations; **not** needed for `/catalogue/*`). Shares its parsing helpers with `app/services/catalogue_csv.py`. **Re-run it after upgrading** so stored `concern_tags` pick up the keyword-matching fix. |
| `scripts/sync_catalogue.py` | Pulls the live catalogue from the store's public Shopify JSON feed and upserts it. |
| `scripts/dedupe_products.py` | One-time cleanup of duplicate products created by the two import paths. |
| `scripts/seed_ingredient_interactions.py` | Seeds ingredient conflict/synergy rules used by the compatibility check. |
| `scripts/build_embeddings.py` | Builds product/ingredient embeddings for the coach. **Re-run after any catalogue change.** |
| `scripts/resolve_shopify_variants.py` | Resolves Shopify variant IDs per product (needed for checkout). |

Typical order on a fresh database: import CSV → seed interactions → build embeddings → resolve Shopify variants.

## Tests

```bash
python -m pytest tests -q
```

`tests/test_unit.py` covers pure logic (config/CORS parsing, frame validation, quality gate, benefit parsing, progress
series, budget extraction). `tests/test_catalogue_csv.py` covers the CSV catalogue, the recommender and the
`/catalogue/*` endpoints. Neither needs a database, network or OpenCV.

## Connecting the frontend

The React app reads the API base URL from `VITE_API_URL` (default `http://localhost:8000/v1`). Keep the frontend's
origin in `FRONTEND_ORIGIN`; the default already allows `http://localhost:2999`. See the [frontend README](../frontend/README.md).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Invalid HTTP request received` in the log, `ERR_SSL_PROTOCOL_ERROR` in the browser | The client used `https://`. The server is HTTP only — use `http://localhost:8000/v1`. |
| `503 Database is unavailable` | Postgres isn't running or `DATABASE_URL` is wrong. |
| `503 AI assistant is not configured` | `ANTHROPIC_API_KEY` missing in `.env`. |
| `502 The AI assistant service failed…` | Anthropic rejected the request; check the server log (e.g. "credit balance is too low"). |
| `503 Skin analysis engine is unavailable` | OpenCV failed to import (e.g. blocked DLL); the app must run from the project `venv`. |
| `/catalogue/recommendations` returns an empty list | No metric crossed a threshold (see `active_concerns` in the response). Not an error. |
| Routine / DB recommendations are empty | Stored `concern_tags` are empty from an older import. Re-run `python scripts/import_catalogue_csv.py`. |
| Analyze returns `422 No face found…` | No face was detected near the centre (glasses glare, face too small/off-centre, or another person nearer the middle). Retake facing the camera in soft light. |
| Analyze returns `400 No passed frames` | The frame failed the quality gate or wasn't a valid JPEG; upload a sharper, evenly lit JPEG. |
| Browser shows a CORS error | Add the frontend origin to `FRONTEND_ORIGIN` and restart. |
| Code changes have no effect | Server started without `--reload`; restart it. |
| First coach request is slow | The sentence-transformer model loads (and may download) on first use. |

## Known limitations

- Face detection is a classic Haar cascade: it can miss faces with glasses glare, strong angles or dim light, and thresholds/scales were tuned on a handful of photos, not a clinical dataset.
- Skin analysis is a heuristic baseline (`heuristic-cv-v0`), not a clinical or trained model. It is a cosmetic reading only.
- Hydration is estimated from texture and shine, not measured.
- No authentication yet — all scans share a guest identity.
- The quality gate uses JPEG header/byte statistics rather than true pixel sharpness or brightness.
- The coach answers only from retrieved catalogue data and depends on paid Anthropic API access.
