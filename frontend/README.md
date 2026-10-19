# YuriWoori — AI Skin Analysis (Frontend)

A React single-page app that guides a user through a face scan, shows an explained skin analysis, and recommends
YuriWoori products and a morning/evening routine. It also includes "Yuri AI", a skincare chat assistant.
Analysis, recommendations, routine and chat are served by the FastAPI backend (see the [backend README](../backend/README.md)).

- **Stack:** React 18, Vite 6, Tailwind CSS 4, lucide-react icons
- **Dev server:** <http://localhost:2999> (fixed port, `strictPort`)
- **Backend:** `http://localhost:8000/v1` by default, configurable via `VITE_API_URL`

---

## Contents

1. [User journey](#user-journey)
2. [What comes from the backend](#what-comes-from-the-backend)
3. [Project structure](#project-structure)
4. [Getting started](#getting-started)
5. [Configuration](#configuration)
6. [Scripts](#scripts)
7. [How the API layer works](#how-the-api-layer-works)
8. [Data mapping](#data-mapping)
9. [Design system](#design-system)
10. [Troubleshooting](#troubleshooting)
11. [Known limitations](#known-limitations)

---

## User journey

Navigation is a simple state machine in `src/App.jsx` (no router). The header shows step progress through `FLOW`:

```
start → signup → permission → tips → camera → review → processing
      → profile → concerns → routine → products → (official yuriwoori.com product page)
assistant (Ask Yuri) is reachable from Start, Routine and Products, outside the numbered steps
/admin  → protected admin dashboard (separate app: login, metrics, analyses table, Export Excel)
```

Signup (name + email + required privacy-notice consent) must happen before any camera step; a saved session is
checked with `GET /users/me` on load. Only the session token is kept in the browser (`localStorage`); the admin
token lives in `sessionStorage` and ends with the tab. Opening a product page from a routine step also sends a
best-effort `product_clicked` event, and reaching the Routine screen sends `recommendations_shown`; tracking never
blocks the link. `/admin` needs the static host to serve `index.html` for that path (Vite dev does).

| Screen | What it does |
|---|---|
| `Start` | Landing page; begin the analysis or open Ask Yuri. |
| `Permission` | Explains camera use and that the photo is saved on the server with the scan. |
| `Tips` | Guidance that maps to the real checks: even light, one centred face, fill the oval, no glare, hold still. |
| `Camera` | Live camera with on-device face/hand detection and full-face checks (MediaPipe), a lighting check, capture enabled only for a usable face or a hand, and "Upload a photo instead". The server repeats the checks after capture. |
| `Review` | Confirm or retake; explains which checks the server runs next. |
| `Processing` | Real progress through the four backend steps (upload → quality check → face + skin analysis → product matching). Error states per cause: quality check failed or no centred face → Retake; server unreachable → Try again. |
| `Profile` | Skin type, overall score, a one-line summary, the seven measurements next to the YuriWoori typical benchmark (each with "What was measured"), key insights, the photo quality check and how it was analysed. |
| `Routine` | The only place products are recommended: morning and evening steps, plus optional extras (e.g. masks). Each product card shows live details from yuriwoori.com (`GET /catalogue/live`: image, price, original price, discount, availability) with Add to cart / quantity, official "How to use" text, the backend's reason and a product link; ingredient interaction notes follow. |
| Cart (header + drawer) | One cart for the app (`services/cart.jsx`, kept in this browser): items merge by Shopify variant, quantity +/−, remove, subtotal, and "Proceed to checkout", which opens yuriwoori.com's own Shopify cart. |
| `Assistant` | Chat with Yuri AI (Claude via the backend). Backend errors are shown as-is. |

Screens after `Processing` need an analysis result; without one, `App` sends the user back to `Start`.

## What comes from the backend

| Feature | Backend endpoint | Notes |
|---|---|---|
| Skin analysis | `POST /scans`, `/scans/{id}/frames`, `/scans/{id}/analyze` | Photo is re-encoded to JPEG and uploaded. |
| Product recommendations | `GET /catalogue/recommendations?scan_id={id}` | Served from the backend's `data/products_export.csv`; includes image, price, step, store link, `matched_concerns`, `active_concerns`, key benefit and how-to-use text. |
| Routine | `GET /scans/{id}/routine` | AM and PM steps with reasons; joined with `GET /products` (step, price, URL) and `GET /catalogue/products` (official how-to-use text, matched by product handle). |
| Ingredient notes | `GET /scans/{id}/compatibility` | Shown when interactions exist (synergistic / caution / avoid in the same routine). |
| Yuri AI chat | `POST /coach/message` | Conversation id is kept for follow-up messages. |

Still static on the frontend: the "what was measured" descriptions and concern guidance (`METRIC_INFO`,
`FOCUS_GUIDANCE` in `data/mock.js`), the suggested chat questions, and the processing-stage labels (their progress
is driven by the real API calls).

## Project structure

```
frontend/
├── index.html                 Vite entry (fonts, favicon, title)
├── vite.config.js             React + Tailwind plugins, port 2999
├── package.json
├── .env / .env.example        VITE_API_URL
├── public/assets/             Logos and the analysis illustration
├── dist/                      Production build output (generated)
└── src/
    ├── main.jsx               React root
    ├── App.jsx                Screen state machine and shared state
    ├── index.css              Tailwind import + brand theme tokens
    ├── components/            Button, Header, Logo, MetricBar, ProductCard, ScoreRing
    ├── screens/               One file per step of the journey
    ├── services/
    │   ├── api.js             fetch wrapper, ApiError, API_URL
    │   ├── skinAnalysis.js    Backend calls + response → screen model mapping
    │   └── camera.js          Capture, upload and brightness helpers
    ├── data/
    │   ├── mock.js            Static copy (focus guidance, stages, suggested questions)
    │   (no product data in the frontend: every product comes from the backend API / official catalogue)
    └── theme/brand.js         Brand colour and logo constants
```

## Getting started

**Prerequisites:** Node.js 18+ (developed on Node 24) and the backend running.

```bash
npm install
copy .env.example .env      # Windows   (cp .env.example .env on macOS/Linux)
npm run dev
```

Open <http://localhost:2999>. Start the backend first (see its README), then run a scan.

The camera needs a secure context: `localhost` works; other hosts require HTTPS.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000/v1` | Base URL of the backend API. Must be **`http://`** for the local backend, and include `/v1`. |

Vite reads `.env` only at startup — **restart `npm run dev` after changing it**. For `npm run preview`, rebuild
first, because the value is baked into the bundle at build time.

The backend must list this app's origin in its `FRONTEND_ORIGIN` (default already includes `http://localhost:2999`).

## Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start the dev server on port 2999. |
| `npm run build` | Production build into `dist/`. |
| `npm run preview` | Serve the built `dist/` on port 2999. |

## How the API layer works

Screens never call `fetch` directly. They use two files:

- **`src/services/api.js`** — `api(path, { method, body })` prefixes `API_URL`, sends JSON, and throws an `ApiError`
  with a readable message. It handles FastAPI's `detail` (string or validation list) and a friendly message when the
  server is unreachable.
- **`src/services/skinAnalysis.js`** — the only place that knows the backend's shapes:
  - `analyzeSkin(photo, onStage)` runs the full scan flow, reports real progress through `onStage`
    (`upload` → `quality` → `analyze` → `match` → `done`), and returns
    `{ scanId, quality, profile, concerns, activeConcerns, catalogueCount, recommendations, routine, compatibility }`.
    Recommendations, routine and product lists are fetched best-effort, so a failure there doesn't discard a successful analysis.
    Errors carry a `kind` (`quality`, `face`, `photo`, `network`, `server`) so Processing can show the right advice.
  - `askYuri(message)` posts to the coach and remembers the conversation id.

## Data mapping

The backend returns seven 0–100 values. They are shown **exactly as returned** (not inverted or re-scaled), with the
direction stated on each: hydration and texture are "higher is better"; the rest are "higher means more of this trait".

| Label | Backend field | Concern tags used by the recommender |
|---|---|---|
| Hydration | `hydration` | `hydration` |
| Oiliness | `oiliness` | `oiliness` |
| Texture | `texture` | none — measured only, never used to pick products |
| Redness | `redness` | `redness` |
| Uneven tone | `pigmentation` | `brightening`, `uneven-tone` |
| Pore visibility | `pore_visibility` | `pore-visibility` |
| Blemishes | `blemish_index` | `blemish` |

A measurement is shown as **"Stood out"** only when the backend lists one of its tags in `active_concerns` (it crossed
the backend's own threshold); the frontend never re-derives thresholds. The overall score is the backend's
`overall_score`. Confidence scores, face markers, dark circles, fine lines and sensitivity are not shown because the
backend does not measure them.

## Design system

Based on the YuriWoori Brand Book v1.2. Colour tokens are defined once in `src/index.css` (`@theme`) and mirrored in
`src/theme/brand.js` for SVG/inline use.

| Token | Hex |
|---|---|
| `jade` | `#005C5D` |
| `jade-soft` | `#9DD4CA` |
| `jade-line` | `#BDDCCD` |
| `mist` | `#E3ECEB` |
| `sage` | `#528778` |
| `cream` | `#F1F5EB` |
| `aqua` | `#D5EEE7` |
| `ink` / `ink-soft` | `#1C2B2A` / `#55676A` |

Typography: **DM Serif Display** for headings, **Montserrat** for body (loaded from Google Fonts in `index.html`).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ERR_SSL_PROTOCOL_ERROR` / backend logs "Invalid HTTP request" | `VITE_API_URL` uses `https://`. Set it to `http://localhost:8000/v1` and restart `npm run dev`. |
| "Can't reach the YuriWoori server" | Backend isn't running, wrong port, or `VITE_API_URL` is wrong. |
| CORS error in the console | Add this app's origin to the backend's `FRONTEND_ORIGIN` and restart the backend. |
| "This photo didn't pass the quality check" | Retake in soft, even light; very dark, bright or blurry photos fail the gate. |
| A 500 from `/analyze` | Backend problem — check the backend terminal. Make sure it was restarted after code changes. |
| Chat replies "Sorry, I couldn't answer that…" | Backend coach failure. The message now includes the specific reason from the backend, e.g. missing `ANTHROPIC_API_KEY` or the Anthropic account being out of credits. |
| Products / Routine say nothing was found | The scan didn't exceed any concern threshold, so the backend recommended nothing. Not an error. |
| Camera doesn't start | Allow camera access in the browser, or use "Upload a photo instead". |
| Changed `.env` but nothing happened | Restart the dev server; rebuild if using `preview`. |

## Known limitations

- Results are a cosmetic, rule-based image reading of visible skin (OpenCV, `heuristic-cv-v0`), not a trained AI
  model and not a medical diagnosis.
- The camera only checks lighting on the device; the face is found by the server after capture.
- There is no pre-scan questionnaire: the backend has no endpoint that accepts self-reported skin type or concerns.
- Stock/availability is not shown: the CSV export is a one-time snapshot, not live inventory.
- Usage text is the product's own "How to Use" copy; no frequency is added beyond what that text says.
- Yuri AI depends on the backend's Anthropic access and answers only from the product catalogue.
- No authentication or saved history in the UI yet (the backend supports passport and progress endpoints that the
  frontend does not use).
