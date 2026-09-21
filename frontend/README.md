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
start → permission → tips → camera → review → processing → results
      → profile → recommendations → products → routine → assistant
```

| Screen | What it does |
|---|---|
| `Start` | Landing page; begin the analysis or open the assistant. |
| `Permission` | Explains camera use; request access or upload a photo instead. |
| `Tips` | Lighting and framing guidance. |
| `Camera` | Live camera with lighting check, countdown auto-capture, manual capture, upload fallback. |
| `Review` | Confirm or retake the photo. |
| `Processing` | Sends the photo to the backend; animated stages; error state with Retake / Try again. |
| `Results` | Per-area score cards with a status (strength / balanced / focus). |
| `Profile` | Skin type, overall score, focus areas and strengths. |
| `Recommendations` | Guidance for each focus area, with the matching products from the catalogue API underneath (each product shown once, under the first area it helps). |
| `Products` | The full list of products matched by the backend to the scan. |
| `Routine` | Morning and evening steps, plus ingredient-compatibility warnings. |
| `Assistant` | Chat with Yuri AI (Claude via the backend). |

Screens after `Processing` need an analysis result; without one, `App` sends the user back to `Start`.

## What comes from the backend

| Feature | Backend endpoint | Notes |
|---|---|---|
| Skin analysis | `POST /scans`, `/scans/{id}/frames`, `/scans/{id}/analyze` | Photo is re-encoded to JPEG and uploaded. |
| Product recommendations | `GET /catalogue/recommendations?scan_id={id}` | Served from the backend's `data/products_export.csv`; includes image, price, step, store link and a match reason. |
| Routine | `GET /scans/{id}/routine` | AM and PM steps with reasons; joined with `GET /products` for step and price. |
| Compatibility warnings | `GET /scans/{id}/compatibility` | Shown when conflicts exist. |
| Yuri AI chat | `POST /coach/message` | Conversation id is kept for follow-up messages. |

Still static on the frontend: the camera's face-lock indicator (simulated — the backend has no face-detection
endpoint), the guidance text on the Recommendations screen (`FOCUS_GUIDANCE`), the suggested chat questions, and the
processing-stage labels.

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
    ├── components/            Button, Header, Logo, ProductCard, ScoreRing
    ├── screens/               One file per step of the journey
    ├── services/
    │   ├── api.js             fetch wrapper, ApiError, API_URL
    │   ├── skinAnalysis.js    Backend calls + response → screen model mapping
    │   └── camera.js          Capture, upload and brightness helpers
    ├── data/
    │   ├── mock.js            Static copy (focus guidance, stages, suggested questions)
    │   └── catalogue.js       Legacy product snapshot; only SITE_URL is still used
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
  - `analyzeSkin(photo)` runs the full scan flow and returns `{ scanId, concerns, profile, recommendations, routine, compatibility }`.
    Recommendations, routine and products are fetched best-effort, so a failure there doesn't discard a successful analysis.
  - `askYuri(message)` posts to the coach and remembers the conversation id.
  - `detectFace()` is a simulated placeholder.

A photo that fails the backend's quality check surfaces as an error on the Processing screen with a hint to retake it.

## Data mapping

The backend returns raw metrics; `buildAnalysis()` in `skinAnalysis.js` turns them into the seven result cards.
Metrics where a higher number means *more of the trait* are flipped so every card is a health score (higher = better).

| Card | Backend field | Direction |
|---|---|---|
| Hydration | `hydration` | as is |
| Oil balance | `oiliness` | `100 − value` |
| Texture | `texture` | as is |
| Redness | `redness` | `100 − value` |
| Pigmentation | `pigmentation` | `100 − value` |
| Pores | `pore_visibility` | `100 − value` |
| Blemishes | `blemish_index` | `100 − value` |

Status per card: **strength** at score ≥ 75; **focus** for the three lowest scores; otherwise **balanced**. The
"overall" score shown on the Profile is the backend's `overall_score`. Face-marker positions, dark circles and fine
lines are not shown because the backend does not measure them.

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
| Chat replies "Sorry, I couldn't answer that…" | Backend coach failure, commonly a missing or unfunded `ANTHROPIC_API_KEY`. |
| Products / Routine say nothing was found | The scan didn't exceed any concern threshold, so the backend recommended nothing. Not an error. |
| Camera doesn't start | Allow camera access in the browser, or use "Upload a photo instead". |
| Changed `.env` but nothing happened | Restart the dev server; rebuild if using `preview`. |

## Known limitations

- Results are a cosmetic, heuristic reading of visible skin, not a medical diagnosis.
- The camera's "Face detected" pill is a UI simulation; only the lighting check is measured.
- Yuri AI depends on the backend's Anthropic access and answers only from the product catalogue.
- No authentication or saved history in the UI yet (the backend supports passport and progress endpoints that the
  frontend does not use).
