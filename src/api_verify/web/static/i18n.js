// Bilingual UI strings. The Chinese-AI-relay community is the primary
// audience; English is the secondary path.
window.APIVerify = window.APIVerify || {};

const T = {
  en: {
    page_title: "API Verify — Is your relay serving the model it claims?",
    nav_how: "How it works",
    nav_privacy: "Privacy",
    nav_lang: "中文",

    hero_title_a: "Is your API relay ",
    hero_title_em: "actually",
    hero_title_b: " serving the model it claims?",
    hero_lead: "Paste a relay endpoint, an API key, and the model name. We run 5 capability and protocol probes designed to expose cheap-model substitution, parameter drops, and capability degradation common to premium models like ",
    hero_lead_models: "gpt-4.1, claude-opus-4-x, gemini-2.5-pro",
    hero_caveat: "Result is an evidence-based risk score, not cryptographic proof. model / usage / system_fingerprint can all be forged by a relay.",

    form_protocol: "Protocol",
    form_endpoint: "Endpoint base URL",
    form_api_key: "API key",
    form_api_key_hint_browser: "Sent directly from your browser to the endpoint. Never crosses our server.",
    form_api_key_hint_server: "Sent once to our server, used to run the probes, then dropped. Not logged or stored.",
    form_model: "Model name to verify",
    form_mode: "Mode",
    form_mode_quick: "Quick — 5 probes, ~10s",
    form_mode_deep: "Deep — 7 probes, ~25s",
    form_remember: "Remember key in this browser (localStorage)",
    form_submit: "Run verification",
    form_running: "Running probes…",

    endpoint_hint_openai: "OpenAI-compatible relay. Include the path up to but not including <code>/chat/completions</code>.",
    endpoint_hint_anthropic: "Anthropic-native relay. Base URL only (we append <code>/v1/messages</code>).",
    endpoint_hint_gemini: "Gemini-native relay. Base URL only (we append <code>/v1beta/models/{model}:generateContent</code>).",

    badge_browser: "Browser-direct mode — your key stays in this browser.",
    badge_server: "Server-proxy mode — key crosses our server once, dropped after use.",

    cors_title: "Connection failed",
    cors_msg: "Browser-direct call failed. This usually means the endpoint blocks CORS (OpenAI and Anthropic official endpoints do this by design). You can retry through our server proxy — your key will be sent once over HTTPS, used to run the probes, then dropped from memory. Source is open for audit.",
    cors_use_server: "Retry via server proxy",
    cors_cancel: "Cancel",

    result_overall: "Overall",
    result_verdict: "Verdict",
    result_probes: "Probes",
    result_p50: "Latency p50",
    result_max: "Latency max",
    result_mode: "Mode",
    result_remaining: "Server-proxy quota remaining",
    result_evidence: "Per-probe evidence",
    result_note: "Reminder: response fields such as model, usage and system_fingerprint can be forged. Treat these probes as evidence, not proof.",

    verdict_pass: "pass",
    verdict_suspicious: "suspicious",
    verdict_strongly: "strongly suspicious",
    verdict_inconclusive: "inconclusive",

    how_title: "How the probes work",
    how_1: "<strong>Metadata echo</strong> — Does the response shape and returned <code>model</code> field line up with what the request asked for?",
    how_2: "<strong>JSON mode</strong> — Tells if the relay honors <code>response_format: json_object</code> or silently drops it.",
    how_3: "<strong>Strict tool calling</strong> — Tests whether the relay preserves strict tool schemas. Cheap models often degrade tool calls to plain text.",
    how_4: "<strong>Error semantics</strong> — Sends an intentionally invalid <code>temperature=99</code>. Real upstreams return a 4xx that names the offending parameter. Relays that silently clamp it are suspicious.",
    how_5: "<strong>Long-context needle</strong> — Plants a passcode inside ~12K characters of padding and asks for it back. Substituted cheap models fail here.",
    how_deep: "Deep mode additionally runs a deterministic-arithmetic reasoning probe and a knowledge-cutoff probe.",

    privacy_title: "Privacy & safety",
    privacy_1: "Default mode: your API key never leaves your browser. Probes are dispatched directly from your machine to the endpoint you typed.",
    privacy_2: "Server-proxy fallback (opt-in, only when the endpoint blocks CORS): the key is used once per request and dropped from memory. Never written to disk, logs, or any storage.",
    privacy_3: "Optional “Remember key” checkbox stores the key in your browser's <code>localStorage</code>. Anyone with access to this browser profile can read it. Don't enable on shared machines.",
    privacy_4: "Server-proxy mode is rate-limited to 5 verifications per hour per IP.",
    privacy_5: "For your own safety: prefer a short-lived / low-budget key when testing untrusted relays.",
    privacy_6: "Source: <a href=\"https://github.com/study8677/api_verify\" target=\"_blank\" rel=\"noopener\">github.com/study8677/api_verify</a>",

    err_network: "Network error",
    err_invalid_url: "Endpoint URL is invalid",
    err_missing_field: "All fields are required",
    err_server_rate_limited: "Server-proxy rate limit reached. Try again later or use browser-direct mode.",

    footer: "API Verify · evidence is not proof",
  },
  zh: {
    page_title: "API Verify — 你的中转站真的是它声称的模型吗？",
    nav_how: "原理",
    nav_privacy: "隐私",
    nav_lang: "EN",

    hero_title_a: "你的 API 中转站",
    hero_title_em: "真的",
    hero_title_b: "是它声称的模型吗？",
    hero_lead: "粘贴中转 endpoint、API key 和模型名，我们跑 5 个能力和协议探针，专门暴露针对高阶模型（如 ",
    hero_lead_models: "gpt-4.1、claude-opus-4-x、gemini-2.5-pro",
    hero_caveat: "输出是“证据型风险评分”，不是数学证明。model、usage、system_fingerprint 等字段都可以被中转站伪造。",

    form_protocol: "协议",
    form_endpoint: "Endpoint 基础 URL",
    form_api_key: "API key",
    form_api_key_hint_browser: "直接从你的浏览器发到 endpoint，不经过我们的服务器。",
    form_api_key_hint_server: "一次性发到我们的服务器，用完立刻从内存丢弃，不落盘不记日志。",
    form_model: "要验证的模型名",
    form_mode: "模式",
    form_mode_quick: "Quick — 5 个探针，约 10 秒",
    form_mode_deep: "Deep — 7 个探针，约 25 秒",
    form_remember: "在本浏览器记住 key（localStorage）",
    form_submit: "开始验证",
    form_running: "正在跑探针…",

    endpoint_hint_openai: "OpenAI-compatible 中转。填到 <code>/chat/completions</code> 之前的路径。",
    endpoint_hint_anthropic: "Anthropic 原生中转。只填基础 URL（我们自动补 <code>/v1/messages</code>）。",
    endpoint_hint_gemini: "Gemini 原生中转。只填基础 URL（我们自动补 <code>/v1beta/models/{model}:generateContent</code>）。",

    badge_browser: "浏览器直调模式 — 你的 key 不离开浏览器。",
    badge_server: "服务器代理模式 — key 过我们服务器一次，用完即丢。",

    cors_title: "连接失败",
    cors_msg: "浏览器直调失败。通常是因为 endpoint 不开放 CORS（OpenAI 和 Anthropic 官方就是默认禁止浏览器直调的）。可以改走我们的服务器代理重试：你的 key 通过 HTTPS 发到我们服务器一次、跑完探针、立即从内存丢弃，源码全部公开可审。",
    cors_use_server: "改用服务器代理重试",
    cors_cancel: "取消",

    result_overall: "总分",
    result_verdict: "结论",
    result_probes: "探针数",
    result_p50: "延迟 p50",
    result_max: "延迟最大",
    result_mode: "模式",
    result_remaining: "服务器代理剩余次数",
    result_evidence: "每个探针的证据",
    result_note: "提醒：model、usage、system_fingerprint 等响应字段可被中转站伪造。本工具仅作为证据，不作为最终定性。",

    verdict_pass: "通过",
    verdict_suspicious: "可疑",
    verdict_strongly: "强可疑",
    verdict_inconclusive: "无法判定",

    how_title: "5 个探针在测什么",
    how_1: "<strong>元数据回显</strong> — 响应结构和返回的 <code>model</code> 字段，是否与请求一致？",
    how_2: "<strong>JSON 模式</strong> — 中转站是否真正支持 <code>response_format: json_object</code>，还是悄悄忽略？",
    how_3: "<strong>严格工具调用</strong> — 中转站是否保留 strict tool schema。廉价模型常把 tool_call 退化成纯文本。",
    how_4: "<strong>错误语义</strong> — 故意发 <code>temperature=99</code>。真正的上游会返 4xx 并指出哪个参数非法；中转站如果悄悄 clamp 就可疑。",
    how_5: "<strong>长上下文针</strong> — 在约 12K 字符的填充里埋一个密码，问它能否取回。被替换成廉价模型这里直接失败。",
    how_deep: "Deep 模式额外加一个确定性算术推理探针和一个知识截止日期探针。",

    privacy_title: "隐私与安全",
    privacy_1: "默认模式：你的 API key 永远不离开浏览器，探针请求从你本机直接发到你填的 endpoint。",
    privacy_2: "服务器代理 fallback（仅在 endpoint 拒绝 CORS 时按按钮触发）：key 每次只用一次然后从内存丢弃，绝不写日志或落盘。",
    privacy_3: "可选的"记住 key"会把 key 存到浏览器 <code>localStorage</code>，谁能访问这个浏览器配置文件就能读到。共享电脑请勿勾选。",
    privacy_4: "服务器代理模式对每个 IP 限流为每小时 5 次。",
    privacy_5: "建议：测试不信任的中转站时，用一个短期或限额的临时 key。",
    privacy_6: "源码：<a href=\"https://github.com/study8677/api_verify\" target=\"_blank\" rel=\"noopener\">github.com/study8677/api_verify</a>",

    err_network: "网络错误",
    err_invalid_url: "Endpoint URL 不合法",
    err_missing_field: "请填完所有字段",
    err_server_rate_limited: "服务器代理已达速率限制，请稍后再试，或使用浏览器直调模式。",

    footer: "API Verify · 证据不等于证明",
  },
};

