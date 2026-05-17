from __future__ import annotations

import json
from typing import Any

import httpx

from ..models import WebProbe, WebProbeResult
from .base import measure_start, ms_since


class AnthropicAdapter:
    """Adapter for Anthropic native `/v1/messages` format."""

    def __init__(self, endpoint: str, api_key: str, model: str, extra_headers: dict[str, str]):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.extra_headers = extra_headers

    def _headers(self) -> dict[str, str]:
        h = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        h.update(self.extra_headers)
        return h

    def _build_body(self, probe: WebProbe) -> dict[str, Any]:
        user_content = probe.user_prompt
        if probe.long_context_padding_chars > 0 and probe.needle:
            user_content = (
                f"{probe.needle}\n\n"
                + ("This is a long context padding section. " * (probe.long_context_padding_chars // 40 + 1))[
                    : probe.long_context_padding_chars
                ]
                + f"\n\n{probe.user_prompt}"
            )
        if probe.require_json:
            user_content = (
                "Respond with ONLY a single JSON object and nothing else. " + user_content
            )

        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": probe.max_tokens,
            "temperature": probe.temperature,
            "messages": [{"role": "user", "content": user_content}],
        }
        if probe.system_prompt:
            body["system"] = probe.system_prompt

        if probe.tool_schema:
            body["tools"] = [
                {
                    "name": probe.tool_schema["name"],
                    "description": probe.tool_schema.get("description", ""),
                    "input_schema": probe.tool_schema["parameters"],
                }
            ]
            body["tool_choice"] = {"type": "tool", "name": probe.tool_schema["name"]}
        if probe.bad_param:
            body.update(probe.bad_param)
        return body

    async def call(self, client: httpx.AsyncClient, probe: WebProbe) -> WebProbeResult:
        url = f"{self.endpoint}/v1/messages"
        body = self._build_body(probe)
        t0 = measure_start()
        try:
            resp = await client.post(url, headers=self._headers(), json=body)
        except httpx.HTTPError as exc:
            return WebProbeResult(
                probe_id=probe.id, category=probe.category, name=probe.name,
                status=None, latency_ms=ms_since(t0),
                model_returned=None, text="", usage=None, tool_call_args=None,
                error_text=str(exc), raw_response_excerpt="",
            )
        latency = ms_since(t0)
        raw_text = resp.text
        try:
            data = resp.json()
        except ValueError:
            data = None

        model_returned = None
        text_parts: list[str] = []
        tool_call_args: dict[str, Any] | None = None
        usage: dict[str, Any] | None = None

        if isinstance(data, dict):
            model_returned = data.get("model")
            if isinstance(data.get("usage"), dict):
                usage = data["usage"]
            for block in data.get("content") or []:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text" and isinstance(block.get("text"), str):
                    text_parts.append(block["text"])
                elif btype == "tool_use":
                    inp = block.get("input")
                    if isinstance(inp, dict):
                        tool_call_args = inp
            if not text_parts and data.get("error"):
                text_parts.append(json.dumps(data["error"])[:500])
        else:
            text_parts.append(raw_text[:500])

        return WebProbeResult(
            probe_id=probe.id, category=probe.category, name=probe.name,
            status=resp.status_code, latency_ms=latency,
            model_returned=str(model_returned) if model_returned else None,
            text="".join(text_parts), usage=usage, tool_call_args=tool_call_args,
            error_text=None if resp.status_code < 400 else raw_text[:200],
            raw_response_excerpt=raw_text[:500],
        )
