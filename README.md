# API Verify

API Verify is an evidence-oriented verifier for OpenAI-compatible API relay services. It helps evaluate whether a relay that claims to provide a specific upstream model is preserving the declared API behavior, model capabilities, request parameters, error semantics, and observable response patterns.

API Verify does not claim to prove the real upstream provider with 100% certainty. Without official signed responses, billing reconciliation, auditable proxy logs, or trusted execution proof, a client can only build a structured evidence chain and produce a risk score.

---

## 中文说明

### 项目定位

很多 API 中转站会以 OpenAI-compatible 格式暴露模型接口，并声称自己转发到某个官方模型。API Verify 的目标是帮助判断这些声明是否可信，重点发现以下风险：

- 用低成本模型冒充高阶模型。
- 忽略或降级 `seed`、`logprobs`、`response_format`、tool calling、strict schema 等参数。
- 隐式 fallback 到其他模型或供应商，但仍返回用户请求的模型名。
- 截断上下文、改写 prompt、压缩输入或伪造 usage。
- 返回与标称上游不一致的错误语义和响应结构。

核心边界：`model`、`usage`、`system_fingerprint`、请求 ID 等响应字段经过中转站后都可以被伪造。因此，本项目输出的是“证据型风险评分”，不是数学证明。

### 当前能力

- OpenAI-compatible Provider Adapter。
- 五类默认探针：
  - metadata: 基础响应结构、模型字段、usage 形态。
  - parameter_fidelity: JSON mode、seed、logprobs 等参数保真。
  - capability: strict tool calling 能力。
  - error_semantics: 非法参数是否返回接近上游的 4xx 错误。
  - statistical_behavior: 低成本重复行为样本，用于后续与官方同日 baseline 对照。
- JSONL 原始证据存储，保留 request、response、headers、SSE events、latency、usage。
- 鉴权请求头脱敏，避免把 API key 写入输出文件。
- 规则评分引擎，输出 `通过`、`可疑`、`强可疑`、`无法判定`。
- Markdown 和 JSON 报告，每条 evidence 都能回指 `runs.jsonl#run_id`。
- `--dry-run` 模式，可在没有真实 key 的情况下验证请求生成、证据链和报告流程。

### 安装

要求 Python 3.10+。

```bash
git clone https://github.com/study8677/api_verify.git
cd api_verify
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

如果只想直接运行当前源码，也可以不安装包，使用 `PYTHONPATH=src` 执行命令。

### 快速开始

#### 1. Dry-run

Dry-run 只生成探针请求和报告链路证据，不进行网络调用，适合检查配置和输出结构。

```bash
PYTHONPATH=src python3 -m api_verify.cli run \
  --config examples/openai-compatible-provider.json \
  --out runs/dry \
  --dry-run

PYTHONPATH=src python3 -m api_verify.cli report \
  --runs runs/dry/runs.jsonl \
  --out runs/dry/report
```

#### 2. 真实中转站试跑

复制示例配置并填写真实的 OpenAI-compatible endpoint、API key、模型名和可选 headers。

```bash
cp examples/openai-compatible-provider.json local-provider.json
$EDITOR local-provider.json
```

示例：

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

运行探针：

```bash
PYTHONPATH=src python3 -m api_verify.cli run \
  --config local-provider.json \
  --out runs/live
```

生成报告：

```bash
PYTHONPATH=src python3 -m api_verify.cli report \
  --runs runs/live/runs.jsonl \
  --out runs/live/report
