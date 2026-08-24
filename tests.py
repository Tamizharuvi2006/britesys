"""
Calder County — Caseworker's Morning Agent
Test Suite (P1 + ACA-2026/2 §3.9).

Focused tests for:
  1. Policy evaluator — permitted, restricted, ambiguous
  2. Structural hard gate — no §3 code path
  3. Malformed input handling
  4. Per-referral failure isolation
  5. Trace integrity
  6. ACA-2026/2 §3.9 — child household hand-off

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
    Referral, ResidentHistory, PolicyVerdict, ProcessingResult, HandoffRecord,
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

    def test_restricted_referrals_have_no_triage_note(self):
        """Restricted actions cannot be performed; agent must not produce a draft triage note."""
        if not os.path.exists(os.path.join(PROJ_DIR, 'output', 'results.json')):
            self.skipTest("No output/results.json — run agent first")

        results = json.load(
            open(os.path.join(PROJ_DIR, 'output', 'results.json'), encoding='utf-8')
        )
        for r in results:
            if r['verdict'] in ('RESTRICTED', 'AMBIGUOUS_ESCALATE'):
                self.assertIsNone(r.get('triage_note'),
                                  f"Referral {r['referral_id']} is {r['verdict']}; triage_note must be None")

# =========================================================================
# 7. ACA-2026/2 §3.9 — Child Household Handoff Tests
# =========================================================================

class TestSection39Handoff(unittest.TestCase):
    """ACA-2026/2 §3.9: household with minor → CHILD_HANDOFF, no triage note."""

    def _make_history_with_minor(self) -> ResidentHistory:
        from models import HouseholdMember, CaseEvent
        return ResidentHistory(
            resident_ref="R-99999",
            status="Active",
            benefit_code="HSP-A",
            district="Test District",
            award_monthly=500.0,
            household=[
                HouseholdMember(name="Adult Member",
                                date_of_birth="1990-01-01",
                                relationship="Applicant"),
                HouseholdMember(name="Child Member",
                                date_of_birth="2020-06-15",   # age 5 on 2026-03-17
                                relationship="Son/daughter"),
            ],
            events=[],
        )

    def _make_history_adults_only(self) -> ResidentHistory:
        from models import HouseholdMember, CaseEvent
        return ResidentHistory(
            resident_ref="R-88888",
            status="Active",
            benefit_code="HSP-B",
            district="Test District",
            award_monthly=700.0,
            household=[
                HouseholdMember(name="Adult A",
                                date_of_birth="1985-03-10",
                                relationship="Applicant"),
                HouseholdMember(name="Adult B",
                                date_of_birth="1988-07-22",
                                relationship="Spouse/partner"),
            ],
            events=[],
        )

    def test_check_for_minors_finds_child(self):
        """check_for_minors returns entries for under-18s."""
        from agent import check_for_minors
        history = self._make_history_with_minor()
        minors = check_for_minors(history)
        self.assertEqual(len(minors), 1)
        self.assertEqual(minors[0]['name'], 'Child Member')
        self.assertEqual(minors[0]['age_on_referral_date'], 5)

    def test_check_for_minors_empty_for_adults(self):
        """check_for_minors returns empty list when all adults."""
        from agent import check_for_minors
        history = self._make_history_adults_only()
        minors = check_for_minors(history)
        self.assertEqual(len(minors), 0)

    def test_check_for_minors_boundary_exactly_18(self):
        """Person turning 18 on referral date is not a minor."""
        from agent import check_for_minors
        from models import HouseholdMember
        history = self._make_history_adults_only()
        # DOB = 2008-03-17 → exactly 18 on 2026-03-17
        history.household.append(
            HouseholdMember(name="Edge Case", date_of_birth="2008-03-17",
                            relationship="Son/daughter")
        )
        minors = check_for_minors(history)
        self.assertEqual(len(minors), 0, "Exactly 18 must NOT be treated as minor")

    def test_check_for_minors_boundary_17_is_minor(self):
        """Person who is 17 on referral date IS a minor."""
        from agent import check_for_minors
        from models import HouseholdMember
        history = self._make_history_adults_only()
        # DOB = 2008-03-18 → still 17 on 2026-03-17 (birthday tomorrow)
        history.household.append(
            HouseholdMember(name="Almost 18", date_of_birth="2008-03-18",
                            relationship="Son/daughter")
        )
        minors = check_for_minors(history)
        self.assertEqual(len(minors), 1, "17-year-old MUST be treated as minor")

    def test_unknown_dob_treated_as_minor(self):
        """§5.2: if DOB cannot be established, §3.9 applies (conservative)."""
        from agent import check_for_minors
        from models import HouseholdMember
        history = self._make_history_adults_only()
        history.household.append(
            HouseholdMember(name="Unknown DOB", date_of_birth="unknown-date",
                            relationship="Son/daughter")
        )
        minors = check_for_minors(history)
        # Must have flagged the unknown-DOB member
        self.assertEqual(len(minors), 1)
        self.assertIsNone(minors[0]['age_on_referral_date'])
        self.assertIn('note', minors[0])  # explanation present

    def test_process_referral_child_handoff_no_triage_note(self):
        """§2.2 of ACA-2026/2: agent must NOT produce a draft note for minor households."""
        from agent import process_referral
        from history_client import HistoryClient
        from unittest.mock import MagicMock

        referral = _make_referral(resident_ref="R-99999")
        history_with_minor = self._make_history_with_minor()

        client = MagicMock(spec=HistoryClient)
        # Return a raw dict matching what from_dict() expects
        client.get_resident.return_value = {
            'resident_ref': 'R-99999', 'status': 'Active',
            'benefit_code': 'HSP-A', 'district': 'Test',
            'award_monthly': 500.0,
            'household': [
                {'name': 'Adult Member', 'date_of_birth': '1990-01-01',
                 'relationship': 'Applicant'},
                {'name': 'Child Member', 'date_of_birth': '2020-06-15',
                 'relationship': 'Son/daughter'},
            ],
            'events': [],
        }

        trace = TraceLogger()
        evaluator = PolicyEvaluator()
        result = process_referral(referral, client, evaluator, trace)

        # Must be CHILD_HANDOFF
        self.assertEqual(result.verdict, 'CHILD_HANDOFF')
        # Must NOT have a triage note
        self.assertIsNone(result.triage_note,
                          "§2.2 ACA-2026/2: no triage note may be produced")
        # Must NOT have an escalation record
        self.assertIsNone(result.escalation,
                          "§3.3 ACA-2026/2: hand-off is not an escalation")
        # Must NOT have an approval request
        self.assertIsNone(result.approval_request,
                          "hand-off requires no approval request")
        # MUST have a handoff record
        self.assertIsNotNone(result.handoff)

    def test_handoff_record_carries_prior_work(self):
        """§3.2 ACA-2026/2: hand-off must carry what agent has already established."""
        from agent import process_referral
        from unittest.mock import MagicMock
        from history_client import HistoryClient

        referral = _make_referral(resident_ref="R-99999")
        client = MagicMock(spec=HistoryClient)
        client.get_resident.return_value = {
            'resident_ref': 'R-99999', 'status': 'Active',
            'benefit_code': 'HSP-A', 'district': 'Northgate',
            'award_monthly': 500.0,
            'household': [
                {'name': 'Adult Member', 'date_of_birth': '1990-01-01',
                 'relationship': 'Applicant'},
                {'name': 'Child Member', 'date_of_birth': '2020-06-15',
                 'relationship': 'Son/daughter'},
            ],
            'events': [],
        }
        trace = TraceLogger()
        result = process_referral(referral, MagicMock(spec=HistoryClient).__class__(), PolicyEvaluator(), trace)
        # Use the client mock directly
        from history_client import HistoryClient
        trace2 = TraceLogger()
        client2 = MagicMock(spec=HistoryClient)
        client2.get_resident.return_value = client.get_resident.return_value
        result2 = process_referral(referral, client2, PolicyEvaluator(), trace2)

        h = result2.handoff
        self.assertIsNotNone(h)
        self.assertIn('R-99999', h.work_already_done)
        self.assertIn('Child Member', h.work_already_done)
        self.assertIn(h.referral_id, referral.referral_id)
        self.assertEqual(len(h.minors_identified), 1)
        self.assertIn('reason', h.__dataclass_fields__)
        self.assertIn('ACA-2026/2', h.reason)

    def test_handoff_distinct_from_escalation(self):
        """§3.3 ACA-2026/2: a hand-off must be distinguishable from an escalation."""
        # HandoffRecord must not have EscalationRecord fields
        from models import HandoffRecord, EscalationRecord
        escalation_fields = {f for f in EscalationRecord.__dataclass_fields__}
        handoff_fields = {f for f in HandoffRecord.__dataclass_fields__}
        # Hand-off must NOT have triggered_sections (escalation-specific)
        self.assertNotIn('triggered_sections', handoff_fields,
                          "HandoffRecord must not have triggered_sections")
        # Hand-off must have minors_identified (handoff-specific)
        self.assertIn('minors_identified', handoff_fields)
        # Hand-off must have work_already_done (handoff-specific)
        self.assertIn('work_already_done', handoff_fields)
        # Escalation must NOT have minors_identified
        self.assertNotIn('minors_identified', escalation_fields)

    def test_trace_captures_handoff_steps(self):
        """Trace must record child_handoff_detected and handoff_created steps."""
        trace = TraceLogger()
        rid = "RF-TEST"
        trace.referral_read(rid, "Test", "Standard")
        trace.history_fetched(rid, "R-1", True)
        trace.child_handoff_detected(rid, [{'name': 'Child', 'date_of_birth': '2020-01-01'}])
        trace.handoff_created(rid)
        trace.processing_continued(rid)

        steps = [e.step_type for e in trace.entries]
        self.assertIn('child_handoff_detected', steps)
        self.assertIn('handoff_created', steps)
        self.assertNotIn('action_blocked', steps,   "handoff is not a block")
        self.assertNotIn('escalation_created', steps, "handoff is not an escalation")
        self.assertNotIn('triage_drafted', steps,   "no triage note for §3.9")

    def test_output_handoffs_json_exists_and_correct(self):
        """handoffs.json must exist and contain only CHILD_HANDOFF referrals."""
        hpath = os.path.join(PROJ_DIR, 'output', 'handoffs.json')
        if not os.path.exists(hpath):
            self.skipTest("No output/handoffs.json — run agent first")
        handoffs = json.load(open(hpath, encoding='utf-8'))
        self.assertEqual(len(handoffs), 3,
                         "Expected exactly 3 CHILD_HANDOFF referrals in current data")
        for h in handoffs:
            self.assertEqual(h['verdict'], 'CHILD_HANDOFF')
            self.assertIsNone(h.get('triage_note'),
                              f"{h['referral_id']}: must have no triage_note")
            self.assertIsNone(h.get('escalation'),
                              f"{h['referral_id']}: must have no escalation")
            self.assertIsNotNone(h.get('handoff'),
                                 f"{h['referral_id']}: must have handoff record")
            self.assertTrue(len(h['handoff']['minors_identified']) > 0,
                            f"{h['referral_id']}: handoff must list minors")
            self.assertTrue(len(h['handoff']['work_already_done']) > 50,
                            f"{h['referral_id']}: work_already_done too short")

    def test_known_affected_referrals(self):
        """The 3 known affected referrals from the actual data are all CHILD_HANDOFF."""
        rpath = os.path.join(PROJ_DIR, 'output', 'results.json')
        if not os.path.exists(rpath):
            self.skipTest("No output/results.json — run agent first")
        results = json.load(open(rpath, encoding='utf-8'))
        results_by_id = {r['referral_id']: r for r in results}
        # These three had minors in the household data
        for rid in ('RF-2026-0412', 'RF-2026-0416', 'RF-2026-0418'):
            self.assertIn(rid, results_by_id, f"{rid} missing from results")
            r = results_by_id[rid]
            self.assertEqual(r['verdict'], 'CHILD_HANDOFF',
                             f"{rid} should be CHILD_HANDOFF, got {r['verdict']}")
            self.assertIsNone(r.get('triage_note'),
                              f"{rid}: must have no triage_note")


if __name__ == '__main__':
    unittest.main()
