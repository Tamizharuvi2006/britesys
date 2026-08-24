"""
Calder County — Caseworker's Morning Agent
Main Orchestrator.

Processes 12 overnight referrals through the complete workflow:
  1. Read referral queue
  2. Fetch resident history
  3. Evaluate against authority policy
  4. Draft triage note
  5. Hard-block restricted actions → escalate
  6. Continue to next referral
  7. Write results + trace

The agent has NO CODE PATH to execute §3 actions.
It can only: read, evaluate, draft notes, create escalation/approval requests.
The hard gate is structural — restricted actions are physically impossible.

Usage:
    python agent.py
    python agent.py --port 8083
    python agent.py --dry-run
"""
import sys

# Ensure UTF-8 output on Windows consoles that default to cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import config
from models import (
    Referral,
    ResidentHistory,
    PolicyVerdict,
    EscalationRecord,
    ApprovalRequest,
    HandoffRecord,
    ProcessingResult,
)
from history_client import HistoryClient, HistoryAPIError
from policy_evaluator import PolicyEvaluator
from triage import generate_triage_note
from trace import TraceLogger


REQUIRED_REFERRAL_FIELDS = {
    "referral_id", "received_at", "resident_ref",
    "source", "summary", "requested_action", "urgency",
}


def load_referrals(path: str = None) -> list:
    """Load and parse the referral queue, sorted by received_at.

    Skips malformed entries with a warning instead of crashing.
    """
    fpath = path or config.REFERRAL_QUEUE_PATH
    with open(fpath, encoding="utf-8") as f:
        raw = json.load(f)

    referrals = []
    for i, entry in enumerate(raw):
        # Validate required fields
        if not isinstance(entry, dict):
            print(f"  ⚠ Skipping referral #{i}: not a dict")
            continue
        missing = REQUIRED_REFERRAL_FIELDS - set(entry.keys())
        if missing:
            rid = entry.get("referral_id", f"#{i}")
            print(f"  ⚠ Skipping referral {rid}: missing fields {missing}")
            continue
        try:
            referrals.append(Referral(**{k: entry[k] for k in REQUIRED_REFERRAL_FIELDS}))
        except (TypeError, ValueError) as e:
            rid = entry.get("referral_id", f"#{i}")
            print(f"  ⚠ Skipping referral {rid}: {e}")

    # Process in chronological order
    referrals.sort(key=lambda r: r.received_at)
    return referrals


def create_escalation(
    referral: Referral,
    history: ResidentHistory,
    decision,
) -> EscalationRecord:
    """
    Create an escalation record per §4.2:
    - Identify the referral
    - State which §3 provision applies
    - Carry sufficient context for a supervisor to act
    """
    # Build context summary so supervisor doesn't need to re-read the case
    applicant = next(
        (m for m in history.household if m.relationship == "Applicant"),
        None,
    )
    applicant_name = applicant.name if applicant else "Unknown"

    recent_events = sorted(
        history.events, key=lambda e: e.date, reverse=True,
    )[:3]
    event_summary = "; ".join(
        f"{e.date} {e.type}" for e in recent_events
    ) if recent_events else "No recent events"

    context = (
        f"Resident: {applicant_name} ({history.resident_ref}), "
        f"District: {history.district}, "
        f"Status: {history.status}, "
        f"Award: £{history.award_monthly:,.2f}/month ({history.benefit_code}), "
        f"Household: {len(history.household)} member(s). "
        f"Recent events: {event_summary}. "
        f"Referral source: {referral.source}, "
        f"Urgency: {referral.urgency}. "
        f"Referral summary: {referral.summary}"
    )

    return EscalationRecord(
        referral_id=referral.referral_id,
        resident_ref=referral.resident_ref,
        requested_action=referral.requested_action,
        triggered_sections=decision.triggered_sections,
        reasoning=decision.reasoning,
        context_summary=context,
    )


