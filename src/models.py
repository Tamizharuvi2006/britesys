"""
Calder County — Caseworker's Morning Agent
Data models for the referral triage workflow.

All domain objects as dataclasses. Python 3 stdlib only.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PolicyVerdict(Enum):
    """Policy evaluation result — four states after ACA-2026/2."""
    PERMITTED = "PERMITTED"
    RESTRICTED = "RESTRICTED"
    AMBIGUOUS_ESCALATE = "AMBIGUOUS_ESCALATE"
    # ACA-2026/2 §3.9: household contains person under 18.
    # This is NOT an escalation — it is ordinary casework that a human must do.
    CHILD_HANDOFF = "CHILD_HANDOFF"


# ---------------------------------------------------------------------------
# Referral (from referral-queue.json)
# ---------------------------------------------------------------------------

@dataclass
class Referral:
    referral_id: str
    received_at: str
    resident_ref: str
    source: str
    summary: str
    requested_action: str
    urgency: str


# ---------------------------------------------------------------------------
# Resident History (from History API)
# ---------------------------------------------------------------------------

@dataclass
class HouseholdMember:
    name: str
    date_of_birth: str
    relationship: str


@dataclass
class CaseEvent:
    date: str
    type: str
    detail: str


@dataclass
class ResidentHistory:
    resident_ref: str
    status: str
    benefit_code: str
    district: str
    award_monthly: float
    household: List[HouseholdMember]
    events: List[CaseEvent]

    @classmethod
    def from_dict(cls, data: dict) -> "ResidentHistory":
        """Parse API response dict into a ResidentHistory."""
        return cls(
            resident_ref=data["resident_ref"],
            status=data["status"],
            benefit_code=data["benefit_code"],
            district=data["district"],
            award_monthly=data["award_monthly"],
            household=[
                HouseholdMember(**m) for m in data.get("household", [])
            ],
            events=[
                CaseEvent(**e) for e in data.get("events", [])
            ],
        )


# ---------------------------------------------------------------------------
# Policy Decision
# ---------------------------------------------------------------------------

@dataclass
class PolicyDecision:
    """Result of evaluating a referral against authority policy."""
    verdict: PolicyVerdict
    triggered_sections: List[str]       # e.g. ["3.2", "3.7"]
    reasoning: str                       # concise human-readable explanation

    @property
    def is_permitted(self) -> bool:
        return self.verdict == PolicyVerdict.PERMITTED

    @property
    def requires_escalation(self) -> bool:
        """True for §3 hard-block escalations only (not §3.9 hand-offs)."""
        return self.verdict in (
            PolicyVerdict.RESTRICTED,
            PolicyVerdict.AMBIGUOUS_ESCALATE,
        )

    @property
    def requires_handoff(self) -> bool:
        """True for §3.9 child-household hand-offs (ACA-2026/2)."""
        return self.verdict == PolicyVerdict.CHILD_HANDOFF


# ---------------------------------------------------------------------------
# Triage Note
# ---------------------------------------------------------------------------

@dataclass
class TriageNote:
    """Drafted triage note for caseworker review (§2.4 — proposal only)."""
    referral_id: str
    resident_ref: str
    situation_summary: str
    referral_context: str
    relevant_history: str
    recommended_next_steps: str
    policy_flags: str


# ---------------------------------------------------------------------------
# Escalation Record (§4.2) — for §3 hard-block cases
# ---------------------------------------------------------------------------

@dataclass
class EscalationRecord:
    """
    Per §4.2: must identify the referral, state which §3 provision applies,
    and carry sufficient context for a supervisor to act without re-reading
    the case from the beginning.

    Used only for RESTRICTED and AMBIGUOUS_ESCALATE verdicts.
    NOT used for §3.9 CHILD_HANDOFF cases — those use HandoffRecord.
    """
    referral_id: str
    resident_ref: str
    requested_action: str
    triggered_sections: List[str]
    reasoning: str
    context_summary: str


# ---------------------------------------------------------------------------
# Handoff Record (ACA-2026/2 §3.9) — distinct from escalation
# ---------------------------------------------------------------------------

@dataclass
class HandoffRecord:
    """
    ACA-2026/2 §3.9: household contains a person under 18.

    This is NOT an escalation. An escalation says the Department must decide
    whether an action may happen at all. A hand-off says: this is ordinary
    casework that a human must do — the agent cannot draft a triage note
    for this case.

    Per §3.2 of ACA-2026/2: the agent must pass whatever it has already
    established to the caseworker, so they do not repeat work already done.
    """
    referral_id: str
    resident_ref: str
    requested_action: str
    minors_identified: List[dict]   # [{name, date_of_birth, relationship}]
    work_already_done: str          # summary of what the agent retrieved
    reason: str = "ACA-2026/2 §3.9 — household includes person under 18"


# ---------------------------------------------------------------------------
# Approval Request (structural hard gate)
# ---------------------------------------------------------------------------

@dataclass
class ApprovalRequest:
    """
    Structural hard gate. The agent creates this but CANNOT execute the
    underlying action. Only a supervisor can approve/reject.
    """
    referral_id: str
    resident_ref: str
    action_requiring_approval: str
    policy_sections: List[str]
    context_for_supervisor: str
    status: str = "PENDING_APPROVAL"  # PENDING_APPROVAL | APPROVED | REJECTED


# ---------------------------------------------------------------------------
# Processing Result (per referral)
# ---------------------------------------------------------------------------

@dataclass
class ProcessingResult:
    """Final result for a single referral."""
    referral_id: str
    resident_ref: str
    verdict: str   # PERMITTED / RESTRICTED / AMBIGUOUS_ESCALATE / CHILD_HANDOFF / ERROR
    triage_note: Optional[TriageNote] = None
    escalation: Optional[EscalationRecord] = None
    approval_request: Optional[ApprovalRequest] = None
    handoff: Optional[HandoffRecord] = None     # ACA-2026/2 §3.9
    error: Optional[str] = None

    @property
    def escalated(self) -> bool:
        return self.escalation is not None

    @property
    def handed_off(self) -> bool:
        return self.handoff is not None

    def to_dict(self) -> dict:
        """Serialize to dict for JSON output."""
        d = {
            "referral_id": self.referral_id,
            "resident_ref": self.resident_ref,
            "verdict": self.verdict,
        }
        if self.triage_note:
            d["triage_note"] = asdict(self.triage_note)
        if self.escalation:
            d["escalation"] = asdict(self.escalation)
        if self.approval_request:
            d["approval_request"] = asdict(self.approval_request)
        if self.handoff:
            d["handoff"] = asdict(self.handoff)
        if self.error:
            d["error"] = self.error
        return d
