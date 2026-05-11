from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


JsonDict = dict[str, Any]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    endpoint: str
    api_key: str
    model: str
    headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 60
    sample_count: int = 3

    @classmethod
    def from_json(cls, data: JsonDict) -> "ProviderConfig":
        return cls(
            provider=str(data["provider"]),
            endpoint=str(data["endpoint"]).rstrip("/"),
            api_key=str(data["api_key"]),
            model=str(data["model"]),
            headers={str(k): str(v) for k, v in data.get("headers", {}).items()},
            timeout_seconds=int(data.get("timeout_seconds", 60)),
            sample_count=int(data.get("sample_count", 3)),
        )


@dataclass(frozen=True)
class Probe:
    id: str
    category: str
    name: str
    endpoint_path: str
    request: JsonDict
    expected_signals: list[str]
    repeats: int = 1
    allow_error_status: bool = False


@dataclass
class RunRecord:
    run_id: str
    provider: str
    model: str
    probe_id: str
    probe_category: str
    timestamp: str
    latency_ms: int | None
    status: int | None
    usage: JsonDict | None
    request: JsonDict
    request_headers: dict[str, str]
    response_headers: dict[str, str]
    response_json: JsonDict | None
    response_text: str
    sse_events: list[str]
    error_text: str | None
    dry_run: bool = False

    @classmethod
    def dry(cls, provider: ProviderConfig, probe: Probe, request_headers: dict[str, str]) -> "RunRecord":
        return cls(
            run_id=str(uuid4()),
            provider=provider.provider,
            model=provider.model,
            probe_id=probe.id,
            probe_category=probe.category,
            timestamp=utc_now_iso(),
            latency_ms=None,
            status=None,
            usage=None,
            request=probe.request,
            request_headers=request_headers,
            response_headers={},
            response_json=None,
            response_text="",
            sse_events=[],
            error_text=None,
            dry_run=True,
        )

    def to_json(self) -> JsonDict:
        return {
            "run_id": self.run_id,
            "provider": self.provider,
            "model": self.model,
            "probe_id": self.probe_id,
            "probe_category": self.probe_category,
            "timestamp": self.timestamp,
            "latency_ms": self.latency_ms,
            "status": self.status,
            "usage": self.usage,
            "request": self.request,
            "request_headers": self.request_headers,
            "response_headers": self.response_headers,
            "response_json": self.response_json,
            "response_text": self.response_text,
            "sse_events": self.sse_events,
            "error_text": self.error_text,
            "dry_run": self.dry_run,
        }
