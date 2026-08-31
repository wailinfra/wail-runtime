import os
import json
import hashlib
import tempfile
import math
import time
from statistics import mean, pstdev
from pathlib import Path
import threading
from wail.core.canonical import canonical_json
from wail_private.risk_store import RiskStore
from wail.runtime.state_fingerprint import compute_state_hash
from wail_private.governance_lifecycle import GovernanceLifecycleEngine
from wail.runtime.hash_input import build_hash_input
from wail.runtime.canonical_serializer import compute_artifact_hash
from wail.runtime.canonical_serializer import build_canonical_object
from wail.runtime.content_proof import generate_content_proof
from wail_private.action_engine import generate_recommendation
from wail_private.impact_calculator import build_impact
from wail_private.pre_incident_engine import evaluate_pre_incident
from wail.runtime.tech_artifact import build_tech_artifact
from wail_private.licensing.features import artifact_permissions
from wail.crypto.hash_utils import (
    calculate_artifact_hash,
    calculate_canonical_hash,
)


from wail_private.artifact_signing import sign_integrity_hash

from wail.runtime.determinism_spec import DETERMINISM_SPEC_VERSION
from wail.runtime.canonical_serializer import (
    compute_schema_hash,
)
from wail_private.risk_store import BASELINE_BUILD_SIZE
ARTIFACT_VERSION = 14
FULL_STREAM_DIR = Path("wail_state") / "full_stream"


# ============================================================
# ARTIFACT CHAIN (LEDGER)
# ============================================================

CHAIN_FILE = Path("wail_state") / "artifact_chain.json"


