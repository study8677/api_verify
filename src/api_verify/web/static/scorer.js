// Scoring mirrors src/api_verify/web/scorer.py.
window.APIVerify = window.APIVerify || {};

function clamp(n) { return Math.max(0, Math.min(100, n)); }

function verdict(score, hasResults) {
  if (!hasResults) return "inconclusive";
  if (score >= 75) return "pass";
  if (score >= 50) return "suspicious";
  if (score > 0)   return "strongly suspicious";
  return "inconclusive";
}

function tryJSON(s) {
  if (!s) return null;
  s = s.trim();
  if (s.startsWith("```")) {
    s = s.replace(/^```(json)?/, "").replace(/```$/, "").trim();
  }
  try { return JSON.parse(s); } catch (e) { return null; }
}

function scoreMetadata(r, requested) {
  let score = 50, reasons = [];
  const text = (r.text || "").trim();
  const returned = (r.model_returned || "").toLowerCase();
  const req = (requested || "").toLowerCase();
  if (text.includes("API_VERIFY_OK")) { score += 20; reasons.push("echoed sentinel exactly"); }
  else if (text) { score += 5; reasons.push("got a response but not the exact sentinel"); }
  if (returned && req) {
    if (returned.includes(req) || req.includes(returned)) {
      score += 20; reasons.push("returned model string is consistent with requested");
    } else {
      score -= 25; reasons.push(`returned model \`${returned}\` differs from requested \`${req}\``);
    }
  }
  if (r.usage && typeof r.usage === "object" && Object.keys(r.usage).length) {
    score += 5; reasons.push("usage object present");
  }
  return [clamp(score), verdict(score, true), reasons.join("; ")];
}

function scoreJSONMode(r) {
  const parsed = tryJSON((r.text || "").trim());
  if (parsed === null) return [30, "suspicious", "JSON mode requested but response was not parseable JSON"];
  if (typeof parsed !== "object" || Array.isArray(parsed)) return [40, "suspicious", "JSON mode returned non-object JSON"];
  if ("number" in parsed && "verdict" in parsed) return [90, "pass", "valid JSON with required keys"];
  return [60, "suspicious", `valid JSON but missing required keys: ${Object.keys(parsed).join(",")}`];
}

function scoreToolCalling(r) {
  if (!r.tool_call_args) {
    const text = (r.text || "").trim();
    if (text.includes("19") && text.includes("23")) return [55, "suspicious", "no tool_calls returned; model answered as plain text (likely tool degradation)"];
    return [30, "strongly suspicious", "strict tool requested but no tool_calls were emitted"];
  }
  const keys = Object.keys(r.tool_call_args).sort().join(",");
  if (keys === "a,b") {
    const ok = Number(r.tool_call_args.a) === 19 && Number(r.tool_call_args.b) === 23;
    if (ok) return [95, "pass", "tool_calls emitted with correct strict schema and arguments"];
    return [75, "pass", "tool_calls emitted with correct schema, arguments differ"];
  }
  return [55, "suspicious", `tool_calls emitted but schema mismatch: ${Object.keys(r.tool_call_args).join(",")}`];
}

function scoreErrorSemantics(r) {
  const status = r.status || 0;
  const body = ((r.text || "") + " " + JSON.stringify(r.usage || {})).toLowerCase();
  if (status >= 400 && status < 500 && body.includes("temperature")) return [95, "pass", "invalid temperature produced a 4xx error mentioning the offending parameter"];
  if (status >= 400 && status < 500) return [65, "suspicious", `got HTTP ${status} but error body did not identify the offending parameter`];
  if (status === 0) return [20, "strongly suspicious", "no response to malformed request"];
  if (status >= 500) return [30, "strongly suspicious", `malformed request triggered HTTP ${status} (server error, not validation)`];
  return [25, "strongly suspicious", `malformed request was accepted (HTTP ${status}); silent parameter dropping suspected`];
}

function scoreNeedle(r) {
  const text = (r.text || "").toUpperCase();
  if (text.includes("ORANGE-SAILBOAT-42")) return [90, "pass", "recovered the needle from long context"];
  if (text.includes("ORANGE") || text.includes("SAILBOAT")) return [55, "suspicious", "partially recovered needle; long-context capability weak"];
  return [30, "strongly suspicious", "needle not recovered; long-context capability likely degraded"];
}

function scoreReasoning(r) {
  const text = (r.text || "").trim();
  if (text === "17" || text.startsWith("17")) return [85, "pass", "deterministic arithmetic answer correct"];
  if (text) return [45, "suspicious", `answer differs from expected \`17\`: ${text.slice(0, 60)}`];
  return [30, "suspicious", "empty response"];
}

function scoreCutoff(r) {
  return [50, "inconclusive", `reported cutoff: \`${(r.text || "").trim().slice(0, 40)}\` — compare against the official cutoff for the claimed model`];
}

function scoreOne(r, requested) {
  if (r.category === "error_semantics") return scoreErrorSemantics(r);
  if (r.status === null) return [15, "strongly suspicious", `transport error: ${r.error_text || "no response"}`];
  if (r.status >= 500) return [25, "strongly suspicious", `upstream returned HTTP ${r.status}`];
  if (r.status >= 400 && r.category !== "error_semantics") {
    return [35, "suspicious", `expected success path but got HTTP ${r.status}: ${(r.text || "").slice(0, 120)}`];
  }
  if (r.probe_id === "metadata") return scoreMetadata(r, requested);
  if (r.probe_id === "json_mode") return scoreJSONMode(r);
  if (r.probe_id === "tool_calling") return scoreToolCalling(r);
  if (r.probe_id === "long_context_needle") return scoreNeedle(r);
  if (r.probe_id === "reasoning_arith") return scoreReasoning(r);
  if (r.probe_id === "cutoff_check") return scoreCutoff(r);
  return [50, "inconclusive", "no scorer registered for this probe"];
}

function median(arr) {
  if (!arr.length) return null;
  const s = arr.slice().sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : Math.round((s[m - 1] + s[m]) / 2);
}

function scoreResults(results, requestedModel) {
  const evidence = [];
  const dimScores = {};
  const latencies = [];

  for (const r of results) {
    const [score, v, rationale] = scoreOne(r, requestedModel);
    (dimScores[r.category] = dimScores[r.category] || []).push(score);
    if (typeof r.latency_ms === "number") latencies.push(r.latency_ms);
    evidence.push({
      probe_id: r.probe_id,
      name_key: r.name_key,
      category: r.category,
      score, verdict: v, rationale,
      status: r.status,
      latency_ms: r.latency_ms,
      model_returned: r.model_returned,
      usage: r.usage,
      text_excerpt: (r.text || "").slice(0, 240),
    });
  }
  const dimensions = {};
  Object.keys(dimScores).sort().forEach((k) => {
    const v = dimScores[k];
    dimensions[k] = { score: Math.round((v.reduce((a, b) => a + b, 0) / v.length) * 10) / 10, runs: v.length };
  });
  const overall = Object.keys(dimensions).length
    ? Math.round((Object.values(dimensions).reduce((a, d) => a + d.score, 0) / Object.keys(dimensions).length) * 10) / 10
    : 0;
  return {
    overall_score: overall,
    verdict: verdict(overall, results.length > 0),
    dimensions,
    evidence,
    stats: {
      latency_ms_p50: median(latencies),
      latency_ms_max: latencies.length ? Math.max(...latencies) : null,
      probe_count: results.length,
    },
  };
}

window.APIVerify.Scorer = { scoreResults };
