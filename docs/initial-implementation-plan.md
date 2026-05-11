# 初版实现计划：Codex + Claude Code 协作

日期：2026-05-11

## 目标

把当前原型推进到“可给用户试跑、可审查、可继续扩展”的初版，而不是宣称能 100% 证明中转站真实上游。

初版定位：

- 对 OpenAI-compatible API 中转站运行低成本探针。
- 保存原始请求、响应、headers、SSE 证据。
- 用规则评分输出“通过 / 可疑 / 强可疑 / 无法判定”。
- 明确说明哪些字段可伪造，哪些属于行为证据。
- 为后续 Claude、Gemini、OpenRouter 专用适配器留下接口边界。

## 当前状态

已完成：

- `docs/api-relay-verification-report.md`：研究报告与总体方案。
- `src/api_verify/adapter.py`：OpenAI-compatible 调用适配器，支持 dry-run 与原始证据保存。
- `src/api_verify/probes.py`：metadata、parameter_fidelity、capability、error_semantics、statistical_behavior 五类探针。
- `src/api_verify/store.py`：JSONL 存储。
- `src/api_verify/scoring.py`：规则评分与字段可伪造提示。
- `src/api_verify/report.py`、`src/api_verify/cli.py`：JSON/Markdown 报告与 CLI。
- `tests/`：核心探针类别与评分逻辑测试。

## 任务分工

### Codex 侧

1. 固化 CLI 输入输出契约：`run` 接受 provider config 并输出 `runs.jsonl`，`report` 接受 `runs.jsonl` 并输出 `report.json` 与 `report.md`。
2. 补齐报告可读性：首屏给出 verdict、overall_score、维度分，每条 evidence 回指 `runs.jsonl#run_id`。
3. 守住最小实现边界：不引入数据库、Web UI、复杂 ML 或供应商 SDK；不承诺数学证明。

### Claude Code 侧

1. 设计低成本官方 baseline 样例。
2. 补充供应商配置模板。
3. 撰写真实试跑操作手册。

## 初版验收标准

必须满足：

- 空 key 场景可 `--dry-run` 完整生成请求证据。
- 填入真实 OpenAI-compatible endpoint/key 后可完成一次网络探针运行。
- `report.json` 与 `report.md` 均可生成。
- 至少五类探针都出现在报告维度里。
- 鉴权头不进入输出文件。
- pytest 可在安装 dev 依赖后运行通过。

建议满足：

- README 包含 dry-run、真实运行、报告生成三段命令。
- 示例配置明确不要提交真实 API key。
- 报告中每个结论都能定位到原始 evidence。
- reviewer 可独立复现 dry-run 与 compileall。

## 下一步优先级

1. 有真实中转站 key 后，先跑低成本探针，不直接上长上下文或多模态高成本测试。
2. 增加官方 baseline 对照命令，确保同日期、同模型、同参数比较。
3. 根据第一组真实结果决定是否扩展 Claude/Gemini 专用适配器。

## 风险控制

- 所有结果只能表述为“证据支持的风险判断”，不能写成“已证明真实上游”。
- baseline 必须带日期、模型名和配置；官方模型行为会变化。
- 长上下文、多模态、工具调用测试可能增加成本，应默认关闭或单独 probe set。
- 错误语义探针要低频合法调用，避免高频攻击式测试。
