from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from typing import Dict, Any


def _canonical_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RegulatoryProfile:
    id: str
    version: str
    retention_rules: Dict[str, Any]
    disclosure_rules: Dict[str, Any]
    oversight_requirements: Dict[str, Any]
    escalation_overrides: Dict[str, Any]
    reporting_format: Dict[str, Any]
    article_bindings: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "retention_rules": self.retention_rules,
            "disclosure_rules": self.disclosure_rules,
            "oversight_requirements": self.oversight_requirements,
            "escalation_overrides": self.escalation_overrides,
            "reporting_format": self.reporting_format,
            "article_bindings": self.article_bindings,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.to_dict())

    def content_hash(self) -> str:
        return _sha256(self.canonical_json())

    def snapshot(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "profile_hash": self.content_hash(),
        }
