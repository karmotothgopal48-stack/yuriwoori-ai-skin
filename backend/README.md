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
                       ├─ live_catalogue.py  yuriwoori.com (public feed + product pages) → THE catalogue
                       ├─ recommendation.py  profile → matching live products
                       ├─ routine_builder.py profile → AM / PM routine of live products
                       ├─ product_records.py live products → products table (a record for routines/carts)
                       ├─ ingredient_compatibility.py  routine → conflict flags
                       ├─ coach.py           RAG + Claude  (needs ANTHROPIC_API_KEY)
                       ├─ shopping_agent.py  budget → cart
                       └─ shopify_client.py  cart → checkout URL
```

Scan photos are never stored: they are checked and analysed in memory, then discarded (only quality scores and
the measured results are saved). `app/uploads/` only holds photos left by older scans, removed with
`scripts/purge_legacy_selfies.py`. Nothing is sent to a third party except the
coach's retrieved context + question (Anthropic) and the checkout cart (Shopify).

### Product catalogue: the live store is the source of truth
Every product the app shows, recommends, puts in a routine or a cart comes from the official Shopify store
(`YURIWOORI_STORE_URL`, default https://yuriwoori.com), read by `app/services/live_catalogue.py`:

- **Shopify Storefront GraphQL API** (`app/services/shopify_client.py`): `POST https://yuriwoori.com/api/2025-07/graphql.json`,
  `Content-Type: application/json`, body `{"query": "...", "variables": {...}}`. The `products(first: 100, after: $cursor)`
  query (cursor-paged) returns product GIDs, handles, titles, descriptions, tags, images and each variant's GID, price,
  compare-at price and `availableForSale`. This works **without a token** for this store (verified).
- **Brand copy** (Shopify metafields `custom.benefits`, `chips`, `keybenefit`, `how_to_use`, `inci`): read in the same query
  when `SHOPIFY_STOREFRONT_PRIVATE_TOKEN` / `SHOPIFY_STOREFRONT_ACCESS_TOKEN` is set with the
  `unauthenticated_read_metafields` scope (tokenless access is refused with `ACCESS_DENIED`, verified). Without such a token
  it is read from each product page, where the store embeds the same metafields as JSON in `<script id="stape-product-data">`.
  This copy drives the concern tags used for matching. A product whose copy can't be read is **not matched** (nothing is
  guessed) and is logged.

### Cart, discounts and checkout: priced by Shopify
`POST /v1/shopify/cart` `{lines: [{variant_id, quantity}]}` creates a Shopify cart with the Storefront `cartCreate`
mutation and returns **Shopify's own** subtotal, each discount it applies (by Shopify's title), total and the
`checkoutUrl` of that same cart. The app never computes discounts. Example (verified 2026-10-13): cleanser ₹855 + toner
₹765 + cream ₹2,025 + eye patch ₹1,350 → subtotal ₹4,995, automatic discount **YWPL1000 −₹1,000**, total ₹3,995.
Only variants the store currently sells and has in stock are accepted.

Only products that can be bought now (priced, in stock, with a variant, not a kit/combo) are recommended.
Caching: the feed is reused for `CATALOGUE_CACHE_SECONDS` (300); an unchanged product's page copy for
`CATALOGUE_CONTENT_CACHE_SECONDS` (3600). If the store can't be reached, the last copy serves for at most
`CATALOGUE_STALE_GRACE_SECONDS` (900) more, flagged `stale` in responses; after that product endpoints return `503`.
Requests to the store retry timeouts, 429 and 5xx twice. Nothing ever falls back to `data/products_export.csv`.

The `products` table is a **record**, not a source: products are upserted by handle (`shopify_product_id`) from live
data when served, so saved routines, recommendations and carts keep valid IDs. Routines are rebuilt from the live
catalogue on every request; a new routine version is saved only when the result changes (older versions are kept).

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
│   └── uploads/                 Legacy scan photos only, to purge (git-ignored; nothing new is written)
├── alembic/ + alembic.ini       Database migrations
├── data/products_export.csv     Old Shopify product export (legacy; not read by the app)
├── scripts/                     Catalogue sync / embeddings / seeding / test snapshot
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
pip install --no-deps -r requirements-mediapipe.txt   # hand detection; --no-deps keeps a single OpenCV

# 4. Configure environment
copy .env.example .env           # then edit .env (see Configuration)

# 5. Create / upgrade the database schema
alembic upgrade head

