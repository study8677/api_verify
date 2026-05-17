// Browser-side adapters mirroring src/api_verify/web/adapters/*.py.
// Each adapter takes a probe, builds the protocol-specific request, calls
// fetch(), and returns a normalized result. Errors are categorised so the UI
// can distinguish CORS / network failures from real HTTP responses.
window.APIVerify = window.APIVerify || {};

class CorsLikely extends Error {
  constructor(orig) { super(orig.message); this.cause = orig; }
}

function padWithNeedle(probe) {
  if (!probe.long_context_padding_chars || !probe.needle) return probe.user_prompt;
  const padBlock = "This is a long context padding section. ";
  const reps = Math.floor(probe.long_context_padding_chars / padBlock.length) + 1;
  const padded = padBlock.repeat(reps).slice(0, probe.long_context_padding_chars);
  return `${probe.needle}\n\n${padded}\n\n${probe.user_prompt}`;
}

function emptyResult(probe, overrides = {}) {
  return Object.assign({
    probe_id: probe.id,
    category: probe.category,
    name_key: probe.name,
    status: null,
    latency_ms: 0,
    model_returned: null,
    text: "",
    usage: null,
    tool_call_args: null,
    error_text: null,
    raw_response_excerpt: "",
  }, overrides);
}

async function fetchWithTimeout(url, options, timeoutMs) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    return await fetch(url, Object.assign({}, options, { signal: ctrl.signal }));
  } finally {
    clearTimeout(timer);
  }
}

// ---------- OpenAI-compatible ----------

class OpenAIAdapter {
  constructor({ endpoint, apiKey, model }) {
    this.endpoint = endpoint.replace(/\/+$/, "");
    this.apiKey = apiKey;
    this.model = model;
  }
  headers() {
    return {
      "Authorization": `Bearer ${this.apiKey}`,
      "Content-Type": "application/json",
      "Accept": "application/json",
    };
  }
  buildBody(probe) {
    const body = {
      model: this.model,
      messages: [{ role: "user", content: padWithNeedle(probe) }],
      temperature: 0,
      max_tokens: probe.max_tokens,
    };
    if (probe.require_json) body.response_format = { type: "json_object" };
    if (probe.tool_schema) {
      body.tools = [{
        type: "function",
        function: {
          name: probe.tool_schema.name,
          description: probe.tool_schema.description || "",
          strict: true,
          parameters: probe.tool_schema.parameters,
        },
      }];
      body.tool_choice = { type: "function", function: { name: probe.tool_schema.name } };
    }
    if (probe.bad_param) Object.assign(body, probe.bad_param);
    return body;
  }
  async call(probe) {
    const url = `${this.endpoint}/chat/completions`;
    const t0 = performance.now();
    let resp;
    try {
      resp = await fetchWithTimeout(url, {
        method: "POST", headers: this.headers(), body: JSON.stringify(this.buildBody(probe)),
      }, 25_000);
    } catch (err) {
      if (err.name === "AbortError") {
        return emptyResult(probe, { latency_ms: 25_000, error_text: "timeout" });
      }
      // TypeError "Failed to fetch" = CORS or DNS / network failure.
      throw new CorsLikely(err);
    }
    const latency = Math.round(performance.now() - t0);
    const raw = await resp.text();
    let data = null;
    try { data = JSON.parse(raw); } catch (e) {}
    let text = "", usage = null, modelReturned = null, toolArgs = null;
    if (data && typeof data === "object") {
      modelReturned = data.model || null;
      usage = (data.usage && typeof data.usage === "object") ? data.usage : null;
      const choices = data.choices || [];
      if (choices.length > 0) {
        const msg = (choices[0].message) || {};
        if (typeof msg.content === "string") text = msg.content;
        else if (Array.isArray(msg.content)) text = msg.content.map(p => (p && p.text) || "").join("");
        const tc = (msg.tool_calls && msg.tool_calls[0]) || null;
        if (tc && tc.function) {
          try { toolArgs = JSON.parse(tc.function.arguments || "{}"); }
          catch (e) { toolArgs = { _unparsed: String(tc.function.arguments || "").slice(0, 200) }; }
        }
      } else if (data.error) {
        text = JSON.stringify(data.error).slice(0, 500);
      }
    } else {
      text = raw.slice(0, 500);
    }
    return emptyResult(probe, {
      status: resp.status, latency_ms: latency,
      model_returned: modelReturned, text, usage, tool_call_args: toolArgs,
      error_text: resp.status >= 400 ? raw.slice(0, 200) : null,
      raw_response_excerpt: raw.slice(0, 500),
    });
  }
}

// ---------- Anthropic native ----------

