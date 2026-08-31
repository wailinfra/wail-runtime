from __future__ import annotations

from typing import Dict, Any

from wail.jurisdiction.regulatory_profile import RegulatoryProfile


class OversightRequirementBinder:

    def resolve(
        self,
        profile: RegulatoryProfile,
        severity: str,
        tier: str,
    ) -> str:
        rules: Dict[str, Any] = profile.oversight_requirements

        if severity in rules:
            rule = rules[severity]

            if isinstance(rule, str):
                return rule

            if isinstance(rule, dict):
                if tier in rule:
                    return rule[tier]
                if "default" in rule:
                    return rule["default"]

        if "default" in rules:
            default_rule = rules["default"]
            if isinstance(default_rule, str):
                return default_rule

        return "NONE"
