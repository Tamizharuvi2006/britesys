#!/usr/bin/env python3
"""
Calder County — Caseworker's Morning Dashboard

A thin read-only dashboard that visualises the agent's output.
Serves a single HTML page with data from output/*.json.

Usage:
    python dashboard.py
    python dashboard.py --port 8080

No dependencies beyond Python 3 stdlib.
"""
import argparse
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(HERE, "output")


def load_json(filename):
    path = os.path.join(OUTPUT, filename)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_html():
    """Build the dashboard HTML with embedded data."""
    results = load_json("results.json") or []
    escalations = load_json("escalations.json") or []
    trace = load_json("trace.json") or []

    # Stats
    total = len(results)
    permitted = sum(1 for r in results if r["verdict"] == "PERMITTED")
    restricted = sum(1 for r in results if r["verdict"] == "RESTRICTED")
    ambiguous = sum(1 for r in results if r["verdict"] == "AMBIGUOUS_ESCALATE")
    errors = sum(1 for r in results if r["verdict"] == "ERROR")

    data_json = json.dumps({
        "results": results,
        "escalations": escalations,
        "trace": trace,
        "stats": {
            "total": total,
            "permitted": permitted,
            "restricted": restricted,
            "ambiguous": ambiguous,
            "errors": errors,
        },
    }, ensure_ascii=False)

    return HTML_TEMPLATE.replace("__DATA_JSON__", data_json)


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Caseworker's Morning — Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #0f1117;
  --surface: #1a1d27;
  --surface-2: #242836;
  --surface-3: #2e3347;
  --border: #363b50;
  --text: #e4e6f0;
  --text-dim: #8b90a8;
  --accent: #6c8aff;
  --accent-glow: rgba(108, 138, 255, 0.15);
  --green: #4ade80;
  --green-bg: rgba(74, 222, 128, 0.1);
  --red: #f87171;
  --red-bg: rgba(248, 113, 113, 0.1);
  --amber: #fbbf24;
  --amber-bg: rgba(251, 191, 36, 0.1);
  --radius: 12px;
  --radius-sm: 8px;
  --transition: 0.2s ease;
}

body {
  font-family: 'Inter', -apple-system, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  line-height: 1.6;
}

/* Header */
.header {
  background: linear-gradient(135deg, #1a1d27 0%, #242836 100%);
  border-bottom: 1px solid var(--border);
  padding: 20px 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.header h1 {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.3px;
}
.header h1 span { color: var(--accent); }
.header .subtitle {
  font-size: 13px;
  color: var(--text-dim);
  margin-top: 2px;
}
.header .badge {
  background: var(--accent-glow);
  color: var(--accent);
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
}

/* Layout */
.layout {
  display: grid;
  grid-template-columns: 380px 1fr;
  height: calc(100vh - 73px);
}

/* Stats bar */
.stats-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}
.stat-card {
  background: var(--surface-2);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  text-align: center;
}
.stat-card .value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}
.stat-card .label {
  font-size: 11px;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-top: 2px;
}
.stat-card.green .value { color: var(--green); }
.stat-card.red .value { color: var(--red); }
.stat-card.amber .value { color: var(--amber); }
.stat-card.blue .value { color: var(--accent); }

/* Sidebar — referral list */
.sidebar {
  background: var(--surface);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
.sidebar-title {
  padding: 16px 20px 8px;
  font-size: 12px;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.8px;
  font-weight: 600;
}
.referral-item {
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background var(--transition);
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.referral-item:hover { background: var(--surface-2); }
.referral-item.active { background: var(--accent-glow); border-left: 3px solid var(--accent); }
.referral-item .icon {
  width: 32px; height: 32px;
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
  margin-top: 2px;
}
.referral-item .icon.permitted { background: var(--green-bg); }
.referral-item .icon.restricted { background: var(--red-bg); }
.referral-item .icon.ambiguous { background: var(--amber-bg); }
.referral-item .info { flex: 1; min-width: 0; }
.referral-item .rid {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}
.referral-item .action {
  font-size: 12px;
  color: var(--text-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}
.referral-item .verdict-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  margin-top: 4px;
  display: inline-block;
}
.verdict-badge.permitted { background: var(--green-bg); color: var(--green); }
.verdict-badge.restricted { background: var(--red-bg); color: var(--red); }
.verdict-badge.ambiguous { background: var(--amber-bg); color: var(--amber); }

/* Main content — detail view */
.main {
  overflow-y: auto;
  padding: 24px 32px;
}
.main .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-dim);
  font-size: 15px;
}
.main .empty-state .icon { font-size: 48px; margin-bottom: 16px; opacity: 0.4; }

/* Detail sections */
.detail-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}
.detail-header .big-icon {
  width: 48px; height: 48px;
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px;
}
.detail-header h2 { font-size: 22px; font-weight: 600; }
.detail-header .meta {
  font-size: 13px;
  color: var(--text-dim);
  margin-top: 2px;
}

.section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 16px;
  overflow: hidden;
}
.section-header {
  padding: 14px 18px;
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-dim);
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
}
.section-body {
  padding: 16px 18px;
}
.section-body pre {
  font-family: 'Inter', monospace;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text);
}

