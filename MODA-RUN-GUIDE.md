# MODA — Run Guide

Run the full stack locally: FastAPI backend + Next.js frontend.

**Prerequisites:** Docker Desktop, Python 3.11+, Node 18+

You'll use two terminals — one for the backend, one for the frontend.

---

## Terminal 1 — Backend

```bash
unzip moda-backend.zip && cd moda-backend

# 1. Start Postgres (with pgvector) in Docker
docker compose up -d

# 2. Python environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

# 3. Ingest outfit images (feed is empty without this)
#    Put images in images/, fill out a CSV like data/outfits.sample.csv
python -m scripts.ingest --csv data/outfits.csv --blend-caption

# 4. Start the API
uvicorn app.main:app --reload
```

Verify: open http://localhost:8000/docs — you should see the API docs.

Notes:
- First ingest downloads the CLIP model (~600MB), one time only.
- The CSV `image` column accepts URLs too, so you can test with a few
  Unsplash links before curating real images.
- To verify the whole recommendation loop without the UI:
  `python -m scripts.smoke_test`

---

## Terminal 2 — Frontend

```bash
unzip moda-frontend.zip && cd moda-frontend

npm install
cp .env.local.example .env.local   # points at http://localhost:8000
npm run dev
```

Open http://localhost:3000 → splash → sign up → quiz → personalized feed.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Feed shows "Demo catalog" banner | Backend not reachable — make sure uvicorn is running on port 8000 |
| `docker compose up` port conflict | Another Postgres is on 5432. Change the mapping in docker-compose.yml to `"5433:5432"` and update `DATABASE_URL` in `.env` to port 5433 |
| Feed is empty (no banner) | No outfits ingested yet — run step 3 |
| `pip install` fails on torch | Make sure you're on Python 3.11/3.12; on Mac use the default pip wheel (no CUDA needed) |
| Quiz hangs ~1 min on first submit | CLIP model loading on first use — subsequent calls are fast |

## The satisfying end-to-end test

1. Sign up, take the quiz picking one clear aesthetic (e.g. minimal + monochrome)
2. Like 4–5 pieces of that aesthetic in the feed
3. Refresh the feed — recommendations should visibly shift toward what you liked