```

输出文件：

- `runs/live/runs.jsonl`: 每次探针的原始证据。
- `runs/live/report/report.json`: 机器可读评分结果。
- `runs/live/report/report.md`: 人类可读报告。

### 如何解读结果

默认评分分为四档：

| 结论 | 含义 |
| --- | --- |
| `通过` | 当前探针证据与声明基本一致，但不代表已证明真实上游。 |
| `可疑` | 存在能力、参数、错误语义或行为偏差，需要进一步对照。 |
| `强可疑` | 出现明显协议矛盾、传输错误或关键能力缺失。 |
| `无法判定` | 证据不足，例如仅 dry-run 或没有有效响应。 |

建议至少准备两份配置：

1. 官方直连 baseline：同日期、同模型、同参数运行。
2. 中转站 relay：同一探针集、同一采样次数运行。

比较时优先看：

- 错误语义是否一致。
- 参数是否被保留或明确报错，而不是静默丢弃。
- tool calling、JSON mode、logprobs 等能力是否符合标称模型。
- usage、latency、输出长度和准确率是否明显偏离同日官方 baseline。

### 安全注意

- 不要提交真实 API key。`local-provider.json` 已在 `.gitignore` 中忽略。
- 输出中的 `Authorization`、`api-key`、`x-api-key` 请求头会被写成 `<redacted>`。
- 仍建议把 `runs/` 当作敏感取证材料处理，因为其中可能包含 prompt、响应内容、供应商 headers 或业务上下文。
- 错误语义探针应低频、合法使用，不要做高频攻击式测试。

### 项目结构

```text
api_verify/
  src/api_verify/
    adapter.py      # OpenAI-compatible 调用适配器与原始证据采集
    probes.py       # 默认探针集
    scoring.py      # 规则评分与证据解释
    report.py       # Markdown 报告生成
    cli.py          # run / report CLI
    models.py       # 配置、探针、运行记录数据模型
    store.py        # JSONL 和 JSON 文件存储
  examples/
    openai-compatible-provider.json
  docs/
    api-relay-verification-report.md
    initial-implementation-plan.md
  tests/
```

### 开发与验证

```bash
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m pytest -q
```

当前环境如果没有安装 `pytest`，可以先运行：

```bash
python3 -m pip install -e ".[dev]"
```

### 路线图

- 增加官方 baseline 对照命令。
- 增加 Anthropic、Gemini、OpenRouter 专用 adapter。
- 扩展长上下文、多模态、JSON schema、tool use 评测集。
- 增加成本估算与限额一致性检查。
- 提供更适合审计归档的 HTML 报告。

---

## English

### What This Project Does

API Verify evaluates OpenAI-compatible API relay services that claim to route requests to a specific upstream model. It collects protocol evidence, runs low-cost probes, and produces a risk-oriented report about whether the relay appears to preserve the declared upstream behavior.

It is designed to detect common relay risks:

- Serving a cheaper model while claiming a premium one.
- Dropping or downgrading parameters such as `seed`, `logprobs`, `response_format`, tool calling, or strict schemas.
- Silently falling back to another model or provider while returning the requested model name.
- Truncating context, rewriting prompts, compressing input, or forging usage.
- Returning error semantics that do not match the declared upstream family.

Important boundary: response fields such as `model`, `usage`, `system_fingerprint`, and request IDs can be forged by a relay. API Verify produces an evidence-based risk score, not cryptographic proof of the real upstream.

### Features

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

### Installation

Python 3.10+ is required.

```bash
git clone https://github.com/study8677/api_verify.git
cd api_verify
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

You can also run directly from source with `PYTHONPATH=src`.

### Quick Start

#### 1. Dry-run

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

#### 2. Run Against a Real Relay

Copy the example provider config and fill in your real endpoint, API key, model, and optional headers.

```bash
cp examples/openai-compatible-provider.json local-provider.json
$EDITOR local-provider.json
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

### How To Interpret Reports

| Verdict | Meaning |
| --- | --- |
| `通过` / pass | Evidence is broadly consistent with the claim, but this is not proof of the upstream. |
| `可疑` / suspicious | Capability, parameter, error, or behavior evidence needs further comparison. |
| `强可疑` / strongly suspicious | Strong protocol conflict, transport issue, or missing key capability. |
| `无法判定` / inconclusive | Not enough response evidence, such as dry-run only. |

For meaningful results, run the same probe set twice:

1. Direct official baseline: same date, same model, same parameters.
2. Relay under test: same probes and sample count.

Then compare:

- Error semantics.
- Whether parameters are preserved, rejected clearly, or silently dropped.
- Tool calling, JSON mode, logprobs, and other declared capabilities.
- Usage, latency, output length, and deterministic task accuracy.

### Security Notes

- Never commit real API keys. `local-provider.json` is ignored by `.gitignore`.
- Request headers named `Authorization`, `api-key`, or `x-api-key` are written as `<redacted>`.
- Treat `runs/` as sensitive evidence because prompts, responses, provider headers, or business context may still appear there.
- Keep boundary probes low-frequency and legitimate.

### Repository Layout

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

### Development

```bash
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m pytest -q
```

If `pytest` is missing:

```bash
python3 -m pip install -e ".[dev]"
```

### Roadmap

- Add a first-class official baseline comparison command.
- Add dedicated adapters for Anthropic, Gemini, and OpenRouter.
- Expand long-context, multimodal, JSON schema, and tool-use probe sets.
- Add cost and rate-limit plausibility checks.
- Generate audit-friendly HTML reports.