/* Policy alert */
.policy-alert {
  background: var(--red-bg);
  border: 1px solid rgba(248, 113, 113, 0.25);
  border-radius: var(--radius-sm);
  padding: 14px 18px;
  margin-bottom: 16px;
}
.policy-alert.amber {
  background: var(--amber-bg);
  border-color: rgba(251, 191, 36, 0.25);
}
.policy-alert .alert-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 6px;
}
.policy-alert.amber .alert-title { color: var(--amber); }
.policy-alert:not(.amber) .alert-title { color: var(--red); }
.policy-alert .alert-body {
  font-size: 13px;
  color: var(--text);
  line-height: 1.6;
}

/* Trace timeline */
.trace-timeline {
  position: relative;
  padding-left: 24px;
}
.trace-timeline::before {
  content: '';
  position: absolute;
  left: 7px;
  top: 8px;
  bottom: 8px;
  width: 2px;
  background: var(--border);
}
.trace-step {
  position: relative;
  padding: 6px 0 6px 16px;
  font-size: 13px;
}
.trace-step::before {
  content: '';
  position: absolute;
  left: -20px;
  top: 12px;
  width: 10px; height: 10px;
  border-radius: 50%;
  background: var(--surface-3);
  border: 2px solid var(--border);
}
.trace-step.read::before { border-color: var(--accent); background: var(--accent-glow); }
.trace-step.ok::before { border-color: var(--green); background: var(--green-bg); }
.trace-step.blocked::before { border-color: var(--red); background: var(--red-bg); }
.trace-step.warn::before { border-color: var(--amber); background: var(--amber-bg); }
.trace-step .step-type {
  font-weight: 500;
  color: var(--text);
}
.trace-step .step-detail {
  color: var(--text-dim);
  margin-left: 4px;
}
.trace-step .step-time {
  font-size: 11px;
  color: var(--text-dim);
  opacity: 0.6;
}

/* Approval request */
.approval-card {
  background: linear-gradient(135deg, rgba(248,113,113,0.08), rgba(248,113,113,0.03));
  border: 1px solid rgba(248, 113, 113, 0.2);
  border-radius: var(--radius);
  padding: 18px;
  margin-bottom: 16px;
}
.approval-card .status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--red-bg);
  color: var(--red);
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 10px;
}
.approval-card .field {
  margin-top: 8px;
  font-size: 13px;
}
.approval-card .field-label {
  color: var(--text-dim);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  margin-bottom: 2px;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--surface-3); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--border); }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1><span>Caseworker's</span> Morning</h1>
    <div class="subtitle">Referral Triage Agent — Problem 5</div>
  </div>
  <div class="badge" id="run-time"></div>
</div>

<div class="layout">
  <div class="sidebar">
    <div class="stats-bar" id="stats-bar"></div>
    <div class="sidebar-title">Referral Queue</div>
    <div id="referral-list"></div>
  </div>
  <div class="main" id="main-content">
    <div class="empty-state">
      <div class="icon">📋</div>
      <div>Select a referral to view details</div>
    </div>
  </div>
</div>

<script>
const DATA = __DATA_JSON__;

// Render stats
function renderStats() {
  const s = DATA.stats;
  document.getElementById('stats-bar').innerHTML = `
    <div class="stat-card blue"><div class="value">${s.total}</div><div class="label">Total</div></div>
    <div class="stat-card green"><div class="value">${s.permitted}</div><div class="label">Permitted</div></div>
    <div class="stat-card red"><div class="value">${s.restricted}</div><div class="label">Restricted</div></div>
    <div class="stat-card amber"><div class="value">${s.ambiguous}</div><div class="label">Ambiguous</div></div>
  `;
  // Run time from trace
  if (DATA.trace.length > 0) {
    const first = DATA.trace[0].timestamp;
    const d = new Date(first);
    document.getElementById('run-time').textContent = d.toLocaleString();
  }
}

// Verdict helpers
function verdictClass(v) {
  if (v === 'PERMITTED') return 'permitted';
  if (v === 'RESTRICTED') return 'restricted';
  return 'ambiguous';
}
function verdictIcon(v) {
  if (v === 'PERMITTED') return '✓';
  if (v === 'RESTRICTED') return '🔒';
  return '⚠';
}
function verdictLabel(v) {
  if (v === 'PERMITTED') return 'Permitted';
  if (v === 'RESTRICTED') return 'Restricted';
  return 'Escalated';
}

// Render referral list
function renderList() {
  const list = document.getElementById('referral-list');
  // Sort by received_at from results (match triage note data)
  const sorted = [...DATA.results];

  list.innerHTML = sorted.map((r, i) => {
    const vc = verdictClass(r.verdict);
    const action = r.triage_note ? r.triage_note.referral_context.split('Requested action: ')[1] || '' : '';
    return `
      <div class="referral-item" data-idx="${i}" onclick="selectReferral(${i})">
        <div class="icon ${vc}">${verdictIcon(r.verdict)}</div>
        <div class="info">
          <div class="rid">${r.referral_id}</div>
          <div class="action">${action || r.verdict}</div>
          <div class="verdict-badge ${vc}">${verdictLabel(r.verdict)}</div>
        </div>
      </div>
    `;
  }).join('');
}

