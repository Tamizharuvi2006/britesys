# AI-USAGE.md

## Tools used

- **Claude (Anthropic)** — via Gemini IDE / Antigravity coding assistant

## What it was used for

- **Architecture and design discussion.** Used AI to discuss the problem, evaluate architectural options, and identify which referrals might trigger §3 restrictions. All decisions were reviewed and validated by hand against `authority-policy.md`.

- **Code scaffolding.** AI generated the initial structure of all Python modules (`models.py`, `config.py`, `history_client.py`, `policy_evaluator.py`, `triage.py`, `trace.py`, `agent.py`). Each file was reviewed, understood, and modified as needed.

- **Policy rule patterns.** AI helped draft `policy_rules.json` (the pattern-matching rules for §3 provisions). Every pattern was manually verified against the authority policy document to ensure correctness.

- **Triage note templates.** AI generated the template-based triage note structure in `triage.py`.

- **Debugging.** AI helped diagnose a Windows console Unicode encoding issue with emoji characters in output.

## What it was NOT used for

- No AI was used for the actual policy evaluation logic decisions — those are deterministic pattern matches against `policy_rules.json`.
- No LLM is used at runtime. The agent is fully deterministic with no AI inference calls.
- No AI-generated code was included without being read and understood first.
