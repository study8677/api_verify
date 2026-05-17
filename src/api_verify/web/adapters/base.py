from __future__ import annotations

import time
from typing import Protocol

import httpx

from ..models import WebProbe, WebProbeResult


class Adapter(Protocol):
    async def call(self, client: httpx.AsyncClient, probe: WebProbe) -> WebProbeResult:
        ...


def build_adapter(protocol: str, endpoint: str, api_key: str, model: str, extra_headers: dict[str, str]):
    from .openai_compat import OpenAICompatAdapter
    from .anthropic import AnthropicAdapter
    from .gemini import GeminiAdapter

    p = protocol.lower()
    if p == "openai":
        return OpenAICompatAdapter(endpoint=endpoint, api_key=api_key, model=model, extra_headers=extra_headers)
    if p == "anthropic":
        return AnthropicAdapter(endpoint=endpoint, api_key=api_key, model=model, extra_headers=extra_headers)
    if p == "gemini":
        return GeminiAdapter(endpoint=endpoint, api_key=api_key, model=model, extra_headers=extra_headers)
    raise ValueError(f"unknown protocol: {protocol!r}")


def measure_start() -> float:
    return time.perf_counter()


def ms_since(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)
