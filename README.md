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
