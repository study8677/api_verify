from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Protocol = Literal["openai", "anthropic", "gemini"]


@dataclass(frozen=True)
class WebProbe:
    """A protocol-agnostic probe definition. Adapters translate to vendor format."""

    id: str
    category: str
    name: str
    user_prompt: str
    system_prompt: str | None = None
    max_tokens: int = 64
    temperature: float = 0.0
    expects_error: bool = False
    require_json: bool = False
    tool_schema: dict[str, Any] | None = None
    bad_param: dict[str, Any] | None = None
    long_context_padding_chars: int = 0
    needle: str | None = None


@dataclass
class WebProbeResult:
    probe_id: str
    category: str
    name: str
    status: int | None
    latency_ms: int
    model_returned: str | None
    text: str
    usage: dict[str, Any] | None
    tool_call_args: dict[str, Any] | None
    error_text: str | None
    raw_response_excerpt: str


@dataclass
class VerifyRequest:
    protocol: Protocol
    endpoint: str
    api_key: str
    model: str
    mode: Literal["quick", "deep"] = "quick"
    extra_headers: dict[str, str] = field(default_factory=dict)
