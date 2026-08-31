from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class RegulatoryObligation:
    disclosure_required: bool
    disclosure_deadline_days: int | None
    retention_class: str
    minimum_retention_days: int
    evidence_integrity_required: bool
    oversight_level: str
    notification_targets: Dict[str, Any]
    reporting_required: bool


class ObligationResolver:

    @staticmethod
    def resolve(context):

        profile = context.profile
        core = (context.classification or {}).get("core_obligation") or {}

        # -------------------------------------------------
        # CORE FIELDS
        # -------------------------------------------------

        core_retention = core.get("retention_class")
        core_disclosure = core.get("disclosure_class")
        core_oversight = core.get("oversight_level")

        # -------------------------------------------------
        # RETENTION 
        # -------------------------------------------------

        retention_rules = profile.retention_rules.get(core_retention)

        if not retention_rules:
            raise ValueError(
                f"No retention mapping defined for core retention class '{core_retention}'"
            )

        retention_class = core_retention
        minimum_retention_days = retention_rules.get("minimum_retention_days")
        evidence_integrity_required = retention_rules.get("evidence_integrity_required")

        # -------------------------------------------------
        # DISCLOSURE 
        # -------------------------------------------------

        disclosure_rules = profile.disclosure_rules.get(core_disclosure)

        if disclosure_rules:
            disclosure_required = disclosure_rules.get("disclosure_required", False)
            disclosure_deadline_days = disclosure_rules.get("deadline_days")
        else:
            disclosure_required = False
            disclosure_deadline_days = None

        # -------------------------------------------------
        # OVERSIGHT 
        # -------------------------------------------------

        oversight_level = profile.oversight_requirements.get(core_oversight, "NONE")

        # -------------------------------------------------
        # REPORTING LOGIC
        # -------------------------------------------------

        reporting_required = disclosure_required

        # -------------------------------------------------
        # NOTIFICATION TARGETS
        # -------------------------------------------------

        notification_targets = {}

        if oversight_level in ["EU_SUPERVISORY_AUTHORITY"]:
            notification_targets = {
                "regulator": True,
            }
        elif oversight_level in ["BOARD_NOTIFICATION"]:
            notification_targets = {
                "board": True,
            }
        elif oversight_level in ["COMPLIANCE_ESCALATION"]:
            notification_targets = {
                "compliance_team": True,
            }

        return RegulatoryObligation(
            disclosure_required=disclosure_required,
            disclosure_deadline_days=disclosure_deadline_days,
            retention_class=retention_class,
            minimum_retention_days=minimum_retention_days,
            evidence_integrity_required=evidence_integrity_required,
            oversight_level=oversight_level,
            notification_targets=notification_targets,
            reporting_required=reporting_required,
        )
