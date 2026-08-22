"""
Calder County — Caseworker's Morning Agent
P1 Test Suite.

Focused tests for:
  1. Policy evaluator — permitted, restricted, ambiguous
  2. Structural hard gate — no §3 code path
  3. Malformed input handling
  4. Per-referral failure isolation
  5. Trace integrity

Python 3 stdlib only (uses unittest).

Usage:
    python tests.py
    python tests.py -v
"""
import ast
import json
import os
import sys
import unittest
from unittest.mock import patch

# Ensure project is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import (
    Referral, ResidentHistory, PolicyVerdict, ProcessingResult,
)
from policy_evaluator import PolicyEvaluator
from trace import TraceLogger
from triage import generate_triage_note


PROJ_DIR = os.path.dirname(os.path.abspath(__file__))


def _make_referral(**overrides) -> Referral:
    """Create a test referral with defaults."""
    defaults = {
        "referral_id": "RF-TEST-001",
        "received_at": "2026-03-17T04:00:00",
        "resident_ref": "R-99999",
        "source": "Test Source",
        "summary": "Test summary.",
        "requested_action": "Test action",
        "urgency": "Standard",
    }
    defaults.update(overrides)
    return Referral(**defaults)


# =========================================================================
# 1. Policy Evaluator Tests
# =========================================================================

class TestPolicyEvaluatorPermitted(unittest.TestCase):
    """Actions that should be clearly PERMITTED under §2."""

    def setUp(self):
        self.evaluator = PolicyEvaluator()

    def test_review_award(self):
        r = _make_referral(requested_action="Review award",
                           summary="Resident requests review of award.")
        d = self.evaluator.evaluate(r)
        self.assertEqual(d.verdict, PolicyVerdict.PERMITTED)

    def test_review_household_composition(self):
        r = _make_referral(requested_action="Review household composition",
                           summary="Partner has left the household.")
        d = self.evaluator.evaluate(r)
        self.assertEqual(d.verdict, PolicyVerdict.PERMITTED)

    def test_flag_for_contact(self):
        r = _make_referral(requested_action="Flag for contact attempt",
                           summary="Correspondence returned undelivered.")
        d = self.evaluator.evaluate(r)
        self.assertEqual(d.verdict, PolicyVerdict.PERMITTED)

    def test_draft_triage_note(self):
        r = _make_referral(requested_action="Draft triage note for supervisor",
                           summary="Routine review needed.")
        d = self.evaluator.evaluate(r)
        self.assertEqual(d.verdict, PolicyVerdict.PERMITTED)


class TestPolicyEvaluatorRestricted(unittest.TestCase):
    """Actions that should be clearly RESTRICTED under §3."""

    def setUp(self):
        self.evaluator = PolicyEvaluator()

    def test_suspend_assistance(self):
        """§3.2 — suspension of award."""
        r = _make_referral(
            requested_action="Suspend assistance pending investigation",
            summary="Anonymous report alleging undeclared employment.",
        )
        d = self.evaluator.evaluate(r)
        self.assertEqual(d.verdict, PolicyVerdict.RESTRICTED)
        self.assertIn("3.2", d.triggered_sections)

    def test_suspend_with_fraud_summary(self):
        """§3.2 + §3.7 — suspension + fraud allegation."""
        r = _make_referral(
            requested_action="Suspend assistance pending investigation",
            summary="Undeclared employment alleged. Suspected fraud.",
        )
        d = self.evaluator.evaluate(r)
        self.assertEqual(d.verdict, PolicyVerdict.RESTRICTED)
        self.assertIn("3.2", d.triggered_sections)
        self.assertIn("3.7", d.triggered_sections)

    def test_update_payment_details(self):
        """§3.4 — change payment details."""
        r = _make_referral(
            requested_action="Update payment details",
            summary="Resident asks to change account.",
        )
        d = self.evaluator.evaluate(r)
        self.assertEqual(d.verdict, PolicyVerdict.RESTRICTED)
        self.assertIn("3.4", d.triggered_sections)

    def test_record_income_change(self):
        """§3.1 — change affecting entitlement."""
        r = _make_referral(
            requested_action="Record income change",
            summary="Resident now receiving training allowance.",
        )
        d = self.evaluator.evaluate(r)
        self.assertEqual(d.verdict, PolicyVerdict.RESTRICTED)
        self.assertIn("3.1", d.triggered_sections)

    def test_draft_explanatory_note_is_communication(self):
        """§3.5 — communication to resident."""
        r = _make_referral(
            requested_action="Draft explanatory note",
            summary="Resident queries why payment was lower.",
        )
        d = self.evaluator.evaluate(r)
        self.assertEqual(d.verdict, PolicyVerdict.RESTRICTED)
        self.assertIn("3.5", d.triggered_sections)

    def test_reinstatement_in_summary(self):
        """§3.2 — reinstatement detected in summary."""
        r = _make_referral(
            requested_action="Draft triage note for supervisor",
            summary="Award to be reinstated from date of termination.",
        )
        d = self.evaluator.evaluate(r)
        self.assertEqual(d.verdict, PolicyVerdict.RESTRICTED)
        self.assertIn("3.2", d.triggered_sections)


