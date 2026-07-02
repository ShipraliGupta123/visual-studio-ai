"""
Model registry and static cost table.

This single file delivers TWO of the PRD's headline goals at once:
  - multi-model choice (2.3): the selector is just MODELS.keys()
  - cost transparency (2.6): COST is a static lookup, no provider billing needed

Endpoint strings + per-image prices verified against fal.ai docs (Jun 2026).
Prices drift - treat the credit numbers as a demo-time config, not gospel.
1 credit := $0.01 here, purely for a clean display. Adjust freely.

To add a model: add one row to MODELS and one to COST. Nothing else changes.
"""

# fal.ai endpoint per selectable model (text-to-image endpoints)
# "__pollinations__" entries are handled in engine.py — free, no API key needed.
MODELS = {
    "flux-free":        "__pollinations__:flux",       # FLUX.1 via Pollinations.ai (free)
    "turbo-free":       "__pollinations__:turbo",      # SDXL-Turbo via Pollinations.ai (free, fastest)
    "nano-banana":      "fal-ai/nano-banana",          # Gemini 2.5 Flash Image (fast/cheap)
    "nano-banana-pro":  "fal-ai/nano-banana-pro",      # Gemini 3 Pro Image (text rendering)
    "flux-dev":         "fal-ai/flux/dev",             # FLUX.1 [dev]
    "flux-schnell":     "fal-ai/flux/schnell",         # FLUX.1 [schnell] (fastest)
}

# Base credits per single image, per model (1 credit = $0.01 display unit).
# nano-banana-pro ~ $0.15/img -> 15 credits ; flux schnell is cheap -> 2, etc.
_BASE_CREDITS = {
    "flux-free":        0,
    "turbo-free":       0,
    "nano-banana":      4,
    "nano-banana-pro":  15,
    "flux-dev":         5,
    "flux-schnell":     2,
}

# Aspect ratio -> rough size multiplier (bigger canvas, slightly more cost).
_RATIO_MULT = {
    "1:1": 1.0,
    "3:4": 1.0,
    "9:16": 1.1,
    "16:9": 1.1,
}

VALID_RATIOS = list(_RATIO_MULT.keys())


def estimate_credits(model: str, aspect_ratio: str, num_variations: int) -> int:
    """Live estimate shown on the submit button (PRD 2.6).
    Pure arithmetic on a static table - intentionally NOT a provider call."""
    base = _BASE_CREDITS[model]
    mult = _RATIO_MULT.get(aspect_ratio, 1.0)
    return round(base * mult * num_variations)
