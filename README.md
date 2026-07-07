# Multi-Model Image Studio — POC (PRD v1.0.0)

A ChatGPT-style front door over multiple image models, with live cost
transparency. Built in the PRD's order: **module 2 → 3 → 1**, auth stubbed.

```
prompt + model + ratio + variations (+ optional reference)
   │   POST /generate  (validates 2.2/2.6/2.7, rate-limited 3.5)
   ▼
fal.ai  (model = config string)  ──►  grid of 1–4 images
   │                                   click-expand, download, regenerate (3.x)
   └─ live estimate via POST /estimate (static table — no provider billing)
```

## Files
- `models.py` — **the keystone.** Model registry (multi-model 2.3) + static cost
  table (transparency 2.6). Add a model = add two rows.
- `engine.py` — one fal.ai call, model as a parameter + error→cause mapping (3.4)
- `app.py` — FastAPI: `/estimate`, `/generate`, `/jobs/{id}`, `/me`, `/config`;
  stubbed auth + in-memory credits (module 1), rate limit (3.5)

## What's IN (success bar = "core multi-model loop works")
Multi-model selection, live cost estimate, 1–4 variations, reference upload,
grid output, mapped errors, rate limiting, credit check/decrement.

## What's STUBBED / CUT (per your answers)
- **Auth** → fixed `FAKE_USER` with seeded credits. No Google/FB/email-verify, no DB.
  Swap `get_current_user` for Clerk/Supabase/Auth.js when auth becomes real.
- **Credits** → display number that decrements on success. No purchase flow.
- **History (3.6), per-tile regenerate, video** → later phases, omitted.

## Setup
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export FAL_KEY=...
uvicorn app:app --reload --port 8000
```
Frontend (Next.js, same stack as before) calls:
`/config` (populate selectors) → `/estimate` (on every selection change) →
`/generate` → poll `/jobs/{id}` → render grid. `/me` for the credits header.

## Verify before demo
- **Endpoint strings + arg names in `models.py`/`engine.py`** against fal.ai's
  current docs. `nano-banana` takes `image_urls` for reference; FLUX endpoints
  may differ slightly. Strings drift — confirm the day you build.
- The **credit numbers are a display config**, loosely pegged to fal pricing
  (nano-banana-pro ≈ $0.15/img). Tune for the demo narrative.

## Deploying to Railway
This app is already Railway-ready: FastAPI + `Procfile` + `requirements.txt`,
no local disk writes, frontend calls same-origin (`API = ""` in `index.html`).

1. **Push to GitHub** — Railway deploys from a connected repo.
2. **railway.app → New Project → Deploy from GitHub repo** → select this repo.
   Railway's Nixpacks builder detects Python via `requirements.txt` and runs
   the `Procfile` start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`.
3. **Add environment variables** (service → Variables tab), copied from your
   local `.env` (never committed — it's gitignored):
   - `FAL_KEY`
   - `ANTHROPIC_API_KEY`
4. **Settings → Networking → Generate Domain** for a public `*.up.railway.app` URL.
5. Verify: page loads, `/config` returns models, a generation runs end-to-end,
   and `/generate-email` returns HTML.

No `runtime.txt` is pinned — Railway's Nixpacks default Python version is used.
None of the current dependencies need a specific version, so this should build
without extra config; add a `runtime.txt` only if a build fails on Python version.

## Demo-only shortcuts — replace before real users touch this
Everything below works for a POC/demo but will silently break or reset in a
real deployment. None of it is Railway-specific — it'd need fixing on any host.

- **Auth is fake.** `get_current_user()` in `app.py` always returns the same
  hardcoded `FAKE_USER`. Every visitor shares one identity and one credit
  balance. Replace with real auth (Clerk/Supabase/Auth.js) before multi-user use.
- **Credits live in a Python dict, not a database.** `FAKE_USER["credits"]`
  resets to 500 on every server restart/redeploy, and isn't shared across
  multiple server instances/workers. No purchase flow exists.
- **Jobs live in the `JOBS` dict in memory (`app.py`).** Same problem: a
  restart wipes in-flight/completed generations, and it won't work if Railway
  ever scales this to >1 instance (each instance has its own `JOBS`/`FAKE_USER`).
  Needs Postgres/Redis to be real.
- **Credit costs are a static lookup table** (`models.py`), not live provider
  billing — a rough display number, not an accounting system.
- **Rate limiting (`slowapi`, 5/minute) is per-process, in-memory** — resets on
  restart and isn't shared across instances. Fine for a demo, not for abuse
  protection at scale.
- **CORS is wide open** (`allow_origins=["*"]` in `app.py`) since frontend and
  API are same-origin today. Lock this down if the frontend ever moves to a
  different origin.
- **No file persistence for generated images** — everything is returned as a
  data URI or a fal.ai-hosted URL. Fine as-is, but if you want a gallery/history
  feature (3.6, already cut from scope) you'll need real storage (S3/R2/etc.).