class TestPolicyEvaluatorAmbiguous(unittest.TestCase):
    """Actions that should be AMBIGUOUS_ESCALATE per §6.1."""

    def setUp(self):
        self.evaluator = PolicyEvaluator()

    def test_record_change_of_address(self):
        """Not clearly §2, not matched §3 — §6.1 applies."""
        r = _make_referral(
            requested_action="Record change of address",
            summary="New address notified. Resident has moved.",
        )
        d = self.evaluator.evaluate(r)
        self.assertEqual(d.verdict, PolicyVerdict.AMBIGUOUS_ESCALATE)
        self.assertIn("6.1", d.triggered_sections)

    def test_unknown_action(self):
        """Completely unknown action — §6.1."""
        r = _make_referral(
            requested_action="Do something unusual",
            summary="Unusual request.",
        )
        d = self.evaluator.evaluate(r)
        self.assertEqual(d.verdict, PolicyVerdict.AMBIGUOUS_ESCALATE)
        self.assertIn("6.1", d.triggered_sections)


# =========================================================================
# 2. Structural Hard Gate Tests
# =========================================================================

class TestStructuralHardGate(unittest.TestCase):
    """Prove the agent cannot execute §3 actions."""

    AGENT_FILES = [
        'agent.py', 'triage.py', 'policy_evaluator.py', 'trace.py',
        'history_client.py', 'models.py', 'config.py',
    ]

    FORBIDDEN_NAMES = [
        'change_award', 'update_award', 'modify_award',
        'suspend_award', 'terminate_award', 'reinstate_award',
        'issue_payment', 'cancel_payment', 'alter_payment',
        'change_payment_details', 'update_payment_details',
        'send_letter', 'send_email', 'send_notification',
        'contact_resident', 'notify_resident',
        'disclose_information', 'record_fraud', 'assert_finding',
        'execute_action', 'perform_action', 'apply_change',
    ]

    def test_no_forbidden_function_names(self):
        """No function in the codebase matches a forbidden capability."""
        for fname in self.AGENT_FILES:
            fpath = os.path.join(PROJ_DIR, fname)
            with open(fpath, encoding='utf-8') as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for forbidden in self.FORBIDDEN_NAMES:
                        self.assertNotIn(
                            forbidden, node.name.lower(),
                            f"{fname}:{node.lineno} has forbidden name '{node.name}'",
                        )

    def test_history_client_read_only(self):
        """history_client.py only exposes GET methods."""
        fpath = os.path.join(PROJ_DIR, 'history_client.py')
        with open(fpath, encoding='utf-8') as f:
            source = f.read()
        self.assertIn('def _get', source)
        self.assertNotIn('def _post', source)
        self.assertNotIn('def _put', source)
        self.assertNotIn('def _patch', source)
        self.assertNotIn('def _delete', source)

    def test_no_http_write_methods(self):
        """No POST/PUT/PATCH/DELETE anywhere in agent code."""
        for fname in self.AGENT_FILES:
            fpath = os.path.join(PROJ_DIR, fname)
            with open(fpath, encoding='utf-8') as f:
                source = f.read().lower()
            for method in ['post', 'put', 'patch', 'delete']:
                self.assertNotIn(
                    f'method="{method}"', source,
                    f"{fname} contains HTTP {method.upper()}",
                )

    def test_agent_never_approves(self):
        """agent.py never sets approval to APPROVED or REJECTED."""
        fpath = os.path.join(PROJ_DIR, 'agent.py')
        with open(fpath, encoding='utf-8') as f:
            source = f.read()
        # PENDING_APPROVAL is OK, but bare APPROVED/REJECTED is not
        lines = source.split('\n')
        for i, line in enumerate(lines, 1):
            if '"APPROVED"' in line and 'PENDING' not in line:
                self.fail(f"agent.py:{i} sets status to APPROVED")
            if '"REJECTED"' in line:
                self.fail(f"agent.py:{i} sets status to REJECTED")


