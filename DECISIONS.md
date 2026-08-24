# DECISIONS.md

> What you chose, what you rejected, and why. What you cut for time. What your solution does not do. What you would fix first.

---

## Day 1

### Problem choice: Problem 5 — The Caseworker's Morning

Chose this because it's a workflow-engineering + policy-enforcement challenge, not a "throw an LLM at it" problem. The core difficulty is making sure the agent **cannot cross the authority boundary**, not generating fancy output.

---

### Architecture: Deterministic pipeline, no LLM

**Chose:** A deterministic, template-based pipeline with structured policy evaluation.

**Rejected:** LangChain / LangGraph / any agent framework. The problem explicitly says "sophisticated planning is not required" — the sequence is known. Adding a framework would introduce complexity without value and make the Day 2 change harder to absorb.

**Rejected (for now):** LLM-based triage note generation. The P0 requirement is a **correct, traceable, policy-compliant** workflow. An LLM can improve note quality later, but if the guardrails fail, nothing else matters.

**Why:** Python stdlib only (as specified). Clean-clone setup = `python agent.py`. No dependencies, no virtual environment, no install step.

---

### Policy-as-data (`policy_rules.json`)

**Chose:** Encode the authority policy as a structured JSON file that the evaluator reads at startup.

**Rejected:** Hardcoding policy checks into the agent logic.

**Why:** The problem tells us a Day 2 change is coming. If the change modifies the authority boundary (e.g., "action X now requires approval"), we want to update a data file, not rewrite the evaluator. This is the single most important architectural decision — it keeps policy separable from workflow.

---

### Three-state policy evaluator

**Chose:** `PERMITTED` / `RESTRICTED` / `AMBIGUOUS_ESCALATE`

**Rejected:** Binary permitted/restricted. 

**Why:** §6.1 says "where it is unclear whether an action falls within section 3, it is to be treated as though it does." A two-state model forces you to guess. A three-state model lets you be honest: "I'm not sure this is restricted, but the policy says to treat uncertainty as restriction." This is a better answer than pretending we know.

---

### Structural hard gate (not just logging)

**Chose:** The agent has **no code path** to execute §3 actions. It can only create `ApprovalRequest` objects. The block is architectural, not behavioral.

**Rejected:** `if restricted: print("please ask supervisor")` — that's a suggestion, not a gate.

**Why:** The problem says "stops to ask a human before doing anything that cannot be undone." The word "stops" implies the action is physically prevented, not merely discouraged.

---

### Audit trace, not fake reasoning

**Chose:** Clean step-by-step audit log (`trace.json`) that records what happened, in what order, on what information, and what was declined.

**Rejected:** LLM-style chain-of-thought reasoning. The agent isn't thinking — it's executing a deterministic pipeline. Faking reasoning would be dishonest.

**Why:** §5.1 requires reconstructability. §5.2 says showing only the output isn't enough. Our trace shows every step that produced each output.

---

### "Review award" treated as PERMITTED

**Chose:** Allow the agent to draft a triage note for "Review award" referrals, noting that any actual award change requires supervisor approval.

**Rejected:** Escalating all "Review award" referrals immediately.

**Why:** Reviewing an award (reading, categorising, drafting a note) is §2 permitted. The *outcome* of that review — actually changing the award — is §3 restricted. The agent does the permitted part and flags the restricted part. This is more useful than refusing to look at it entirely.

---

### "Record change of address" treated as AMBIGUOUS → ESCALATE

**Chose:** Escalate under §6.1 — unclear whether recording an address change affects entitlement (§3.1) or is irreversible (§3.8).

**Why:** The problem warns that "routine-looking requests can engage section 3 just as squarely as a dramatic one." An address change *could* affect eligibility. Per §6.1, treat ambiguity as restriction. Per §6.2, "the fact that a caseworker would probably have approved it is not relevant."

---

### "Draft explanatory note" (RF-0417) treated as RESTRICTED (§3.5)

**Chose:** Escalate — an explanatory note sent to a resident is a communication under §3.5.

**Why:** The resident asked "why was my payment lower." Drafting a note to explain this to them is drafting a communication. §3.5 prohibits "any communication sent to a resident" without approval. Even if the agent only drafts it, the requested action implies it would be sent.

---

### "Record income change" (RF-0419) treated as RESTRICTED (§3.1)

**Chose:** Escalate — recording an income change directly affects award calculation.

**Why:** An income change feeds into the award amount. This is squarely §3.1: "any change to a resident's entitlement, award amount, or eligibility status."

---

## What the solution does NOT do

