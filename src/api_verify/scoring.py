from __future__ import annotations

import json
from collections import defaultdict
from typing import Any


FIELD_FORGERY_WARNING = (
    "model/system_fingerprint/usage/request-id 等字段经过中转站后都可伪造；"
    "本项只作为协议一致性信号，不能单独证明真实上游。"
)


def score_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    dimension_scores: dict[str, list[int]] = defaultdict(list)

    for record in records:
        probe_id = str(record.get("probe_id"))
        category = str(record.get("probe_category"))
        score, verdict, rationale = score_record(record)
        dimension_scores[category].append(score)
        evidence.append(
            {
                "run_id": record.get("run_id"),
                "probe_id": probe_id,
                "category": category,
                "score": score,
                "verdict": verdict,
                "rationale": rationale,
                "artifact_ref": f"runs.jsonl#{record.get('run_id')}",
            }
        )

    dimensions = {
        category: {
            "score": round(sum(values) / len(values), 2),
            "runs": len(values),
        }
        for category, values in sorted(dimension_scores.items())
        if values
    }
    overall_score = (
        round(sum(item["score"] for item in dimensions.values()) / len(dimensions), 2) if dimensions else 0
    )

    return {
        "overall_score": overall_score,
        "verdict": verdict_from_score(overall_score, bool(records)),
        "dimensions": dimensions,
        "field_forgery_warning": FIELD_FORGERY_WARNING,
        "evidence": evidence,
    }


def score_record(record: dict[str, Any]) -> tuple[int, str, str]:
    if record.get("dry_run"):
        return 0, "无法判定", "dry-run only; request artifact captured but no response evidence"
    if record.get("status") is None:
        return 20, "强可疑", f"network or transport error: {record.get('error_text')}"

    category = record.get("probe_category")
    status = int(record["status"])
    response = record.get("response_json") or {}

    if category == "error_semantics":
        return score_error_semantics(status, response, record)
    if status >= 400:
        return 35, "可疑", f"probe expected a successful capability path but got HTTP {status}"
    if category == "metadata":
        return score_metadata(response, record)
    if category == "parameter_fidelity":
        return score_parameter_fidelity(response, record)
    if category == "capability":
        return score_capability(response)
    if category == "statistical_behavior":
        return score_statistical_behavior(response, record)
    return 50, "无法判定", "unknown probe category"


def score_metadata(response: dict[str, Any], record: dict[str, Any]) -> tuple[int, str, str]:
    requested_model = (((record.get("request") or {}).get("model")) or "").lower()
    returned_model = str(response.get("model", "")).lower()
    usage_ok = isinstance(response.get("usage"), dict)
    choices_ok = bool(response.get("choices"))
    score = 50
    reasons = [FIELD_FORGERY_WARNING]
    if returned_model and requested_model and requested_model in returned_model:
        score += 20
        reasons.append("returned model string is consistent with request")
    elif returned_model:
        score -= 15
        reasons.append(f"returned model differs from request: {returned_model}")
    else:
        score -= 10
        reasons.append("missing model field")
    if usage_ok:
        score += 15
        reasons.append("usage object present")
    if choices_ok:
        score += 15
        reasons.append("choices object present")
    return clamp(score), verdict_from_score(score, True), "; ".join(reasons)


def score_parameter_fidelity(response: dict[str, Any], record: dict[str, Any]) -> tuple[int, str, str]:
    text = extract_text(response)
    score = 45
    reasons = []
    if parse_json_object(text) is not None:
        score += 25
        reasons.append("JSON response format appears honored")
    else:
        score -= 10
        reasons.append("could not parse assistant content as JSON")
    if "logprobs" in json.dumps(response, ensure_ascii=False):
        score += 15
        reasons.append("logprobs-like structure present")
    else:
        reasons.append("logprobs not evident; may be unsupported or silently dropped")
    if record.get("usage"):
        score += 10
        reasons.append("usage present for parameter probe")
    return clamp(score), verdict_from_score(score, True), "; ".join(reasons)


def score_capability(response: dict[str, Any]) -> tuple[int, str, str]:
    choices = response.get("choices") or []
    message = ((choices[0] or {}).get("message") or {}) if choices else {}
    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        return 35, "可疑", "strict tool probe did not return tool_calls; possible capability degradation"
    args_text = ((tool_calls[0].get("function") or {}).get("arguments") or "")
    args = parse_json_object(args_text)
    if isinstance(args, dict) and set(args) == {"a", "b"}:
        return 90, "通过", "tool_calls present and strict arguments match expected schema"
    return 60, "可疑", "tool_calls present but arguments do not cleanly match strict schema"


def score_error_semantics(status: int, response: dict[str, Any], record: dict[str, Any]) -> tuple[int, str, str]:
    text = json.dumps(response, ensure_ascii=False).lower() + " " + str(record.get("response_text", "")).lower()
    if 400 <= status < 500 and "temperature" in text:
        return 90, "通过", "invalid temperature produced a client error mentioning the offending parameter"
    if 400 <= status < 500:
        return 65, "可疑", "client error returned, but offending parameter was not clearly identified"
    return 25, "强可疑", f"invalid parameter was accepted or transformed; HTTP {status}"


def score_statistical_behavior(response: dict[str, Any], record: dict[str, Any]) -> tuple[int, str, str]:
    text = extract_text(response).strip()
    score = 55
    reasons = ["single-run quality is weak evidence; compare repeated samples against official baseline"]
    if text == "17":
        score += 25
        reasons.append("answer matches deterministic expected result")
    elif text:
        score -= 10
        reasons.append(f"answer differs from expected result: {text[:80]}")
    if record.get("latency_ms") is not None:
        score += 5
        reasons.append("latency captured for distribution comparison")
    if record.get("usage"):
        score += 5
        reasons.append("usage captured for distribution comparison")
    return clamp(score), verdict_from_score(score, True), "; ".join(reasons)


def verdict_from_score(score: float, has_records: bool) -> str:
    if not has_records:
        return "无法判定"
    if score >= 75:
        return "通过"
    if score >= 50:
        return "可疑"
    if score > 0:
        return "强可疑"
    return "无法判定"


def clamp(score: int) -> int:
    return max(0, min(100, score))


def extract_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = (choices[0] or {}).get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    return ""


def parse_json_object(value: str) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None
