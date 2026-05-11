from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from .models import ProviderConfig, Probe, RunRecord, utc_now_iso


SENSITIVE_HEADERS = {"authorization", "api-key", "x-api-key"}


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            redacted[key] = "<redacted>"
        else:
            redacted[key] = value
    return redacted


class OpenAICompatibleAdapter:
    def __init__(self, config: ProviderConfig):
        self.config = config

    def request_headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        headers.update(self.config.headers)
        return headers

    def run_probe(self, probe: Probe, dry_run: bool = False) -> RunRecord:
        headers = self.request_headers()
        if dry_run:
            return RunRecord.dry(self.config, probe, redact_headers(headers))

        url = f"{self.config.endpoint}{probe.endpoint_path}"
        body = json.dumps(probe.request).encode("utf-8")
        request = Request(url, data=body, headers=headers, method="POST")
        started = time.perf_counter()
        timestamp = utc_now_iso()

        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
                latency_ms = int((time.perf_counter() - started) * 1000)
                response_headers = dict(response.headers.items())
                response_json, sse_events = self._parse_response(raw, response_headers)
                return RunRecord(
                    run_id=str(uuid4()),
                    provider=self.config.provider,
                    model=self.config.model,
                    probe_id=probe.id,
                    probe_category=probe.category,
                    timestamp=timestamp,
                    latency_ms=latency_ms,
                    status=response.status,
                    usage=self._usage(response_json),
                    request=probe.request,
                    request_headers=redact_headers(headers),
                    response_headers=response_headers,
                    response_json=response_json,
                    response_text=raw,
                    sse_events=sse_events,
                    error_text=None,
                )
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            latency_ms = int((time.perf_counter() - started) * 1000)
            response_json, sse_events = self._parse_response(raw, dict(exc.headers.items()))
            return RunRecord(
                run_id=str(uuid4()),
                provider=self.config.provider,
                model=self.config.model,
                probe_id=probe.id,
                probe_category=probe.category,
                timestamp=timestamp,
                latency_ms=latency_ms,
                status=exc.code,
                usage=self._usage(response_json),
                request=probe.request,
                request_headers=redact_headers(headers),
                response_headers=dict(exc.headers.items()),
                response_json=response_json,
                response_text=raw,
                sse_events=sse_events,
                error_text=str(exc),
            )
        except URLError as exc:
            return RunRecord(
                run_id=str(uuid4()),
                provider=self.config.provider,
                model=self.config.model,
                probe_id=probe.id,
                probe_category=probe.category,
                timestamp=timestamp,
                latency_ms=int((time.perf_counter() - started) * 1000),
                status=None,
                usage=None,
                request=probe.request,
                request_headers=redact_headers(headers),
                response_headers={},
                response_json=None,
                response_text="",
                sse_events=[],
                error_text=str(exc),
            )

    def _parse_response(self, raw: str, headers: dict[str, str]) -> tuple[dict[str, Any] | None, list[str]]:
        content_type = next((value for key, value in headers.items() if key.lower() == "content-type"), "")
        if "text/event-stream" in content_type or raw.lstrip().startswith("data:"):
            events = [line.removeprefix("data:").strip() for line in raw.splitlines() if line.startswith("data:")]
            final_json = None
            for event in reversed(events):
                if event and event != "[DONE]":
                    try:
                        final_json = json.loads(event)
                        break
                    except json.JSONDecodeError:
                        continue
            return final_json, events
        try:
            return json.loads(raw), []
        except json.JSONDecodeError:
            return None, []

    def _usage(self, response_json: dict[str, Any] | None) -> dict[str, Any] | None:
        if not response_json:
            return None
        usage = response_json.get("usage")
        return usage if isinstance(usage, dict) else None