def create_approval_request(
    referral: Referral,
    decision,
    context_summary: str,
) -> ApprovalRequest:
    """
    Create a structural approval request.
    The agent CANNOT execute this action — only a supervisor can approve.
    """
    return ApprovalRequest(
        referral_id=referral.referral_id,
        resident_ref=referral.resident_ref,
        action_requiring_approval=referral.requested_action,
        policy_sections=decision.triggered_sections,
        context_for_supervisor=context_summary,
        status="PENDING_APPROVAL",
    )


# ---------------------------------------------------------------------------
# ACA-2026/2 §3.9 — Safeguarding gate
# ---------------------------------------------------------------------------

REFERENCE_DATE_STR = "2026-03-17"  # The date the referrals were received


def _age_on_reference_date(date_of_birth: str) -> int:
    """Calculate age as of the referral date (17 March 2026)."""
    from datetime import date
    ref = date.fromisoformat(REFERENCE_DATE_STR)
    dob = date.fromisoformat(date_of_birth)
    return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))


def check_for_minors(history: ResidentHistory) -> list:
    """
    ACA-2026/2 §5.1: whether a household includes a person under 18 is
    determined from the household composition held by the Department,
    NOT from the wording of the referral.

    Returns list of minor household members as dicts, empty if none.
    """
    minors = []
    for member in history.household:
        try:
            age = _age_on_reference_date(member.date_of_birth)
            if age < 18:
                minors.append({
                    "name": member.name,
                    "date_of_birth": member.date_of_birth,
                    "relationship": member.relationship,
                    "age_on_referral_date": age,
                })
        except (ValueError, AttributeError):
            # ACA-2026/2 §5.2: if DOB cannot be parsed, treat §3.9 as applying
            minors.append({
                "name": getattr(member, "name", "Unknown"),
                "date_of_birth": getattr(member, "date_of_birth", "unknown"),
                "relationship": getattr(member, "relationship", "unknown"),
                "age_on_referral_date": None,
                "note": "DOB could not be established — §3.9 applied per §6.1",
            })
    return minors


def create_handoff_record(
    referral: Referral,
    history: ResidentHistory,
    minors: list,
) -> HandoffRecord:
    """
    ACA-2026/2 §3.2: hand-off must carry whatever the agent has already
    established, so the caseworker does not repeat that work.
    """
    work_done = (
        f"Resident: {history.resident_ref} ({history.status}, "
        f"£{history.award_monthly}/month, {history.benefit_code}, "
        f"District: {history.district}).\n"
        f"Household size: {len(history.household)} member(s).\n"
        f"Minor(s): "
        + ", ".join(
            f"{m['name']} aged {m['age_on_referral_date']}"
            for m in minors
        )
        + ".\n"
        f"Recent events: {len(history.events)} case event(s) on record.\n"
        f"Source of referral: {referral.source}. Urgency: {referral.urgency}.\n"
        f"Summary: {referral.summary}"
    )
    return HandoffRecord(
        referral_id=referral.referral_id,
        resident_ref=referral.resident_ref,
        requested_action=referral.requested_action,
        minors_identified=minors,
        work_already_done=work_done,
    )


# ---------------------------------------------------------------------------
# Core referral processing
# ---------------------------------------------------------------------------


def process_referral(
    referral: Referral,
    history_client: HistoryClient,
    policy_evaluator: PolicyEvaluator,
    trace: TraceLogger,
) -> ProcessingResult:
    """
    Process a single referral through the full workflow.
    Returns a ProcessingResult — never raises.

    Any unexpected exception is caught, logged to the trace, and
    processing continues with the next referral.
    """
    rid = referral.referral_id

    try:
        return _process_referral_inner(
            referral, history_client, policy_evaluator, trace,
        )
    except Exception as e:
        # Catch-all: one referral crashing must not kill the batch
        trace.error(rid, f"Unexpected error: {type(e).__name__}: {e}")
        trace.processing_continued(rid)
        return ProcessingResult(
            referral_id=rid,
            resident_ref=referral.resident_ref,
            verdict="ERROR",
            error=f"Unexpected error: {type(e).__name__}: {e}",
        )


