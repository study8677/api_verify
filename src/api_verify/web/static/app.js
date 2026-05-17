// Main UI controller. Orchestrates the form, browser-direct probe execution,
// CORS-failure fallback to /api/verify, results rendering, and i18n.
(() => {
  const { I18N } = window.APIVerify;
  const { QUICK_PROBES, DEEP_EXTRA_PROBES } = window.APIVerify.PROBES;
  const { buildAdapter, CorsLikely } = window.APIVerify.Adapters;
  const { scoreResults } = window.APIVerify.Scorer;

  const PROTOCOL_DEFAULTS = {
    openai:    { endpoint: "https://api.openai.com/v1",                  model: "gpt-4.1",         hintKey: "endpoint_hint_openai" },
    anthropic: { endpoint: "https://api.anthropic.com",                  model: "claude-opus-4-5", hintKey: "endpoint_hint_anthropic" },
    gemini:    { endpoint: "https://generativelanguage.googleapis.com",  model: "gemini-2.5-pro",  hintKey: "endpoint_hint_gemini" },
  };

  const KEY_STORAGE = "apiverify.key.v1";
  const REMEMBER_FLAG = "apiverify.remember.v1";

  let currentForm = null; // remembered between browser-direct attempt and server-fallback retry

  function $(id) { return document.getElementById(id); }

  function setupLangToggle() {
    I18N.setLang(I18N.detect());
    $("lang-toggle").addEventListener("click", () => {
      I18N.setLang(I18N.current === "zh" ? "en" : "zh");
      // re-render the mode badge / hint with new language
      updateProtocolHint();
      updateModeBadge("browser");
    });
  }

  function updateProtocolHint() {
    const sel = $("protocol").value;
    const d = PROTOCOL_DEFAULTS[sel];
    if (!d) return;
    $("endpoint-hint").innerHTML = I18N.t(d.hintKey);
    $("endpoint").placeholder = d.endpoint;
    $("model").placeholder = d.model;
  }

  function updateModeBadge(mode) {
    const el = $("mode-badge");
    el.textContent = I18N.t(mode === "browser" ? "badge_browser" : "badge_server");
    el.className = "mode-badge " + (mode === "browser" ? "mode-browser" : "mode-server");
  }

  function restorePersisted() {
    let remember = false;
    try { remember = localStorage.getItem(REMEMBER_FLAG) === "1"; } catch (e) {}
    $("remember-key").checked = remember;
    if (remember) {
      try {
        const k = localStorage.getItem(KEY_STORAGE);
        if (k) $("api_key").value = k;
      } catch (e) {}
    }
    // restore last-used protocol defaults
    updateProtocolHint();
  }

  function persistKeyIfRequested() {
    const remember = $("remember-key").checked;
    try {
      if (remember) {
        localStorage.setItem(REMEMBER_FLAG, "1");
        localStorage.setItem(KEY_STORAGE, $("api_key").value);
      } else {
        localStorage.removeItem(REMEMBER_FLAG);
        localStorage.removeItem(KEY_STORAGE);
      }
    } catch (e) {}
  }

  async function runBrowserDirect(form) {
    const adapter = buildAdapter(form.protocol, {
      endpoint: form.endpoint, apiKey: form.api_key, model: form.model,
    });
    const probes = form.mode === "deep"
      ? QUICK_PROBES.concat(DEEP_EXTRA_PROBES)
      : QUICK_PROBES.slice();
    // Probe head-of-line: run the first probe alone to detect CORS early.
    const first = await adapter.call(probes[0]);
    const rest = await Promise.all(probes.slice(1).map((p) => adapter.call(p).catch((err) => {
      // a single CORS-like failure among parallel probes — surface but don't stop
      if (err && err.message) {
        return { probe_id: p.id, category: p.category, name_key: p.name,
                 status: null, latency_ms: 0, model_returned: null, text: "",
                 usage: null, tool_call_args: null,
                 error_text: "browser-direct call failed: " + err.message,
                 raw_response_excerpt: "" };
      }
      throw err;
    })));
    return [first, ...rest];
  }

  async function runViaServer(form) {
    const resp = await fetch("/api/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    const data = await resp.json();
    if (!resp.ok) {
      if (resp.status === 429) throw new Error(I18N.t("err_server_rate_limited"));
      throw new Error(data.detail || data.message || `HTTP ${resp.status}`);
    }
    return data;
  }

  function showCorsPrompt() {
    return new Promise((resolve) => {
      const prompt = $("cors-prompt");
      prompt.classList.remove("hidden");
      const use = $("cors-use-server");
      const cancel = $("cors-cancel");
      const cleanup = () => {
        prompt.classList.add("hidden");
        use.removeEventListener("click", onUse);
        cancel.removeEventListener("click", onCancel);
      };
      const onUse = () => { cleanup(); resolve(true); };
      const onCancel = () => { cleanup(); resolve(false); };
      use.addEventListener("click", onUse);
      cancel.addEventListener("click", onCancel);
    });
  }

  async function onSubmit(e) {
    e.preventDefault();
    const form = {
      protocol: $("protocol").value,
      endpoint: $("endpoint").value.trim(),
      api_key:  $("api_key").value,
      model:    $("model").value.trim(),
      mode:     $("mode").value,
    };
    if (!form.endpoint || !form.api_key || !form.model) {
      setStatus(I18N.t("err_missing_field"));
      return;
    }
    currentForm = form;
    persistKeyIfRequested();
    $("submit").disabled = true;
    setStatus(I18N.t("form_running"));
    $("result").classList.add("hidden");
    updateModeBadge("browser");

    let scored, modeUsed = "browser";
    try {
      const results = await runBrowserDirect(form);
      scored = scoreResults(results, form.model);
    } catch (err) {
      // First probe threw CorsLikely → ask the user whether to fall back to the server.
      if (err instanceof CorsLikely) {
        setStatus("");
        $("submit").disabled = false;
        const useServer = await showCorsPrompt();
        if (!useServer) return;
        $("submit").disabled = true;
        setStatus(I18N.t("form_running"));
        modeUsed = "server";
        try {
          scored = await runViaServer(form);
        } catch (e2) {
          setStatus("Error: " + e2.message);
          $("submit").disabled = false;
          return;
        }
      } else {
        setStatus("Error: " + (err.message || err));
        $("submit").disabled = false;
        return;
      }
    }

    setStatus("");
    updateModeBadge(modeUsed);
    renderResult(scored, modeUsed);
    $("submit").disabled = false;
    $("result").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function setStatus(s) { $("status").textContent = s; }

  function verdictClass(v) {
    if (v === "pass" || v === "通过") return "pass";
    if (v === "suspicious" || v === "可疑") return "suspicious";
    if (v === "strongly suspicious" || v === "强可疑") return "strongly";
    return "inconclusive";
  }
  function localizedVerdict(v) {
    const map = {
      pass: I18N.t("verdict_pass"),
      suspicious: I18N.t("verdict_suspicious"),
      "strongly suspicious": I18N.t("verdict_strongly"),
      inconclusive: I18N.t("verdict_inconclusive"),
    };
    return map[v] || v;
  }
  function localizedProbeName(nameOrKey) {
    if (nameOrKey && typeof nameOrKey === "object") {
      return nameOrKey[I18N.current] || nameOrKey.en || JSON.stringify(nameOrKey);
    }
    return String(nameOrKey || "");
  }

  function renderResult(data, mode) {
    $("overall-score").textContent = data.overall_score ?? "—";
    const vEl = $("overall-verdict");
    vEl.textContent = localizedVerdict(data.verdict);
    vEl.className = "verdict " + verdictClass(data.verdict);

    $("meta-probes").textContent = data.stats?.probe_count ?? "—";
    $("meta-p50").textContent = data.stats?.latency_ms_p50 ?? "—";
    $("meta-max").textContent = data.stats?.latency_ms_max ?? "—";
    $("meta-mode").textContent = I18N.t(mode === "browser" ? "badge_browser" : "badge_server");
    const rl = data.rate_limit || null;
    $("meta-remaining").textContent = rl ? `${rl.remaining_this_hour}/${rl.max_per_hour}` : "—";

    const dimEl = $("dimensions");
    dimEl.innerHTML = "";
    Object.entries(data.dimensions || {}).forEach(([k, v]) => {
      const card = document.createElement("div");
      card.className = "dim";
      card.innerHTML = `<div class="dn">${escapeHTML(k)}</div><div class="ds">${v.score}</div><div class="dr">${v.runs} probe(s)</div>`;
      dimEl.appendChild(card);
    });

    const evEl = $("evidence");
    evEl.innerHTML = "";
    (data.evidence || []).forEach((ev) => {
      const div = document.createElement("div");
      div.className = "ev";
      const displayName = localizedProbeName(ev.name_key || ev.name || ev.probe_id);
      const usage = ev.usage ? JSON.stringify(ev.usage) : "—";
      div.innerHTML = `
        <div class="row">
          <div>
            <div class="name">${escapeHTML(displayName)}</div>
            <div class="cat">${escapeHTML(ev.category)}</div>
          </div>
          <div>
            <span class="verdict ${verdictClass(ev.verdict)}">${escapeHTML(localizedVerdict(ev.verdict))}</span>
            <strong style="margin-left:8px;">${ev.score}</strong>
          </div>
        </div>
        <div class="ratio">${escapeHTML(ev.rationale || "")}</div>
        <div class="meta-line">HTTP ${ev.status ?? "—"} · ${ev.latency_ms ?? "—"} ms · model_returned=${escapeHTML(ev.model_returned || "—")} · usage=${escapeHTML(usage)}</div>
        ${ev.text_excerpt ? `<div class="body">${escapeHTML(ev.text_excerpt)}</div>` : ""}
      `;
      evEl.appendChild(div);
    });

    $("note").textContent = I18N.t("result_note");
    $("result").classList.remove("hidden");
  }

  function escapeHTML(s) {
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  // ---------- bootstrap ----------
  document.addEventListener("DOMContentLoaded", () => {
    setupLangToggle();
    $("protocol").addEventListener("change", updateProtocolHint);
    restorePersisted();
    updateModeBadge("browser");
    $("verify-form").addEventListener("submit", onSubmit);
  });
})();
