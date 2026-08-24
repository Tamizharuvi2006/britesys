#!/usr/bin/env python3
"""
Calder County — Caseworker's Morning Dashboard
Professional Light-Theme Case Management Interface
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

DASH_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(DASH_DIR)
OUTPUT = os.path.join(REPO_ROOT, "output")
DATA_DIR = os.path.join(REPO_ROOT, "data")
SERVICES_DIR = os.path.join(REPO_ROOT, "services")


def load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def build_html():
    results = load_json(os.path.join(OUTPUT, "results.json")) or []
    trace = load_json(os.path.join(OUTPUT, "trace.json")) or []
    queue = load_json(os.path.join(DATA_DIR, "referral-queue.json")) or []
    history_data = load_json(os.path.join(SERVICES_DIR, "_history_data.json")) or {}

    total = len(results)
    permitted = sum(1 for r in results if r.get("verdict") == "PERMITTED")
    restricted = sum(1 for r in results if r.get("verdict") == "RESTRICTED")
    ambiguous = sum(1 for r in results if r.get("verdict") == "AMBIGUOUS_ESCALATE")
    handoffs = sum(1 for r in results if r.get("verdict") == "CHILD_HANDOFF")
    needs_action = restricted + ambiguous + handoffs

    run_ts = trace[0]["timestamp"] if trace else ""

    # Map queue by referral_id
    queue_map = {q.get("referral_id"): q for q in queue}

    # Enrich results with queue & history information for complete case-management views
    enriched_results = []
    for r in results:
        rid = r.get("referral_id")
        rref = r.get("resident_ref")
        q_item = queue_map.get(rid, {})
        h_item = history_data.get(rref, {})

        enriched = dict(r)
        enriched["queue_meta"] = q_item
        enriched["history_meta"] = {
            "status": h_item.get("status", "Unknown"),
            "benefit_code": h_item.get("benefit_code", "N/A"),
            "district": h_item.get("district", "N/A"),
            "award_monthly": h_item.get("award_monthly", 0.0),
            "household": h_item.get("household", []),
            "events_count": len(h_item.get("events", [])),
            "events": h_item.get("events", []),
        }
        enriched_results.append(enriched)

    payload = json.dumps({
        "results": enriched_results,
        "trace": trace,
        "stats": {
            "total": total,
            "permitted": permitted,
            "restricted": restricted,
            "ambiguous": ambiguous,
            "handoffs": handoffs,
            "needs_action": needs_action,
        },
        "run_ts": run_ts,
    }, ensure_ascii=False)

    return HTML_TEMPLATE.replace("__DATA__", payload)


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Caseworker's Morning — Calder County</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
/* ── Reset & Global ──────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:          #F7F8FA;
  --surface:     #FFFFFF;
  --surface-sub: #F9FAFB;
  --border:      #E4E7EC;
  --border-sub:  #F2F4F7;

  --text-main:   #172033;
  --text-body:   #344054;
  --text-muted:  #667085;
  --text-sub:    #98A2B3;

  --primary:     #3157A6;
  --primary-bg:  #EEF4FF;
  --primary-bdr: #C7D7FE;

  --green:       #16845B;
  --green-bg:    #F0FDF4;
  --green-bdr:   #BBF7D0;

  --red:         #C93636;
  --red-bg:      #FEF2F2;
  --red-bdr:     #FECACA;

  --amber:       #B7791F;
  --amber-bg:    #FFFBEB;
  --amber-bdr:   #FDE68A;

  --violet:      #7057C8;
  --violet-bg:   #F5F3FF;
  --violet-bdr:  #DDD6FE;

  --radius:      8px;
  --radius-sm:   6px;
  --shadow-sm:   0 1px 2px rgba(16, 24, 40, 0.04);
}

body {
  font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg);
  color: var(--text-main);
  height: 100vh;
  overflow: hidden;
  font-size: 13.5px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

/* ── Scrollbars ─────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #D0D5DD; border-radius: 3px; }

/* ── App Shell ──────────────────────────────────────────── */
.app-shell {
  display: grid;
  grid-template-rows: 56px auto 1fr;
  height: 100vh;
  overflow: hidden;
}

/* ── Top Header ─────────────────────────────────────────── */
.app-header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.header-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-icon {
  width: 32px;
  height: 32px;
  background: var(--primary-bg);
  border: 1px solid var(--primary-bdr);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
}
.header-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-main);
  letter-spacing: -0.2px;
}
.header-sub {
  font-size: 12px;
  color: var(--text-muted);
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}
.header-run {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
}
.btn-refresh {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 500;
  font-family: inherit;
  color: var(--text-body);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  transition: all 0.15s ease;
}
.btn-refresh:hover {
  background: var(--surface-sub);
  color: var(--text-main);
  border-color: #D0D5DD;
}

/* ── Summary Stat Bar ───────────────────────────────────── */
.summary-bar {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 10px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.stat-cards-group {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 7px 14px;
  min-width: 125px;
  box-shadow: var(--shadow-sm);
  display: flex;
  align-items: center;
  gap: 10px;
}
.stat-card-icon {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
}
.stat-card-icon.neutral { background: var(--border-sub); color: var(--text-muted); }
.stat-card-icon.green   { background: var(--green-bg); color: var(--green); }
.stat-card-icon.red     { background: var(--red-bg); color: var(--red); }
.stat-card-icon.violet  { background: var(--violet-bg); color: var(--violet); }

.stat-card-data { display: flex; flex-direction: column; }
.stat-card-val {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-main);
  line-height: 1.1;
}
.stat-card-lbl {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 500;
  margin-top: 1px;
}

.attention-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  background: var(--amber-bg);
  border: 1px solid var(--amber-bdr);
  color: var(--amber);
  font-size: 12px;
  font-weight: 600;
  border-radius: 20px;
  white-space: nowrap;
}

/* ── Main Workspace Layout ──────────────────────────────── */
.workspace {
  display: grid;
  grid-template-columns: 320px 1fr;
  overflow: hidden;
  height: 100%;
}

/* ── Left Referral Queue ────────────────────────────────── */
.queue-panel {
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}
.queue-header-area {
  padding: 12px 14px 8px;
  border-bottom: 1px solid var(--border-sub);
}
.queue-heading {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

/* Filter Tabs */
.filter-tabs {
  display: flex;
  background: var(--border-sub);
  padding: 2px;
  border-radius: var(--radius-sm);
  gap: 2px;
}
.filter-tab {
  flex: 1;
  border: none;
  background: transparent;
  padding: 5px 4px;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-muted);
  border-radius: 4px;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.12s ease;
}
.filter-tab:hover {
  color: var(--text-main);
}
.filter-tab.active {
  background: var(--surface);
  color: var(--primary);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.06);
}

/* Queue Item List */
.queue-items {
  overflow-y: auto;
  flex: 1;
}
.queue-row {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-sub);
  cursor: pointer;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  border-left: 3px solid transparent;
  transition: background 0.12s ease, border-color 0.12s ease;
}
.queue-row:hover {
  background: var(--bg);
}
.queue-row.selected {
  background: #EEF4FF;
  border-left: 3px solid #3157A6;
}
.queue-row.selected .row-id {
  color: #3157A6;
}
.queue-row.hidden {
  display: none;
}

.row-status-icon {
  width: 22px;
  height: 22px;
  border-radius: 5px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
}
.row-status-icon.green  { background: var(--green-bg); color: var(--green); }
.row-status-icon.red    { background: var(--red-bg); color: var(--red); }
.row-status-icon.amber  { background: var(--amber-bg); color: var(--amber); }
.row-status-icon.violet { background: var(--violet-bg); color: var(--violet); }

.row-content {
  flex: 1;
  min-width: 0;
}
.row-id-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.row-id {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-main);
}
.row-action {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 1px;
}
.row-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  font-weight: 500;
  padding: 1px 6px;
  border-radius: 10px;
  margin-top: 3px;
  border: 1px solid transparent;
}
.row-tag.green  { background: var(--green-bg); border-color: var(--green-bdr); color: var(--green); }
.row-tag.red    { background: var(--red-bg); border-color: var(--red-bdr); color: var(--red); }
.row-tag.amber  { background: var(--amber-bg); border-color: var(--amber-bdr); color: var(--amber); }
.row-tag.violet { background: var(--violet-bg); border-color: var(--violet-bdr); color: var(--violet); }

/* ── Right Selected Case Detail Area ────────────────────── */
.detail-panel {
  overflow-y: auto;
  padding: 20px 28px;
  background: var(--bg);
}

.empty-placeholder {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-sub);
}
.empty-placeholder svg {
  opacity: 0.5;
}

/* Selected Case Header */
.case-header-block {
  margin-bottom: 14px;
}
.case-meta-line {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 3px;
}
.case-meta-line strong {
  color: var(--text-main);
  font-weight: 600;
}
.case-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-main);
  letter-spacing: -0.3px;
}
.case-subtitle {
  font-size: 12.5px;
  color: var(--text-muted);
  margin-top: 1px;
}

/* Semantic Decision Banner */
.decision-banner {
  border-radius: var(--radius);
  border: 1px solid;
  padding: 14px 18px;
  margin-bottom: 14px;
  box-shadow: var(--shadow-sm);
}
.decision-banner.green  { background: var(--green-bg); border-color: var(--green-bdr); }
.decision-banner.red    { background: var(--red-bg); border-color: var(--red-bdr); }
.decision-banner.amber  { background: var(--amber-bg); border-color: var(--amber-bdr); }
.decision-banner.violet { background: var(--violet-bg); border-color: var(--violet-bdr); }

.banner-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.banner-heading-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
}
.decision-banner.green  .banner-heading-wrap { color: var(--green); }
.decision-banner.red    .banner-heading-wrap { color: var(--red); }
.decision-banner.amber  .banner-heading-wrap { color: var(--amber); }
.decision-banner.violet .banner-heading-wrap { color: var(--violet); }

.banner-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 16px;
  background: var(--surface);
  border: 1px solid;
}
.decision-banner.green  .banner-badge { color: var(--green); border-color: var(--green-bdr); }
.decision-banner.red    .banner-badge { color: var(--red); border-color: var(--red-bdr); }
.decision-banner.amber  .banner-badge { color: var(--amber); border-color: var(--amber-bdr); }
.decision-banner.violet .banner-badge { color: var(--violet); border-color: var(--violet-bdr); }

.banner-message {
  font-size: 13.5px;
  color: var(--text-body);
  line-height: 1.5;
}
.banner-action-bar {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.badge-no-action {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-main);
  background: var(--surface);
  padding: 3px 9px;
  border-radius: 4px;
  border: 1px solid #D0D5DD;
}

/* Policy Chips with [ §X.X ] Section Tags */
.policy-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  font-weight: 500;
  padding: 3px 9px;
  border-radius: 4px;
  background: var(--surface);
  border: 1px solid;
}
.policy-chip.red   { color: var(--red); border-color: var(--red-bdr); }
.policy-chip.amber { color: var(--amber); border-color: var(--amber-bdr); }
.sec-tag {
  font-weight: 700;
  font-size: 11px;
  padding: 1px 4px;
  border-radius: 3px;
}
.policy-chip.red .sec-tag   { background: var(--red-bg); color: var(--red); }
.policy-chip.amber .sec-tag { background: var(--amber-bg); color: var(--amber); }

/* ── 3-Card Information Grid (Compact) ──────────────────── */
.info-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}
@media (max-width: 1050px) {
  .info-grid { grid-template-columns: 1fr; }
}

.clean-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}
.clean-card-header {
  padding: 8px 12px;
  background: var(--surface-sub);
  border-bottom: 1px solid var(--border);
  font-size: 10.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 6px;
}
.clean-card-body {
  padding: 10px 12px;
}

/* Key-Value Pair Layout */
.kv-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.kv-item {
  display: flex;
  flex-direction: column;
}
.kv-label {
  font-size: 10px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--text-muted);
}
.kv-value {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-main);
  margin-top: 1px;
}
.kv-value.muted {
  font-weight: 400;
  color: var(--text-body);
}

/* ── Decision & Authority Highlight Section ─────────────── */
.action-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 14px;
}
@media (max-width: 900px) {
  .action-grid { grid-template-columns: 1fr; }
}

.authority-highlight-card {
  border-left: 3px solid var(--primary);
}
.guardrail-box {
  background: var(--surface-sub);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  margin-top: 6px;
}
.guardrail-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-muted);
}
.guardrail-statement {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-main);
  margin-top: 1px;
}

/* Steps List */
.steps-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.step-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12px;
  color: var(--text-body);
}
.step-num {
  width: 17px;
  height: 17px;
  border-radius: 50%;
  background: var(--border-sub);
  border: 1px solid var(--border);
  color: var(--text-main);
  font-size: 10.5px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
}

/* Work Gathered Checklist */
.checklist-box {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 8px;
}
.checklist-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-body);
}
.check-bullet {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.check-bullet.ok  { background: var(--green-bg); color: var(--green); }
.check-bullet.no  { background: var(--red-bg); color: var(--red); }
.check-bullet.lav { background: var(--violet-bg); color: var(--violet); }

/* Formatted Context Box */
.context-box-text {
  font-family: inherit;
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-body);
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--surface-sub);
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
}

/* ── Execution History Timeline ─────────────────────────── */
.trace-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  margin-bottom: 14px;
  overflow: hidden;
}
.trace-card-header {
  padding: 8px 14px;
  background: var(--surface-sub);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.trace-heading {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 6px;
}
.btn-trace-toggle {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 2px 7px;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.btn-trace-toggle:hover {
  background: var(--surface);
  color: var(--text-main);
}

.timeline-body {
  padding: 12px 16px;
  position: relative;
}
.audit-timeline {
  position: relative;
  padding-left: 24px;
}
.audit-timeline::before {
  content: '';
  position: absolute;
  left: 8px;
  top: 8px;
  bottom: 8px;
  width: 1px;
  background: var(--border);
}
.tl-item {
  position: relative;
  padding: 5px 0 5px 10px;
}
.tl-node {
  position: absolute;
  left: -20px;
  top: 8px;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: var(--surface);
  border: 2px solid var(--border);
}
.tl-node.read    { border-color: var(--primary); background: var(--primary-bg); }
.tl-node.ok      { border-color: var(--green); background: var(--green-bg); }
.tl-node.blocked { border-color: var(--red); background: var(--red-bg); }
.tl-node.warn    { border-color: var(--amber); background: var(--amber-bg); }
.tl-node.handoff { border-color: var(--violet); background: var(--violet-bg); }
.tl-node.cont    { border-color: var(--text-sub); }

.tl-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.tl-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-main);
}
.tl-timestamp {
  font-size: 10.5px;
  color: var(--text-sub);
  font-variant-numeric: tabular-nums;
}
.tl-desc {
  font-size: 11.5px;
  color: var(--text-muted);
  margin-top: 1px;
}

.json-trace-drawer {
  display: none;
  background: #111827;
  color: #F3F4F6;
  font-family: monospace;
  font-size: 11px;
  padding: 10px 14px;
  max-height: 220px;
  overflow-y: auto;
  border-top: 1px solid var(--border);
}
.json-trace-drawer.open {
  display: block;
}
</style>
</head>
<body>
<div class="app-shell">

  <!-- ── Top Header ──────────────────────────────────────── -->
  <header class="app-header">
    <div class="header-brand">
      <div class="header-icon" id="brand-icon"></div>
      <div>
        <div class="header-title">Caseworker's Morning</div>
        <div class="header-sub">Calder County — Department of Household Services</div>
      </div>
    </div>
    <div class="header-actions">
      <div class="header-run" id="header-run-ts">
        <span id="clock-icon"></span>
        <span id="run-ts-text">—</span>
      </div>
      <button class="btn-refresh" onclick="location.reload()">
        <span id="refresh-icon"></span>
        <span>Refresh</span>
      </button>
    </div>
  </header>

  <!-- ── Summary Bar ──────────────────────────────────────── -->
  <section class="summary-bar">
    <div class="stat-cards-group" id="stat-cards"></div>
    <div class="attention-badge" id="attention-badge" style="display:none">
      <span id="attention-icon"></span>
      <span id="attention-text">9 cases require human attention</span>
    </div>
  </section>

  <!-- ── Main Workspace ──────────────────────────────────── -->
  <div class="workspace">

    <!-- Left Queue -->
    <aside class="queue-panel">
      <div class="queue-header-area">
        <div class="queue-heading">Referral Queue</div>
        <div class="filter-tabs" id="filter-tabs">
          <button class="filter-tab active" data-filter="action">Needs action</button>
          <button class="filter-tab" data-filter="all">All</button>
          <button class="filter-tab" data-filter="done">Completed</button>
          <button class="filter-tab" data-filter="hand">Handoff</button>
        </div>
      </div>
      <div class="queue-items" id="queue-list"></div>
    </aside>

    <!-- Right Detail -->
    <main class="detail-panel" id="detail-panel">
      <div class="empty-placeholder">
        <div id="placeholder-icon"></div>
        <p>Select a referral from the queue to view case details</p>
      </div>
    </main>

  </div>
</div>

<script>
const D = __DATA__;

/* ── Inline Lucide SVG Generator ─────────────────────────── */
const SVG_DEFS = {
  'scale': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/></svg>',
  'clock-3': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16.5 12"/></svg>',
  'refresh-cw': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/></svg>',
  'inbox': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg>',
  'circle-check': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>',
  'shield-alert': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="M12 8v4"/><path d="M12 16h.01"/></svg>',
  'shield-check': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/></svg>',
  'triangle-alert': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/></svg>',
  'user-round-check': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 21a8 8 0 0 1 13.292-6"/><circle cx="10" cy="8" r="5"/><path d="m16 19 2 2 4-4"/></svg>',
  'user-round': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/></svg>',
  'user': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
  'layers': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>',
  'file-text': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/></svg>',
  'history': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/></svg>',
  'arrow-up-right': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/></svg>',
  'arrow-right': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>',
  'chevron-right': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6"/></svg>',
  'chevron-down': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>',
  'check': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>',
  'x': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
  'code': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
  'folder-check': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/><path d="m9 13 2 2 4-4"/></svg>',
  'user-check': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><polyline points="16 11 18 13 22 9"/></svg>',
};

function ic(name, size=13, className='') {
  const svg = SVG_DEFS[name] || SVG_DEFS['file-text'];
  return svg.replace('<svg', `<svg width="${size}" height="${size}" class="${className}" style="display:inline-block;vertical-align:middle;flex-shrink:0;"`);
}

/* ── Formatting Utilities ────────────────────────────────── */
const esc = s => String(s ?? '')
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;');

function formatTime(isoStr) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return isoStr;
  }
}

function formatDate(isoStr) {
  if (!isoStr) return '—';
  try {
    const d = new Date(isoStr);
    return d.toLocaleString([], {
      day: 'numeric', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  } catch {
    return isoStr;
  }
}

function getVerdictInfo(verdict) {
  switch(verdict) {
    case 'PERMITTED':
      return { label: 'Completed', color: 'green', icon: 'circle-check' };
    case 'RESTRICTED':
      return { label: 'Restricted', color: 'red', icon: 'shield-alert' };
    case 'AMBIGUOUS_ESCALATE':
      return { label: 'Needs review', color: 'amber', icon: 'triangle-alert' };
    case 'CHILD_HANDOFF':
      return { label: 'Handoff', color: 'violet', icon: 'user-round-check' };
    default:
      return { label: verdict, color: 'amber', icon: 'file-text' };
  }
}

/* ── Render Header & Summary Elements ─────────────────────── */
document.getElementById('brand-icon').innerHTML = ic('scale', 18);
document.getElementById('clock-icon').innerHTML = ic('clock-3', 13);
document.getElementById('refresh-icon').innerHTML = ic('refresh-cw', 12);
document.getElementById('attention-icon').innerHTML = ic('triangle-alert', 13);
document.getElementById('placeholder-icon').innerHTML = ic('file-text', 40);

const stats = D.stats || {};
document.getElementById('stat-cards').innerHTML = `
  <div class="stat-card">
    <div class="stat-card-icon neutral">${ic('inbox', 14)}</div>
    <div class="stat-card-data">
      <div class="stat-card-val">${stats.total || 0}</div>
      <div class="stat-card-lbl">Total referrals</div>
    </div>
  </div>
  <div class="stat-card">
    <div class="stat-card-icon green">${ic('circle-check', 14)}</div>
    <div class="stat-card-data">
      <div class="stat-card-val" style="color:var(--green)">${stats.permitted || 0}</div>
      <div class="stat-card-lbl">Completed</div>
    </div>
  </div>
  <div class="stat-card">
    <div class="stat-card-icon red">${ic('shield-alert', 14)}</div>
    <div class="stat-card-data">
      <div class="stat-card-val" style="color:var(--red)">${stats.restricted || 0}</div>
      <div class="stat-card-lbl">Restricted</div>
    </div>
  </div>
  <div class="stat-card">
    <div class="stat-card-icon violet">${ic('user-round-check', 14)}</div>
    <div class="stat-card-data">
      <div class="stat-card-val" style="color:var(--violet)">${stats.handoffs || 0}</div>
      <div class="stat-card-lbl">Human handoff</div>
    </div>
  </div>
`;

if (D.run_ts) {
  document.getElementById('run-ts-text').textContent = 'Last run ' + formatDate(D.run_ts);
}

if (stats.needs_action > 0) {
  const badge = document.getElementById('attention-badge');
  document.getElementById('attention-text').textContent = `${stats.needs_action} cases require human attention`;
  badge.style.display = 'inline-flex';
}

/* ── Trace Mapping ───────────────────────────────────────── */
const traceMap = {};
(D.trace || []).forEach(t => {
  const rid = t.referral_id;
  if (!traceMap[rid]) traceMap[rid] = [];
  traceMap[rid].push(t);
});

/* ── Queue Population ────────────────────────────────────── */
const qListEl = document.getElementById('queue-list');
let currentSelectedIndex = -1;

D.results.forEach((r, i) => {
  const vInfo = getVerdictInfo(r.verdict);
  const qMeta = r.queue_meta || {};
  const actionText = qMeta.requested_action || r.handoff?.requested_action || r.escalation?.requested_action || 'Review referral';

  let filterClasses = [];
  if (r.verdict === 'PERMITTED') filterClasses.push('f-done');
  if (r.verdict === 'CHILD_HANDOFF') { filterClasses.push('f-hand'); filterClasses.push('f-action'); }
  if (r.verdict === 'RESTRICTED' || r.verdict === 'AMBIGUOUS_ESCALATE') filterClasses.push('f-action');

  const row = document.createElement('div');
  row.className = `queue-row ${filterClasses.join(' ')}`;
  row.dataset.idx = i;
  row.innerHTML = `
    <div class="row-status-icon ${vInfo.color}">
      ${ic(vInfo.icon, 13)}
    </div>
    <div class="row-content">
      <div class="row-id-line">
        <span class="row-id">${esc(r.referral_id)}</span>
      </div>
      <div class="row-action">${esc(actionText)}</div>
      <span class="row-tag ${vInfo.color}">${esc(vInfo.label)}</span>
    </div>
  `;
  row.addEventListener('click', () => selectReferral(i));
  qListEl.appendChild(row);
});

/* ── Filter Tab Handling ─────────────────────────────────── */
document.querySelectorAll('.filter-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const f = tab.dataset.filter;

    document.querySelectorAll('.queue-row').forEach(row => {
      if (f === 'all') {
        row.classList.remove('hidden');
      } else if (f === 'action') {
        row.classList.toggle('hidden', !row.classList.contains('f-action'));
      } else if (f === 'done') {
        row.classList.toggle('hidden', !row.classList.contains('f-done'));
      } else if (f === 'hand') {
        row.classList.toggle('hidden', !row.classList.contains('f-hand'));
      }
    });

    // If current selected item is hidden, select first visible
    const visible = document.querySelector('.queue-row:not(.hidden)');
    if (visible) {
      const idx = parseInt(visible.dataset.idx, 10);
      selectReferral(idx);
    }
  });
});

/* ── Audit Step Meta ─────────────────────────────────────── */
const STEP_META = {
  referral_read:          { label: 'Referral received', icon: 'file-text', node: 'read' },
  history_fetched:        { label: 'Resident history retrieved', icon: 'history', node: 'ok' },
  policy_evaluated:       { label: 'Authority policy evaluated', icon: 'shield-check', node: 'ok' },
  triage_drafted:         { label: 'Triage note drafted', icon: 'file-text', node: 'ok' },
  action_permitted:       { label: 'Action permitted (§2)', icon: 'circle-check', node: 'ok' },
  action_blocked:         { label: 'Action blocked (not permitted)', icon: 'shield-alert', node: 'blocked' },
  escalation_created:     { label: 'Escalation record created', icon: 'triangle-alert', node: 'blocked' },
  approval_requested:     { label: 'Approval requested', icon: 'clock-3', node: 'warn' },
  child_handoff_detected: { label: 'Child household detected (§3.9)', icon: 'user-round-check', node: 'handoff' },
  handoff_created:        { label: 'Handoff record created', icon: 'user-round-check', node: 'handoff' },
  processing_continued:   { label: 'Processing continued', icon: 'arrow-right', node: 'cont' },
  error:                  { label: 'Error occurred', icon: 'shield-alert', node: 'blocked' }
};

const POLICY_TITLES = {
  '3.1': 'Entitlement & award changes',
  '3.2': 'Award changes & suspensions',
  '3.3': 'Payment alterations',
  '3.4': 'Bank & payment details',
  '3.5': 'Third-party communications',
  '3.6': 'Benefit code alterations',
  '3.7': 'Findings of fact / fraud',
  '3.8': 'Case closure without review',
  '3.9': 'Child household safeguarding',
  '6.1': 'Unclear / Ambiguous authority'
};

/* ── Render Selected Referral Detail ─────────────────────── */
function selectReferral(idx) {
  currentSelectedIndex = idx;
  document.querySelectorAll('.queue-row').forEach(row => {
    row.classList.toggle('selected', parseInt(row.dataset.idx, 10) === idx);
  });

  const r = D.results[idx];
  if (!r) return;

  const q = r.queue_meta || {};
  const h = r.history_meta || {};
  const vInfo = getVerdictInfo(r.verdict);
  const actionText = q.requested_action || r.handoff?.requested_action || r.escalation?.requested_action || 'Review referral';

  // Find applicant name
  const household = h.household || [];
  const applicant = household.find(m => (m.relationship || '').toLowerCase().includes('applicant')) || household[0] || {};
  const applicantName = applicant.name || 'Resident';

  let html = '';

  /* 1. Header */
  html += `
    <div class="case-header-block">
      <div class="case-meta-line">
        <strong>${esc(r.referral_id)}</strong>
        <span>·</span>
        <span>${esc(r.resident_ref)}</span>
        <span>·</span>
        <span>Urgency: <strong>${esc(q.urgency || 'Standard')}</strong></span>
      </div>
      <div class="case-title">${esc(actionText)}</div>
      <div class="case-subtitle">Resident: ${esc(applicantName)} (${esc(r.resident_ref)}) · District: ${esc(h.district || 'N/A')}</div>
    </div>
  `;

  /* 2. Semantic Decision Banner (Clean, Professional & Scannable) */
  if (r.verdict === 'AMBIGUOUS_ESCALATE') {
    html += `
      <div class="decision-banner amber">
        <div class="banner-top">
          <div class="banner-heading-wrap">
            ${ic('triangle-alert', 16)}
            <span>Needs supervisor review</span>
          </div>
          <span class="banner-badge">Ambiguous · Escalated</span>
        </div>
        <div class="banner-message">
          Action "${esc(actionText)}" is not explicitly permitted under §2. Per §6.1, unclear actions are treated as though they fall within §3.
        </div>
        <div class="banner-action-bar">
          <span class="badge-no-action">The agent did not perform the action.</span>
          <span class="policy-chip amber">${ic('clock-3', 11)} <span>Pending approval</span></span>
          <span class="policy-chip amber"><span class="sec-tag">[ §6.1 ]</span> <span>Unclear / Ambiguous authority</span></span>
        </div>
        ${r.escalation?.reasoning ? `
          <div style="margin-top:10px;">
            <button style="background:transparent;border:none;color:var(--amber);font-size:11.5px;font-weight:600;cursor:pointer;padding:0;display:inline-flex;align-items:center;gap:4px;font-family:inherit;" onclick="const d=document.getElementById('why-blocked-${esc(r.referral_id)}');const isOp=d.style.display==='block';d.style.display=isOp?'none':'block';const ic=this.querySelector('.arrow-icon');if(ic)ic.style.transform=isOp?'':'rotate(90deg)';">
              <span class="arrow-icon" style="display:inline-flex;align-items:center;transition:transform .15s;">${ic('chevron-right', 12)}</span>
              <span>Why was this escalated?</span>
            </button>
            <div id="why-blocked-${esc(r.referral_id)}" style="display:none;margin-top:6px;padding:8px 10px;background:var(--surface);border-radius:4px;border:1px solid var(--amber-bdr);font-size:12px;color:var(--text-body);line-height:1.5;">
              ${esc(r.escalation.reasoning)}
            </div>
          </div>
        ` : ''}
      </div>
    `;
  } else if (r.verdict === 'RESTRICTED') {
    const sections = r.escalation?.triggered_sections || ['3.2'];
    html += `
      <div class="decision-banner red">
        <div class="banner-top">
          <div class="banner-heading-wrap">
            ${ic('shield-alert', 16)}
            <span>Action blocked</span>
          </div>
          <span class="banner-badge">Restricted · Approval Required</span>
        </div>
        <div class="banner-message">
          This action requires supervisor approval before it can proceed under authority policy.
        </div>
        <div class="banner-action-bar">
          <span class="badge-no-action">The agent did not perform the action.</span>
          <span class="policy-chip red">${ic('clock-3', 11)} <span>Pending approval</span></span>
          ${sections.map(s => `<span class="policy-chip red"><span class="sec-tag">[ §${esc(s)} ]</span> <span>${esc(POLICY_TITLES[s] || 'Policy restriction')}</span></span>`).join('')}
        </div>
        ${r.escalation?.reasoning ? `
          <div style="margin-top:10px;">
            <button style="background:transparent;border:none;color:var(--red);font-size:11.5px;font-weight:600;cursor:pointer;padding:0;display:inline-flex;align-items:center;gap:4px;font-family:inherit;" onclick="const d=document.getElementById('why-blocked-${esc(r.referral_id)}');const isOp=d.style.display==='block';d.style.display=isOp?'none':'block';const ic=this.querySelector('.arrow-icon');if(ic)ic.style.transform=isOp?'':'rotate(90deg)';">
              <span class="arrow-icon" style="display:inline-flex;align-items:center;transition:transform .15s;">${ic('chevron-right', 12)}</span>
              <span>Why was this blocked?</span>
            </button>
            <div id="why-blocked-${esc(r.referral_id)}" style="display:none;margin-top:6px;padding:8px 10px;background:var(--surface);border-radius:4px;border:1px solid var(--red-bdr);font-size:12px;color:var(--text-body);line-height:1.5;">
              ${esc(r.escalation.reasoning)}
            </div>
          </div>
        ` : ''}
      </div>
    `;
  } else if (r.verdict === 'CHILD_HANDOFF') {
    html += `
      <div class="decision-banner violet">
        <div class="banner-top">
          <div class="banner-heading-wrap">
            ${ic('user-round-check', 16)}
            <span>Human handoff required</span>
          </div>
          <span class="banner-badge">ACA-2026/2 §3.9 Safeguarding</span>
        </div>
        <div class="banner-message">
          Household includes a person under 18. Automated triage drafting is disabled for this referral under ACA-2026/2 §3.9. This is ordinary casework that a human caseworker must handle.
        </div>
        <div class="banner-action-bar">
          <span class="badge-no-action">Triage note: NOT GENERATED</span>
          <span class="badge-no-action">Next: Caseworker review</span>
        </div>
      </div>
    `;
  } else if (r.verdict === 'PERMITTED') {
    html += `
      <div class="decision-banner green">
        <div class="banner-top">
          <div class="banner-heading-wrap">
            ${ic('circle-check', 16)}
            <span>Action permitted — within §2</span>
          </div>
          <span class="banner-badge">Completed · Proposal Drafted</span>
        </div>
        <div class="banner-message">
          Action "${esc(actionText)}" falls within delegated assistant authority under §2. Automated triage draft prepared for caseworker review.
        </div>
      </div>
    `;
  }

  /* 3. 3-Card Information Grid (Resident | Situation | Referral) */
  html += `
    <div class="info-grid">
      <!-- RESIDENT -->
      <div class="clean-card">
        <div class="clean-card-header">
          ${ic('user-round', 12)}
          <span>Resident</span>
        </div>
        <div class="clean-card-body">
          <div class="kv-list">
            <div class="kv-item"><span class="kv-label">Name</span><span class="kv-value">${esc(applicantName)}</span></div>
            <div class="kv-item"><span class="kv-label">Resident ID</span><span class="kv-value">${esc(r.resident_ref)}</span></div>
            <div class="kv-item"><span class="kv-label">District</span><span class="kv-value">${esc(h.district || 'N/A')}</span></div>
            <div class="kv-item"><span class="kv-label">Status</span><span class="kv-value">${esc(h.status || 'Active')}</span></div>
          </div>
        </div>
      </div>

      <!-- SITUATION -->
      <div class="clean-card">
        <div class="clean-card-header">
          ${ic('layers', 12)}
          <span>Situation</span>
        </div>
        <div class="clean-card-body">
          <div class="kv-list">
            <div class="kv-item"><span class="kv-label">Benefit Code</span><span class="kv-value">${esc(h.benefit_code || 'N/A')}</span></div>
            <div class="kv-item"><span class="kv-label">Monthly Award</span><span class="kv-value">£${Number(h.award_monthly || 0).toFixed(2)}</span></div>
            <div class="kv-item"><span class="kv-label">Household Size</span><span class="kv-value">${household.length} member${household.length === 1 ? '' : 's'}</span></div>
            <div class="kv-item"><span class="kv-label">Case Events</span><span class="kv-value">${h.events_count || 0} on record</span></div>
          </div>
        </div>
      </div>

      <!-- REFERRAL -->
      <div class="clean-card">
        <div class="clean-card-header">
          ${ic('file-text', 12)}
          <span>Referral</span>
        </div>
        <div class="clean-card-body">
          <div class="kv-list">
            <div class="kv-item"><span class="kv-label">Received</span><span class="kv-value">${formatDate(q.received_at)}</span></div>
            <div class="kv-item"><span class="kv-label">Source</span><span class="kv-value">${esc(q.source || 'Direct')}</span></div>
            <div class="kv-item"><span class="kv-label">Urgency</span><span class="kv-value">${esc(q.urgency || 'Standard')}</span></div>
            <div class="kv-item"><span class="kv-label">Summary</span><span class="kv-value muted">${esc(q.summary || 'No summary provided.')}</span></div>
          </div>
        </div>
      </div>
    </div>
  `;

  /* Case History (Expandable Recent Events) */
  const events = h.events || [];
  if (events.length > 0) {
    html += `
      <div class="clean-card" style="margin-bottom:14px">
        <div class="clean-card-header" style="cursor:pointer;justify-content:space-between;user-select:none;" onclick="const el=document.getElementById('events-drawer-${esc(r.referral_id)}');const icon=this.querySelector('.toggle-icon');const isOpen=el.style.display==='block';el.style.display=isOpen?'none':'block';icon.style.transform=isOpen?'':'rotate(180deg)';">
          <span style="display:flex;align-items:center;gap:6px">
            ${ic('history', 12)}
            <span>Case History · ${events.length} Event${events.length === 1 ? '' : 's'} on Record</span>
          </span>
          <span style="display:flex;align-items:center;gap:4px;font-size:11px;color:var(--text-muted)">
            <span>View ${events.length} events</span>
            <span class="toggle-icon" style="display:inline-flex;align-items:center;transition:transform .2s">${ic('chevron-down', 12)}</span>
          </span>
        </div>
        <div id="events-drawer-${esc(r.referral_id)}" style="display:none;padding:8px 14px;background:var(--surface);border-top:1px solid var(--border);">
          <div style="display:flex;flex-direction:column;gap:4px;">
            ${events.map(e => `
              <div style="display:flex;align-items:baseline;gap:12px;padding:5px 0;border-bottom:1px solid var(--border-sub);font-size:12px;">
                <span style="font-variant-numeric:tabular-nums;color:var(--text-muted);font-weight:500;min-width:78px;flex-shrink:0;">${esc(e.date)}</span>
                <span style="font-weight:600;color:var(--text-main);min-width:140px;flex-shrink:0;">${esc(e.type)}</span>
                <span style="color:var(--text-body);flex:1;">${esc(e.detail)}</span>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;
  }

  /* 4. Decision & Authority Highlight Section */
  html += `<div class="action-grid">`;

  // Left: Decision & Authority Card
  let authorityHeaderColor = vInfo.color;
  let authorityVerdictText = vInfo.label.toUpperCase();
  let authorityStatusText = 'No supervisor approval needed';
  let guardrailText = 'Triage proposal generated for review';

  if (r.verdict === 'RESTRICTED') {
    const sec = r.escalation?.triggered_sections?.map(s => '§' + s).join(', ') || '§3';
    authorityStatusText = `Supervisor approval required (${sec})`;
    guardrailText = 'The agent did not perform the action.';
  } else if (r.verdict === 'AMBIGUOUS_ESCALATE') {
    authorityStatusText = 'Supervisor determination required (§6.1)';
    guardrailText = 'The agent did not perform the action.';
  } else if (r.verdict === 'CHILD_HANDOFF') {
    authorityStatusText = 'Human caseworker handoff required (§3.9)';
    guardrailText = 'Triage drafting prevented — no note generated.';
  }

  html += `
    <div class="clean-card authority-highlight-card">
      <div class="clean-card-header">
        <span style="display:inline-flex;color:var(--${authorityHeaderColor});">${ic('shield-check', 12)}</span>
        <span>Decision &amp; Authority</span>
      </div>
      <div class="clean-card-body">
        <div class="kv-list">
          <div class="kv-item">
            <span class="kv-label">Authority Determination</span>
            <span class="kv-value" style="color:var(--${authorityHeaderColor});font-size:13.5px;">${esc(authorityVerdictText)}</span>
          </div>
          <div class="kv-item">
            <span class="kv-label">Requirement</span>
            <span class="kv-value">${esc(authorityStatusText)}</span>
          </div>
          <div class="guardrail-box">
            <div class="guardrail-label">Execution Guardrail</div>
            <div class="guardrail-statement">${esc(guardrailText)}</div>
          </div>
        </div>
      </div>
    </div>
  `;

  // Right: Next Steps Card
  html += `
    <div class="clean-card">
      <div class="clean-card-header">
        ${ic('arrow-up-right', 12)}
        <span>Next Steps</span>
      </div>
      <div class="clean-card-body">
        <div class="steps-list">
  `;

  if (r.verdict === 'RESTRICTED' || r.verdict === 'AMBIGUOUS_ESCALATE') {
    html += `
      <div class="step-item"><span class="step-num">1</span><span>Escalated to supervisor for determination.</span></div>
      <div class="step-item"><span class="step-num">2</span><span>Do not act until supervisor approval is received.</span></div>
      <div class="step-item"><span class="step-num">3</span><span>Follow supervisor decision recorded in audit record.</span></div>
    `;
  } else if (r.verdict === 'CHILD_HANDOFF') {
    html += `
      <div class="step-item"><span class="step-num">1</span><span>Refer case directly to a human caseworker.</span></div>
      <div class="step-item"><span class="step-num">2</span><span>Review preserved resident history and safeguarding facts.</span></div>
      <div class="step-item"><span class="step-num">3</span><span>Caseworker conducts full manual assessment.</span></div>
    `;
  } else {
    html += `
      <div class="step-item"><span class="step-num">1</span><span>Caseworker reviews drafted triage proposal.</span></div>
      <div class="step-item"><span class="step-num">2</span><span>Verify resident history and factual situation.</span></div>
      <div class="step-item"><span class="step-num">3</span><span>Proceed with permitted administrative next steps.</span></div>
    `;
  }

  html += `
        </div>
      </div>
    </div>
  </div>
  `;

  /* 5. Specific Content Cards (Context / Triage Note / Work Gathered) */
  if (r.verdict === 'CHILD_HANDOFF' && r.handoff) {
    const minors = r.handoff.minors_identified || [];
    html += `
      <div class="clean-card" style="margin-bottom:14px">
        <div class="clean-card-header">
          <span style="display:inline-flex;color:var(--violet);">${ic('user-round-check', 12)}</span>
          <span>Child Safeguarding Review — Minors Identified</span>
        </div>
        <div class="clean-card-body">
          <div class="checklist-box">
            ${minors.map(m => `
              <div class="checklist-item">
                <div class="check-bullet lav">${ic('user', 10)}</div>
                <span><strong>${esc(m.name)}</strong> (${esc(m.relationship)}) — Age ${m.age_on_referral_date !== null ? m.age_on_referral_date : 'Under 18 (DOB ' + esc(m.date_of_birth) + ')'}</span>
              </div>
            `).join('')}
          </div>
          <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">
            Per ACA-2026/2 §5.1, child presence is determined from Department household records.
          </div>
        </div>
      </div>
    `;

    html += `
      <div class="clean-card" style="margin-bottom:14px">
        <div class="clean-card-header">
          ${ic('folder-check', 12)}
          <span>Work Gathered (Preserved for Caseworker per §3.2)</span>
        </div>
        <div class="clean-card-body">
          <div class="checklist-box">
            <div class="checklist-item"><div class="check-bullet ok">${ic('check', 10)}</div><span>Referral read &amp; logged</span></div>
            <div class="checklist-item"><div class="check-bullet ok">${ic('check', 10)}</div><span>Resident history retrieved from database</span></div>
            <div class="checklist-item"><div class="check-bullet ok">${ic('check', 10)}</div><span>Household composition verified</span></div>
            <div class="checklist-item"><div class="check-bullet no">${ic('x', 10)}</div><span>Triage note: NOT GENERATED (§2.2 ACA-2026/2 prohibits draft note)</span></div>
          </div>
          <div class="context-box-text" style="margin-top:8px">${esc(r.handoff.work_already_done)}</div>
        </div>
      </div>
    `;
  }

  if (r.escalation?.context_summary) {
    html += `
      <div class="clean-card" style="margin-bottom:14px">
        <div class="clean-card-header">
          ${ic('user-check', 12)}
          <span>Context for Supervisor Determination (§4.2)</span>
        </div>
        <div class="clean-card-body">
          <div class="context-box-text">${esc(r.escalation.context_summary)}</div>
        </div>
      </div>
    `;
  }

  if (r.triage_note) {
    const tn = r.triage_note;
    html += `
      <div class="clean-card" style="margin-bottom:14px">
        <div class="clean-card-header">
          ${ic('file-text', 12)}
          <span>Drafted Triage Proposal (§2.4 — Caseworker Review)</span>
        </div>
        <div class="clean-card-body">
          <div class="kv-list">
            ${tn.situation_summary ? `<div class="kv-item"><span class="kv-label">Situation Summary</span><div class="context-box-text">${esc(tn.situation_summary)}</div></div>` : ''}
            ${tn.referral_context ? `<div class="kv-item" style="margin-top:4px"><span class="kv-label">Referral Context</span><div class="context-box-text">${esc(tn.referral_context)}</div></div>` : ''}
            ${tn.relevant_history ? `<div class="kv-item" style="margin-top:4px"><span class="kv-label">Relevant History</span><div class="context-box-text">${esc(tn.relevant_history)}</div></div>` : ''}
            ${tn.recommended_next_steps ? `<div class="kv-item" style="margin-top:4px"><span class="kv-label">Recommended Next Steps</span><div class="context-box-text">${esc(tn.recommended_next_steps)}</div></div>` : ''}
          </div>
        </div>
      </div>
    `;
  }

  /* 6. Execution History / Audit Timeline */
  const steps = traceMap[r.referral_id] || [];
  if (steps.length > 0) {
    const timelineItems = steps.map(step => {
      const meta = STEP_META[step.step] || { label: step.step, icon: 'file-text', node: 'cont' };
      return `
        <div class="tl-item">
          <div class="tl-node ${meta.node}"></div>
          <div class="tl-header-row">
            <span class="tl-title">${esc(meta.label)}</span>
            <span class="tl-timestamp">${formatTime(step.timestamp)}</span>
          </div>
          <div class="tl-desc">${esc(step.detail)}</div>
        </div>
      `;
    }).join('');

    html += `
      <div class="trace-card">
        <div class="trace-card-header">
          <div class="trace-heading">
            ${ic('history', 12)}
            <span>Execution History</span>
          </div>
          <button class="btn-trace-toggle" onclick="document.getElementById('raw-trace-${esc(r.referral_id)}').classList.toggle('open')">
            ${ic('code', 11)}
            <span>View full trace</span>
          </button>
        </div>
        <div class="timeline-body">
          <div class="audit-timeline">
            ${timelineItems}
          </div>
        </div>
        <div class="json-trace-drawer" id="raw-trace-${esc(r.referral_id)}">
          <pre>${esc(JSON.stringify(steps, null, 2))}</pre>
        </div>
      </div>
    `;
  }

  const detailEl = document.getElementById('detail-panel');
  detailEl.innerHTML = html;
  detailEl.scrollTop = 0;
}

/* ── Initialize with First Actionable Referral ────────────── */
window.addEventListener('DOMContentLoaded', () => {
  // Default to first item matching 'Needs action' (or index 0)
  const defaultRow = document.querySelector('.queue-row.f-action') || document.querySelector('.queue-row');
  if (defaultRow) {
    selectReferral(parseInt(defaultRow.dataset.idx, 10));
  }
});
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
