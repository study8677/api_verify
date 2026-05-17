from __future__ import annotations

import asyncio

import httpx

from .adapters import build_adapter
from .models import VerifyRequest, WebProbe, WebProbeResult
from .web_probes import DEEP_EXTRA_PROBES, QUICK_PROBES

PER_PROBE_TIMEOUT_SECONDS = 25.0
TOTAL_TIMEOUT_SECONDS = 60.0


async def run_verification(req: VerifyRequest) -> list[WebProbeResult]:
    adapter = build_adapter(
        protocol=req.protocol,
        endpoint=req.endpoint,
        api_key=req.api_key,
        model=req.model,
        extra_headers=req.extra_headers,
    )
    probes: list[WebProbe] = list(QUICK_PROBES)
    if req.mode == "deep":
        probes.extend(DEEP_EXTRA_PROBES)

    limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
    timeout = httpx.Timeout(PER_PROBE_TIMEOUT_SECONDS, connect=10.0)
    # follow_redirects=False: validate_endpoint() checked the user-supplied URL
    # against a private-address blocklist, but a redirect could send us to
    # link-local metadata addresses or back to localhost. Refuse to chase them.
    async with httpx.AsyncClient(limits=limits, timeout=timeout, follow_redirects=False) as client:
        tasks = [adapter.call(client, probe) for probe in probes]
        try:
            results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=TOTAL_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            # one or more probes still pending; surface partial info
            results = [
                WebProbeResult(
                    probe_id=p.id, category=p.category, name=p.name,
                    status=None, latency_ms=int(TOTAL_TIMEOUT_SECONDS * 1000),
                    model_returned=None, text="", usage=None, tool_call_args=None,
                    error_text="overall timeout", raw_response_excerpt="",
                )
                for p in probes
            ]
    return results
