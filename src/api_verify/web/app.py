from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .models import VerifyRequest
from .ratelimit import RateLimiter
from .runner import run_verification
from .safety import UnsafeEndpoint, validate_endpoint
from .scorer import score_results

log = logging.getLogger("apiverify")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

STATIC_DIR = Path(__file__).parent / "static"

RATE_LIMIT_PER_HOUR = int(os.environ.get("APIVERIFY_RATE_LIMIT_PER_HOUR", "5"))
REDIS_URL = os.environ.get("APIVERIFY_REDIS_URL") or None


class VerifyBody(BaseModel):
    protocol: Literal["openai", "anthropic", "gemini"]
    endpoint: str = Field(min_length=1, max_length=512)
    api_key: str = Field(min_length=1, max_length=512)
    model: str = Field(min_length=1, max_length=200)
    mode: Literal["quick", "deep"] = "quick"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.limiter = RateLimiter(REDIS_URL, max_per_hour=RATE_LIMIT_PER_HOUR)
    log.info("startup complete; rate_limit_per_hour=%s redis=%s", RATE_LIMIT_PER_HOUR, bool(REDIS_URL))
    try:
        yield
    finally:
        await app.state.limiter.close()


app = FastAPI(title="apiverify.aidcmo.com", lifespan=lifespan)


def _client_ip(request: Request) -> str:
    # SECURITY: This is safe ONLY because our nginx site config uses
    # `proxy_set_header X-Forwarded-For $remote_addr` (replace, not append).
    # If anyone changes that to $proxy_add_x_forwarded_for, a client-supplied
    # header would land at the right position and bypass per-IP rate limits.
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/verify")
async def verify(body: VerifyBody, request: Request) -> JSONResponse:
    # Validate the endpoint BEFORE consuming rate-limit quota — typos and SSRF
    # attempts shouldn't burn a real user's hourly budget.
    try:
        safe_endpoint = validate_endpoint(body.endpoint)
    except UnsafeEndpoint as exc:
        raise HTTPException(status_code=400, detail=f"endpoint rejected: {exc}")

    ip = _client_ip(request)
    rl = await request.app.state.limiter.check(ip)
    if not rl.allowed:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(rl.retry_after_seconds)},
            content={
                "error": "rate_limited",
                "message": f"You can run at most {RATE_LIMIT_PER_HOUR} verifications per hour from one IP.",
                "retry_after_seconds": rl.retry_after_seconds,
            },
        )

    req = VerifyRequest(
        protocol=body.protocol,
        endpoint=safe_endpoint,
        api_key=body.api_key,
        model=body.model,
        mode=body.mode,
    )

    log.info("verify: protocol=%s model=%s mode=%s ip=%s", req.protocol, req.model, req.mode, ip)

    try:
        results = await run_verification(req)
    except Exception as exc:
        # Don't log.exception() here — the chained exception can carry the raw
        # httpx Request, including Authorization / x-api-key headers.
        log.error("verification failed: protocol=%s model=%s err=%s", req.protocol, req.model, type(exc).__name__)
        raise HTTPException(status_code=500, detail=f"verification crashed: {type(exc).__name__}")

    summary = score_results(results, requested_model=body.model)
    # intentionally do NOT echo back the api_key
    summary["request"] = {
        "protocol": req.protocol,
        "endpoint": req.endpoint,
        "model": req.model,
        "mode": req.mode,
    }
    summary["rate_limit"] = {"remaining_this_hour": rl.remaining, "max_per_hour": RATE_LIMIT_PER_HOUR}
    return JSONResponse(content=summary)


# Static frontend
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
