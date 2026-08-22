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

- **Does not use an LLM.** Triage notes are template-based. They're accurate but not eloquent. An LLM could improve readability — this is a P2 enhancement, not a P0 gap.
- **Does not have a UI.** Problem 5 does not score interface quality. The CLI output and JSON files are the deliverable.
- **Does not handle partial history API failures gracefully beyond retry.** If a resident's history can't be fetched after retry, the referral is logged as an error and processing continues. A production system would queue it for retry.
- **Does not persist approval state.** `ApprovalRequest` objects are written to JSON but there's no mechanism for a supervisor to approve/reject them at runtime. This would be needed for a real deployment.
- **Does not validate referral data.** We trust the queue format. A production system would validate fields.

---

## What I would fix first

1. **Add proper tests.** Unit tests for the policy evaluator especially — it's the most critical component.
2. **LLM-enhanced triage notes.** The templates work but a well-prompted LLM would produce better situation summaries.
3. **Approval workflow.** Let supervisors approve/reject escalated referrals and have the agent resume processing.
4. **Better ambiguity detection.** The current pattern matching is broad but brittle. A more sophisticated approach would parse the action semantically.

---

## Cuts made for time

- No unit tests (would be P1)
- No UI (not scored for Problem 5)
- No LLM integration (P2)
- No persistent state / database