def _process_referral_inner(
    referral: Referral,
    history_client: HistoryClient,
    policy_evaluator: PolicyEvaluator,
    trace: TraceLogger,
) -> ProcessingResult:
    """Inner processing logic — may raise on unexpected errors."""
    rid = referral.referral_id

    # Step 1: Log referral read
    trace.referral_read(rid, referral.source, referral.urgency)

    # Step 2: Fetch resident history
    try:
        raw_history = history_client.get_resident(referral.resident_ref)
        history = ResidentHistory.from_dict(raw_history)
        trace.history_fetched(
            rid, referral.resident_ref, success=True,
            detail=f"Status={history.status}, Award=£{history.award_monthly}",
        )
    except HistoryAPIError as e:
        trace.history_fetched(
            rid, referral.resident_ref, success=False, detail=str(e),
        )
        trace.error(rid, f"Cannot process — history unavailable: {e}")
        trace.processing_continued(rid)
        return ProcessingResult(
            referral_id=rid,
            resident_ref=referral.resident_ref,
            verdict="ERROR",
            error=f"History API error: {e}",
        )

    # Step 3 (NEW — ACA-2026/2 §3.9): Check for minors BEFORE drafting triage note.
    # Per §4.1: applies to any referral not yet triaged, including part-way through.
    # Per §4.2: if work already begun, preserve it and hand to caseworker.
    minors = check_for_minors(history)
    if minors:
        trace.child_handoff_detected(rid, minors)
        handoff = create_handoff_record(referral, history, minors)
        trace.handoff_created(rid)
        # §2.2 of ACA-2026/2: agent must NOT produce a draft note at all.
        # §3.3: this is NOT an escalation — no approval request, no §4.2 escalation record.
        trace.processing_continued(rid)
        return ProcessingResult(
            referral_id=rid,
            resident_ref=referral.resident_ref,
            verdict=PolicyVerdict.CHILD_HANDOFF.value,
            handoff=handoff,
        )

    # Step 4: Evaluate against authority policy (only reached if no minors)
    decision = policy_evaluator.evaluate(referral)
    trace.policy_evaluated(
        rid, decision.verdict.value,
        decision.triggered_sections, decision.reasoning,
    )

    # Step 5: Act based on verdict
    if decision.is_permitted:
        # PERMITTED — action within §2: draft triage proposal for caseworker
        triage_note = generate_triage_note(referral, history, decision)
        trace.triage_drafted(rid)
        trace.action_permitted(rid, referral.requested_action)
        trace.processing_continued(rid)
        return ProcessingResult(
            referral_id=rid,
            resident_ref=referral.resident_ref,
            verdict=decision.verdict.value,
            triage_note=triage_note,
        )
    else:
        # RESTRICTED or AMBIGUOUS_ESCALATE — hard block (do not draft triage note)
        trace.action_blocked(
            rid, referral.requested_action, decision.triggered_sections,
        )

        # Create escalation record (§4.2)
        escalation = create_escalation(referral, history, decision)
        trace.escalation_created(rid, decision.triggered_sections)

        # Create structural approval request (hard gate)
        approval = create_approval_request(
            referral, decision, escalation.context_summary,
        )
        trace.approval_requested(rid)

        # §4.3: continue processing the rest
        trace.processing_continued(rid)

        return ProcessingResult(
            referral_id=rid,
            resident_ref=referral.resident_ref,
            verdict=decision.verdict.value,
            triage_note=None,
            escalation=escalation,
            approval_request=approval,
        )


