from typing import Dict, Any
from wail_private.impact_calculator import build_impact

class ArtifactBuilder:

    @staticmethod
    def build(trace: Dict[str, Any]) -> Dict[str, Any]:
        artifact = {
            "artifact_version": 14,
            "metadata": trace.get("metadata"),
            "runtime": {"timing": trace.get("runtime_surface", {})},
            "statistics": trace.get("statistics"),
            "drift_analysis": trace.get("drift_analysis"),
            "incident": trace.get("incident"),

            "control": trace.get("control"),
            "execution": trace.get("execution"),

            "obligation": trace.get("obligation"),
            "core_obligation": trace.get("core_obligation"),
            "escalation": trace.get("escalation"),
            "enforcement": trace.get("enforcement"),
            "governance": trace.get("governance"),

            "determinism": {
                "request_fingerprint": trace.get("request_fingerprint"),
                "trace_fingerprint": trace.get("trace_fingerprint"),
            },

            "integrity": trace.get("integrity"),
            "determinism_spec_version": trace.get("determinism_spec_version"),
            "canonical_schema_hash": trace.get("canonical_schema_hash"),
        }
        artifact["impact"] = build_impact(artifact)
        return artifact