def _load_chain():
    if CHAIN_FILE.exists():
        try:
            return json.loads(CHAIN_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_chain(chain):
    CHAIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHAIN_FILE.write_text(json.dumps(chain))


def _segment_key(metadata):
    ctx = metadata.get("invocation_context", {})

    provider = metadata.get("provider")
    model = metadata.get("model")
    service = ctx.get("service")
    env = ctx.get("env")

    return f"{provider}:{model}:{service}:{env}"


# ============================================================
# PERCENTILE
# ============================================================


def _percentile(values, p):
    if not values:
        return 0

    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (p / 100)
    f = math.floor(k)
    c = math.ceil(k)

    if f == c:
        return sorted_vals[int(k)]

    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return int(d0 + d1)


# ============================================================
# DISTRIBUTION
# ============================================================


def _build_distribution(values):

    clean_values = [v for v in values if isinstance(v, (int, float))]

    if not clean_values:
        return {
            "min": 0,
            "max": 0,
            "mean": 0,
            "std_dev": 0,
            "p50": 0,
            "p75": 0,
            "p90": 0,
            "p95": 0,
            "p99": 0,
            "sample_count": 0,
        }

    return {
        "min": min(clean_values),
        "max": max(clean_values),
        "mean": int(mean(clean_values)),
        "std_dev": int(pstdev(clean_values)) if len(clean_values) > 1 else 0,
        "p50": _percentile(clean_values, 50),
        "p75": _percentile(clean_values, 75),
        "p90": _percentile(clean_values, 90),
        "p95": _percentile(clean_values, 95),
        "p99": _percentile(clean_values, 99),
        "sample_count": len(clean_values),
    }


# ============================================================
# STATISTICS
# ============================================================


def _build_statistics(trace):

    store = RiskStore.get_instance()
    segment = store.get_segment(trace)

    runtime_surface = trace.get("runtime_surface", {})

    current_latency = runtime_surface.get("duration_ms")
    current_first = runtime_surface.get("first_token_latency_ms")

    latencies = []
    first_tokens = []

    if segment:
        latencies.extend(segment.latencies)
        first_tokens.extend(segment.first_token_latencies)

    if isinstance(current_latency, (int, float)):
        latencies.append(current_latency)

    if isinstance(current_first, (int, float)):
        first_tokens.append(current_first)

    latency_stats = _build_distribution(latencies)
    first_token_stats = _build_distribution(first_tokens)

    sample_count = latency_stats.get("sample_count", 0)

    statistics = {
        "latency": latency_stats,
        "runtime_calibration": {
            "current": sample_count,
            "required": BASELINE_BUILD_SIZE,
            "ready": sample_count >= BASELINE_BUILD_SIZE,
        },
    }

    if first_token_stats["sample_count"] > 0:
        statistics["first_token"] = first_token_stats

    return statistics



def _build_governance_layer(
    trace_id,
    incident,
    obligation,
    escalation,
    regulatory,
):

    if not incident or not obligation:
        return {
            "events": [],
            "regulatory_relevant": False,
        }

    tier = obligation.get("tier", 1)
    detection_ts = int(time.time() * 1000)

    incident_id = f"{trace_id}:{incident.get('incident_class')}"

    engine = GovernanceLifecycleEngine(
        incident_id=incident_id,
        tier=tier,
        detection_timestamp_ms=detection_ts,
    )

    if escalation and escalation.get("escalated"):

        evidence_hash = hashlib.sha256(
            canonical_json(incident).encode("utf-8")
        ).hexdigest()

        engine.transition(
            actor_id="system_auto",
            reason_code="auto_ack_on_escalation",
            evidence_hash=evidence_hash,
            timestamp_ms=int(time.time() * 1000),
        )

    state = engine.export_state()

    regulatory_valid = False

    regime = obligation.get("regime_obligation")

    if regime:
        regulatory_valid = regime.get("report_required", False)

    state["regulatory_relevant"] = regulatory_valid

    return state


# ============================================================
# EXPORT
# ============================================================


def export_audit_artifact(
    input_payload,
    policy_version,
    score,
    severity,
    enforcement_decision,
    output_path,
    plan=None,
):
    reroute_response = None
    if not input_payload.get("_wail_async"):
        payload = dict(input_payload)
        payload["_wail_async"] = True

        threading.Thread(
            target=export_audit_artifact,
            args=(
                payload,
                policy_version,
                score,
                severity,
                enforcement_decision,
                output_path,
                plan,
            ),
            daemon=False,
        ).start()
        return

    state_hash = compute_state_hash()
    runtime_surface = input_payload["runtime_surface"]
    trace_id = input_payload["trace_id"]
    stream_surface = runtime_surface.get("stream_surface") or {}
    full_timeline = stream_surface.get("full_timeline")

    if full_timeline:
        FULL_STREAM_DIR.mkdir(parents=True, exist_ok=True)
        timeline_path = FULL_STREAM_DIR / f"{trace_id}.json"

        with open(timeline_path, "w", encoding="utf-8") as tf:
            json.dump(
                {
                    "trace_id": trace_id,
                    "full_timeline": full_timeline,
                },
                tf,
                indent=2,
            )

        stream_surface = dict(stream_surface)
        stream_surface.pop("full_timeline", None)

    duration = runtime_surface.get("duration_ms", 0)
    first_token = runtime_surface.get("first_token_latency_ms")

    timing = {
        "duration_ms": duration,
        "first_token_latency_ms": first_token,
        "input_token_count": runtime_surface.get("input_token_count", 0),
        "output_token_count": runtime_surface.get("output_token_count", 0),
        "stream_chunk_count": runtime_surface.get("stream_chunk_count"),
        "latency_per_output_token_ms": runtime_surface.get(
            "latency_per_output_token_ms"
        ),
    }

    incident = input_payload.get("incident")
    if not isinstance(incident, dict):
        incident = {}
    obligation = input_payload.get("obligation")
    escalation = input_payload.get("escalation")
    regulatory = input_payload.get("regulatory")

    statistics_block = _build_statistics(input_payload)
 
    if "stream_surface" in runtime_surface:
        if "full_timeline" in runtime_surface["stream_surface"]:
            del runtime_surface["stream_surface"]["full_timeline"]

    content_proof_input = {
        "model": input_payload["model"],
        "provider": input_payload["provider"],
        "request_fingerprint": input_payload["request_fingerprint"],
        "invocation_context": input_payload["invocation_context"],
        "runtime_surface": runtime_surface,
    }

    if input_payload.get("prompt_hash") is not None:
        content_proof_input["prompt_hash"] = input_payload.get("prompt_hash")

    content_proof = generate_content_proof(content_proof_input)
    execution_target = input_payload.get("execution_target")

    if not execution_target:
        execution_target = {
            "from_provider": input_payload.get("provider"),
            "from_model": input_payload.get("model"),

            "to_provider": input_payload.get("provider"),
            "to_model": input_payload.get("model"),
        }

    from_model = execution_target.get("from_model")
    to_model = execution_target.get("to_model")

  
    if not from_model:
        from_model = input_payload.get("model")

    if not to_model:
        to_model = execution_target.get("model")

    execution_changed = (
        from_model is not None
        and to_model is not None
        and from_model != to_model
    )    

  
    artifact = {
        "artifact_version": ARTIFACT_VERSION,
        "metadata": {
            "trace_id": trace_id,
            "timestamp_ms": int(time.time() * 1000),
            "model": input_payload["model"],
            "provider": input_payload["provider"],
            "invocation_context": input_payload["invocation_context"],
        },
        "execution": {
            "initial_provider": execution_target.get("from_provider") or input_payload.get("provider"),
            "initial_model": from_model or input_payload.get("model"),
            "final_provider": execution_target.get("to_provider") or execution_target.get("provider"),
            "final_model": to_model,
            "rerouted": execution_changed,
            "intervened": execution_changed,
        },
        "execution_target": execution_target,
        "routing_hysteresis": input_payload.get("routing_hysteresis"),
        "content_proof": content_proof,
        "runtime": {
            "timing": timing,
            "events": input_payload["events"],
            "reliability": {
                "retry_count": runtime_surface.get("retry_count", 0),
                "error_flag": runtime_surface.get("error_flag", False),
                "timeout_flag": runtime_surface.get("timeout_flag", False),
            },
            "stream_surface": stream_surface,
        },
        "statistics": statistics_block,
        "drift_analysis": input_payload.get("drift_analysis", {}),
        "risk": input_payload.get("risk", {}),
        "decision_snapshot": input_payload.get("decision_snapshot", {}),
        "incident": incident,
        "obligation": obligation,
        "escalation": escalation,
        "enforcement": input_payload.get("enforcement", {}),
        "governance": _build_governance_layer(
            trace_id,
            incident,
            obligation,
            escalation,
            regulatory,
        ),
    }
  
    artifact["impact"] = build_impact(artifact)
    if execution_changed:
        artifact["metadata"]["model"] = to_model
        artifact["metadata"]["provider"] = execution_target.get("to_provider") or execution_target.get("provider")

    pre_incident = evaluate_pre_incident(artifact) if incident else None

    if pre_incident:
        artifact["pre_incident"] = pre_incident

    control = input_payload.get("control", {})
    enforcement = input_payload.get("enforcement", {}) or {}
    effective_execution_decision = (
        input_payload.get("effective_execution_decision", {}) or {}
    )

    effective_decision = effective_execution_decision.get("decision")
    effective_reason = effective_execution_decision.get("reason")

    if not incident:
        action = {}
    else:
        action = generate_recommendation(artifact)

    artifact["control"] = control

    if not incident:
        execution_flow = {
            "stage_1_detection": {
                "drift_detected": False,
                "risk_level": None,
            },
            "stage_2_pre_incident": {
                "triggered": False,
                "level": None,
            },
            "stage_3_decision": {},
            "stage_4_outcome": {},
        }
    else:
        execution_flow = {
            "stage_1_detection": {
                "drift_detected": artifact.get("drift_analysis") is not None,
                "risk_level": artifact.get("risk", {}).get("severity"),
            },
            "stage_2_pre_incident": {
                "triggered": pre_incident.get("triggered") if pre_incident else False,
                "level": pre_incident.get("level") if pre_incident else None,
            },
            "stage_3_decision": {
                "control_decision": control.get("decision"),
                "control_reason": control.get("reason"),
                "enforcement_decision": enforcement.get("decision"),
                "effective_decision": effective_decision,
                "effective_reason": effective_reason,
            },
            "stage_4_outcome": {
                "execution_changed": execution_changed,
            },
        }
    artifact["execution_flow"] = execution_flow
    if incident:
        artifact["recommended_action"] = action

    artifact["determinism"] = {
        "request_fingerprint": input_payload["request_fingerprint"],
        "trace_fingerprint": input_payload["trace_fingerprint"],
        "prompt_hash": input_payload.get("prompt_hash"),
    }
    artifact["determinism_spec_version"] = 1
    artifact["canonical_schema_hash"] = calculate_canonical_hash(artifact)
    chain = _load_chain()
    segment = _segment_key(artifact["metadata"])
    previous_hash = chain.get(segment)
    artifact_hash = calculate_artifact_hash(artifact)
    artifact["integrity"] = {
        "state_hash": state_hash,
        "policy_version": policy_version,
        "enforcement_decision": artifact.get("enforcement", {}).get("decision"),
        "previous_artifact_hash": previous_hash,
        "artifact_hash": artifact_hash,
    }

    artifact["determinism_spec_version"] = DETERMINISM_SPEC_VERSION

    schema_snapshot = {
        "artifact_version": ARTIFACT_VERSION,
        "structure_keys": sorted(list(artifact.keys())),
    }

    artifact["canonical_schema_hash"] = compute_schema_hash(schema_snapshot)

    if regulatory:
        artifact["regulatory"] = regulatory

    canonical_artifact = build_canonical_object(artifact)

    hash_input = build_hash_input(canonical_artifact)

    artifact_hash = compute_artifact_hash(hash_input)

    artifact["integrity"]["artifact_hash"] = artifact_hash

    chain[segment] = artifact_hash
    _save_chain(chain)

    artifact["integrity"].update(sign_integrity_hash(artifact_hash))

    execution_target = artifact.get("execution_target") or {}

    from_m = execution_target.get("from_model")
    to_m = execution_target.get("to_model")

    execution_changed = (
        from_m is not None
        and to_m is not None
        and from_m != to_m
    )

    artifact["execution"]["intervened"] = execution_changed
    artifact["execution"]["rerouted"] = execution_changed

    if execution_changed:
        artifact["execution"]["final_model"] = to_m
        artifact["execution"]["final_provider"] = execution_target.get("to_provider")

        artifact["metadata"]["model"] = to_m
        artifact["metadata"]["provider"] = execution_target.get("to_provider")
  
    tech_artifact = build_tech_artifact(artifact)
    tech_path = str(output_path).replace(".json", "_tech.json")
    permissions = artifact_permissions(plan)
    if permissions["full"]:
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix=".tmp_", dir=os.path.dirname(output_path)
        )

        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(artifact, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, output_path)

        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except:
                    pass

    if permissions["tech"]:
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix=".tmp_", dir=os.path.dirname(tech_path)
        )

        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(tech_artifact, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, tech_path)

        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except:
                    pass

    if reroute_response is not None:
        return reroute_response



def export_audit_artifact_async(
    input_payload,
    policy_version,
    score,
    severity,
    enforcement_decision,
    output_path,
    plan=None,
):
    threading.Thread(
        target=export_audit_artifact,
        args=(
            input_payload,
            policy_version,
            score,
            severity,
            enforcement_decision,
            output_path,
            plan,
        ),
        daemon=False,
    ).start()
