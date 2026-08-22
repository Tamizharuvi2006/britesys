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
    """Three-state policy evaluation result."""
    PERMITTED = "PERMITTED"
    RESTRICTED = "RESTRICTED"
    AMBIGUOUS_ESCALATE = "AMBIGUOUS_ESCALATE"


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
        return self.verdict in (
            PolicyVerdict.RESTRICTED,
            PolicyVerdict.AMBIGUOUS_ESCALATE,
        )


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
# Escalation Record (§4.2)
# ---------------------------------------------------------------------------

@dataclass
class EscalationRecord:
    """
    Per §4.2: must identify the referral, state which §3 provision applies,
    and carry sufficient context for a supervisor to act without re-reading
    the case from the beginning.
    """
    referral_id: str
    resident_ref: str
    requested_action: str
    triggered_sections: List[str]
    reasoning: str
    context_summary: str


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
    verdict: str                        # PERMITTED / RESTRICTED / AMBIGUOUS_ESCALATE
    triage_note: Optional[TriageNote] = None
    escalation: Optional[EscalationRecord] = None
    approval_request: Optional[ApprovalRequest] = None
    error: Optional[str] = None

    @property
    def escalated(self) -> bool:
        return self.escalation is not None

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
        if self.error:
            d["error"] = self.error
        return d
