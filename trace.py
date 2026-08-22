"""
Calder County — Caseworker's Morning Agent
Execution Trace Logger.

Per §5.1: every action must be recorded so a supervisor can reconstruct
what was done, in what order, on what information, and what was declined.

Per §5.2: must show the steps that produced the output, not just the output.

Clean audit-style trace — not fake LLM reasoning.
"""
import json
import os
from datetime import datetime, timezone
from typing import List, Optional

import config


class TraceEntry:
    """A single audit step in the execution trace."""

    def __init__(
        self,
        referral_id: str,
        step_type: str,
        detail: str,
        timestamp: str = None,
    ):
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.referral_id = referral_id
        self.step_type = step_type
        self.detail = detail

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "referral_id": self.referral_id,
            "step": self.step_type,
            "detail": self.detail,
        }


class TraceLogger:
    """
    Audit trace logger.

    Records every step of the workflow for full reconstructability.
    Outputs both to console (tree-style) and to JSON file.
    """

    def __init__(self):
        self._entries: List[TraceEntry] = []
        self._current_referral: Optional[str] = None

    def _log(self, referral_id: str, step_type: str, detail: str):
        """Record a trace entry and print to console."""
        entry = TraceEntry(referral_id, step_type, detail)
        self._entries.append(entry)

        # Console output: tree-style
        if referral_id != self._current_referral:
            self._current_referral = referral_id
            print(f"\n{referral_id}")

        # Determine tree character
        prefix = "├─" if step_type != "processing_continued" else "└─"
        print(f"  {prefix} {step_type}: {detail}")

    # ----- Step methods -----

    def referral_read(self, referral_id: str, source: str, urgency: str):
        self._log(
            referral_id, "referral_read",
            f"Source: {source}, Urgency: {urgency}",
        )

    def history_fetched(
        self, referral_id: str, resident_ref: str, success: bool,
        detail: str = "",
    ):
        status = "OK" if success else "FAILED"
        msg = f"Resident {resident_ref} — {status}"
        if detail:
            msg += f" ({detail})"
        self._log(referral_id, "history_fetched", msg)

    def policy_evaluated(
        self, referral_id: str, verdict: str,
        sections: List[str], reasoning: str,
    ):
        section_str = ", ".join(f"§{s}" for s in sections) if sections else "none"
        self._log(
            referral_id, "policy_evaluated",
            f"Verdict: {verdict}, Matched: {section_str}",
        )

    def triage_drafted(self, referral_id: str):
        self._log(referral_id, "triage_drafted", "Triage note generated")

    def action_permitted(self, referral_id: str, action: str):
        self._log(
            referral_id, "action_permitted",
            f"Action '{action}' is within §2 — proceeding",
        )

    def action_blocked(
        self, referral_id: str, action: str, sections: List[str],
    ):
        section_str = ", ".join(f"§{s}" for s in sections)
        self._log(
            referral_id, "action_blocked",
            f"HARD BLOCK — Action '{action}' requires approval ({section_str})",
        )

    def escalation_created(self, referral_id: str, sections: List[str]):
        section_str = ", ".join(f"§{s}" for s in sections)
        self._log(
            referral_id, "escalation_created",
            f"Escalation record created — {section_str}",
        )

    def approval_requested(self, referral_id: str):
        self._log(
            referral_id, "approval_requested",
            "Approval request created — PENDING_APPROVAL",
        )

    def processing_continued(self, referral_id: str):
        self._log(referral_id, "processing_continued", "→ next referral")

    def error(self, referral_id: str, error_msg: str):
        self._log(referral_id, "error", f"ERROR: {error_msg}")

    # ----- Output -----

    def save(self, output_dir: str = None):
        """Write trace to output/trace.json."""
        out = output_dir or config.OUTPUT_DIR
        os.makedirs(out, exist_ok=True)
        path = os.path.join(out, "trace.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                [e.to_dict() for e in self._entries],
                f, indent=2, ensure_ascii=False,
            )
        print(f"\n📋 Trace written to {path} ({len(self._entries)} entries)")

    @property
    def entries(self) -> List[TraceEntry]:
        return list(self._entries)
