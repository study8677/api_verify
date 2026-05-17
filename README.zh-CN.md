# API Verify

[English](README.md) | [中文](README.zh-CN.md)

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)
![License](https://img.shields.io/badge/license-unspecified-lightgrey)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)

API Verify 是一个面向 OpenAI-compatible API 中转站的“证据型”验证工具。它用于评估某个声称转发到特定上游模型的中转服务，是否真的在 API 行为、模型能力、请求参数、错误语义、可观察响应模式等方面与所声称的上游保持一致。

API Verify 并不试图 100% 证明真实上游。在没有官方签名响应、账单对账、可审计代理日志或可信执行证明的前提下，客户端只能构造一条结构化证据链，并据此输出风险评分。

## 在线版本

公开实例：**<https://apiverify.aidcmo.com>**。粘贴 endpoint、key、模型名即可在浏览器里快速验证。Web 服务源码在 [`src/api_verify/web/`](src/api_verify/web/)，部署说明在 [`deploy/`](deploy/README.md)。

## 项目定位

很多 API 中转站会以 OpenAI-compatible 格式暴露模型接口，并声称自己转发到某个官方模型。API Verify 的目标是帮助判断这些声明是否可信，重点发现以下风险：

- 用低成本模型冒充高阶模型。
- 忽略或降级 `seed`、`logprobs`、`response_format`、tool calling、strict schema 等参数。
- 隐式 fallback 到其他模型或供应商，但仍返回用户请求的模型名。
- 截断上下文、改写 prompt、压缩输入或伪造 usage。
- 返回与标称上游不一致的错误语义和响应结构。

核心边界：`model`、`usage`、`system_fingerprint`、请求 ID 等响应字段经过中转站后都可以被伪造。因此，本项目输出的是“证据型风险评分”，不是数学证明。

## 当前能力

- OpenAI-compatible Provider Adapter。
- 五类默认探针：
  - metadata：基础响应结构、模型字段、usage 形态。
  - parameter_fidelity：JSON mode、seed、logprobs 等参数保真。
  - capability：strict tool calling 能力。
  - error_semantics：非法参数是否返回接近上游的 4xx 错误。
  - statistical_behavior：低成本重复行为样本，用于后续与官方同日 baseline 对照。
- JSONL 原始证据存储，保留 request、response、headers、SSE events、latency、usage。
- 鉴权请求头脱敏，避免把 API key 写入输出文件。
- 规则评分引擎，输出 `通过`、`可疑`、`强可疑`、`无法判定`。
- Markdown 和 JSON 报告，每条 evidence 都能回指 `runs.jsonl#run_id`。
- `--dry-run` 模式，可在没有真实 key 的情况下验证请求生成、证据链和报告流程。

## 安装

要求 Python 3.10+。

```bash
git clone https://github.com/study8677/api_verify.git
cd api_verify
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

如果只想直接运行当前源码，也可以不安装包，使用 `PYTHONPATH=src` 执行命令。

## 快速开始

### 1. Dry-run

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

### 2. 真实中转站试跑

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

- `runs/live/runs.jsonl`：每次探针的原始证据。
- `runs/live/report/report.json`：机器可读评分结果。
- `runs/live/report/report.md`：人类可读报告。

## 如何解读结果

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

## 安全注意

- 不要提交真实 API key。`local-provider.json` 已在 `.gitignore` 中忽略。
- 输出中的 `Authorization`、`api-key`、`x-api-key` 请求头会被写成 `<redacted>`。
- 仍建议把 `runs/` 当作敏感取证材料处理，因为其中可能包含 prompt、响应内容、供应商 headers 或业务上下文。
- 错误语义探针应低频、合法使用，不要做高频攻击式测试。

## 项目结构

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

## 开发与验证

```bash
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m pytest -q
```

当前环境如果没有安装 `pytest`，可以先运行：

```bash
python3 -m pip install -e ".[dev]"
```

## 路线图

- 增加官方 baseline 对照命令。
- 增加 Anthropic、Gemini、OpenRouter 专用 adapter。
- 扩展长上下文、多模态、JSON schema、tool use 评测集。
- 增加成本估算与限额一致性检查。
- 提供更适合审计归档的 HTML 报告。
