# The Caseworker's Morning — Referral Triage Agent

> Problem 5 — Brite Spark 2026

An automated casework assistant that processes overnight referrals, fetches resident history, enforces authority policy with a **structural hard gate**, and — after amendment ACA-2026/2 — detects child households and routes them to a human caseworker before any triage note is generated.

## Quick start

**Python 3 only. No dependencies. No install step.**

```bash
# 1. Start the History API
python services/history_service.py --port 8083

# 2. Run the agent (in another terminal)
python agent.py

# 3. Optional: view results in the dashboard
python dashboard.py
# → http://127.0.0.1:8080
```

Results appear in `output/` automatically.

## What it does

1. **Reads** 12 overnight referrals from `referral-queue.json`
2. **Fetches** each resident's history from the History API
3. **Checks household composition** — if any member is under 18, the referral is handed off to a human caseworker immediately, before any triage note is generated (ACA-2026/2 §3.9)
4. **Evaluates** every requested action against `authority-policy.md` (loaded as structured data from `policy_rules.json`)
5. **Drafts** a triage note for caseworker review (§2.4 — proposal only)
6. **Hard-blocks** any action that falls under §3 — the agent creates an escalation record and approval request but **cannot execute the action**
7. **Applies §6.1** — ambiguous actions are treated as restricted
8. **Continues processing** — one referral failing never stops the rest (§4.3)
9. **Produces a full execution trace** — every step recorded per §5

## Output

All output goes to `output/` (generated at runtime — not committed):

| File | What it contains |
|---|---|
| `results.json` | Processing result for every referral |
| `escalations.json` | §3 hard-block referrals with approval requests |
| `handoffs.json` | ACA-2026/2 §3.9 hand-offs — child households routed to caseworker |
| `trace.json` | Full audit trace — every step, every decision, reconstructable per §5 |

## Architecture

```
agent.py              ← Orchestrator + §3.9 CHILD_HANDOFF safeguarding gate
├── history_client.py ← HTTP client for History API (read-only)
├── policy_evaluator.py ← Policy evaluator (PERMITTED / RESTRICTED / AMBIGUOUS)
│   └── policy_rules.json ← Policy-as-data (editable, no code changes needed)
├── triage.py         ← Triage note generator (template-based, permitted §2 actions only)
├── trace.py          ← Audit trace logger (§5 compliant)
├── models.py         ← All domain dataclasses
├── config.py         ← Configuration (env var overrides)
└── dashboard.py      ← Lightweight read-only case-management dashboard
```

**Key design:** Policy rules are loaded from `policy_rules.json`, not hardcoded. §3.9 safeguarding is a factual household check, not a text pattern — it runs against the Department's data, not the referral wording (per ACA-2026/2 §5.1).

## Project files

| File | Purpose |
|---|---|
| `PROBLEM.md` | Original problem statement |
| `authority-policy.md` | Authority policy ACA-2026/1 |
| `referral-queue.json` | The 12 overnight referrals |
| `services/history_service.py` | Resident History API (mock) |
| `services/_history_data.json` | History data for 12 residents |
| `tests.py` | Test suite (37 tests, stdlib unittest) |
| `DECISIONS.md` | Architectural decisions, trade-offs, cuts, Day 2 rationale |
| `AI-USAGE.md` | AI tool usage disclosure |
| `dashboard.py` | Professional case-management viewer |

## Running the tests

```bash
python tests.py -v
# or
python -m pytest tests.py -v
```

37 tests covering: policy evaluation, structural hard gate, malformed input, failure isolation, trace integrity, §4.2 escalation compliance, and §3.9 child handoff (ACA-2026/2).

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `HISTORY_API_BASE` | `http://127.0.0.1:8083` | History API URL |
| `HISTORY_API_TIMEOUT` | `10` | Request timeout (seconds) |
| `HISTORY_API_RETRIES` | `1` | Number of retries on failure |
| `OUTPUT_DIR` | `./output` | Output directory |

## Policy evaluation — current run

| Verdict | Count | Meaning |
|---|---|---|
| ✓ PERMITTED | 3 | Action within §2 — triage note drafted |
| 🔒 RESTRICTED | 5 | Action matches §3 — hard blocked, escalated |
| ⚠ AMBIGUOUS | 1 | Not clearly §2 — treated as §3 per §6.1 |
| 👶 CHILD_HANDOFF | 3 | Household includes person under 18 — handed to caseworker (ACA-2026/2 §3.9) |
