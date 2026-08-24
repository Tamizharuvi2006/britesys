#!/usr/bin/env python3
"""
Calder County — Caseworker's Morning Dashboard
Read-only viewer for agent output files. No business logic.

Usage:
    python dashboard.py
    python dashboard.py --port 8080
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
    results   = load_json("results.json")   or []
    escalations = load_json("escalations.json") or []
    trace     = load_json("trace.json")     or []
    handoffs  = load_json("handoffs.json")  or []

    total     = len(results)
    permitted = sum(1 for r in results if r["verdict"] == "PERMITTED")
    restricted= sum(1 for r in results if r["verdict"] == "RESTRICTED")
    ambiguous = sum(1 for r in results if r["verdict"] == "AMBIGUOUS_ESCALATE")
    handoff_n = sum(1 for r in results if r["verdict"] == "CHILD_HANDOFF")

    run_ts = trace[0]["timestamp"] if trace else ""

    data = json.dumps({
        "results": results,
        "trace": trace,
        "stats": {
            "total": total, "permitted": permitted,
            "restricted": restricted, "ambiguous": ambiguous,
            "handoffs": handoff_n,
        },
        "run_ts": run_ts,
    }, ensure_ascii=False)

    return HTML.replace("__DATA__", data)


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Caseworker's Morning</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
/* ─── Reset ─────────────────────────────────────────────── */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

/* ─── Design tokens ─────────────────────────────────────── */
:root{
  --bg:          #08090c;
  --surface:     #0e1015;
  --glass:       rgba(255,255,255,0.035);
  --glass-border:rgba(255,255,255,0.07);
  --glass-hover: rgba(255,255,255,0.06);

  --text:        #e8eaf0;
  --text-dim:    #5c6070;
  --text-mid:    #8890a4;

  --green:       #34c97b;
  --green-dim:   rgba(52,201,123,0.10);
  --green-line:  rgba(52,201,123,0.22);

  --red:         #e05c5c;
  --red-dim:     rgba(224,92,92,0.10);
  --red-line:    rgba(224,92,92,0.22);

  --amber:       #e8a838;
  --amber-dim:   rgba(232,168,56,0.10);
  --amber-line:  rgba(232,168,56,0.22);

  --purple:      #a47de8;
  --purple-dim:  rgba(164,125,232,0.10);
  --purple-line: rgba(164,125,232,0.22);

  --accent:      #5b7fff;
  --accent-dim:  rgba(91,127,255,0.12);
  --accent-line: rgba(91,127,255,0.24);

  --radius:      14px;
  --radius-sm:   9px;
  --ease:        cubic-bezier(.16,1,.3,1);
}

body{
  font-family:'Inter',system-ui,sans-serif;
  background:var(--bg);
  color:var(--text);
  min-height:100vh;
  -webkit-font-smoothing:antialiased;
}

/* ─── Scrollbar ──────────────────────────────────────────── */
::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.08);border-radius:2px}

/* ─── Layout ─────────────────────────────────────────────── */
.root{display:grid;grid-template-rows:auto 1fr;height:100vh}

/* ─── Topbar ─────────────────────────────────────────────── */
.topbar{
  border-bottom:1px solid var(--glass-border);
  background:var(--surface);
  padding:16px 28px;
  display:flex;align-items:center;justify-content:space-between;
  gap:16px;
}
.topbar-left{display:flex;align-items:center;gap:14px}
.logo{
  width:36px;height:36px;
  background:var(--accent-dim);
  border:1px solid var(--accent-line);
  border-radius:10px;
  display:flex;align-items:center;justify-content:center;
  font-size:16px;flex-shrink:0;
}
.title h1{font-size:15px;font-weight:600;letter-spacing:-.2px}
.title p{font-size:12px;color:var(--text-dim);margin-top:1px}

.stat-pills{display:flex;gap:8px;flex-wrap:wrap}
.pill{
  display:flex;align-items:center;gap:6px;
  padding:5px 12px;border-radius:20px;
  font-size:12px;font-weight:500;
  border:1px solid;
}
.pill.green {background:var(--green-dim); border-color:var(--green-line); color:var(--green)}
.pill.red   {background:var(--red-dim);   border-color:var(--red-line);   color:var(--red)}
.pill.amber {background:var(--amber-dim); border-color:var(--amber-line); color:var(--amber)}
.pill.purple{background:var(--purple-dim);border-color:var(--purple-line);color:var(--purple)}
.pill.blue  {background:var(--accent-dim);border-color:var(--accent-line);color:var(--accent)}
.pill .dot{width:6px;height:6px;border-radius:50%;background:currentColor}

.run-ts{font-size:11px;color:var(--text-dim);flex-shrink:0}

/* ─── Body split ─────────────────────────────────────────── */
.body{display:grid;grid-template-columns:300px 1fr;overflow:hidden}

/* ─── Sidebar ────────────────────────────────────────────── */
.sidebar{
  background:var(--surface);
  border-right:1px solid var(--glass-border);
  display:flex;flex-direction:column;
  overflow:hidden;
}
.sidebar-head{
  padding:14px 16px 10px;
  font-size:10px;font-weight:600;letter-spacing:.8px;
  text-transform:uppercase;color:var(--text-dim);
  border-bottom:1px solid var(--glass-border);
}
.list{overflow-y:auto;flex:1}

.item{
  padding:13px 16px;
  border-bottom:1px solid rgba(255,255,255,0.04);
  cursor:pointer;
  display:flex;align-items:flex-start;gap:11px;
  transition:background .15s;
  border-left:2px solid transparent;
}
.item:hover{background:var(--glass-hover)}
.item.active{
  background:var(--accent-dim);
  border-left-color:var(--accent);
}

.item-icon{
  width:28px;height:28px;border-radius:8px;
  display:flex;align-items:center;justify-content:center;
  font-size:12px;flex-shrink:0;margin-top:1px;
  border:1px solid;
}
.item-icon.green {background:var(--green-dim); border-color:var(--green-line)}
.item-icon.red   {background:var(--red-dim);   border-color:var(--red-line)}
.item-icon.amber {background:var(--amber-dim); border-color:var(--amber-line)}
.item-icon.purple{background:var(--purple-dim);border-color:var(--purple-line)}

.item-body{flex:1;min-width:0}
.item-id{font-size:12px;font-weight:600;color:var(--text)}
.item-action{
  font-size:11px;color:var(--text-dim);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  margin-top:2px;
}
.item-badge{
  font-size:9px;font-weight:600;
  padding:2px 7px;border-radius:8px;
  border:1px solid;letter-spacing:.3px;
  margin-top:5px;display:inline-block;text-transform:uppercase;
}
.item-badge.green {background:var(--green-dim); border-color:var(--green-line); color:var(--green)}
.item-badge.red   {background:var(--red-dim);   border-color:var(--red-line);   color:var(--red)}
.item-badge.amber {background:var(--amber-dim); border-color:var(--amber-line); color:var(--amber)}
.item-badge.purple{background:var(--purple-dim);border-color:var(--purple-line);color:var(--purple)}

/* ─── Detail pane ────────────────────────────────────────── */
.detail{overflow-y:auto;padding:28px 32px}

.empty{
  height:100%;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:12px;
  color:var(--text-dim);
}
.empty-icon{font-size:40px;opacity:.3}
.empty p{font-size:14px}

/* Detail header */
.dh{display:flex;align-items:flex-start;gap:16px;margin-bottom:24px}
.dh-icon{
  width:48px;height:48px;border-radius:14px;
  display:flex;align-items:center;justify-content:center;
  font-size:22px;border:1px solid;flex-shrink:0;
}
.dh-icon.green {background:var(--green-dim); border-color:var(--green-line)}
.dh-icon.red   {background:var(--red-dim);   border-color:var(--red-line)}
.dh-icon.amber {background:var(--amber-dim); border-color:var(--amber-line)}
.dh-icon.purple{background:var(--purple-dim);border-color:var(--purple-line)}

.dh-text h2{font-size:22px;font-weight:700;letter-spacing:-.4px}
.dh-text .meta{font-size:13px;color:var(--text-dim);margin-top:3px}

/* Alert banners */
.alert{
  border-radius:var(--radius-sm);
  padding:14px 16px;
  margin-bottom:16px;
  border:1px solid;
}
.alert.red   {background:var(--red-dim);   border-color:var(--red-line)}
.alert.amber {background:var(--amber-dim); border-color:var(--amber-line)}
.alert.purple{background:var(--purple-dim);border-color:var(--purple-line)}
.alert.green {background:var(--green-dim); border-color:var(--green-line)}

.alert-title{
  font-size:13px;font-weight:600;margin-bottom:5px;
  display:flex;align-items:center;gap:8px;
}
.alert.red    .alert-title{color:var(--red)}
.alert.amber  .alert-title{color:var(--amber)}
.alert.purple .alert-title{color:var(--purple)}
.alert.green  .alert-title{color:var(--green)}

.alert-body{font-size:13px;color:var(--text-mid);line-height:1.65}

/* Approval badge */
.approval{
  display:inline-flex;align-items:center;gap:6px;
  background:var(--red-dim);border:1px solid var(--red-line);
  color:var(--red);
  padding:5px 12px;border-radius:20px;
  font-size:11px;font-weight:600;letter-spacing:.3px;
  margin-bottom:16px;
}

/* Glass cards */
.card{
  background:var(--glass);
  border:1px solid var(--glass-border);
  border-radius:var(--radius);
  margin-bottom:14px;
  overflow:hidden;
}
.card-head{
  padding:11px 16px;
  font-size:10px;font-weight:600;letter-spacing:.7px;text-transform:uppercase;
  color:var(--text-dim);
  border-bottom:1px solid var(--glass-border);
  background:rgba(255,255,255,0.018);
}
.card-body{padding:14px 16px}
.card-body pre{
  font-family:'Inter',monospace;
  font-size:12.5px;line-height:1.75;
  white-space:pre-wrap;word-break:break-word;
  color:var(--text);
}

/* Checklist */
.checklist{display:flex;flex-direction:column;gap:7px}
.check-row{display:flex;align-items:center;gap:10px;font-size:13px}
.check-row .ck{
  width:18px;height:18px;border-radius:5px;
  display:flex;align-items:center;justify-content:center;
  font-size:10px;flex-shrink:0;
}
.ck.ok   {background:var(--green-dim);border:1px solid var(--green-line);color:var(--green)}
.ck.skip {background:var(--red-dim);  border:1px solid var(--red-line);  color:var(--red)}
.ck.pass {background:var(--purple-dim);border:1px solid var(--purple-line);color:var(--purple)}

/* Policy tags */
.policy-tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.ptag{
  font-size:11px;font-weight:600;
  padding:3px 10px;border-radius:6px;
  background:var(--red-dim);border:1px solid var(--red-line);color:var(--red);
}

/* Trace timeline */
.timeline{position:relative;padding-left:22px}
.timeline::before{
  content:'';position:absolute;left:6px;top:8px;bottom:8px;
  width:1px;background:var(--glass-border);
}
.trow{position:relative;padding:5px 0 5px 14px;font-size:12.5px}
.trow::before{
  content:'';position:absolute;left:-16px;top:12px;
  width:8px;height:8px;border-radius:50%;
  background:var(--surface);border:1px solid var(--glass-border);
}
.trow.t-read::before   {border-color:var(--accent); background:var(--accent-dim)}
.trow.t-ok::before     {border-color:var(--green);  background:var(--green-dim)}
.trow.t-block::before  {border-color:var(--red);    background:var(--red-dim)}
.trow.t-handoff::before{border-color:var(--purple); background:var(--purple-dim)}
.trow.t-warn::before   {border-color:var(--amber);  background:var(--amber-dim)}
.trow.t-cont::before   {border-color:var(--text-dim);background:var(--glass)}

.step-name{font-weight:500;color:var(--text)}
.step-detail{color:var(--text-dim);margin-left:4px}
.step-ts{display:block;font-size:10px;color:var(--text-dim);opacity:.5;margin-top:1px}

/* Divider */
.divider{height:1px;background:var(--glass-border);margin:20px 0}
</style>
</head>
<body>
<div class="root">

<!-- TOPBAR -->
<header class="topbar">
  <div class="topbar-left">
    <div class="logo">⚖</div>
    <div class="title">
      <h1>Caseworker's Morning</h1>
      <p>Referral Triage Agent — Problem 5 · Brite Spark 2026</p>
    </div>
  </div>
  <div class="stat-pills" id="pills"></div>
  <div class="run-ts" id="run-ts"></div>
</header>

<!-- BODY -->
<div class="body">

  <!-- SIDEBAR -->
  <nav class="sidebar">
    <div class="sidebar-head">Referral Queue</div>
    <div class="list" id="list"></div>
  </nav>

  <!-- DETAIL -->
  <main class="detail" id="detail">
    <div class="empty">
      <div class="empty-icon">📋</div>
      <p>Select a referral to view details</p>
    </div>
  </main>

</div>
</div>

<script>
const D = __DATA__;

/* ── helpers ───────────────────────────────────────────── */
function vc(verdict){
  if(verdict==='PERMITTED')         return 'green';
  if(verdict==='RESTRICTED')        return 'red';
  if(verdict==='AMBIGUOUS_ESCALATE')return 'amber';
  if(verdict==='CHILD_HANDOFF')     return 'purple';
  return 'blue';
}
function vi(verdict){
  if(verdict==='PERMITTED')         return '✓';
  if(verdict==='RESTRICTED')        return '🔒';
  if(verdict==='AMBIGUOUS_ESCALATE')return '⚠';
  if(verdict==='CHILD_HANDOFF')     return '👶';
  return '?';
}
function vl(verdict){
  if(verdict==='PERMITTED')         return 'Permitted';
  if(verdict==='RESTRICTED')        return 'Restricted';
  if(verdict==='AMBIGUOUS_ESCALATE')return 'Escalated';
  if(verdict==='CHILD_HANDOFF')     return 'Handoff';
  return verdict;
}
function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

/* ── pills ─────────────────────────────────────────────── */
const s = D.stats;
document.getElementById('pills').innerHTML = `
  <div class="pill blue"><span class="dot"></span>${s.total} Total</div>
  <div class="pill green"><span class="dot"></span>${s.permitted} Permitted</div>
  <div class="pill red"><span class="dot"></span>${s.restricted} Restricted</div>
  <div class="pill amber"><span class="dot"></span>${s.ambiguous} Ambiguous</div>
  <div class="pill purple"><span class="dot"></span>${s.handoffs} Handoff</div>
`;
if(D.run_ts){
  document.getElementById('run-ts').textContent =
    'Run: ' + new Date(D.run_ts).toLocaleString();
}

/* ── trace index ───────────────────────────────────────── */
const traceMap = {};
D.trace.forEach(t=>{
  if(!traceMap[t.referral_id]) traceMap[t.referral_id]=[];
  traceMap[t.referral_id].push(t);
});

/* ── sidebar ───────────────────────────────────────────── */
const list = document.getElementById('list');
D.results.forEach((r,i)=>{
  const c = vc(r.verdict);
  const tn = r.triage_note||{};
  // Extract action from referral_context or fallback
  let action = '';
  if(tn.referral_context){
    const m = tn.referral_context.match(/Requested action:\s*(.+)/);
    if(m) action = m[1].trim();
  }
  if(!action && r.handoff) action = r.handoff.requested_action||'';

  const el = document.createElement('div');
  el.className='item';
  el.dataset.idx=i;
  el.innerHTML=`
    <div class="item-icon ${c}">${vi(r.verdict)}</div>
    <div class="item-body">
      <div class="item-id">${r.referral_id}</div>
      <div class="item-action">${esc(action||r.verdict)}</div>
      <span class="item-badge ${c}">${vl(r.verdict)}</span>
    </div>
  `;
  el.addEventListener('click',()=>open(i));
  list.appendChild(el);
});

/* ── trace step class ──────────────────────────────────── */
function tclass(step){
  if(step==='referral_read')                 return 't-read';
  if(['history_fetched','triage_drafted',
      'action_permitted'].includes(step))    return 't-ok';
  if(['action_blocked',
      'escalation_created'].includes(step))  return 't-block';
  if(['child_handoff_detected',
      'handoff_created'].includes(step))     return 't-handoff';
  if(['approval_requested',
      'policy_evaluated'].includes(step))    return 't-warn';
  if(step==='processing_continued')          return 't-cont';
  return '';
}

/* ── detail view ───────────────────────────────────────── */
function open(idx){
  // Highlight
  document.querySelectorAll('.item').forEach(el=>{
    el.classList.toggle('active', +el.dataset.idx===idx);
  });

  const r  = D.results[idx];
  const c  = vc(r.verdict);
  const tn = r.triage_note||null;
  const h  = r.handoff||null;
  const esc_rec = r.escalation||null;
  const appr    = r.approval_request||null;
  const steps   = traceMap[r.referral_id]||[];

  let html = '';

  /* Header */
  html += `
    <div class="dh">
      <div class="dh-icon ${c}">${vi(r.verdict)}</div>
      <div class="dh-text">
        <h2>${r.referral_id}</h2>
        <div class="meta">${r.resident_ref} &nbsp;·&nbsp; ${vl(r.verdict)}</div>
      </div>
    </div>
  `;

  /* ── CHILD HANDOFF ─────────────────────────────────── */
  if(r.verdict==='CHILD_HANDOFF' && h){
    html += `
      <div class="alert purple">
        <div class="alert-title">👶 Child Household — ACA-2026/2 §3.9</div>
        <div class="alert-body">${esc(h.reason)}</div>
      </div>
    `;

    /* Minors */
    const minorRows = (h.minors_identified||[]).map(m=>`
      <div class="check-row">
        <div class="ck pass">👶</div>
        <span>${esc(m.name)} &nbsp;<span style="color:var(--text-dim)">age ${m.age_on_referral_date} · ${esc(m.relationship)}</span></span>
      </div>
    `).join('');

    html += `
      <div class="card">
        <div class="card-head">Minors Identified in Household</div>
        <div class="card-body"><div class="checklist">${minorRows}</div></div>
      </div>
    `;

    /* What was NOT generated */
    html += `
      <div class="card">
        <div class="card-head">Triage Note</div>
        <div class="card-body">
          <div class="checklist">
            <div class="check-row"><div class="ck skip">✕</div><span style="color:var(--text-dim)">Not generated — §2.2 of ACA-2026/2 prohibits drafting a triage note for this case</span></div>
          </div>
        </div>
      </div>
    `;

    /* Work gathered */
    html += `
      <div class="card">
        <div class="card-head">Work Already Gathered (passed to caseworker)</div>
        <div class="card-body"><pre>${esc(h.work_already_done)}</pre></div>
      </div>
    `;

    /* Next step */
    html += `
      <div class="alert green">
        <div class="alert-title">Next Step</div>
        <div class="alert-body">Human caseworker handles this referral. Work above has been preserved so the caseworker does not repeat it (ACA-2026/2 §3.2).</div>
      </div>
    `;
  }

  /* ── RESTRICTED / AMBIGUOUS ────────────────────────── */
  if(r.verdict==='RESTRICTED' || r.verdict==='AMBIGUOUS_ESCALATE'){
    const acol = r.verdict==='RESTRICTED' ? 'red' : 'amber';
    const secs = esc_rec ? esc_rec.triggered_sections.map(s=>'§'+s).join(', ') : '';
    html += `
      <div class="alert ${acol}">
        <div class="alert-title">${r.verdict==='RESTRICTED'?'🔒 Action Blocked':'⚠ Ambiguous — Escalated'} ${secs ? '— '+secs : ''}</div>
        <div class="alert-body">${esc((esc_rec||{}).reasoning||'')}</div>
      </div>
    `;
    if(appr){
      html += `<div class="approval">⏳ ${appr.status.replace('_',' ')}</div>`;
    }
    if(esc_rec){
      const tags = esc_rec.triggered_sections.map(s=>`<span class="ptag">§${esc(s)}</span>`).join('');
      html += `
        <div class="card">
          <div class="card-head">Policy Sections</div>
          <div class="card-body"><div class="policy-tags">${tags}</div></div>
        </div>
      `;
    }
  }

  /* ── PERMITTED ─────────────────────────────────────── */
  if(r.verdict==='PERMITTED'){
    html += `
      <div class="alert green">
        <div class="alert-title">✓ Action Permitted — within §2</div>
        <div class="alert-body">Triage note has been drafted for caseworker review.</div>
      </div>
    `;
  }

  /* Triage note sections (only if present) */
  if(tn){
    if(tn.situation_summary){
      html += `<div class="card"><div class="card-head">Situation</div><div class="card-body"><pre>${esc(tn.situation_summary)}</pre></div></div>`;
    }
    if(tn.referral_context){
      html += `<div class="card"><div class="card-head">Referral</div><div class="card-body"><pre>${esc(tn.referral_context)}</pre></div></div>`;
    }
    if(tn.relevant_history){
      html += `<div class="card"><div class="card-head">Relevant History</div><div class="card-body"><pre>${esc(tn.relevant_history)}</pre></div></div>`;
    }
    if(tn.recommended_next_steps){
      html += `<div class="card"><div class="card-head">Recommended Next Steps</div><div class="card-body"><pre>${esc(tn.recommended_next_steps)}</pre></div></div>`;
    }
  }

  /* Escalation context */
  if(esc_rec && esc_rec.context_summary){
    html += `<div class="card"><div class="card-head">Supervisor Context</div><div class="card-body"><pre>${esc(esc_rec.context_summary)}</pre></div></div>`;
  }

  /* Execution trace */
  if(steps.length){
    const rows = steps.map(t=>`
      <div class="trow ${tclass(t.step)}">
        <span class="step-name">${esc(t.step)}</span>
        <span class="step-detail">— ${esc(t.detail)}</span>
        <span class="step-ts">${t.timestamp}</span>
      </div>
    `).join('');
    html += `
      <div class="card">
        <div class="card-head">Execution Trace</div>
        <div class="card-body"><div class="timeline">${rows}</div></div>
      </div>
    `;
  }

  document.getElementById('detail').innerHTML = html;
  document.getElementById('detail').scrollTop = 0;
}
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = build_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        print(f"  [dashboard] {fmt % args}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()

    if not os.path.exists(os.path.join(OUTPUT, "results.json")):
        print("No output files found. Run the agent first:")
        print("  python agent.py")
        sys.exit(1)

    print(f"Dashboard → http://127.0.0.1:{args.port}")
    print("Press Ctrl+C to stop.\n")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