// Trace step classification
function traceStepClass(step) {
  if (step === 'referral_read') return 'read';
  if (step === 'history_fetched' || step === 'action_permitted' || step === 'triage_drafted') return 'ok';
  if (step === 'action_blocked' || step === 'escalation_created') return 'blocked';
  if (step === 'policy_evaluated' || step === 'approval_requested' || step === 'processing_continued') return 'warn';
  return '';
}

// Select and show referral detail
function selectReferral(idx) {
  // Highlight
  document.querySelectorAll('.referral-item').forEach(el => el.classList.remove('active'));
  document.querySelector(`.referral-item[data-idx="${idx}"]`).classList.add('active');

  const r = DATA.results[idx];
  const tn = r.triage_note || {};
  const esc = r.escalation || null;
  const appr = r.approval_request || null;
  const vc = verdictClass(r.verdict);

  // Get trace for this referral
  const referralTrace = DATA.trace.filter(t => t.referral_id === r.referral_id);

  let html = '';

  // Header
  html += `
    <div class="detail-header">
      <div class="big-icon icon ${vc}">${verdictIcon(r.verdict)}</div>
      <div>
        <h2>${r.referral_id}</h2>
        <div class="meta">${r.resident_ref} · ${verdictLabel(r.verdict)}</div>
      </div>
    </div>
  `;

  // Policy alert (if restricted/ambiguous)
  if (r.verdict === 'RESTRICTED') {
    const sections = esc ? esc.triggered_sections.map(s => '§' + s).join(', ') : '';
    html += `
      <div class="policy-alert">
        <div class="alert-title">🔒 Action Blocked — ${sections}</div>
        <div class="alert-body">${esc ? esc.reasoning : ''}</div>
      </div>
    `;
  } else if (r.verdict === 'AMBIGUOUS_ESCALATE') {
    html += `
      <div class="policy-alert amber">
        <div class="alert-title">⚠ Escalated — §6.1 Ambiguity Rule</div>
        <div class="alert-body">${esc ? esc.reasoning : ''}</div>
      </div>
    `;
  }

  // Approval request
  if (appr) {
    html += `
      <div class="approval-card">
        <div class="status">⏳ ${appr.status.replace('_', ' ')}</div>
        <div class="field">
          <div class="field-label">Action Requiring Approval</div>
          ${appr.action_requiring_approval}
        </div>
        <div class="field">
          <div class="field-label">Policy Sections</div>
          ${appr.policy_sections.map(s => '§' + s).join(', ')}
        </div>
      </div>
    `;
  }

  // Situation
  html += `
    <div class="section">
      <div class="section-header">Situation</div>
      <div class="section-body"><pre>${tn.situation_summary || 'N/A'}</pre></div>
    </div>
  `;

  // Referral context
  html += `
    <div class="section">
      <div class="section-header">Referral</div>
      <div class="section-body"><pre>${tn.referral_context || 'N/A'}</pre></div>
    </div>
  `;

  // History
  html += `
    <div class="section">
      <div class="section-header">Relevant History</div>
      <div class="section-body"><pre>${tn.relevant_history || 'N/A'}</pre></div>
    </div>
  `;

  // Next steps
  html += `
    <div class="section">
      <div class="section-header">Recommended Next Steps</div>
      <div class="section-body"><pre>${tn.recommended_next_steps || 'N/A'}</pre></div>
    </div>
  `;

  // Escalation context (if exists)
  if (esc) {
    html += `
      <div class="section">
        <div class="section-header">Supervisor Context</div>
        <div class="section-body"><pre>${esc.context_summary}</pre></div>
      </div>
    `;
  }

  // Execution trace
  html += `
    <div class="section">
      <div class="section-header">Execution Trace</div>
      <div class="section-body">
        <div class="trace-timeline">
          ${referralTrace.map(t => `
            <div class="trace-step ${traceStepClass(t.step)}">
              <span class="step-type">${t.step}</span>
              <span class="step-detail">— ${t.detail}</span>
              <div class="step-time">${t.timestamp}</div>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `;

  document.getElementById('main-content').innerHTML = html;
}

// Init
renderStats();
renderList();
</script>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            html = build_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        elif self.path.startswith("/api/"):
            name = self.path.split("/api/")[1].split("?")[0]
            data = load_json(f"{name}.json")
            if data is not None:
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        print(f"  [dashboard] {fmt % args}")


def main():
    ap = argparse.ArgumentParser(description="Caseworker's Morning Dashboard")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()

    # Check output exists
    if not os.path.exists(os.path.join(OUTPUT, "results.json")):
        print("No output files found. Run the agent first:")
        print("  python agent.py")
        sys.exit(1)

    print(f"Dashboard: http://127.0.0.1:{args.port}")
    print("Press Ctrl+C to stop.\n")
    ThreadingHTTPServer(("127.0.0.1", args.port), DashboardHandler).serve_forever()


if __name__ == "__main__":
    main()
