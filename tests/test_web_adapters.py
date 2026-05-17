"""Unit tests for the per-protocol adapters.

Local DNS on the dev box rewrites public hosts into the 198.18/15 range, which
the SSRF guard correctly rejects. So instead of hitting the network we mock
httpx and check that each adapter (a) builds the right request body, and
(b) parses the right response shape.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from api_verify.web.adapters.anthropic import AnthropicAdapter
from api_verify.web.adapters.gemini import GeminiAdapter
from api_verify.web.adapters.openai_compat import OpenAICompatAdapter
from api_verify.web.web_probes import QUICK_PROBES


class StubResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class StubClient:
    """Minimal async-context-shaped client capturing the last request."""

    def __init__(self, response: StubResponse):
        self.response = response
        self.last_call: dict[str, Any] = {}

    async def post(self, url, headers=None, json=None):
        self.last_call = {"url": url, "headers": headers, "json": json}
        return self.response


def _find_probe(probe_id: str):
    for p in QUICK_PROBES:
        if p.id == probe_id:
            return p
    raise KeyError(probe_id)


# ---------- OpenAI-compatible ----------

@pytest.mark.asyncio
async def test_openai_metadata_probe_parses_choices():
    adapter = OpenAICompatAdapter(
        endpoint="https://api.example.com/v1", api_key="k", model="gpt-4.1", extra_headers={}
    )
    client = StubClient(StubResponse(200, {
        "model": "gpt-4.1-2025-04-14",
        "choices": [{"message": {"content": "API_VERIFY_OK"}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 6},
    }))
    res = await adapter.call(client, _find_probe("metadata"))
    assert client.last_call["url"] == "https://api.example.com/v1/chat/completions"
    assert client.last_call["json"]["model"] == "gpt-4.1"
    assert res.status == 200
    assert res.text == "API_VERIFY_OK"
    assert res.model_returned == "gpt-4.1-2025-04-14"
    assert res.usage == {"prompt_tokens": 12, "completion_tokens": 6}


@pytest.mark.asyncio
async def test_openai_tool_calling_probe_parses_tool_args():
    adapter = OpenAICompatAdapter(
        endpoint="https://api.example.com/v1", api_key="k", model="gpt-4.1", extra_headers={}
    )
    client = StubClient(StubResponse(200, {
        "model": "gpt-4.1",
        "choices": [{
            "message": {
                "tool_calls": [{
                    "function": {"name": "add_numbers", "arguments": '{"a": 19, "b": 23}'}
                }]
            }
        }],
    }))
    res = await adapter.call(client, _find_probe("tool_calling"))
    assert "tools" in client.last_call["json"]
    assert client.last_call["json"]["tools"][0]["function"]["strict"] is True
    assert res.tool_call_args == {"a": 19, "b": 23}


@pytest.mark.asyncio
async def test_openai_bad_param_passes_through():
    adapter = OpenAICompatAdapter(
        endpoint="https://api.example.com/v1", api_key="k", model="gpt-4.1", extra_headers={}
    )
    client = StubClient(StubResponse(400, {"error": {"message": "Invalid temperature"}}))
    res = await adapter.call(client, _find_probe("error_semantics"))
    assert client.last_call["json"]["temperature"] == 99
    assert res.status == 400
    assert "temperature" in res.text.lower()


# ---------- Anthropic ----------

@pytest.mark.asyncio
async def test_anthropic_metadata_probe_parses_content_blocks():
    adapter = AnthropicAdapter(
        endpoint="https://api.example.com", api_key="k", model="claude-opus-4-5", extra_headers={}
    )
    client = StubClient(StubResponse(200, {
        "model": "claude-opus-4-5-20251022",
        "content": [{"type": "text", "text": "API_VERIFY_OK"}],
        "usage": {"input_tokens": 8, "output_tokens": 4},
    }))
    res = await adapter.call(client, _find_probe("metadata"))
    assert client.last_call["url"] == "https://api.example.com/v1/messages"
    assert client.last_call["headers"]["x-api-key"] == "k"
    assert client.last_call["headers"]["anthropic-version"] == "2023-06-01"
    assert res.text == "API_VERIFY_OK"
    assert res.model_returned == "claude-opus-4-5-20251022"


@pytest.mark.asyncio
async def test_anthropic_tool_calling_parses_tool_use_block():
    adapter = AnthropicAdapter(
        endpoint="https://api.example.com", api_key="k", model="claude-opus-4-5", extra_headers={}
    )
    client = StubClient(StubResponse(200, {
        "model": "claude-opus-4-5",
        "content": [
            {"type": "tool_use", "name": "add_numbers", "input": {"a": 19, "b": 23}},
        ],
    }))
    res = await adapter.call(client, _find_probe("tool_calling"))
    body = client.last_call["json"]
    assert body["tools"][0]["name"] == "add_numbers"
    assert body["tool_choice"] == {"type": "tool", "name": "add_numbers"}
    assert res.tool_call_args == {"a": 19, "b": 23}


# ---------- Gemini ----------

@pytest.mark.asyncio
async def test_gemini_metadata_probe_parses_candidates():
    adapter = GeminiAdapter(
        endpoint="https://generativelanguage.googleapis.com",
        api_key="k", model="gemini-2.5-pro", extra_headers={},
    )
    client = StubClient(StubResponse(200, {
        "modelVersion": "gemini-2.5-pro-001",
        "candidates": [{"content": {"parts": [{"text": "API_VERIFY_OK"}]}}],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
    }))
    res = await adapter.call(client, _find_probe("metadata"))
    assert client.last_call["url"].endswith("/v1beta/models/gemini-2.5-pro:generateContent")
    assert client.last_call["headers"]["x-goog-api-key"] == "k"
    assert res.text == "API_VERIFY_OK"
    assert res.model_returned == "gemini-2.5-pro-001"
    assert res.usage == {"promptTokenCount": 10, "candidatesTokenCount": 5}


@pytest.mark.asyncio
async def test_gemini_tool_calling_parses_function_call():
    adapter = GeminiAdapter(
        endpoint="https://generativelanguage.googleapis.com",
        api_key="k", model="gemini-2.5-pro", extra_headers={},
    )
    client = StubClient(StubResponse(200, {
        "candidates": [{
            "content": {"parts": [{"functionCall": {"name": "add_numbers", "args": {"a": 19, "b": 23}}}]}
        }]
    }))
    res = await adapter.call(client, _find_probe("tool_calling"))
    body = client.last_call["json"]
    assert body["tools"][0]["functionDeclarations"][0]["name"] == "add_numbers"
    assert res.tool_call_args == {"a": 19, "b": 23}


def test_safety_blocks_localhost_and_private():
    from api_verify.web.safety import UnsafeEndpoint, validate_endpoint
    with pytest.raises(UnsafeEndpoint):
        validate_endpoint("http://localhost/v1")
    with pytest.raises(UnsafeEndpoint):
        validate_endpoint("http://127.0.0.1:6379")
    with pytest.raises(UnsafeEndpoint):
        validate_endpoint("ftp://api.example.com")
    with pytest.raises(UnsafeEndpoint):
        validate_endpoint("http://no-scheme")
