# The Caseworker's Morning — Referral Triage Agent

> Problem 5 — Brite Spark 2026

An automated casework assistant that processes overnight referrals, fetches resident history, drafts triage notes, and **enforces authority policy with a structural hard gate** — the agent physically cannot perform restricted actions.

## Quick start

**Python 3 only. No dependencies. No install step.**

```bash
# 1. Start the History API
python services/history_service.py --port 8083

# 2. Run the agent (in another terminal)
python agent.py
```

That's it. Results appear in `output/`.

## What it does

1. **Reads** 12 overnight referrals from `referral-queue.json`
2. **Fetches** each resident's history from the History API
3. **Evaluates** every requested action against `authority-policy.md` (loaded as structured data from `policy_rules.json`)
4. **Drafts** a triage note for caseworker review (§2.4 — proposal only)
5. **Hard-blocks** any action that falls under §3 — the agent creates an escalation record and approval request but **cannot execute the action**
6. **Applies §6.1** — ambiguous actions are treated as restricted
7. **Continues processing** — escalating one referral never stops the rest (§4.3)
8. **Produces a full execution trace** — every step recorded per §5

## Output

All output goes to `output/`:

| File | What it contains |
|---|---|
| `results.json` | Processing result for every referral (triage note + escalation if applicable) |
| `escalations.json` | Only the escalated referrals with approval requests |
| `trace.json` | Full audit trace — every step, every decision, reconstructable per §5 |

## Architecture

```
agent.py              ← Orchestrator (entry point)
├── history_client.py ← HTTP client for History API
├── policy_evaluator.py ← Three-state evaluator (PERMITTED / RESTRICTED / AMBIGUOUS)
│   └── policy_rules.json ← Policy-as-data (editable, no code changes needed)
├── triage.py         ← Triage note generator (template-based)
├── trace.py          ← Audit trace logger (§5 compliant)
├── models.py         ← All domain dataclasses
└── config.py         ← Configuration (env var overrides)
```

**Key design:** Policy rules are loaded from `policy_rules.json`, not hardcoded. To change what requires approval, edit the JSON — no code changes needed.

## Project files

| File | Purpose |
|---|---|
| `PROBLEM.md` | Original problem statement |
| `authority-policy.md` | Authority policy ACA-2026/1 |
| `referral-queue.json` | The 12 overnight referrals |
| `services/history_service.py` | Resident History API (mock) |
| `services/_history_data.json` | History data for 12 residents |
| `DECISIONS.md` | Architectural decisions, trade-offs, cuts |
| `AI-USAGE.md` | AI tool usage disclosure |

## Configuration

All settings can be overridden via environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `HISTORY_API_BASE` | `http://127.0.0.1:8083` | History API URL |
| `HISTORY_API_TIMEOUT` | `10` | Request timeout (seconds) |
| `HISTORY_API_RETRIES` | `1` | Number of retries on failure |
| `OUTPUT_DIR` | `./output` | Output directory |

## Policy evaluation summary

The agent evaluates every referral against the authority policy. Current run:

| Verdict | Count | Meaning |
|---|---|---|
| ✓ PERMITTED | 6 | Action within §2 — triage note drafted |
| 🔒 RESTRICTED | 5 | Action matches §3 — hard blocked, escalated |
| ⚠ AMBIGUOUS | 1 | Not clearly §2 — treated as §3 per §6.1 |