# 6. Record the live catalogue and build search data (see Scripts)
python scripts/sync_catalogue.py
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
| `ANTHROPIC_API_KEY` | For chat | Powers `/v1/coach/message`. Missing key → `503`; out of credits → `503` with a "console.anthropic.com" hint; other API failure → `502` with Anthropic's own message. |
| `SHOPIFY_STORE_DOMAIN` | For checkout | Store domain, e.g. `your-store.myshopify.com`. |
| `SHOPIFY_STOREFRONT_ACCESS_TOKEN` | For checkout | Storefront API token. |
| `JWT_SECRET` | Yes | Signs customer session tokens and report links (min 32 chars). Generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Rotating it signs every customer out and invalidates all report links. |
| `BACKEND_PORT`, `ENVIRONMENT` | No | Defaults `8000` / `development`. |

## Running the server

```bash
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- Interactive docs (Swagger UI): <http://localhost:8000/docs>
- Health check: <http://localhost:8000/v1/health> → `{"status":"ok","service":"yuriwoori-backend"}`
- The server speaks **plain HTTP**. Point clients at `http://`, not `https://`.
- Without `--reload`, code changes only apply after a manual restart.
- **Production must use HTTPS.** Plain HTTP is for local development only: customer session tokens,
  names, emails and selfies travel in these requests. Put the API behind a TLS-terminating reverse proxy or load
  balancer, set `FRONTEND_ORIGIN` to the real `https://` site origin, and run uvicorn with
  `--proxy-headers --forwarded-allow-ips=<proxy ip>` so the recorded client IP is the visitor's, not the proxy's.

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
| GET | `/scans/{scan_id}/recommendations` | Ranked live products for the scan, chosen on every request. The frontend uses `/catalogue/recommendations` instead. |
| GET | `/scans/{scan_id}/routine` | `{AM: [...], PM: [...], catalogue_fetched_at, catalogue_stale}`, rebuilt from the live catalogue on every request. Each step: product, reason, `handle`, `routine_step`, `product_url`, live `price`, `available`, `variant_id`, `how_to_use`. Saved as a new version only when it changed. |
| GET | `/scans/{scan_id}/maintenance-routine` | Live-catalogue care routine for a balanced scan (not saved). |
| GET | `/scans/{scan_id}/compatibility` | Ingredient conflict flags for the latest routine (call after `/routine`). |

### Products — `/products`
Live store products with a stable UUID (their record row).

| Method | Path | Description |
|---|---|---|
| GET | `/products?category=` | Live catalogue, optionally filtered by category; includes `handle`, `available`, `variant_id`. |
| GET | `/products/{product_id}` | Detail from the live store: concern tags, chips, benefits, ingredients. `404` if no longer sold. |

### Catalogue — `/catalogue`
The live store catalogue (see "Product catalogue" above). Bundles/kits are hidden unless `include_bundles=true`.
Every endpoint returns `503` when the store can't be read and no recent copy exists.

| Method | Path | Description |
|---|---|---|
| GET | `/catalogue/products` | List products. Filters: `step` (cleanse, tone, treat, moisturize, protect, mask), `concern` (e.g. `hydration`), `q` (name search), `include_bundles`. |
| GET | `/catalogue/products/{handle}` | One product: price, image, description, concern tags, chips, ingredients, store URL, `product_id`, `variant_id`, `available`, plus `key_benefit` and `how_to_use` (verbatim from the product page's copy, `null` when missing). |
| GET | `/catalogue/live` | **Current details for given products.** `handles=a,b,c` (Shopify product handles): title, image, price, compare-at price and discount, availability, product URL, variant IDs, usage guidance, plus `fetched_at` and `stale`. Unknown handles are left out. |
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
Only products that can be bought now are ranked. Concern tags are derived by keyword-matching each product's title
plus the chips/benefits/key-benefit copy from its live product page — see `CONCERN_KEYWORDS` in
`app/services/catalogue_rules.py`. The routine uses the same ranking.

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

### Users and engagement tracking

Signup is required before a scan. There is no password: name + WhatsApp + email + accepted privacy notice returns a
signed session token (`Authorization: Bearer …`) for a new email. An email that already has an account is only opened
with proof: the browser already holds that account's session, or the first request answers `{"code_required": true,
"sent_to": "<masked>"}` and emails a 6-digit sign-in code, and the form is sent again with `"code"`. Knowing someone's
email therefore never opens their results. The sign-in code also counts as email verification.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/users/signup` | — | `{name, email, consent: true}` → `{token, user}`. Refused (`400`) without consent. Stores `consented_at` + `consent_version`. |
| GET | `/users/me` | user | The signed-up user for the token. |
| POST | `/scans` | user | Now requires a user token; the scan is linked to the user and the **server-side** request IP is stored. `/frames` and `/analyze` only accept the scan's own user (`403` otherwise). |
| POST | `/events` | user | `{event_type: "recommendations_shown" \| "product_clicked", scan_id, product_handle?}`. "Shown" is recorded once per scan (one row per offered product); a click is accepted only for a product this scan recommended or put in its routine, and the URL stored is the catalogue's. |