class AnthropicAdapter {
  constructor({ endpoint, apiKey, model }) {
    this.endpoint = endpoint.replace(/\/+$/, "");
    this.apiKey = apiKey;
    this.model = model;
  }
  headers() {
    return {
      "x-api-key": this.apiKey,
      "anthropic-version": "2023-06-01",
      // Browser-direct mode requires this opt-in header; Anthropic blocks CORS
      // by default without it.
      "anthropic-dangerous-direct-browser-access": "true",
      "Content-Type": "application/json",
      "Accept": "application/json",
    };
  }
  buildBody(probe) {
    let user = padWithNeedle(probe);
    if (probe.require_json) {
      user = "Respond with ONLY a single JSON object and nothing else. " + user;
    }
    const body = {
      model: this.model,
      max_tokens: probe.max_tokens,
      temperature: 0,
      messages: [{ role: "user", content: user }],
    };
    if (probe.tool_schema) {
      body.tools = [{
        name: probe.tool_schema.name,
        description: probe.tool_schema.description || "",
        input_schema: probe.tool_schema.parameters,
      }];
      body.tool_choice = { type: "tool", name: probe.tool_schema.name };
    }
    if (probe.bad_param) Object.assign(body, probe.bad_param);
    return body;
  }
  async call(probe) {
    const url = `${this.endpoint}/v1/messages`;
    const t0 = performance.now();
    let resp;
    try {
      resp = await fetchWithTimeout(url, {
        method: "POST", headers: this.headers(), body: JSON.stringify(this.buildBody(probe)),
      }, 25_000);
    } catch (err) {
      if (err.name === "AbortError") return emptyResult(probe, { latency_ms: 25_000, error_text: "timeout" });
      throw new CorsLikely(err);
    }
    const latency = Math.round(performance.now() - t0);
    const raw = await resp.text();
    let data = null;
    try { data = JSON.parse(raw); } catch (e) {}
    let text = "", toolArgs = null, modelReturned = null, usage = null;
    if (data && typeof data === "object") {
      modelReturned = data.model || null;
      if (data.usage && typeof data.usage === "object") usage = data.usage;
      const blocks = data.content || [];
      const texts = [];
      for (const b of blocks) {
        if (!b || typeof b !== "object") continue;
        if (b.type === "text" && typeof b.text === "string") texts.push(b.text);
        else if (b.type === "tool_use" && b.input && typeof b.input === "object") toolArgs = b.input;
      }
      text = texts.join("");
      if (!text && data.error) text = JSON.stringify(data.error).slice(0, 500);
    } else {
      text = raw.slice(0, 500);
    }
    return emptyResult(probe, {
      status: resp.status, latency_ms: latency,
      model_returned: modelReturned, text, usage, tool_call_args: toolArgs,
      error_text: resp.status >= 400 ? raw.slice(0, 200) : null,
      raw_response_excerpt: raw.slice(0, 500),
    });
  }
}

// ---------- Gemini native ----------

class GeminiAdapter {
  constructor({ endpoint, apiKey, model }) {
    this.endpoint = endpoint.replace(/\/+$/, "");
    this.apiKey = apiKey;
    this.model = model;
  }
  headers() {
    return {
      "Content-Type": "application/json",
      "Accept": "application/json",
      "x-goog-api-key": this.apiKey,
    };
  }
  buildBody(probe) {
    let user = padWithNeedle(probe);
    if (probe.require_json) user = "Respond with ONLY a single JSON object and nothing else. " + user;
    const generationConfig = {
      temperature: 0,
      maxOutputTokens: probe.max_tokens,
    };
    if (probe.require_json) generationConfig.responseMimeType = "application/json";
    if (probe.bad_param && "temperature" in probe.bad_param) {
      generationConfig.temperature = probe.bad_param.temperature;
    }
    const body = {
      contents: [{ role: "user", parts: [{ text: user }] }],
      generationConfig,
    };
    if (probe.tool_schema) {
      body.tools = [{
        functionDeclarations: [{
          name: probe.tool_schema.name,
          description: probe.tool_schema.description || "",
          parameters: probe.tool_schema.parameters,
        }],
      }];
      body.toolConfig = {
        functionCallingConfig: { mode: "ANY", allowedFunctionNames: [probe.tool_schema.name] },
      };
    }
    return body;
  }
  async call(probe) {
    const safeModel = encodeURIComponent(this.model);
    const url = `${this.endpoint}/v1beta/models/${safeModel}:generateContent`;
    const t0 = performance.now();
    let resp;
    try {
      resp = await fetchWithTimeout(url, {
        method: "POST", headers: this.headers(), body: JSON.stringify(this.buildBody(probe)),
      }, 25_000);
    } catch (err) {
      if (err.name === "AbortError") return emptyResult(probe, { latency_ms: 25_000, error_text: "timeout" });
      throw new CorsLikely(err);
    }
    const latency = Math.round(performance.now() - t0);
    const raw = await resp.text();
    let data = null;
    try { data = JSON.parse(raw); } catch (e) {}
    let text = "", toolArgs = null, modelReturned = this.model, usage = null;
    if (data && typeof data === "object") {
      if (data.modelVersion) modelReturned = data.modelVersion;
      if (data.usageMetadata) usage = data.usageMetadata;
      const cands = data.candidates || [];
      if (cands.length > 0) {
        const parts = ((cands[0].content || {}).parts) || [];
        const texts = [];
        for (const p of parts) {
          if (typeof p.text === "string") texts.push(p.text);
          else if (p.functionCall && p.functionCall.args && typeof p.functionCall.args === "object") toolArgs = p.functionCall.args;
        }
        text = texts.join("");
      } else if (data.error) {
        text = JSON.stringify(data.error).slice(0, 500);
      }
    } else {
      text = raw.slice(0, 500);
    }
    return emptyResult(probe, {
      status: resp.status, latency_ms: latency,
      model_returned: modelReturned, text, usage, tool_call_args: toolArgs,
      error_text: resp.status >= 400 ? raw.slice(0, 200) : null,
      raw_response_excerpt: raw.slice(0, 500),
    });
  }
}

function buildAdapter(protocol, opts) {
  switch (protocol) {
    case "openai":    return new OpenAIAdapter(opts);
    case "anthropic": return new AnthropicAdapter(opts);
    case "gemini":    return new GeminiAdapter(opts);
    default: throw new Error("unknown protocol: " + protocol);
  }
}

window.APIVerify.Adapters = { buildAdapter, CorsLikely };
