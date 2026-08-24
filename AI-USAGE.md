# AI-USAGE.md

## Tools used

- **Claude (Anthropic)** — via Gemini IDE / Antigravity coding assistant

## What it was used for

### Day 1

- **Architecture and design discussion.** Used AI to discuss the problem, evaluate architectural options, and identify which referrals might trigger §3 restrictions. All decisions were reviewed and validated by hand against `authority-policy.md`.

- **Code scaffolding.** AI generated the initial structure of all Python modules (`models.py`, `config.py`, `history_client.py`, `policy_evaluator.py`, `triage.py`, `trace.py`, `agent.py`). Each file was reviewed, understood, and modified as needed.

- **Policy rule patterns.** AI helped draft `policy_rules.json` (the pattern-matching rules for §3 provisions). Every pattern was manually verified against the authority policy document to ensure correctness.

- **Triage note templates.** AI generated the template-based triage note structure in `triage.py`.

- **Debugging.** AI helped diagnose a Windows console Unicode encoding issue with emoji characters in output.

- **P1 robustness.** AI generated the per-referral failure isolation logic and the test suite (`tests.py`). All tests were reviewed and the test cases were verified against the spec.

### Day 2

- **Amendment analysis.** AI read ACA-2026/2, identified the 3 affected referrals by calculating ages from household DOB data, and explained the distinction between a hand-off (§3.9) and an escalation (§3–§4) that the amendment required.

- **§3.9 implementation.** AI generated the `check_for_minors()` function, `HandoffRecord` dataclass, `CHILD_HANDOFF` verdict, the safeguarding gate in `_process_referral_inner()`, new trace step methods, and the `handoffs.json` output. All code was reviewed against the amendment text before committing.

- **§3.9 tests.** AI generated 11 new tests covering boundary conditions (exactly 18, 17+1 day, unknown DOB), the no-triage-note guarantee, structural distinction from escalation, trace step verification, and actual output file validation. Each test was reviewed for correctness.

- **DECISIONS.md Day 2 entry.** AI drafted the rationale sections. Content was reviewed and reflects the actual implementation choices made.

## What it was NOT used for

- No AI was used for the actual policy evaluation logic decisions — those are deterministic pattern matches against `policy_rules.json`.
- No LLM is used at runtime. The agent is fully deterministic with no AI inference calls.
- No AI-generated code was included without being read and understood first.
- All policy/legal interpretation (which referrals trigger which sections, what the amendment means) was verified by hand against the source documents.
