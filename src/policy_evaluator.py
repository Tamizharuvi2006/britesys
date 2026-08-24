"""
Calder County — Caseworker's Morning Agent
Policy Evaluator.

Evaluates each referral's requested_action + summary against the authority
policy (loaded as data from policy_rules.json).

Three possible verdicts:
  PERMITTED          — action clearly falls under §2
  RESTRICTED         — action matches a §3 provision
  AMBIGUOUS_ESCALATE — action is not clearly §2, so treat as §3 per §6.1
"""
import json
import re
from typing import List, Tuple

import config
from models import PolicyDecision, PolicyVerdict, Referral


class PolicyEvaluator:
    """Evaluates referral actions against authority policy rules."""

    def __init__(self, rules_path: str = None):
        path = rules_path or config.POLICY_RULES_PATH
        with open(path, encoding="utf-8") as f:
            self._rules = json.load(f)
        self._restricted = self._rules["restricted_actions"]
        self._permitted = self._rules["permitted_actions"]

    def evaluate(self, referral: Referral) -> PolicyDecision:
        """
        Evaluate a referral against the policy.

        Checks both requested_action and summary against §3 rules.
        Returns PERMITTED / RESTRICTED / AMBIGUOUS_ESCALATE.
        """
        action_lower = referral.requested_action.lower().strip()
        summary_lower = referral.summary.lower().strip()

        # Step 1: Check for §3 restrictions
        matched_sections, reasons = self._check_restricted(
            action_lower, summary_lower
        )

        if matched_sections:
            return PolicyDecision(
                verdict=PolicyVerdict.RESTRICTED,
                triggered_sections=matched_sections,
                reasoning="; ".join(reasons),
            )

        # Step 2: Check if explicitly permitted under §2
        if self._check_permitted(action_lower):
            return PolicyDecision(
                verdict=PolicyVerdict.PERMITTED,
                triggered_sections=[],
                reasoning=(
                    f"Action '{referral.requested_action}' falls within §2 "
                    f"permitted actions."
                ),
            )

        # Step 3: Not clearly §2 and not matched §3 — §6.1 applies
        return PolicyDecision(
            verdict=PolicyVerdict.AMBIGUOUS_ESCALATE,
            triggered_sections=["6.1"],
            reasoning=(
                f"Action '{referral.requested_action}' is not explicitly "
                f"permitted under §2. Per §6.1, where it is unclear whether "
                f"an action falls within §3, it is to be treated as though "
                f"it does."
            ),
        )

    def _check_restricted(
        self, action: str, summary: str
    ) -> Tuple[List[str], List[str]]:
        """
        Check action + summary against all §3 rules.
        Returns (matched_sections, reasons).
        """
        matched_sections = []
        reasons = []

        for rule in self._restricted:
            section = rule["section"]
            description = rule["description"]

            # Check action against action_patterns (substring match)
            action_hit = any(
                pattern in action for pattern in rule["action_patterns"]
            )

            # Check action against keywords
            keyword_hit = any(
                kw in action for kw in rule.get("keywords_in_action", [])
            )

            # Check summary against summary_patterns (regex)
            summary_hit = any(
                re.search(pattern, summary)
                for pattern in rule.get("summary_patterns", [])
            )

            if action_hit or keyword_hit or summary_hit:
                matched_sections.append(section)
                match_sources = []
                if action_hit or keyword_hit:
                    match_sources.append("requested_action")
                if summary_hit:
                    match_sources.append("summary")
                reasons.append(
                    f"§{section} ({description}) — "
                    f"matched via {', '.join(match_sources)}"
                )

        return matched_sections, reasons

    def _check_permitted(self, action: str) -> bool:
        """Check if action matches a §2 permitted pattern."""
        return any(
            pattern in action
            for pattern in self._permitted["patterns"]
        )