# =========================================================================
# 3. Malformed Input Tests
# =========================================================================

class TestMalformedInput(unittest.TestCase):
    """Agent handles bad input without crashing."""

    def test_load_referrals_missing_fields(self):
        """Referral with missing fields is skipped, not crashed."""
        import tempfile
        bad_queue = [
            {"referral_id": "RF-BAD-001", "received_at": "2026-03-17T01:00:00"},
            {
                "referral_id": "RF-GOOD-001",
                "received_at": "2026-03-17T02:00:00",
                "resident_ref": "R-99999",
                "source": "Test",
                "summary": "Test",
                "requested_action": "Review award",
                "urgency": "Standard",
            },
        ]
        tmp = os.path.join(PROJ_DIR, "output", "_test_bad_queue.json")
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        with open(tmp, 'w') as f:
            json.dump(bad_queue, f)
        try:
            from agent import load_referrals
            referrals = load_referrals(tmp)
            self.assertEqual(len(referrals), 1)
            self.assertEqual(referrals[0].referral_id, "RF-GOOD-001")
        finally:
            os.remove(tmp)

    def test_load_referrals_non_dict_entry(self):
        """Non-dict entries are skipped."""
        import tempfile
        bad_queue = ["not a dict", 42, None]
        tmp = os.path.join(PROJ_DIR, "output", "_test_nondicts.json")
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        with open(tmp, 'w') as f:
            json.dump(bad_queue, f)
        try:
            from agent import load_referrals
            referrals = load_referrals(tmp)
            self.assertEqual(len(referrals), 0)
        finally:
            os.remove(tmp)


# =========================================================================
# 4. Per-Referral Failure Isolation Tests
# =========================================================================

class TestFailureIsolation(unittest.TestCase):
    """One referral failing must not kill the batch."""

    def test_process_referral_catches_api_error(self):
        """API error for one referral produces ERROR result, not crash."""
        from agent import process_referral
        from history_client import HistoryClient

        referral = _make_referral(resident_ref="R-NONEXISTENT")
        # Use a client pointing at a port nothing is listening on
        client = HistoryClient(base_url="http://127.0.0.1:19999", retries=0, timeout=1)
        evaluator = PolicyEvaluator()
        trace = TraceLogger()

        result = process_referral(referral, client, evaluator, trace)
        self.assertEqual(result.verdict, "ERROR")
        self.assertIsNotNone(result.error)
        # Should not have raised

    def test_process_referral_catches_unexpected_error(self):
        """Unexpected exception produces ERROR result, not crash."""
        from agent import process_referral
        from history_client import HistoryClient

        referral = _make_referral()
        # Create a client that will raise something unexpected
        client = HistoryClient()
        evaluator = PolicyEvaluator()
        trace = TraceLogger()

        # Patch get_resident to raise a bizarre error
        def explode(*args, **kwargs):
            raise RuntimeError("Simulated unexpected failure")

        client.get_resident = explode
        result = process_referral(referral, client, evaluator, trace)
        self.assertEqual(result.verdict, "ERROR")
        self.assertIn("RuntimeError", result.error)


