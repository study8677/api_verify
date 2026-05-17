from __future__ import annotations

import json
from typing import Any

import httpx

from ..models import WebProbe, WebProbeResult
from .base import measure_start, ms_since


class OpenAICompatAdapter:
    def __init__(self, endpoint: str, api_key: str, model: str, extra_headers: dict[str, str]):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.extra_headers = extra_headers

    def _headers(self) -> dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.api_key}",
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
        messages: list[dict[str, Any]] = []
        if probe.system_prompt:
            messages.append({"role": "system", "content": probe.system_prompt})
        messages.append({"role": "user", "content": user_content})

        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": probe.temperature,
            "max_tokens": probe.max_tokens,
        }
        if probe.require_json:
            body["response_format"] = {"type": "json_object"}
        if probe.tool_schema:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": probe.tool_schema["name"],
                        "description": probe.tool_schema.get("description", ""),
                        "strict": True,
                        "parameters": probe.tool_schema["parameters"],
                    },
                }
            ]
            body["tool_choice"] = {"type": "function", "function": {"name": probe.tool_schema["name"]}}
        if probe.bad_param:
            body.update(probe.bad_param)
        return body

    async def call(self, client: httpx.AsyncClient, probe: WebProbe) -> WebProbeResult:
        url = f"{self.endpoint}/chat/completions"
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
        text = ""
        usage = None
        tool_call_args: dict[str, Any] | None = None

        if isinstance(data, dict):
            model_returned = data.get("model")
            usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
            choices = data.get("choices") or []
            if choices:
                msg = (choices[0] or {}).get("message") or {}
                content = msg.get("content")
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    text = "".join(part.get("text", "") for part in content if isinstance(part, dict))
                tool_calls = msg.get("tool_calls") or []
                if tool_calls:
                    fn = (tool_calls[0] or {}).get("function") or {}
                    raw_args = fn.get("arguments") or ""
                    try:
                        tool_call_args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                    except (ValueError, TypeError):
                        tool_call_args = {"_unparsed": str(raw_args)[:200]}
            elif data.get("error"):
                text = json.dumps(data.get("error"))[:500]
        else:
            text = raw_text[:500]

        return WebProbeResult(
            probe_id=probe.id, category=probe.category, name=probe.name,
            status=resp.status_code, latency_ms=latency,
            model_returned=str(model_returned) if model_returned else None,
            text=text, usage=usage, tool_call_args=tool_call_args,
            error_text=None if resp.status_code < 400 else raw_text[:200],
            raw_response_excerpt=raw_text[:500],
        )
