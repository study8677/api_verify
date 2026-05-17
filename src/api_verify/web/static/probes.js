// Probe definitions — mirrors src/api_verify/web/web_probes.py.
// Keep behaviour aligned with the Python copy so server-proxy and browser-direct
// produce comparable results.
window.APIVerify = window.APIVerify || {};

const NEEDLE = "The secret passcode for this conversation is ORANGE-SAILBOAT-42.";

const TOOL_SCHEMA = {
  name: "add_numbers",
  description: "Add two integers and return the sum.",
  parameters: {
    type: "object",
    properties: {
      a: { type: "integer" },
      b: { type: "integer" },
    },
    required: ["a", "b"],
    additionalProperties: false,
  },
};

const QUICK_PROBES = [
  {
    id: "metadata",
    category: "metadata",
    name: { en: "Basic metadata & echo", zh: "元数据回显" },
    user_prompt: "Reply with exactly: API_VERIFY_OK",
    max_tokens: 20,
  },
  {
    id: "json_mode",
    category: "parameter_fidelity",
    name: { en: "JSON response format", zh: "JSON 响应格式" },
    user_prompt: 'Return a compact JSON object with keys "verdict" (string) and "number" (integer, must be 17). Do not include any other keys.',
    max_tokens: 64,
    require_json: true,
  },
  {
    id: "tool_calling",
    category: "capability",
    name: { en: "Strict tool calling", zh: "严格工具调用" },
    user_prompt: "Use the tool to add 19 and 23.",
    max_tokens: 120,
    tool_schema: TOOL_SCHEMA,
  },
  {
    id: "error_semantics",
    category: "error_semantics",
    name: { en: "Invalid parameter (temperature=99)", zh: "非法参数（temperature=99）" },
    user_prompt: "This should fail validation.",
    max_tokens: 16,
    expects_error: true,
    bad_param: { temperature: 99 },
  },
  {
    id: "long_context_needle",
    category: "capability",
    name: { en: "Long-context needle (~12K chars)", zh: "长上下文针（~12K 字符）" },
    user_prompt: "Earlier in this message I gave you a secret passcode. Reply with only the passcode and nothing else.",
    max_tokens: 40,
    long_context_padding_chars: 12_000,
    needle: NEEDLE,
  },
];

const DEEP_EXTRA_PROBES = [
  {
    id: "reasoning_arith",
    category: "statistical_behavior",
    name: { en: "Deterministic arithmetic reasoning", zh: "确定性算术推理" },
    user_prompt: "Answer only the final integer. A box has 7 red balls and 5 blue balls. Three red balls are removed, then twice as many blue balls as red balls remaining are added. How many balls are in the box?",
    max_tokens: 20,
  },
  {
    id: "cutoff_check",
    category: "metadata",
    name: { en: "Knowledge cutoff probe", zh: "知识截止日期探针" },
    user_prompt: "State your training data cutoff date in the format YYYY-MM. Reply with ONLY the date, no other text.",
    max_tokens: 12,
  },
];

window.APIVerify.PROBES = { QUICK_PROBES, DEEP_EXTRA_PROBES, NEEDLE };