- **Does not use a runtime LLM.** Triage notes are deterministic and template-based to guarantee 100% policy compliance, hard-gate enforcement, and audit reconstructibility.
- **Does not provide a full production case-management UI.** A lightweight read-only dashboard (`dashboard.py`) is included for demonstration and inspection, but it does not provide live database mutations, interactive approval actioning, or persistent multi-user session state.
- **Does not provide persistent retry/queue infrastructure for production API failures.** Individual referral failures are isolated so one failed history lookup does not stop the remaining queue batch (§4.3 compliance).
- **Does not persist approval workflow states across runs.** `ApprovalRequest` and `EscalationRecord` objects are written to structured JSON, but there is no interactive database-backed supervisor approval engine.
- **Does not provide full production-grade schema validation.** Basic malformed referral handling is implemented: invalid entries are skipped and recorded without stopping the batch.

---

## What I would fix first

1. **Add a persistent approval workflow** so supervisors can approve/reject escalations and record decisions directly in the audit trail.
2. **Replace the lightweight dashboard** with a full-scale production caseworker UI with interactive approval-state visibility, role-based access, and direct casework handoff workflows.
3. **Improve ambiguity detection** beyond the current deterministic policy patterns while retaining a strict hard safety boundary.
4. **Consider LLM-assisted note generation** only after preserving the deterministic policy gate, safeguarding checks, and audit trace.

---

## Cuts made for time

- No production-grade persistent approval workflow
- No database / persistent case state (JSON files used for transparency and clean testing)
- No full-featured production case-management UI (lightweight read-only dashboard provided)
- No LLM runtime integration (deliberately avoided to prioritize deterministic policy guardrails)

---

## Day 2

### Amendment ACA-2026/2 — Policy §3.9: Child Household Safeguarding

**What changed:** The organizers added §3.9: the agent may not draft a triage note for any referral where the household includes a person under 18. This applies immediately, including to referrals part-way through processing.

**Impact on our data:** 3 of the 12 referrals are affected (RF-2026-0412, RF-2026-0416, RF-2026-0418). All three previously produced normal PERMITTED triage notes. They now become `CHILD_HANDOFF`.

---

### Decision: Add `CHILD_HANDOFF` verdict — do not reuse `RESTRICTED`

**Chose:** A new `PolicyVerdict.CHILD_HANDOFF` value and a new `HandoffRecord` dataclass.

**Rejected:** Reusing `EscalationRecord` or treating §3.9 as another restricted case.

**Why:** The amendment is explicit that a hand-off is distinguishable from an escalation. An escalation says "the Department must decide whether this may happen at all." A hand-off says "this is ordinary casework that a human must do." Collapsing them into one record type would violate the letter of the amendment and confuse supervisors reviewing the output.

---

### Decision: §3.9 check as a pre-triage safeguarding gate in `agent.py`

**Chose:** The minor check runs immediately after history is fetched, before the policy evaluator or triage note generation code is reached.

**Why:** The amendment states the agent "may not produce a draft note for such a case at all" (§2.2). Safeguarding is a factual check on Department household records (§5.1), distinct from requested-action policy evaluation. If minor members are detected, the agent immediately constructs a `HandoffRecord` and preserves prior work, completely bypassing note generation and escalation. Per §4.1 (applies to part-way referrals) and §4.2 (preserve work already done), the sequence is: read referral → fetch history → check minors → if minor, hand off with what was already retrieved; if not, continue to policy evaluation.

---

### Decision: Age determined from household DOB vs. referral date, not from referral text

**Chose:** Calculate age from `date_of_birth` in the Department's household record against 17 March 2026 (the date the referrals were received), per §5.1 of the amendment.

**Rejected:** Reading "child" mentions from the referral summary text.

**Why:** The amendment is explicit: "determined from the household composition held by the Department, not from the wording of the referral." We also handled the edge case from §5.2 — if a DOB cannot be parsed, treat §3.9 as applying (conservative, matches the fallback to §6.1 principle).

---

### Decision: `handoffs.json` as a separate output file

**Chose:** Write `handoffs.json` alongside `escalations.json` and `results.json`.

**Why:** Hand-offs must be visibly distinguishable from escalations in the output. A caseworker or supervisor picking up the handoffs file should immediately see these are §3.9 cases — ordinary work requiring a human — not §3 authority blocks requiring a Department approval decision.

---

### Decision: No triage note drafted for Restricted or Ambiguous actions

**Chose:** When an action is RESTRICTED (§3) or AMBIGUOUS (§6.1), the agent hard-blocks execution, drafts an `EscalationRecord` and `ApprovalRequest`, and sets `triage_note = None`.

**Rejected:** Generating a triage note with "CANNOT PROCEED" text for blocked actions.

**Why:** If policy explicitly prevents the agent from executing a requested action without supervisor approval, the agent must not generate a completed triage note for that action. Producing a draft note for an unauthorized action contradicts the structural hard gate and creates ambiguity about whether the action was performed. The agent's output for restricted cases is solely the escalation package for the supervisor.

---

### What we would do differently

- The reference date (`2026-03-17`) is currently hardcoded. In a real system it would come from the referral's `received_at` field or a system clock, not a constant.
- The test for `test_handoff_record_carries_prior_work` is messier than it should be because of the mock setup. A dedicated test fixture would be cleaner.

