(() => {
  const form = document.getElementById('verify-form');
  const submitBtn = document.getElementById('submit');
  const statusEl = document.getElementById('status');
  const resultEl = document.getElementById('result');
  const protocolSel = document.getElementById('protocol');
  const endpointInput = document.getElementById('endpoint');
  const endpointHint = document.getElementById('endpoint-hint');
  const modelInput = document.getElementById('model');

  const PROTOCOL_DEFAULTS = {
    openai:    { endpoint: 'https://api.openai.com/v1', model: 'gpt-4.1', hint: 'For OpenAI-compatible relays. Include the path up to but not including <code>/chat/completions</code>.' },
    anthropic: { endpoint: 'https://api.anthropic.com',  model: 'claude-opus-4-5', hint: 'Anthropic-native relay. Path should be the base (we append <code>/v1/messages</code>).' },
    gemini:    { endpoint: 'https://generativelanguage.googleapis.com', model: 'gemini-2.5-pro', hint: 'Gemini-native relay. Path should be the base (we append <code>/v1beta/models/{model}:generateContent</code>).' },
  };

  function applyDefaults() {
    const d = PROTOCOL_DEFAULTS[protocolSel.value];
    if (!d) return;
    if (!endpointInput.value) endpointInput.value = d.endpoint;
    if (!modelInput.value) modelInput.value = d.model;
    endpointHint.innerHTML = d.hint;
  }
  protocolSel.addEventListener('change', () => {
    const d = PROTOCOL_DEFAULTS[protocolSel.value];
    endpointInput.placeholder = d.endpoint;
    modelInput.placeholder = d.model;
    endpointHint.innerHTML = d.hint;
  });
  applyDefaults();

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    submitBtn.disabled = true;
    statusEl.textContent = 'Running probes... this can take 10–60 seconds.';
    resultEl.classList.add('hidden');

    const body = {
      protocol: protocolSel.value,
      endpoint: endpointInput.value.trim(),
      api_key: document.getElementById('api_key').value,
      model: modelInput.value.trim(),
      mode: document.getElementById('mode').value,
    };

    let data;
    try {
      const resp = await fetch('/api/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      data = await resp.json();
      if (!resp.ok) {
        const msg = data.detail || data.message || data.error || ('HTTP ' + resp.status);
        statusEl.textContent = 'Error: ' + msg;
        submitBtn.disabled = false;
        return;
      }
    } catch (err) {
      statusEl.textContent = 'Network error: ' + err.message;
      submitBtn.disabled = false;
      return;
    }

    statusEl.textContent = '';
    renderResult(data);
    submitBtn.disabled = false;
    resultEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  function verdictClass(v) {
    if (!v) return 'inconclusive';
    if (v === 'pass') return 'pass';
    if (v === 'suspicious') return 'suspicious';
    if (v === 'strongly suspicious') return 'strongly';
    return 'inconclusive';
  }

  function renderResult(data) {
    document.getElementById('overall-score').textContent = data.overall_score ?? '—';
    const verdictEl = document.getElementById('overall-verdict');
    verdictEl.textContent = data.verdict;
    verdictEl.className = 'verdict ' + verdictClass(data.verdict);

    document.getElementById('meta-probes').textContent = data.stats?.probe_count ?? '—';
    document.getElementById('meta-p50').textContent = data.stats?.latency_ms_p50 ?? '—';
    document.getElementById('meta-max').textContent = data.stats?.latency_ms_max ?? '—';
    const rl = data.rate_limit || {};
    document.getElementById('meta-remaining').textContent =
      (rl.remaining_this_hour ?? '—') + ' / ' + (rl.max_per_hour ?? '—');

    const dimEl = document.getElementById('dimensions');
    dimEl.innerHTML = '';
    Object.entries(data.dimensions || {}).forEach(([k, v]) => {
      const card = document.createElement('div');
      card.className = 'dim';
      card.innerHTML = `<div class="dn">${escape(k)}</div><div class="ds">${v.score}</div><div class="dr">${v.runs} probe(s)</div>`;
      dimEl.appendChild(card);
    });

    const evEl = document.getElementById('evidence');
    evEl.innerHTML = '';
    (data.evidence || []).forEach((ev) => {
      const div = document.createElement('div');
      div.className = 'ev';
      const usage = ev.usage ? JSON.stringify(ev.usage) : '—';
      div.innerHTML = `
        <div class="row">
          <div>
            <div class="name">${escape(ev.name || ev.probe_id)}</div>
            <div class="cat">${escape(ev.category)}</div>
          </div>
          <div>
            <span class="verdict ${verdictClass(ev.verdict)}">${escape(ev.verdict)}</span>
            <strong style="margin-left:8px;">${ev.score}</strong>
          </div>
        </div>
        <div class="ratio">${escape(ev.rationale || '')}</div>
        <div class="meta-line">HTTP ${ev.status ?? '—'} · ${ev.latency_ms ?? '—'} ms · model_returned=${escape(ev.model_returned || '—')} · usage=${escape(usage)}</div>
        ${ev.text_excerpt ? `<div class="body">${escape(ev.text_excerpt)}</div>` : ''}
      `;
      evEl.appendChild(div);
    });

    document.getElementById('note').textContent = data.note || '';
    resultEl.classList.remove('hidden');
  }

  function escape(s) {
    if (s === null || s === undefined) return '';
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
})();
