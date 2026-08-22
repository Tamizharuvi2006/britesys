"""
Calder County — Caseworker's Morning Agent
Triage Note Generator.

Drafts structured triage notes per §2.4 — these are proposals only.
They have no effect on the case until a caseworker adopts them.

Deterministic template-based approach (P0). 
Can be swapped with LLM-based generation later (P2).
"""
from models import (
    Referral,
    ResidentHistory,
    PolicyDecision,
    PolicyVerdict,
    TriageNote,
)


def generate_triage_note(
    referral: Referral,
    history: ResidentHistory,
    decision: PolicyDecision,
) -> TriageNote:
    """
    Generate a structured triage note for caseworker review.

    This is a §2.4 draft — a proposal with no effect until adopted.
    """

    # --- Situation summary ---
    applicant = next(
        (m for m in history.household if m.relationship == "Applicant"),
        None,
    )
    applicant_name = applicant.name if applicant else "Unknown"
    household_size = len(history.household)
    other_members = [
        f"{m.name} ({m.relationship})"
        for m in history.household
        if m.relationship != "Applicant"
    ]

    situation_summary = (
        f"Resident: {applicant_name} ({history.resident_ref})\n"
        f"District: {history.district}\n"
        f"Status: {history.status}\n"
        f"Benefit code: {history.benefit_code}\n"
        f"Monthly award: £{history.award_monthly:,.2f}\n"
        f"Household size: {household_size}"
    )
    if other_members:
        situation_summary += f"\nOther members: {', '.join(other_members)}"

    # --- Referral context ---
    referral_context = (
        f"Referral {referral.referral_id} received {referral.received_at}\n"
        f"Source: {referral.source}\n"
        f"Urgency: {referral.urgency}\n"
        f"Summary: {referral.summary}\n"
        f"Requested action: {referral.requested_action}"
    )

    # --- Relevant history ---
    if history.events:
        # Show most recent events (up to 5)
        recent = sorted(history.events, key=lambda e: e.date, reverse=True)[:5]
        event_lines = [
            f"  {e.date} — {e.type}: {e.detail}" for e in recent
        ]
        relevant_history = (
            f"Recent case events ({len(history.events)} total, "
            f"showing last {len(recent)}):\n" + "\n".join(event_lines)
        )
    else:
        relevant_history = "No prior case events on record."

    # --- Recommended next steps ---
    if decision.verdict == PolicyVerdict.PERMITTED:
        next_steps = _permitted_next_steps(referral, history)
    elif decision.verdict == PolicyVerdict.RESTRICTED:
        next_steps = _restricted_next_steps(referral, decision)
    else:  # AMBIGUOUS_ESCALATE
        next_steps = _ambiguous_next_steps(referral, decision)

    # --- Policy flags ---
    if decision.is_permitted:
        policy_flags = "No policy restrictions identified. Action within §2."
    else:
        sections = ", ".join(f"§{s}" for s in decision.triggered_sections)
        policy_flags = (
            f"POLICY RESTRICTION: {sections}\n"
            f"Reasoning: {decision.reasoning}\n"
            f"Action CANNOT be performed without supervisor approval."
        )

    return TriageNote(
        referral_id=referral.referral_id,
        resident_ref=referral.resident_ref,
        situation_summary=situation_summary,
        referral_context=referral_context,
        relevant_history=relevant_history,
        recommended_next_steps=next_steps,
        policy_flags=policy_flags,
    )


def _permitted_next_steps(referral: Referral, history: ResidentHistory) -> str:
    """Generate next-step recommendations for permitted actions."""
    action = referral.requested_action.lower()

    if "review" in action and "household" in action:
        return (
            f"Review household composition for {history.resident_ref}. "
            f"Current household has {len(history.household)} member(s). "
            f"Verify reported change against records and update if confirmed. "
            f"Note: any resulting change to award amount requires supervisor "
            f"approval under §3.1."
        )
    elif "review" in action and "award" in action:
        return (
            f"Review award for {history.resident_ref}. "
            f"Current monthly award: £{history.award_monthly:,.2f} "
            f"({history.benefit_code}). "
            f"Assess whether circumstances warrant recalculation. "
            f"Note: any actual change to the award amount requires supervisor "
            f"approval under §3.1."
        )
    elif "flag" in action:
        return (
            f"Flag referral {referral.referral_id} for caseworker attention. "
            f"Resident {history.resident_ref} ({history.district}). "
            f"Reason: {referral.summary}"
        )
    elif "triage" in action or "draft" in action:
        return (
            f"Triage note drafted for caseworker review. "
            f"Referral concerns: {referral.summary}"
        )
    else:
        return (
            f"Process referral as requested: {referral.requested_action}. "
            f"Resident: {history.resident_ref}, "
            f"District: {history.district}."
        )


def _restricted_next_steps(referral: Referral, decision: PolicyDecision) -> str:
    """Generate next steps for restricted (§3) actions."""
    sections = ", ".join(f"§{s}" for s in decision.triggered_sections)
    return (
        f"⛔ CANNOT PROCEED — action requires supervisor approval.\n"
        f"Requested action: {referral.requested_action}\n"
        f"Policy restriction: {sections}\n"
        f"The assistant is not permitted to perform this action, "
        f"nor any partial or preparatory version of it (§4.1).\n"
        f"This referral has been escalated. A supervisor must review "
        f"and approve before any action is taken."
    )


def _ambiguous_next_steps(referral: Referral, decision: PolicyDecision) -> str:
    """Generate next steps for ambiguous (§6.1) actions."""
    return (
        f"⚠️ ESCALATED (§6.1) — unclear whether action falls within §3.\n"
        f"Requested action: {referral.requested_action}\n"
        f"Per §6.1: 'Where it is unclear whether an action falls within "
        f"section 3, it is to be treated as though it does.'\n"
        f"This referral has been escalated for supervisor review.\n"
        f"The convenience or likelihood of approval is not relevant (§6.2)."
    )
