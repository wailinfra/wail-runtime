from typing import Dict


class RetentionPolicyResolver:

    def resolve(self, profile, classification: Dict) -> Dict:

        incident_class = classification.get("incident_class")

        if not incident_class:
            raise ValueError("Classification must contain 'incident_class' field")

        retention_rules = profile.retention_rules

        rule = retention_rules.get(incident_class) or retention_rules.get("default")

        if not rule:
            raise ValueError("Retention rule not defined")

        return {
            "retention_class": rule.get("retention_class"),
            "minimum_retention_days": rule.get("minimum_retention_days"),
            "evidence_integrity_required": rule.get(
                "evidence_integrity_required",
                True,
            ),
        }