There is no admin area: no admin login, no `/admin` routes, and no customer listing or Excel export over the API.

The ranked product list served by `/catalogue/recommendations?scan_id=` for a signed-up user is stored once in
`recommendations`: what the user was actually offered (a `product_clicked` event is accepted only for one of these).

**Purchases are not tracked.** A product click is not a purchase. Tracking purchases would need a Shopify order
integration: an Admin API token with `read_orders` or an `orders/create` webhook (plus its signing secret), a public
HTTPS backend URL, and a way to tie an order to a scan (for example a Storefront cart carrying the scan id as a cart
attribute).

Behind a reverse proxy, run Uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy ip>` so the stored IP is the
client's, not the proxy's.

## Skin-analysis reports and delivery — `/reports`, `/delivery`
When an analysis is **saved**, the backend itself makes the scan's report record and sends it on every ready channel
(`delivery.report_after_analysis`, a background task of `POST /scans/{id}/analyze`: owner only, one report per scan,
never sent twice). The frontend's own `POST /reports {scan_id}` does the same and is harmless if it comes too.
The report (`app/services/reports.py`) is **generated in memory each time** it is sent, its PDF downloaded or its link
opened (`reports.content_for`), from the scan's saved `skin_profiles` row, the same recommendation/routine rules as the
app, the live Shopify catalogue and Shopify's own pricing of the routine (`cartCreate`: subtotal, the discounts Shopify
applies, total) — then discarded. **Nothing of it is stored**: `reports` keeps only the scan, owner, link-token hash and
expiry (`content` is NULL; the 26 reports made before keep their stored content exactly as it is — never read or changed —
and db/models.py refuses any insert with content or any change to stored content), and `result_deliveries` keeps
only each message's status, contact and provider id. Prices are as of that moment. If Shopify can't price the routine,
no total is shown; if the catalogue is unavailable the send fails with `catalogue_unavailable` and can be retried.
A PDF uploaded to WhatsApp (document-header template) is deleted from WhatsApp's media store when the webhook reports
the message delivered/read/failed, right away if the send failed, else by `scripts/purge_whatsapp_media.py --apply`.

**PDF** (`app/services/report_pdf.py`, ReportLab): name and date, every measured value with what it measures and the
internal benchmark, concerns, AM/PM routine with product images, prices, compare-at prices, availability and usage,
optional extras, Shopify's subtotal/discounts/total, and the report link.

**Secure link**: `FRONTEND_PUBLIC_URL/report#t=<token>`. The token is HMAC(JWT_SECRET, report id) — 256 bits, only its
SHA-256 is stored; it sits in the URL fragment (never sent to servers) and the page sends it in `X-Report-Token`.
Links expire after `REPORT_LINK_DAYS` and the owner can withdraw them (`POST /reports/scan/{id}/revoke`); invalid,
expired and withdrawn links all get the same 404. Responses are `no-store`. Rotating `JWT_SECRET` invalidates all links.
Static hosting must serve `index.html` for `/report` (SPA fallback).

**Delivery** (`app/services/delivery.py`): only to the report owner's own email / WhatsApp number, only with their
consent (`users.report_consent_at`: a separate checkbox at signup, or the "Yes, send my report" button), and only after
they verify their **mobile (WhatsApp) number** with a 6-digit code (10 minutes, 5 tries, 1 code/minute, 5/hour per
account and 5/hour per number or address across accounts; only an HMAC is stored). Mobile verification is required for
**every** report, by WhatsApp and by email. The email copy also waits for an **email code** (offered on the results
page) while `EMAIL_REPORT_REQUIRES_EMAIL_VERIFICATION=true` (the default), so a mistyped address never receives
someone's report; set it to `false` to send to the address entered once the mobile is verified. Verifying the mobile releases every waiting report, on both channels. Invalid requests get a `422`
naming only the field and the reason, never the submitted value (no photo or contact data is echoed).
One `result_deliveries` row per report and channel (unique index); retries update it under a row lock, so a report is
never sent twice:

