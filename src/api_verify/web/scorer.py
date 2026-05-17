from __future__ import annotations

import json
import statistics
from collections import defaultdict
from typing import Any

from .models import WebProbeResult


FIELD_FORGERY_NOTE = (
    "Response fields such as `model`, `usage`, and `system_fingerprint` can be forged by a relay. "
    "Treat these probes as evidence, not cryptographic proof."
)


def score_results(results: list[WebProbeResult], requested_model: str) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    dim_scores: dict[str, list[int]] = defaultdict(list)
    latencies = [r.latency_ms for r in results if r.latency_ms is not None]

    for r in results:
        score, verdict, rationale = _score_one(r, requested_model)
        dim_scores[r.category].append(score)
        evidence.append(
            {
                "probe_id": r.probe_id,
                "name": r.name,
                "category": r.category,
                "score": score,
                "verdict": verdict,
                "rationale": rationale,
                "status": r.status,
                "latency_ms": r.latency_ms,
                "model_returned": r.model_returned,
                "usage": r.usage,
                "text_excerpt": (r.text or "")[:240],
            }
        )

    dimensions = {
        cat: {"score": round(sum(v) / len(v), 1), "runs": len(v)}
        for cat, v in sorted(dim_scores.items())
        if v
    }
    overall = round(sum(d["score"] for d in dimensions.values()) / len(dimensions), 1) if dimensions else 0

    return {
        "overall_score": overall,
        "verdict": _verdict(overall, bool(results)),
        "dimensions": dimensions,
        "evidence": evidence,
        "stats": {
            "latency_ms_p50": int(statistics.median(latencies)) if latencies else None,
            "latency_ms_max": max(latencies) if latencies else None,
            "probe_count": len(results),
        },
        "note": FIELD_FORGERY_NOTE,
    }


def _score_one(r: WebProbeResult, requested_model: str) -> tuple[int, str, str]:
    if r.category == "error_semantics":
        return _score_error_semantics(r)
    if r.status is None:
        return 15, "strongly suspicious", f"transport error: {r.error_text or 'no response'}"
    if r.status >= 500:
        return 25, "strongly suspicious", f"upstream returned HTTP {r.status}"
    if r.status >= 400 and r.category != "error_semantics":
        return 35, "suspicious", f"expected success path but got HTTP {r.status}: {(r.text or '')[:120]}"

    if r.probe_id == "metadata":
        return _score_metadata(r, requested_model)
    if r.probe_id == "json_mode":
        return _score_json_mode(r)
    if r.probe_id == "tool_calling":
        return _score_tool_calling(r)
    if r.probe_id == "long_context_needle":
        return _score_needle(r)
    if r.probe_id == "reasoning_arith":
        return _score_reasoning(r)
    if r.probe_id == "cutoff_check":
        return _score_cutoff(r)
    return 50, "inconclusive", "no scorer registered for this probe"


def _score_metadata(r: WebProbeResult, requested: str) -> tuple[int, str, str]:
    score = 50
    reasons: list[str] = []
    text = (r.text or "").strip()
    returned = (r.model_returned or "").lower()
    req = requested.lower()
    if "API_VERIFY_OK" in text:
        score += 20
        reasons.append("echoed sentinel exactly")
    elif text:
        score += 5
        reasons.append("got a response but not the exact sentinel")
    if returned and req:
        if req in returned or returned in req:
            score += 20
            reasons.append("returned model string is consistent with requested")
        else:
            score -= 25
            reasons.append(f"returned model `{returned}` differs from requested `{req}`")
    if isinstance(r.usage, dict) and r.usage:
        score += 5
        reasons.append("usage object present")
    return _clamp(score), _verdict(score, True), "; ".join(reasons)


def _score_json_mode(r: WebProbeResult) -> tuple[int, str, str]:
    text = (r.text or "").strip()
    parsed = _try_json(text)
    if parsed is None:
        return 30, "suspicious", "JSON mode requested but response was not parseable JSON"
    if not isinstance(parsed, dict):
        return 40, "suspicious", "JSON mode returned non-object JSON"
    if "number" in parsed and "verdict" in parsed:
        return 90, "pass", "valid JSON with required keys"
    return 60, "suspicious", f"valid JSON but missing required keys: {list(parsed.keys())}"


def _score_tool_calling(r: WebProbeResult) -> tuple[int, str, str]:
    if not r.tool_call_args:
        text = (r.text or "").strip()
        if "19" in text and "23" in text:
            return 55, "suspicious", "no tool_calls returned; model answered as plain text (likely tool degradation)"
        return 30, "strongly suspicious", "strict tool requested but no tool_calls were emitted"
    args = r.tool_call_args
    if set(args.keys()) == {"a", "b"}:
        try:
            ok = int(args["a"]) == 19 and int(args["b"]) == 23
        except (TypeError, ValueError):
            ok = False
        if ok:
            return 95, "pass", "tool_calls emitted with correct strict schema and arguments"
        return 75, "pass", "tool_calls emitted with correct schema, arguments differ"
    return 55, "suspicious", f"tool_calls emitted but schema mismatch: {list(args.keys())}"


def _score_error_semantics(r: WebProbeResult) -> tuple[int, str, str]:
    status = r.status or 0
    body = (r.text or "").lower() + " " + json.dumps(r.usage or {}).lower()
    if 400 <= status < 500 and "temperature" in body:
        return 95, "pass", "invalid temperature produced a 4xx error mentioning the offending parameter"
    if 400 <= status < 500:
        return 65, "suspicious", f"got HTTP {status} but error body did not identify the offending parameter"
    if status == 0:
        return 20, "strongly suspicious", "no response to malformed request"
    if status >= 500:
        return 30, "strongly suspicious", f"malformed request triggered HTTP {status} (server error, not validation)"
    return 25, "strongly suspicious", f"malformed request was accepted (HTTP {status}); silent parameter dropping suspected"


def _score_needle(r: WebProbeResult) -> tuple[int, str, str]:
    text = (r.text or "").upper()
    if "ORANGE-SAILBOAT-42" in text:
        return 90, "pass", "recovered the needle from long context"
    if "ORANGE" in text or "SAILBOAT" in text:
        return 55, "suspicious", "partially recovered needle; long-context capability weak"
    return 30, "strongly suspicious", "needle not recovered; long-context capability likely degraded"


def _score_reasoning(r: WebProbeResult) -> tuple[int, str, str]:
    text = (r.text or "").strip()
    if text == "17" or text.startswith("17"):
        return 85, "pass", "deterministic arithmetic answer correct"
    if text:
        return 45, "suspicious", f"answer differs from expected `17`: {text[:60]}"
    return 30, "suspicious", "empty response"


def _score_cutoff(r: WebProbeResult) -> tuple[int, str, str]:
    text = (r.text or "").strip()
    return 50, "inconclusive", f"reported cutoff: `{text[:40]}` — compare against the official cutoff for the claimed model"


def _verdict(score: float, has_results: bool) -> str:
    if not has_results:
        return "inconclusive"
    if score >= 75:
        return "pass"
    if score >= 50:
        return "suspicious"
    if score > 0:
        return "strongly suspicious"
    return "inconclusive"


def _clamp(n: int) -> int:
    return max(0, min(100, n))


def _try_json(s: str) -> Any:
    s = s.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.startswith("json"):
            s = s[4:]
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return None
