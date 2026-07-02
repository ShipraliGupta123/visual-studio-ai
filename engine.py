"""
Generation engine. One fal.ai call pattern, model passed as a parameter -
this is what makes 'multi-model' a config change, not new code per provider.

Also owns PRD 3.4: map ugly provider errors to accurate, human causes.
"""
import base64
import fal_client  # needs FAL_KEY env var
import os
import random
import urllib.request
from urllib.parse import quote
from typing import Optional

from models import MODELS


class GenerationError(Exception):
    """Carries a user-facing cause (PRD 3.4), not a raw backend string."""
    def __init__(self, cause: str):
        super().__init__(cause)
        self.cause = cause


def _map_error(e: Exception) -> str:
    """Translate provider/SDK exceptions into accurate user-facing causes."""
    msg = str(e).lower()
    if "content" in msg or "safety" in msg or "moderation" in msg or "nsfw" in msg:
        return "This prompt was blocked by the model's content policy. Try rephrasing."
    if "timeout" in msg or "timed out" in msg:
        return "The model took too long to respond. Please try again."
    if "rate" in msg and "limit" in msg:
        return "The model is busy right now (rate limit). Wait a moment and retry."
    if "invalid" in msg and ("image" in msg or "url" in msg):
        return "The reference image couldn't be read. Try a different file."
    if any(k in msg for k in ("auth", "credential", "401", "403", "unauthorized", "api key", "invalid key", "forbidden")):
        return "fal.ai API key is missing or invalid. Restart the server with a real FAL_KEY. Use flux-free or turbo-free to test without a key."
    return f"Generation failed: {str(e)[:120]}"


_RATIO_DIMS = {
    "1:1":  (1024, 1024),
    "3:4":  (768,  1024),
    "9:16": (576,  1024),
    "16:9": (1024, 576),
}


def _fetch_data_uri(url: str) -> str:
    """Downloads one image and returns it as a base64 data URI."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
        mime = resp.headers.get_content_type() or "image/jpeg"
        b64 = base64.b64encode(raw).decode()
        return f"data:{mime};base64,{b64}"


def _pollinations_generate(
    variant: str,
    prompt: str,
    aspect_ratio: str,
    num_variations: int,
    on_image=None,          # called with each data-URI as soon as it's ready
) -> list[str]:
    w, h = _RATIO_DIMS.get(aspect_ratio, (1024, 1024))
    encoded = quote(prompt)

    data_uris = []
    for i in range(num_variations):
        seed = random.randint(1, 99999)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width={w}&height={h}&seed={seed}&model={variant}&nologo=true"
        )
        try:
            uri = _fetch_data_uri(url)
            data_uris.append(uri)
            if on_image:
                on_image(uri)          # notify caller immediately
            print(f"[pollinations] image {i+1}/{num_variations} OK")
        except Exception as e:
            print(f"[pollinations] image {i+1}/{num_variations} FAILED: {e}")

    if not data_uris:
        raise GenerationError("All images failed to generate from Pollinations. Please try again.")

    return data_uris


def generate(
    model: str,
    prompt: str,
    aspect_ratio: str,
    num_variations: int,
    reference_image_url: Optional[str] = None,
    on_image=None,
) -> list[str]:
    """Returns a list of image data-URIs/URLs. Raises GenerationError on failure."""
    endpoint = MODELS[model]
    if endpoint.startswith("__pollinations__:"):
        variant = endpoint.split(":")[1]
        return _pollinations_generate(variant, prompt, aspect_ratio, num_variations, on_image=on_image)

    fal_key = os.environ.get("FAL_KEY", "")
    if not fal_key or fal_key.lower() == "dummy":
        raise GenerationError(
            "This model needs a real fal.ai API key. "
            "Get one free at fal.ai, then restart the server with FAL_KEY=your_key. "
            "To test for free right now, switch to flux-free or turbo-free."
        )

    args: dict = {
        "prompt": prompt,
        "num_images": num_variations,
        "aspect_ratio": aspect_ratio,
    }
    if reference_image_url:
        # nano-banana family takes image_urls for image-to-image / reference
        args["image_urls"] = [reference_image_url]

    try:
        result = fal_client.subscribe(endpoint, arguments=args)
        return [img["url"] for img in result["images"]]
    except Exception as e:  # noqa: BLE001 - we deliberately convert everything
        raise GenerationError(_map_error(e)) from e
