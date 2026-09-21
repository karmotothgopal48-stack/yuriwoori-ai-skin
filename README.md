# YuriWoori — AI Skin Analysis

Monorepo for the YuriWoori skin-analysis experience: a guided face scan, an explained skin profile, matched
products from the YuriWoori catalogue, an AM/PM routine and a skincare chat assistant.

```
yuriwoori-final/
├── frontend/   React + Vite + Tailwind single-page app        → http://localhost:2999
└── backend/    FastAPI + PostgreSQL (pgvector) + OpenCV API   → http://localhost:8000/v1
```

| Folder | What it is | Docs |
|---|---|---|
| [`frontend/`](frontend) | The user-facing app: camera capture, results, recommendations, routine, chat | [frontend/README.md](frontend/README.md) |
| [`backend/`](backend) | Scan analysis, catalogue (`data/products_export.csv`) recommendations, routine, coach | [backend/README.md](backend/README.md) |

## Quick start

Run each service in its own terminal. Start the backend first.

```bash
# 1. Backend  (needs Python 3.11+, PostgreSQL with pgvector — see backend/README.md)
cd backend
python -m venv venv
venv\Scripts\activate                # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env               # then fill in DATABASE_URL, ANTHROPIC_API_KEY, …
alembic upgrade head
python scripts/import_catalogue_csv.py
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 2. Frontend  (needs Node 18+)
cd frontend
npm install
copy .env.example .env               # VITE_API_URL=http://localhost:8000/v1
npm run dev
```

Open <http://localhost:2999> and run a scan. The API docs are at <http://localhost:8000/docs>.

## How the two halves connect

- The frontend calls the backend at `VITE_API_URL` (`frontend/.env`), which must be plain `http://` locally.
- The backend allows the frontend's origin through `FRONTEND_ORIGIN` (`backend/.env`); the default already includes
  `http://localhost:2999`.

## Notes

- `.env` files hold local secrets and are git-ignored; copy from each folder's `.env.example`.
- Saved scan photos (`backend/app/uploads/`) are personal images and are git-ignored.
- `backend/src/app/passport/page.tsx` is a leftover Next.js file that the backend does not use.
