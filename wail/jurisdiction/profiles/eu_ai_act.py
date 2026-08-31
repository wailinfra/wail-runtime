from wail.jurisdiction.regulatory_profile import RegulatoryProfile


def get_profile():

    return RegulatoryProfile(
        id="EU_AI_ACT",
        version="1.0.0",
        # -------------------------------------------------
        # CORE → LEGAL RETENTION MAPPING
        # -------------------------------------------------
        retention_rules={
            "LOW_IMPACT": {
                "minimum_retention_days": 90,
                "evidence_integrity_required": False,
            },
            "MEDIUM_IMPACT": {
                "minimum_retention_days": 180,
                "evidence_integrity_required": True,
            },
            "HIGH_IMPACT": {
                "minimum_retention_days": 365,
                "evidence_integrity_required": True,
            },
            "SYSTEMIC_RISK": {
                "minimum_retention_days": 1825,  
                "evidence_integrity_required": True,
            },
        },
        # -------------------------------------------------
        # CORE → DISCLOSURE MAPPING
        # -------------------------------------------------
        disclosure_rules={
            "internal_only": {
                "disclosure_required": False,
                "deadline_days": None,
            },
            "supervisory_notification": {
                "disclosure_required": True,
                "deadline_days": 15,
            },
            "mandatory_report": {
                "disclosure_required": True,
                "deadline_days": 7,
            },
            "public_disclosure": {
                "disclosure_required": True,
                "deadline_days": 3,
            },
        },
        # -------------------------------------------------
        # CORE → OVERSIGHT MAPPING
        # -------------------------------------------------
        oversight_requirements={
            "internal_review": "INTERNAL_AUDIT",
            "compliance_team": "COMPLIANCE_ESCALATION",
            "executive_escalation": "BOARD_NOTIFICATION",
            "external_authority": "EU_SUPERVISORY_AUTHORITY",
        },
        escalation_overrides={},
        reporting_format={
            "type": "EU_STANDARD_REPORT",
        },
        article_bindings={
            "EU_AI_ACT_ARTICLE_12": [
                "trace_fingerprint",
                "artifact_hash",
                "incident_class",
                "retention_class",
            ]
        },
    )
