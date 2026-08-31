from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

from wail.jurisdiction.regulatory_profile import RegulatoryProfile


@dataclass(frozen=True)
class JurisdictionContext:
    profile: RegulatoryProfile
    incident_id: int
    classification: Dict[str, Any]
    severity: str
    tier: str

    def snapshot(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "regime_id": self.profile.id,
            "regime_version": self.profile.version,
            "regime_profile_hash": self.profile.content_hash(),
            "classification": self.classification,
            "severity": self.severity,
            "tier": self.tier,
        }