| Status | Meaning |
|---|---|
| `pending` | not sent yet; `reason` says why: `not_configured`, `no_contact`, `test_mode` (not a listed test contact), `no_consent`, `contact_changed` (the account's contact changed after the report was made: never sent to the new one), `mobile_not_verified`, `mobile_verification_unavailable` (email only: WhatsApp isn't set up or the number isn't a test contact, so no mobile code can be sent), `not_verified` (email code, only when required by policy) |
| `sending` | handed to the provider now (a stuck row may be retried after 5 minutes) |
| `accepted` | WhatsApp's Cloud API accepted it; not yet confirmed sent |
| `sent` | email: the SMTP server accepted it · WhatsApp: the webhook reported `sent` |
| `delivered` | WhatsApp webhook reported `delivered`/`read` |
| `failed` | the provider refused/failed (`error`); safe to retry |

Email: summary + PDF attached + link, with a fixed `Message-ID` per report. WhatsApp: an approved template with a short
summary and the link (no PDF attachment). Confirming a contact sends any report waiting for it.

| Method | Path | Description |
|---|---|---|
| POST | `/reports` | `{scan_id}`: make the report (once) and send it wherever ready → status per channel. |
| GET | `/reports/scan/{scan_id}` | Owner: delivery status (the page polls while a message is on its way). |
| GET | `/reports/scan/{scan_id}/pdf` | Owner: the PDF. |
| POST | `/reports/scan/{scan_id}/revoke` | Owner: withdraw the link. |
| GET | `/reports/shared`, `/reports/shared/pdf` | With `X-Report-Token`: the report / its PDF. |
| GET | `/delivery/status` | Per channel: `available`, `verified`, masked `destination`; and `report_consent`. |
| POST | `/delivery/verify/start`, `/delivery/verify/confirm` | One-time code to the user's own contact. |
| POST | `/delivery/scans/{scan_id}/send` | `{channel}`: send or safely retry (records consent). |
| GET/POST | `/delivery/whatsapp/webhook` | Meta subscription check / signed status callbacks (`X-Hub-Signature-256`). |

**Email**: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_SECURITY`.
**WhatsApp** (Cloud API, `POST https://graph.facebook.com/<WHATSAPP_API_VERSION>/<WHATSAPP_PHONE_NUMBER_ID>/messages`):
`WHATSAPP_ACCESS_TOKEN` (system-user token with `whatsapp_business_messaging`), `WHATSAPP_PHONE_NUMBER_ID`, the webhook
(`WHATSAPP_WEBHOOK_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`, subscribe to `messages`) and two templates approved in WhatsApp Manager:
- `WHATSAPP_OTP_TEMPLATE`: category **Authentication**, with a copy-code button (the code fills `{{1}}` and the button).
- `WHATSAPP_RESULTS_TEMPLATE`: category **Utility**, body with 5 variables, e.g. *"Hi {{1}}, your YuriWoori skin-analysis
  report is ready. What we noticed: {{2}}. Morning routine: {{3}}. Evening routine: {{4}}. View your report and continue
  to checkout: {{5}}"*
  To send the PDF itself, approve this template with a **DOCUMENT header** and set `WHATSAPP_RESULTS_TEMPLATE_HAS_DOCUMENT=true`:
  the PDF is uploaded (`POST /{phone-number-id}/media`) and sent as the header document, with the same 5 variables.

**Automatic sending:** right after signup every customer is asked to verify their mobile number with a WhatsApp
code (skipped automatically when WhatsApp isn't set up or the number is already verified). They can instead choose
"Continue without receiving my report"; the analysis still works and they can verify later on the results page.
When their analysis is saved, the report is generated and, with their consent, sent to the verified WhatsApp number
and to their email address automatically. Each channel's status is recorded independently.

### Customer report delivery: local setup and testing
Real messages need real provider accounts; nothing is simulated. Until a channel is configured it shows
"isn't set up yet" and nothing is sent. Work through these steps on your own PC (no AWS, no deployment).

**1. Delivery test mode (on by default).** While `DELIVERY_TEST_MODE=true`, codes and reports go **only** to the
contacts in `DELIVERY_TEST_EMAILS` / `DELIVERY_TEST_WHATSAPP`; every other customer's delivery stays pending with
reason `test_mode` and nothing is sent to them. Reports are never redirected to the test contacts, so test by
signing up with **your own** email and WhatsApp number. Set `DELIVERY_TEST_MODE=false` only when going live.

**2. Fill in `backend/.env`** (copy names from `.env.example`; never commit real values or paste them anywhere):

| Purpose | Variables |
|---|---|
| Test contacts | `DELIVERY_TEST_EMAILS` (your email), `DELIVERY_TEST_WHATSAPP` (your number, any format) |
| Email | `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` |
| WhatsApp | `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_OTP_TEMPLATE`, `WHATSAPP_RESULTS_TEMPLATE`, `WHATSAPP_TEMPLATE_LANGUAGE`, `WHATSAPP_RESULTS_TEMPLATE_HAS_DOCUMENT`, optionally `WHATSAPP_BUSINESS_ACCOUNT_ID` (template check) and `WHATSAPP_API_VERSION` |
| Customer replies -> team | `DELIVERY_REPLY_TO` (Reply-To of report emails), `DELIVERY_REPLY_FORWARD_EMAIL` (WhatsApp messages from customers are emailed here) |
| WhatsApp webhook (optional) | `WHATSAPP_WEBHOOK_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` (needs a public HTTPS address): delivery status + customers' messages |
| Report links | `FRONTEND_PUBLIC_URL` (`http://localhost:2999` locally), `REPORT_LINK_DAYS` |

Email with Google Workspace (yuriwoori.com's mail is hosted on Google): `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`,
`SMTP_SECURITY=starttls`, `SMTP_USERNAME=support@yuriwoori.com`, `SMTP_PASSWORD=` an **App Password** for that
account (requires 2-Step Verification), `SMTP_FROM=YuriWoori <support@yuriwoori.com>`. This works only if
`support@` is a Google Workspace **user** mailbox; if it is a Google Group or an alias it has no password, so log in
as a user who is allowed to "send mail as" `support@` (Gmail settings > Accounts) and keep `SMTP_FROM` as `support@`.
Replies already go to `support@` (`DELIVERY_REPLY_TO`). The domain's SPF record
must also allow Google (`include:_spf.google.com`) and DKIM should be enabled, or mail may be marked as spam.

WhatsApp: in Meta Business Manager, a WhatsApp Business account with a registered sending number, a system-user
token with `whatsapp_business_messaging`, and two templates approved in WhatsApp Manager (described above): an
**Authentication** template with a copy-code button, and a **Utility** report template with 5 body variables
(add a DOCUMENT header and set `WHATSAPP_RESULTS_TEMPLATE_HAS_DOCUMENT=true` to send the PDF itself).

**3. Check the configuration — nothing is sent:**

```bash
cd backend
.venv311\Scripts\python.exe scripts\check_delivery_config.py      # Windows (Linux/macOS: .venv/bin/python)
```

It lists missing settings by name, logs in to the SMTP server and disconnects, reads the WhatsApp number's details,
checks the templates are APPROVED in your language with the right shape (when `WHATSAPP_BUSINESS_ACCOUNT_ID` is set),
and shows whether test mode is on and which test contacts are listed (masked). Repeat until it ends with
`email ready, WhatsApp ready`.

To send **one** test email (only to an address listed in `DELIVERY_TEST_EMAILS`, with the same sender and Reply-To as
report emails), add `--send-test-email <your address>`. It reports whether the SMTP server accepted the message;
check the inbox and the spam folder to confirm delivery.

**4. Restart the backend** — settings are read only when it starts. Stop the running server (Ctrl+C in its terminal),
then from `backend/`:

```bash
.venv311\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The frontend (`cd frontend && npx vite --host 127.0.0.1`) and the database (Docker container) don't need a restart.

**5. Test the workflow** at http://localhost:2999:
1. Sign up with **your own** name, email and WhatsApp number (the ones in the test lists), accept the privacy notice
   and tick **"Send my skin-analysis report …"**.
2. Right after signup, verify your mobile number with the 6-digit code you receive on WhatsApp. The email copy asks for
   an email code on the results page (unless `EMAIL_REPORT_REQUIRES_EMAIL_VERIFICATION=false`).
3. Take the photo and complete the analysis. The report is generated from the saved results and sent automatically.
4. On the routine page, the **"Your skin-analysis report"** panel shows each channel's recorded status:
   **Email** → `Sent` (the SMTP server accepted it); **WhatsApp** → `accepted` (WhatsApp's API accepted it), and
   `sent`/`delivered` only once WhatsApp confirms through the webhook — which a local PC can't receive, so locally
   it stays `accepted`.
5. Open the link in the email or WhatsApp message on this PC: it shows the report and offers the PDF. Changing a
   character in the link gives "isn't valid or has expired".

**Customer replies reach the team:** report emails carry `Reply-To: DELIVERY_REPLY_TO` and say so in the text.
A customer's WhatsApp message to the business number arrives on the webhook and is emailed to
`DELIVERY_REPLY_FORWARD_EMAIL` with the customer's name (when the number belongs to a registered customer), number and
text; media is not forwarded. Meta's webhook retries are de-duplicated, and if forwarding fails the webhook answers 503
so Meta retries. Answering a customer on WhatsApp needs an inbox tool connected to the Cloud API number; the forwarding
email itself doesn't reach the customer. Without the webhook (e.g. on a local PC), WhatsApp messages from customers are
not received at all.

**Retries don't duplicate:** a report already sent (email) or accepted (WhatsApp) is never sent again; `Try again`
appears only after a failure. To test a failure safely, use a wrong `SMTP_PASSWORD` — the email shows `failed` with
a retry, and the WhatsApp status is unaffected. To start a fresh test, run a new analysis rather than resending.

## Customer follow-up spreadsheet (Google Sheets)

Each customer who submits their details gets one row in the team's private Google Sheet **YuriWoori Customer
Tracking** (worksheet tab `CustomerTracking`), kept up to date when they confirm a contact or finish an analysis.
Code: `app/services/customer_sheet.py`, `app/services/google_sheets.py`, `scripts/customer_sheet.py`.

**How it signs in.** A Google Cloud **service account** (server-to-server OAuth 2.0, JWT bearer grant) with scope
`https://www.googleapis.com/auth/spreadsheets`. It has no access to anyone's Drive: it can open only spreadsheets
explicitly shared with its email address. Its JSON key stays on the backend, outside the project folder (a key inside
it is refused); access tokens are kept in memory only. The JWT is signed with Google's official `google-auth` library.

**Reliability.** PostgreSQL is the source of truth. A submission only queues a `customer_sheet_sync` row in the same
transaction; the write runs after the response, so a Google outage never loses a submission or slows the analysis.
Every write first looks the row up by **Customer ID** (the internal user ID, never the email), so an append whose
answer was lost is found and updated, not added twice. A row is marked `synced` only after it is **read back** with
the written values. Quota (429 / rate-limit 403) and 5xx errors are retried with backoff (`Retry-After` honoured); a
rejected key, a sheet not shared, a disabled API, a missing tab or changed columns wait an hour per retry. Values
are written `RAW` (never run as formulas; `+91…` stays text). Updates never touch the team's three columns.
Retries happen on the next customer activity, or schedule `python scripts/customer_sheet.py sync`.

**Columns** (row 1, A–M, exactly): Customer ID · Date Added · Customer Name · Email · Phone / WhatsApp Number ·
Consent Status · Email Verification Status · Phone Verification Status · Analysis Status · Assigned Team Member ·
Follow-up Status · Follow-up Notes · Last Updated. Values come from the database only. Never exported: photos, image
data, measurements, report content, codes, passwords, tokens. Only customers who accepted the privacy notice that
names the Google spreadsheet (version `2026-10-19b` or later) are queued; existing customers are never exported
automatically.

### Setup (owner)

1. **Google Cloud project** (console.cloud.google.com, signed in with your Google account): create a project, e.g.
   "yuriwoori-sheets". APIs & Services → Library → **Google Sheets API** → Enable.
2. **Service account**: IAM & Admin → Service Accounts → Create service account (e.g. `yuriwoori-sheets`). Grant it
   **no project roles** (sharing the sheet is the only access it needs).
3. **Key**: open the service account → Keys → Add key → Create new key → JSON. The browser downloads the file once.
   Move it to a folder outside this project and outside OneDrive, e.g. `C:\Users\<you>\.yuriwoori\google-sheets-key.json`.
   Never commit, email or paste it. If it leaks, delete that key in the console and create a new one.
4. **Sheet**: in Google Sheets create a spreadsheet named **YuriWoori Customer Tracking**, rename the first tab to
   `CustomerTracking`, and type the 13 column names above into A1:M1 (optional: View → Freeze → 1 row).
5. **Share with the service account**: Share → add the service account's email (shown by `check`, ends with
   `.iam.gserviceaccount.com`) as **Editor**, untick "Notify people". Keep General access = **Restricted**.
6. **Team access**: Share → add each team member's Google account (Editor or Commenter). Never choose "Anyone with
   the link". Remove people the same way.
7. **Configure and test** (from `backend/`): set the variables in `.env` (see `.env.example`), then
   ```
   python scripts/customer_sheet.py check                 # settings, key file, service account email (no network)
   python scripts/customer_sheet.py test                  # read-only: token, sheet, tab, columns
   python scripts/customer_sheet.py test-write --confirm  # one fake TEST- row, written twice (no customer data)
   ```
   Delete the TEST- row afterwards. Set `CUSTOMER_SHEET_SYNC_ENABLED=true` and restart the backend only after the
   privacy notice wording has been approved.

**Operations:** `status`, `sync`, `retry`, `reconcile` (dry run; `--apply` queues and writes eligible customers -
this exports real customers; `--all` rewrites every eligible row, e.g. after rows were deleted or edited).

**Known limits:** if a team member sorts the sheet in the instant between the app's lookup and its write, the
read-back detects it, re-queues both customers and repairs their app columns on the next run. Sheets cannot report
its sharing settings through this scope: check Share → General access = Restricted yourself.

### Rollback (earlier Microsoft Excel Online version)

The Excel version needed a Microsoft 365 work/school account (Microsoft's Excel API supports neither personal
OneDrive nor app-only access). It is no longer wired in. What remains of it: `app/services/ms_graph.py` (unused,
marked legacy; delete once approved), the `ms_graph_*` / `customer_sheet_drive_id|item_id|table` fields in
`app/core/config.py` (unused), and the `.secrets/` ignore rules (its token-cache folder; never created here). To
restore it: take `customer_sheet.py`, `scripts/customer_sheet.py`, `tests/test_customer_sheet.py` from the version
before the Google change, set the `MS_GRAPH_*` variables, and revert the privacy-notice line to Microsoft 365 with a
new consent version. The database table `customer_sheet_sync` (migration `b8c9d0e1f2a3`) is used by both versions.

## Scan flow (what the frontend calls)

```
POST /scans                              → scan_id
POST /scans/{id}/frames  (front, JPEG)   → passed? (else ask the user to retake)
POST /scans/{id}/analyze                 → skin profile
GET  /catalogue/recommendations?scan_id={id} → products (from the live store catalogue)
GET  /scans/{id}/routine                 → AM / PM (live products, rebuilt each time)
GET  /catalogue/live?handles=…           → current prices / availability / variants for the cards and cart
GET  /scans/{id}/compatibility           → warnings
```

The frame quality gate (`cv_quality.py`) is deliberately lightweight: it reads the JPEG header and byte statistics
(no pixel decode). A frame passes when sharpness ≥ 15, lighting ≥ 40 and the combined quality ≥ 55. Non-JPEG or
tiny/corrupt images always fail, so clients must send JPEG.

## Skin analysis metrics

`skin_analysis.py` first **finds and validates the face** with MediaPipe Face Landmarker (`data/models/face_landmarker.task`):
exactly one face, fully inside the photo, centred, large enough, not turned or tilted beyond the limits, and not
covered by a hand. Otherwise `/analyze` returns `422` saying what to fix (e.g. *"Move slightly closer"*). The landmarks
outline the measured region (forehead, cheeks, nose, chin; eyes, brows and lips cut out), which is resampled so the
face is always 224 px tall, and only **skin-coloured pixels** (YCrCb mask) inside it are measured. The fixed scale
matters: texture, pores and blemishes are pixel-scale measures and otherwise changed with camera resolution and distance. Metrics (HSV/LAB statistics, edge density, blob detection) are on a 0–100 scale:

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
| `scripts/sync_catalogue.py` | Records the whole live catalogue in the `products` table (by handle, with ingredient links); marks products the store no longer lists inactive (never deletes). Optional — the app records products as it serves them — but run it before `build_embeddings.py`. |
| `scripts/customer_sheet.py` | Customer follow-up spreadsheet (Google Sheets): `check` settings and key file, read-only `test`, `test-write --confirm` (one fake row), `status`, `sync`, `retry`, `reconcile` (dry run unless `--apply`). |
| `scripts/check_delivery_config.py` | Checks the report-delivery settings without sending anything: missing variables, SMTP login, WhatsApp number and template approval, test mode and test contacts (masked). |
| `scripts/seed_ingredient_interactions.py` | Seeds ingredient conflict/synergy rules used by the compatibility check. |
| `scripts/build_embeddings.py` | Builds product/ingredient embeddings for the coach. **Re-run after the store's catalogue changes.** |
| `scripts/capture_store_snapshot.py` | Saves the live store to `tests/fixtures/store_snapshot.json` for the offline tests. |
| `scripts/import_catalogue_csv.py` | Legacy: imports `data/products_export.csv`. Not needed; the app never chooses products from it, and rows it writes are overwritten with live data when served. |
| `scripts/dedupe_products.py` | One-time cleanup of duplicate products created by the old two import paths. |
| `scripts/resolve_shopify_variants.py` | Legacy (needs the Storefront token). Not needed: variant IDs come from the live feed. |

Typical order on a fresh database: sync catalogue → seed interactions → build embeddings.

## Tests

```bash
python -m pytest tests -q
```

`tests/test_unit.py` covers pure logic (config/CORS parsing, frame validation, quality gate, benefit parsing, progress
series, budget extraction). The catalogue tests read the store from `tests/fixtures/store_snapshot.json` (a real
capture of yuriwoori.com, refreshed with `scripts/capture_store_snapshot.py`), so they need no network:
`test_live_catalogue.py` (feed, pages, retries, caching, staleness), `test_catalogue_api.py` (recommender and
`/catalogue/*`), `test_routine_flow.py`, `test_product_records.py`. `tests/test_live_routine_db.py` runs the routine
endpoints against the real database inside a rolled-back transaction, and is skipped when PostgreSQL isn't running.

## Connecting the frontend

The React app reads the API base URL from `VITE_API_URL` (default `http://localhost:8000/v1`). Keep the frontend's
origin in `FRONTEND_ORIGIN`; the default already allows `http://localhost:2999`. See the [frontend README](../frontend/README.md).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Invalid HTTP request received` in the log, `ERR_SSL_PROTOCOL_ERROR` in the browser | The client used `https://`. The server is HTTP only — use `http://localhost:8000/v1`. |
| `503 Database is unavailable` | Postgres isn't running or `DATABASE_URL` is wrong. |
| `503 AI assistant is not configured` | `ANTHROPIC_API_KEY` missing in `.env`. |
| `503 …run out of API credits` | The Anthropic account's credit balance is too low. Add credits at console.anthropic.com — this is a billing action, not a code fix. |
| `502 The AI assistant service failed: …` | Anthropic rejected the request for another reason; the message is Anthropic's own (e.g. an invalid model, rate limit). |
| `503 Skin analysis engine is unavailable` | OpenCV failed to import (e.g. blocked DLL); the app must run from the project `venv`. |
| `/catalogue/recommendations` returns an empty list | No metric crossed a threshold (see `active_concerns` in the response). Not an error. |
| Product endpoints return `503 Could not load live products from https://yuriwoori.com` | The store couldn't be reached (and no copy from the last ~20 minutes exists). Check network access to `YURIWOORI_STORE_URL`; requests retry automatically after 30 s. |
| A product is never recommended | Its product page copy couldn't be read (see the log warning "No product copy on the live page of …"), it is out of stock, or its copy doesn't mention a matching concern. |
| Analyze returns `422 No face found…` | No face was detected near the centre (glasses glare, face too small/off-centre, or another person nearer the middle). Retake facing the camera in soft light. |
| Analyze returns `400 No passed frames` | The frame failed the quality gate or wasn't a valid JPEG; upload a sharper, evenly lit JPEG. |
| Browser shows a CORS error | Add the frontend origin to `FRONTEND_ORIGIN` and restart. |
| Code changes have no effect | Server started without `--reload`; restart it. |
| First coach request is slow | The sentence-transformer model loads (and may download) on first use. |

## Known limitations

- Face validation uses MediaPipe landmarks: a hand over the face is detected, but other coverings (a mask, a scarf) are not, and glasses frames or a beard inside the face outline read as texture. Formula constants and levels were tuned on a handful of photos, not a clinical dataset.
- Skin analysis is a heuristic baseline (`heuristic-cv-v0`), not a clinical or trained model. It is a cosmetic reading only.
- Hydration is estimated from texture and shine, not measured.
- Accounts have no password: a new device opens an existing account with a code emailed to it, so sign-in needs working email (SMTP).
- The quality gate uses JPEG header/byte statistics rather than true pixel sharpness or brightness.
- The coach answers only from retrieved catalogue data and depends on paid Anthropic API access.
