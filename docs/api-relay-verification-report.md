# API 中转站模型真实性验证调研报告

日期：2026-05-11

## 1. 问题定义

目标不是验证“这个 API key 字符串是否属于 OpenAI/Anthropic/Google”，而是验证一个中转站在声称提供某个模型或某类官方 API 时，实际请求是否被转发到了它标称的上游模型，是否存在以下“掺水”行为：

- 用便宜模型冒充昂贵模型，例如用 flash/mini/开源模型冒充 pro/opus/gpt 高阶模型。
- 对请求参数降级，例如忽略 `temperature`、`top_p`、`seed`、`logprobs`、tool strict、JSON schema、长上下文等。
- 隐式走 fallback 或多供应商路由，返回模型名仍伪装成用户请求的模型。
- 截断上下文、压缩提示词、改写 system prompt 或过滤工具定义。
- 返回伪造的响应元数据、usage 或错误码。

核心判断：在普通 HTTP API 层面，除非官方供应商提供可验证签名/远程证明，否则客户端无法 100% 证明中转站调用了哪个真实上游。能做到的是分层取证，给出“强怀疑/基本一致/无法判定”的置信度。

## 2. 可利用的信号

### OpenAI

OpenAI completion/chat 响应中的 `model`、`usage`、部分接口中的 `system_fingerprint` 可以作为直连官方时的元数据参考。经过中转站后这些字段可被伪造，不能单独作为证明。

### Anthropic Claude

Claude Messages API 的 `model`、`usage`、`stop_reason`、tool use、vision、长上下文与错误格式可作为交叉验证信号。经过中转站后仍需结合行为探针判断。

### Google Gemini

Gemini 的 `modelVersion`、`responseId`、模型元数据、多模态、长上下文、函数调用和 code execution 等能力可用于探针设计。响应字段同样不能单独证明真实上游。

### 多供应商聚合器

透明聚合器通常会明示 provider routing、fallback、provider order、是否允许 fallback、参数转换和上游 debug 信息。是否披露这些机制，是判断可信度的重要信号。

## 3. 验证方法分层

### A. 协议与元数据一致性

收集 request body、headers、endpoint、时间戳、response body、headers、状态码、SSE chunk、usage、模型名、fingerprint/modelVersion、错误响应格式等证据。该层成本低，可发现明显伪装，但不能证明真实上游。

### B. 参数保真度探针

使用 `seed`、低温度、`logprobs/top_logprobs`、JSON mode/structured output、strict tools、长上下文阶梯、多模态输入等探针，检测参数是否被静默吞掉或能力是否被降级。

### C. 行为指纹与统计检验

建立官方直连基线，再对中转站进行 A/B 测试。比较正确率、拒答率、平均输出长度、首 token 延迟、tokens/sec、usage 比例、错误类型。该层只能给概率结论，需要同日期 baseline。

### D. 经济与限额一致性

检查价格、token 计费、速率限制、上下文窗口和供应稳定性。中转价格长期低于官方边际成本且无合理解释时，风险升高。

### E. 诱导错误与边界测试

用不存在的模型名、非法参数、超上下文窗口、供应商特有 header/beta feature 等合法低频请求，观察错误语义是否接近标称上游。

## 4. 建议架构

1. Provider Adapter：统一 OpenAI-compatible、Anthropic、Gemini、OpenRouter 等调用接口，保存原始请求/响应。
2. Probe Suite：元数据、参数、能力、错误、长上下文、统计任务集。
3. Baseline Store：保存官方直连基线与中转站样本，带日期、模型名、参数和原始 artifact。
4. Scoring Engine：输出 metadata consistency、parameter fidelity、capability match、behavioral similarity、economic plausibility、error semantics 等维度分。
5. Report Generator：生成面向决策的证据报告。

## 5. 第一阶段交付物

- 研究报告与方案说明。
- OpenAI-compatible 最小验证原型 CLI。
- JSONL 原始证据存储。
- Markdown/JSON 报告模板。
- 至少五类探针：metadata、parameter_fidelity、capability、error_semantics、statistical_behavior。

## 6. 验收标准

- 能对一个 OpenAI-compatible 中转站跑完整探针并生成机器可读结果。
- 报告明确区分“字段可伪造”和“行为证据”。
- 每个结论都有原始请求/响应证据索引。
- 不把单次回答质量差误判为掺水；必须结合重复样本或明确协议矛盾。

## 7. 风险与开放问题

- 没有官方签名时无法给出数学证明，只能做概率与证据链。
- 官方模型会更新，行为基线需要带日期和版本。
- 中转站可能真实调用高阶模型但加入系统 prompt 或审查层，表现会偏移。
- 长上下文和多模态探针成本高，需要分级运行。
- 公开评测需注意服务条款、隐私和滥用风险。

## 8. 决策建议

先做“证据型验证工具”，不要承诺“一键证明真假”。第一版目标是发现明显伪造和降级，量化与官方基线的偏差，并给用户一个有证据链的风险评分。如果业务必须达到强证明级别，需要推动供应商提供官方签名响应、可审计代理、账单/请求 ID 对账或可信执行环境证明。
