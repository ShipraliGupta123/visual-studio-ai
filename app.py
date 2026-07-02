"""
FastAPI surface for the multi-model image studio POC.

Build order is the PRD's 2 -> 3 -> 1:
  Module 2 (generation core): /estimate, /generate  + validation 2.2/2.6/2.7
  Module 3 (output):          grid via job result, error mapping 3.4, rate limit 3.5
  Module 1 (auth): STUBBED - a fake fixed user with seeded credits. No OAuth, no DB.

Run:  uvicorn app:app --reload --port 8000
Env:  FAL_KEY=...
Deps: fastapi uvicorn[standard] fal-client slowapi python-multipart
"""
import os
import uuid
from dotenv import load_dotenv

load_dotenv()  # reads .env into os.environ before anything else runs
from typing import Dict, List, Optional

from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from models import MODELS, VALID_RATIOS, estimate_credits
from engine import generate, GenerationError

# ---- rate limiter (PRD 3.5) ----
limiter = Limiter(key_func=get_remote_address)

app = FastAPI()
app.state.limiter = limiter
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================================================================
# MODULE 1 (STUBBED): fake auth + in-memory credit wallet.
# Replace get_current_user with a real managed-auth dependency later.
# ======================================================================
FAKE_USER = {"id": "demo-user", "email": "demo@example.com", "credits": 500}


def get_current_user() -> dict:
    """Stub: always the same demo user. Swap for Clerk/Supabase/Auth.js later."""
    return FAKE_USER


# ---- in-memory job store (POC only) ----
JOBS: Dict[str, dict] = {}


# ── serve the frontend ──────────────────────────────────────────────────────
@app.get("/")
def index():
    return FileResponse("index.html")


# ======================================================================
# MODULE 2: generation core
# ======================================================================

class EstimateReq(BaseModel):
    model: str
    aspect_ratio: str
    num_variations: int = Field(ge=1, le=4)


@app.post("/estimate")
def estimate(req: EstimateReq):
    """Live cost estimate for the submit button (PRD 2.6)."""
    if req.model not in MODELS:
        raise HTTPException(400, "Unknown model")
    if req.aspect_ratio not in VALID_RATIOS:
        raise HTTPException(400, "Unsupported aspect ratio")
    return {"credits": estimate_credits(req.model, req.aspect_ratio, req.num_variations)}


class GenerateReq(BaseModel):
    prompt: str = ""
    model: str
    aspect_ratio: str
    num_variations: int = Field(ge=1, le=4)
    reference_image_url: Optional[str] = None


@app.post("/generate")
@limiter.limit("5/minute")  # PRD 3.5: cap parallel/abusive requests
def start_generation(
    request: Request,                      # required by slowapi
    req: GenerateReq,
    bg: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    # --- validations (PRD 2.6 / 2.7) ---
    if req.model not in MODELS:
        raise HTTPException(400, "Unknown model")
    if req.aspect_ratio not in VALID_RATIOS:
        raise HTTPException(400, "Unsupported aspect ratio")
    if not req.prompt.strip() and not req.reference_image_url:
        raise HTTPException(400, "Add a prompt or a reference image before generating.")

    cost = estimate_credits(req.model, req.aspect_ratio, req.num_variations)
    if user["credits"] < cost:
        raise HTTPException(402, "Not enough credits for this generation.")

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "running", "images": [], "error": None, "cost": cost}

    def _run():
        try:
            def on_image(data_uri):
                # Append each image the moment it's ready — frontend sees it on next poll
                JOBS[job_id]["images"].append(data_uri)

            urls = generate(
                req.model, req.prompt, req.aspect_ratio,
                req.num_variations, req.reference_image_url,
                on_image=on_image,
            )
            user["credits"] -= cost
            JOBS[job_id]["status"] = "done"
        except GenerationError as ge:
            JOBS[job_id] = {"status": "error", "images": [],
                            "error": ge.cause, "cost": cost}

    bg.add_task(_run)
    return {"job_id": job_id, "estimated_cost": cost,
            "credits_remaining": user["credits"]}


# ======================================================================
# MODULE 3: output handling - poll returns grid data or mapped error
# ======================================================================

@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    return JOBS.get(job_id, {"status": "not_found"})


@app.get("/me")
def me(user: dict = Depends(get_current_user)):
    """Credits + identity for the header. (Stubbed user.)"""
    return {"email": user["email"], "credits": user["credits"]}


@app.get("/config")
def config():
    """Drives the frontend selectors so models/ratios live in one place."""
    return {"models": list(MODELS.keys()), "aspect_ratios": VALID_RATIOS}


# ======================================================================
# EMAIL BUILDER: uses Claude to generate an HTML email from brand details
# ======================================================================

class EmailReq(BaseModel):
    company: str
    tagline: str = ""
    tone: str = "luxury"


@app.post("/generate-email")
def gen_email(req: EmailReq):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            400,
            "ANTHROPIC_API_KEY is not set. Add it to your environment and restart the server.",
        )

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are an expert email designer. Generate a complete, production-ready HTML email.

Brand details:
- Company: {req.company}
- Tagline: {req.tagline or "Pure. Cold. Perfect."}
- Tone: {req.tone}
- Product: Ultra-pure Himalayan mineral water — premium and luxury

Technical rules (email clients are strict):
- ALL CSS must be inline on every element — no <style> blocks, no classes
- Table-based layout for broad email client support
- Max width 600px, centered with margin:0 auto

Content structure:
1. Hero image — use exactly: <img src="PRODUCT_IMAGE_PLACEHOLDER" alt="{req.company}" style="width:100%;max-width:600px;display:block;margin:0 auto">
2. Brand headline (compelling, matches tone)
3. Body copy — 2-3 sentences on purity, origin, and luxury
4. CTA button — href="#", label fits the brand
5. Footer — brand name + unsubscribe link

Visual direction: {req.tone} aesthetic. Choose colors, spacing, and typography to match that feel.

Return ONLY the complete HTML (<!DOCTYPE html> … </html>). No explanation, no markdown fences."""

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return {"html": msg.content[0].text}
