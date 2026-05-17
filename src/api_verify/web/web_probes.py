from __future__ import annotations

from .models import WebProbe


_NEEDLE = "The secret passcode for this conversation is ORANGE-SAILBOAT-42."

_TOOL_SCHEMA = {
    "name": "add_numbers",
    "description": "Add two integers and return the sum.",
    "parameters": {
        "type": "object",
        "properties": {
            "a": {"type": "integer"},
            "b": {"type": "integer"},
        },
        "required": ["a", "b"],
        "additionalProperties": False,
    },
}


QUICK_PROBES: list[WebProbe] = [
    WebProbe(
        id="metadata",
        category="metadata",
        name="Basic metadata & echo",
        user_prompt="Reply with exactly: API_VERIFY_OK",
        max_tokens=20,
    ),
    WebProbe(
        id="json_mode",
        category="parameter_fidelity",
        name="JSON response format",
        user_prompt='Return a compact JSON object with keys "verdict" (string) and "number" (integer, must be 17). Do not include any other keys.',
        max_tokens=64,
        require_json=True,
    ),
    WebProbe(
        id="tool_calling",
        category="capability",
        name="Strict tool calling",
        user_prompt="Use the tool to add 19 and 23.",
        max_tokens=120,
        tool_schema=_TOOL_SCHEMA,
    ),
    WebProbe(
        id="error_semantics",
        category="error_semantics",
        name="Invalid parameter (temperature=99)",
        user_prompt="This should fail validation.",
        max_tokens=16,
        expects_error=True,
        bad_param={"temperature": 99},
    ),
    WebProbe(
        id="long_context_needle",
        category="capability",
        name="Long-context needle (~12K chars)",
        user_prompt=(
            "Earlier in this message I gave you a secret passcode. "
            "Reply with only the passcode and nothing else."
        ),
        max_tokens=40,
        long_context_padding_chars=12_000,
        needle=_NEEDLE,
    ),
]


DEEP_EXTRA_PROBES: list[WebProbe] = [
    WebProbe(
        id="reasoning_arith",
        category="statistical_behavior",
        name="Deterministic arithmetic reasoning",
        user_prompt=(
            "Answer only the final integer. A box has 7 red balls and 5 blue balls. "
            "Three red balls are removed, then twice as many blue balls as red balls "
            "remaining are added. How many balls are in the box?"
        ),
        max_tokens=20,
    ),
    WebProbe(
        id="cutoff_check",
        category="metadata",
        name="Knowledge cutoff probe",
        user_prompt=(
            "State your training data cutoff date in the format YYYY-MM. "
            "Reply with ONLY the date, no other text."
        ),
        max_tokens=12,
    ),
]