# =========================================================================
# 5. Trace Integrity Tests
# =========================================================================

class TestTraceIntegrity(unittest.TestCase):
    """Trace captures every step including errors."""

    def test_trace_captures_all_step_types(self):
        """TraceLogger records all expected step types."""
        trace = TraceLogger()
        rid = "RF-TEST"

        trace.referral_read(rid, "Test", "Standard")
        trace.history_fetched(rid, "R-1", True)
        trace.policy_evaluated(rid, "PERMITTED", [], "test")
        trace.triage_drafted(rid)
        trace.action_permitted(rid, "test")
        trace.processing_continued(rid)

        steps = [e.step_type for e in trace.entries]
        self.assertEqual(steps, [
            "referral_read", "history_fetched", "policy_evaluated",
            "triage_drafted", "action_permitted", "processing_continued",
        ])

    def test_trace_captures_blocked_flow(self):
        """Blocked referral trace includes block + escalation + approval."""
        trace = TraceLogger()
        rid = "RF-TEST"

        trace.referral_read(rid, "Test", "High")
        trace.history_fetched(rid, "R-1", True)
        trace.policy_evaluated(rid, "RESTRICTED", ["3.2"], "test")
        trace.triage_drafted(rid)
        trace.action_blocked(rid, "Suspend", ["3.2"])
        trace.escalation_created(rid, ["3.2"])
        trace.approval_requested(rid)
        trace.processing_continued(rid)

        steps = [e.step_type for e in trace.entries]
        self.assertIn("action_blocked", steps)
        self.assertIn("escalation_created", steps)
        self.assertIn("approval_requested", steps)
        self.assertIn("processing_continued", steps)

    def test_trace_captures_errors(self):
        """Errors are traced, not silently dropped."""
        trace = TraceLogger()
        rid = "RF-TEST"

        trace.referral_read(rid, "Test", "Standard")
        trace.error(rid, "API timeout")
        trace.processing_continued(rid)

        steps = [e.step_type for e in trace.entries]
        self.assertIn("error", steps)
        # Error detail is preserved
        error_entry = [e for e in trace.entries if e.step_type == "error"][0]
        self.assertIn("API timeout", error_entry.detail)

    def test_trace_entries_have_timestamps(self):
        """Every trace entry has a timestamp."""
        trace = TraceLogger()
        trace.referral_read("RF-TEST", "Test", "Standard")
        for entry in trace.entries:
            self.assertIsNotNone(entry.timestamp)
            self.assertIn("T", entry.timestamp)  # ISO format


# =========================================================================
# 6. Escalation Record Compliance (§4.2)
# =========================================================================

class TestEscalationCompliance(unittest.TestCase):
    """Escalation records must satisfy §4.2 requirements."""

    def test_escalation_has_all_required_fields(self):
        """§4.2: referral ID, §3 provision, sufficient context."""
        if not os.path.exists(os.path.join(PROJ_DIR, 'output', 'escalations.json')):
            self.skipTest("No output/escalations.json — run agent first")

        escalations = json.load(
            open(os.path.join(PROJ_DIR, 'output', 'escalations.json'), encoding='utf-8')
        )
        for e in escalations:
            esc = e['escalation']
            self.assertTrue(esc.get('referral_id'), f"Missing referral_id")
            self.assertTrue(esc.get('triggered_sections'), f"Missing triggered_sections")
            self.assertTrue(esc.get('context_summary'), f"Missing context_summary")
            self.assertTrue(len(esc['context_summary']) > 50,
                            f"Context too short for supervisor")


if __name__ == '__main__':
    unittest.main()
