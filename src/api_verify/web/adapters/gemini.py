from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx

from ..models import WebProbe, WebProbeResult
from .base import measure_start, ms_since


class GeminiAdapter:
    """Adapter for Google Gemini native generateContent format."""

    def __init__(self, endpoint: str, api_key: str, model: str, extra_headers: dict[str, str]):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.extra_headers = extra_headers

    def _headers(self) -> dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-goog-api-key": self.api_key,
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
            user_content = "Respond with ONLY a single JSON object and nothing else. " + user_content

        gen_config: dict[str, Any] = {
            "temperature": probe.temperature,
            "maxOutputTokens": probe.max_tokens,
        }
        if probe.require_json:
            gen_config["responseMimeType"] = "application/json"
        if probe.bad_param and "temperature" in probe.bad_param:
            gen_config["temperature"] = probe.bad_param["temperature"]

        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
            "generationConfig": gen_config,
        }
        if probe.system_prompt:
            body["systemInstruction"] = {"parts": [{"text": probe.system_prompt}]}
        if probe.tool_schema:
            body["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": probe.tool_schema["name"],
                            "description": probe.tool_schema.get("description", ""),
                            "parameters": probe.tool_schema["parameters"],
                        }
                    ]
                }
            ]
            body["toolConfig"] = {
                "functionCallingConfig": {
                    "mode": "ANY",
                    "allowedFunctionNames": [probe.tool_schema["name"]],
                }
            }
        return body

    async def call(self, client: httpx.AsyncClient, probe: WebProbe) -> WebProbeResult:
        # Gemini path includes the model. Encode it: the model name comes from
        # untrusted input and `../../` would otherwise traverse the URL path.
        safe_model = quote(self.model, safe="")
        url = f"{self.endpoint}/v1beta/models/{safe_model}:generateContent"
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

        model_returned: str | None = self.model  # Gemini doesn't echo model field; trust requested
        text_parts: list[str] = []
        tool_call_args: dict[str, Any] | None = None
        usage: dict[str, Any] | None = None

        if isinstance(data, dict):
            if isinstance(data.get("usageMetadata"), dict):
                usage = data["usageMetadata"]
            if isinstance(data.get("modelVersion"), str):
                model_returned = data["modelVersion"]
            candidates = data.get("candidates") or []
            if candidates:
                content = (candidates[0] or {}).get("content") or {}
                for part in content.get("parts") or []:
                    if not isinstance(part, dict):
                        continue
                    if isinstance(part.get("text"), str):
                        text_parts.append(part["text"])
                    elif isinstance(part.get("functionCall"), dict):
                        args = part["functionCall"].get("args")
                        if isinstance(args, dict):
                            tool_call_args = args
            elif data.get("error"):
                text_parts.append(json.dumps(data["error"])[:500])
        else:
            text_parts.append(raw_text[:500])

        return WebProbeResult(
            probe_id=probe.id, category=probe.category, name=probe.name,
            status=resp.status_code, latency_ms=latency,
            model_returned=model_returned,
            text="".join(text_parts), usage=usage, tool_call_args=tool_call_args,
            error_text=None if resp.status_code < 400 else raw_text[:200],
            raw_response_excerpt=raw_text[:500],
        )