const I18N = {
  current: "en",
  t(key) { return (T[this.current] && T[this.current][key]) || T.en[key] || key; },
  apply() {
    const lang = this.current;
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    document.title = this.t("page_title");
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const k = el.getAttribute("data-i18n");
      el.textContent = this.t(k);
    });
    document.querySelectorAll("[data-i18n-html]").forEach((el) => {
      const k = el.getAttribute("data-i18n-html");
      el.innerHTML = this.t(k);
    });
    document.querySelectorAll("[data-i18n-attr]").forEach((el) => {
      // format: data-i18n-attr="placeholder:key,title:key"
      const spec = el.getAttribute("data-i18n-attr");
      spec.split(",").forEach((pair) => {
        const [attr, key] = pair.split(":").map((s) => s.trim());
        if (attr && key) el.setAttribute(attr, this.t(key));
      });
    });
    try { localStorage.setItem("apiverify.lang", lang); } catch (e) { /* private mode */ }
  },
  setLang(lang) {
    if (!T[lang]) lang = "en";
    this.current = lang;
    this.apply();
  },
  detect() {
    let saved = null;
    try { saved = localStorage.getItem("apiverify.lang"); } catch (e) {}
    if (saved && T[saved]) return saved;
    const nav = (navigator.language || "en").toLowerCase();
    return nav.startsWith("zh") ? "zh" : "en";
  },
};

window.APIVerify.I18N = I18N;