def write_outputs(results: list, trace: TraceLogger, output_dir: str = None):
    """Write all output files."""
    out = output_dir or config.OUTPUT_DIR
    os.makedirs(out, exist_ok=True)

    # results.json — all processing results
    results_path = os.path.join(out, "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(
            [r.to_dict() for r in results],
            f, indent=2, ensure_ascii=False,
        )
    print(f"\n📄 Results written to {results_path}")

    # escalations.json — just the escalated referrals (§3 hard blocks)
    escalated = [r.to_dict() for r in results if r.escalated]
    escalations_path = os.path.join(out, "escalations.json")
    with open(escalations_path, "w", encoding="utf-8") as f:
        json.dump(escalated, f, indent=2, ensure_ascii=False)
    print(f"🔒 Escalations written to {escalations_path}")

    # handoffs.json — ACA-2026/2 §3.9 child-household hand-offs
    handed_off = [r.to_dict() for r in results if r.handed_off]
    handoffs_path = os.path.join(out, "handoffs.json")
    with open(handoffs_path, "w", encoding="utf-8") as f:
        json.dump(handed_off, f, indent=2, ensure_ascii=False)
    print(f"👶 Handoffs written to {handoffs_path}")

    # trace.json
    trace.save(out)


def print_summary(results: list):
    """Print a concise summary to console."""
    total = len(results)
    permitted = sum(1 for r in results if r.verdict == "PERMITTED")
    restricted = sum(1 for r in results if r.verdict == "RESTRICTED")
    ambiguous = sum(1 for r in results if r.verdict == "AMBIGUOUS_ESCALATE")
    handoffs = sum(1 for r in results if r.verdict == "CHILD_HANDOFF")
    errors = sum(1 for r in results if r.verdict == "ERROR")

    print("\n" + "=" * 60)
    print("  CASEWORKER'S MORNING — PROCESSING SUMMARY")
    print("=" * 60)
    print(f"  Total referrals:  {total}")
    print(f"  ✓ Permitted:      {permitted}")
    print(f"  🔒 Restricted:     {restricted}")
    print(f"  ⚠ Ambiguous:      {ambiguous}")
    print(f"  👶 Handoff (§3.9):  {handoffs}")
    if errors:
        print(f"  ✗ Errors:         {errors}")
    print("=" * 60)

    if restricted + ambiguous > 0:
        print("\n  Escalated referrals:")
        for r in results:
            if r.escalated:
                sections = ", ".join(
                    f"§{s}" for s in r.escalation.triggered_sections
                )
                print(f"    {r.referral_id} — {sections} — {r.escalation.requested_action}")

    if handoffs > 0:
        print("\n  Handoff referrals (ACA-2026/2 §3.9):")
        for r in results:
            if r.handed_off:
                minor_names = ", ".join(
                    f"{m['name']} (age {m['age_on_referral_date']})"
                    for m in r.handoff.minors_identified
                )
                print(f"    {r.referral_id} — minor(s): {minor_names}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Caseworker's Morning — Referral Triage Agent",
    )
    parser.add_argument(
        "--port", type=int, default=8083,
        help="History API port (default: 8083)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse and evaluate only, don't call history API",
    )
    args = parser.parse_args()

    # Override API base if port specified
    if args.port != 8083:
        config.HISTORY_API_BASE = f"http://127.0.0.1:{args.port}"

    print("=" * 60)
    print("  CASEWORKER'S MORNING — REFERRAL TRIAGE AGENT")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    # Initialize components
    trace = TraceLogger()
    policy_evaluator = PolicyEvaluator()
    history_client = HistoryClient()

    # Load referrals
    referrals = load_referrals()
    print(f"\n📥 Loaded {len(referrals)} referrals from queue")

    # Health check (warning, not fatal — individual referrals fail gracefully)
    if not args.dry_run:
        try:
            health = history_client.health_check()
            print(
                f"✓ History API healthy — "
                f"{health.get('records', '?')} residents available"
            )
        except HistoryAPIError as e:
            print(f"⚠ History API unavailable: {e}")
            print("  Start it with: python services/history_service.py --port 8083")
            print("  Continuing anyway — individual referrals will fail gracefully.")

    # Process each referral
    results = []
    for i, referral in enumerate(referrals, 1):
        print(f"\n{'─' * 40}")
        print(f"  Processing {i}/{len(referrals)}: {referral.referral_id}")
        print(f"{'─' * 40}")

        result = process_referral(
            referral, history_client, policy_evaluator, trace,
        )
        results.append(result)

    # Write outputs
    write_outputs(results, trace)

    # Summary
    print_summary(results)


if __name__ == "__main__":
    main()
