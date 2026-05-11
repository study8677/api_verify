from __future__ import annotations

from .models import Probe


def build_default_probes(model: str, sample_count: int = 3) -> list[Probe]:
    return [
        metadata_probe(model),
        parameter_fidelity_probe(model),
        capability_probe(model),
        error_semantics_probe(model),
        statistical_behavior_probe(model, sample_count),
    ]


def metadata_probe(model: str) -> Probe:
    return Probe(
        id="metadata.basic_chat",
        category="metadata",
        name="Basic metadata and usage shape",
        endpoint_path="/chat/completions",
        request={
            "model": model,
            "messages": [{"role": "user", "content": "Reply with exactly: API_VERIFY_METADATA_OK"}],
            "temperature": 0,
            "max_tokens": 16,
        },
        expected_signals=[
            "HTTP 2xx",
            "response model field present and consistent with request",
            "usage object shape present when provider claims OpenAI-compatible accounting",
            "headers and request id style preserved as evidence, not proof",
        ],
    )


def parameter_fidelity_probe(model: str) -> Probe:
    return Probe(
        id="params.seed_json_logprobs",
        category="parameter_fidelity",
        name="Seed, JSON response format, and logprobs handling",
        endpoint_path="/chat/completions",
        request={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": "Return compact JSON with keys verdict and number. number must be 17.",
                }
            ],
            "temperature": 0,
            "seed": 12345,
            "response_format": {"type": "json_object"},
            "logprobs": True,
            "top_logprobs": 2,
            "max_tokens": 64,
        },
        expected_signals=[
            "unsupported parameters should fail with upstream-like errors instead of being silently dropped",
            "if accepted, JSON mode should produce parseable JSON",
            "logprobs structure should be present when accepted",
            "repeated seed calls should be unusually stable for providers that support seed",
        ],
    )


def capability_probe(model: str) -> Probe:
    return Probe(
        id="capability.strict_tool_call",
        category="capability",
        name="Strict tool-calling capability",
        endpoint_path="/chat/completions",
        request={
            "model": model,
            "messages": [{"role": "user", "content": "Use the tool to add 19 and 23."}],
            "temperature": 0,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "add_numbers",
                        "description": "Add two integers.",
                        "strict": True,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "a": {"type": "integer"},
                                "b": {"type": "integer"},
                            },
                            "required": ["a", "b"],
                            "additionalProperties": False,
                        },
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": "add_numbers"}},
            "max_tokens": 80,
        },
        expected_signals=[
            "tool_calls emitted in OpenAI-compatible shape",
            "strict schema arguments contain only a and b",
            "provider does not degrade tool definition into plain text",
        ],
    )


def error_semantics_probe(model: str) -> Probe:
    return Probe(
        id="error.invalid_parameter",
        category="error_semantics",
        name="Invalid parameter error semantics",
        endpoint_path="/chat/completions",
        request={
            "model": model,
            "messages": [{"role": "user", "content": "This request should fail because temperature is invalid."}],
            "temperature": 99,
            "max_tokens": 8,
        },
        expected_signals=[
            "HTTP 4xx expected",
            "error object should identify invalid temperature rather than silently clamping it",
            "error format should resemble declared upstream family",
        ],
        allow_error_status=True,
    )


def statistical_behavior_probe(model: str, sample_count: int = 3) -> Probe:
    return Probe(
        id="behavior.repeat_reasoning",
        category="statistical_behavior",
        name="Repeated low-cost behavioral sample",
        endpoint_path="/chat/completions",
        request={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Answer only the final integer. A box has 7 red balls and 5 blue balls. "
                        "Three red balls are removed, then twice as many blue balls as red balls "
                        "remaining are added. How many balls are in the box?"
                    ),
                }
            ],
            "temperature": 0,
            "max_tokens": 16,
        },
        expected_signals=[
            "repeat accuracy and output shape should be compared with a same-date official baseline",
            "latency, output length, and usage distribution are behavioral evidence, not proof",
        ],
        repeats=max(1, sample_count),
    )
