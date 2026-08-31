from __future__ import annotations

from typing import Dict, Any

from wail.jurisdiction.regulatory_profile import RegulatoryProfile


class DisclosureClockEngine:

    def calculate_deadline(
        self,
        profile: RegulatoryProfile,
        severity: str,
        tier: str,
    ) -> int:
        rules: Dict[str, Any] = profile.disclosure_rules

        if severity not in rules:
            raise ValueError(f"No disclosure rule defined for severity '{severity}'")

        rule = rules[severity]

        if isinstance(rule, int):
            return rule

        if isinstance(rule, dict):
            if tier in rule:
                return rule[tier]
            if "default" in rule:
                return rule["default"]

        raise ValueError(
            f"Invalid disclosure rule configuration for severity '{severity}'"
        )
