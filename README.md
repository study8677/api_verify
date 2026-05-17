# API Verify

[English](README.md) | [中文](README.zh-CN.md)

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)
![License](https://img.shields.io/badge/license-unspecified-lightgrey)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)

API Verify is an evidence-oriented verifier for OpenAI-compatible API relay services. It helps evaluate whether a relay that claims to provide a specific upstream model is preserving the declared API behavior, model capabilities, request parameters, error semantics, and observable response patterns.

API Verify does not claim to prove the real upstream provider with 100% certainty. Without official signed responses, billing reconciliation, auditable proxy logs, or trusted execution proof, a client can only build a structured evidence chain and produce a risk score.

## What This Project Does

API Verify evaluates OpenAI-compatible API relay services that claim to route requests to a specific upstream model. It collects protocol evidence, runs low-cost probes, and produces a risk-oriented report about whether the relay appears to preserve the declared upstream behavior.

It is designed to detect common relay risks:

- Serving a cheaper model while claiming a premium one.
- Dropping or downgrading parameters such as `seed`, `logprobs`, `response_format`, tool calling, or strict schemas.
- Silently falling back to another model or provider while returning the requested model name.
- Truncating context, rewriting prompts, compressing input, or forging usage.
- Returning error semantics that do not match the declared upstream family.

Important boundary: response fields such as `model`, `usage`, `system_fingerprint`, and request IDs can be forged by a relay. API Verify produces an evidence-based risk score, not cryptographic proof of the real upstream.

## Features

- OpenAI-compatible provider adapter.
- Five default probe categories:
  - metadata: response shape, model field, and usage shape.
  - parameter_fidelity: JSON mode, seed, logprobs, and related parameter handling.
  - capability: strict tool-calling behavior.
  - error_semantics: upstream-like handling of invalid parameters.
  - statistical_behavior: repeated low-cost behavioral samples for same-day baseline comparison.
- JSONL artifact store for request, response, headers, SSE events, latency, and usage.
- Authorization header redaction.
- Rule-based scoring with four verdicts: pass, suspicious, strongly suspicious, or inconclusive.
- Markdown and JSON reports with evidence references back to `runs.jsonl#run_id`.
- Dry-run mode for validating the request/report pipeline without making network calls.

## Installation

Python 3.10+ is required.

```bash
git clone https://github.com/study8677/api_verify.git
cd api_verify
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

You can also run directly from source with `PYTHONPATH=src`.

## Quick Start

### 1. Dry-run

Dry-run creates request artifacts and exercises the report pipeline without calling a real provider.

```bash
PYTHONPATH=src python3 -m api_verify.cli run \
  --config examples/openai-compatible-provider.json \
  --out runs/dry \
  --dry-run

PYTHONPATH=src python3 -m api_verify.cli report \
  --runs runs/dry/runs.jsonl \
  --out runs/dry/report
```

### 2. Run Against a Real Relay

Copy the example provider config and fill in your real endpoint, API key, model, and optional headers.

```bash
cp examples/openai-compatible-provider.json local-provider.json
$EDITOR local-provider.json
```

Example:

```json
{
  "provider": "relay-under-test",
  "endpoint": "https://api.example.com/v1",
  "api_key": "replace-with-key",
  "model": "gpt-4.1",
  "headers": {
    "X-Relay-Debug": "optional"
  },
  "timeout_seconds": 60,
  "sample_count": 3
}
```

Run probes:

```bash
PYTHONPATH=src python3 -m api_verify.cli run \
  --config local-provider.json \
  --out runs/live
```

Generate reports:

```bash
PYTHONPATH=src python3 -m api_verify.cli report \
  --runs runs/live/runs.jsonl \
  --out runs/live/report
```

Generated files:

- `runs/live/runs.jsonl`: raw probe artifacts.
- `runs/live/report/report.json`: machine-readable scoring output.
- `runs/live/report/report.md`: human-readable report.

## How To Interpret Reports

| Verdict | Meaning |
| --- | --- |
| pass | Evidence is broadly consistent with the claim, but this is not proof of the upstream. |
| suspicious | Capability, parameter, error, or behavior evidence needs further comparison. |
| strongly suspicious | Strong protocol conflict, transport issue, or missing key capability. |
| inconclusive | Not enough response evidence, such as dry-run only. |

For meaningful results, run the same probe set twice:

1. Direct official baseline: same date, same model, same parameters.
2. Relay under test: same probes and sample count.

Then compare:

- Error semantics.
- Whether parameters are preserved, rejected clearly, or silently dropped.
- Tool calling, JSON mode, logprobs, and other declared capabilities.
- Usage, latency, output length, and deterministic task accuracy.

## Security Notes

- Never commit real API keys. `local-provider.json` is ignored by `.gitignore`.
- Request headers named `Authorization`, `api-key`, or `x-api-key` are written as `<redacted>`.
- Treat `runs/` as sensitive evidence because prompts, responses, provider headers, or business context may still appear there.
- Keep boundary probes low-frequency and legitimate.

## Repository Layout

```text
api_verify/
  src/api_verify/
    adapter.py      # OpenAI-compatible adapter and artifact capture
    probes.py       # Default probe suite
    scoring.py      # Rule-based scoring and rationales
    report.py       # Markdown report rendering
    cli.py          # run / report CLI
    models.py       # Provider, probe, and run data models
    store.py        # JSONL and JSON persistence
  examples/
    openai-compatible-provider.json
  docs/
    api-relay-verification-report.md
    initial-implementation-plan.md
  tests/
```

## Development

```bash
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m pytest -q
```

If `pytest` is missing:

```bash
python3 -m pip install -e ".[dev]"
```

## Roadmap

- Add a first-class official baseline comparison command.
- Add dedicated adapters for Anthropic, Gemini, and OpenRouter.
- Expand long-context, multimodal, JSON schema, and tool-use probe sets.
- Add cost and rate-limit plausibility checks.
- Generate audit-friendly HTML reports.
