import time
import os
import ulid
import logging

from contextlib import contextmanager
from contextvars import ContextVar

from wail_private.risk_worker import RiskWorker
from wail.runtime.state_store import state_store
from wail.runtime.audit_export import export_audit_artifact
from wail_private.risk_engine import evaluate_runtime_risk
from wail_private.policy_engine import PolicyEngine
from wail_private.escalation_manager import EscalationManager
from wail_private.risk_store import RiskStore
from wail_private.classification_engine import ClassificationEngine
from wail_private.jurisdiction_adapter import JurisdictionAdapter
from wail_private.control_policy import generate_runtime_action
from wail.runtime.content_proof import generate_content_proof
from wail.runtime.state_store import enforce_state
from wail.jurisdiction.regime_registry import RegimeRegistry
from wail.runtime.runtime_cli import render_runtime_summary
from wail_private.telemetry.state import record_runtime_usage
from wail.core.fingerprint import (
    build_request_fingerprint,
    build_trace_fingerprint,
)
from wail_private import runtime_decision_store
from wail_private.licensing.license import load_license, LicenseError
from wail_private.licensing.license_notice import show_downgrade_notice_if_needed
from wail_private.governance_gate import (
    apply_governance_if_entitled,
    attach_incident_regime_if_entitled,
)
from wail_private.recovery_engine import (
    evaluate_recovery,
    register_degradation,
)

from wail.runtime_config import _runtime_config
from wail.execution.bridge import (
    bind_runtime_trace,
    complete_runtime_trace,
    current_parent_agent_name,
)
from wail_private.execution.runtime_control_evidence import RuntimeControlEvidenceStore



logger = logging.getLogger("wail")
LICENSE_VALID = False
_ACTIVE_PLAN = None
_LICENSE_PAYLOAD = {}
_NEXT_LICENSE_TRANSITION = None


def _strictness_for_plan(plan, valid=True):
    if not valid or not plan:
        return "disabled"
    return "balanced"


_STRICTNESS_MODE = "disabled"


def _apply_license_result(result):
    global LICENSE_VALID
    global _ACTIVE_PLAN
    global _LICENSE_PAYLOAD
    global _NEXT_LICENSE_TRANSITION
    global _STRICTNESS_MODE

    if not result.get("valid"):
        LICENSE_VALID = False
        _ACTIVE_PLAN = None
        _LICENSE_PAYLOAD = result.get("payload") or {}
        _NEXT_LICENSE_TRANSITION = None
        _STRICTNESS_MODE = "disabled"
        return

    LICENSE_VALID = True
    _ACTIVE_PLAN = result.get("effective_plan")

    if not _ACTIVE_PLAN:
        raise LicenseError("License missing effective plan.")

    _LICENSE_PAYLOAD = result.get("payload") or {}

    now = int(time.time())

    transitions = []


    expires_at = _LICENSE_PAYLOAD.get("expires_at")
    if expires_at and expires_at > now:
        transitions.append(int(expires_at))

    trial_expires_at = result.get("trial_expires_at")
    if (
        result.get("trial_active")
        and trial_expires_at
        and trial_expires_at > now
    ):
        transitions.append(int(trial_expires_at))

    _NEXT_LICENSE_TRANSITION = min(transitions) if transitions else None
    _STRICTNESS_MODE = _strictness_for_plan(
        _ACTIVE_PLAN,
        LICENSE_VALID,
    )

def _refresh_license_if_needed():
    global _NEXT_LICENSE_TRANSITION

    if _NEXT_LICENSE_TRANSITION is None:
        return

    now = int(time.time())

    if now <= _NEXT_LICENSE_TRANSITION:
        return

    try:
        result = load_license()
        _apply_license_result(result)

    except Exception:
        _apply_license_result({
            "valid": False,
            "payload": _LICENSE_PAYLOAD,
        })


def refresh_license_state():
    _refresh_license_if_needed()
    show_downgrade_notice_if_needed(
        _ACTIVE_PLAN,
        _LICENSE_PAYLOAD,
    )

    return {
        "valid": LICENSE_VALID,
        "plan": _ACTIVE_PLAN,
        "issued_at": _LICENSE_PAYLOAD.get("issued_at"),
    }

try:
    _apply_license_result(load_license())

except Exception:
    LICENSE_VALID = False
    _ACTIVE_PLAN = None
    _LICENSE_PAYLOAD = {}
    _NEXT_LICENSE_TRANSITION = None
    _STRICTNESS_MODE = "disabled"

_STRICTNESS_MODE = _strictness_for_plan(_ACTIVE_PLAN, LICENSE_VALID)

_current_trace: ContextVar[dict | None] = ContextVar("current_trace", default=None)

_escalation_manager = EscalationManager()
_classification_engine = ClassificationEngine()


def _next_id():
    return str(ulid.new())


def get_current_trace_id():
    frame = _current_trace.get()
    if frame:
        return frame.get("trace_id")
    return None


def _attach_regime_snapshot(incident: dict) -> dict:

    regime_id = RegimeRegistry.get_active_regime()

    if not regime_id:
        return incident

    profile = JurisdictionAdapter._load_profile(regime_id)

    incident["regime"] = {
        "id": profile.id,
        "version": profile.version,
        "profile_hash": profile.content_hash(),
    }

    return incident


# =====================================================
# TRACE START
# =====================================================
start_ts = time.time()


def wail_start(
    model=None,
    provider=None,
    transport=None,
    invocation_context=None,
    sampling_params=None,
    prompt_hash=None,
):
    refresh_license_state()

    if not LICENSE_VALID:
        logger.warning("WAIL running in degraded mode")

    state_store.start()
    ok = enforce_state()

    if not ok:
        return {"wail_disabled": True}

    trace_id = _next_id()
    start = time.perf_counter()
    span_id = _next_id()

    parent_frame = _current_trace.get()
    parent_span_id = parent_frame.get("span_id") if parent_frame else None

    runtime_context = dict(_runtime_config)

    if invocation_context:
        runtime_context.update(
            dict(invocation_context)
        )

    invocation_context = runtime_context
    sampling_params = sampling_params or {}

    request_surface = {
        "model": model,
        "provider": provider,
        "transport": transport,
        "temperature": sampling_params.get("temperature"),
        "top_p": sampling_params.get("top_p"),
        "max_tokens": sampling_params.get("max_tokens"),
        "invocation_context": invocation_context,
        "prompt_hash": prompt_hash,
        "params_hash": None,
    }

    request_fingerprint = build_request_fingerprint(request_surface)
    parent_agent_name = current_parent_agent_name()

    frame = {

        "_parent_frame": parent_frame,

        # =========================
        # TRACE
        # =========================
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "start": start,

        # =========================
        # EXECUTION
        # =========================
        "transport": transport,
        "provider": provider,
        "model": model,
        "execution_target": None,
        "parent_agent_name": parent_agent_name,

        # =========================
        # ORIGINAL EXECUTION
        # =========================
        "initial_transport": transport,
        "initial_provider": provider,
        "initial_model": model,

        # =========================
        # REQUEST
        # =========================
        "invocation_context": invocation_context,
        "sampling": sampling_params,
        "request_fingerprint": request_fingerprint,
        "prompt_hash": prompt_hash,

        # =========================
        # RUNTIME
        # =========================
        "retry_count": 0,
        "events": [],
        "first_token_ts": None,
        "input_token_count": 0,
        "output_token_count": 0,
        "error_flag": False,
        "timeout_flag": False,
        "interrupted_flag": False,
        "stream_surface": {},
        "ttft_watcher": None,
    }
    _current_trace.set(frame)

    try:
        execution_kind = (
            invocation_context.get("type")
            or "model"
        )

        bind_runtime_trace(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            kind=execution_kind,
            name=model,
        )
    except Exception:
        logger.exception(
            "WAIL execution instrumentation failed during trace binding; "
            "continuing runtime request without execution binding"
        )

    return trace_id


# =====================================================
# UPDATE HELPERS
# =====================================================


def update_sampling_config(temperature=None, top_p=None, max_tokens=None):
    frame = _current_trace.get()
    if not frame:
        return
    frame["sampling"] = {
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
    }


def update_token_usage(input_tokens=0, output_tokens=0):
    frame = _current_trace.get()

    if not frame:
        return

    frame["input_token_count"] += input_tokens or 0
    frame["output_token_count"] += output_tokens or 0


def update_stream_surface(surface: dict):
    frame = _current_trace.get()
    if not frame:
        return
    frame["stream_surface"].update(surface)


def append_event(event: dict):
    frame = _current_trace.get()
    if not frame:
        return
    frame["events"].append(event)


def emit_event(event_type: str, payload=None):
    frame = _current_trace.get()
    if not frame:
        return
    frame["events"].append({"type": event_type, "payload": payload or {}})


def wail_retry():
    frame = _current_trace.get()
    if frame:
        frame["retry_count"] += 1

def mark_runtime_error():
    frame = _current_trace.get()
    if frame:
        frame["error_flag"] = True


def mark_runtime_interrupted():
    frame = _current_trace.get()
    if frame:
        frame["error_flag"] = True
        frame["interrupted_flag"] = True


def mark_first_token():

    frame = _current_trace.get()

    if not frame:
        return

    if frame["first_token_ts"] is None:
        frame["first_token_ts"] = time.perf_counter()


def set_ttft_watcher(watcher):

    frame = _current_trace.get()  

    if not frame:
        
        return

    frame["ttft_watcher"] = watcher   


def get_ttft_watcher():
    frame = _current_trace.get()
    if not frame:
        return None
    return frame.get("ttft_watcher")


def clear_ttft_watcher():
    frame = _current_trace.get()
    if not frame:
        return
    frame["ttft_watcher"] = None



# =====================================================
# TRACE END
# =====================================================


def wail_end(ctx=None):

    frame = ctx or _current_trace.get()

    if not frame or not isinstance(frame, dict):
        return

    if not LICENSE_VALID:
        frame["degraded_mode"] = True

    try:
        end = time.perf_counter()

        duration_ms = int(max(end - frame["start"], 0) * 1000)

        first_token_latency_ms = None

        if frame["first_token_ts"] is not None:
            first_token_latency_ms = int(
                (frame["first_token_ts"] - frame["start"]) * 1000
            )

        input_tokens = frame["input_token_count"]
        output_tokens = frame["output_token_count"]

        stream_chunk_count = (
            frame["stream_surface"].get("stream_chunk_count")
            if frame["stream_surface"]
            else None
        )
        latency_per_output_token_ms = None
        if output_tokens and output_tokens > 0:
            latency_per_output_token_ms = int(duration_ms / output_tokens)

        runtime_surface = {
            "duration_ms": duration_ms,
            "first_token_latency_ms": first_token_latency_ms,
            "input_token_count": input_tokens,
            "output_token_count": output_tokens,
            "stream_chunk_count": stream_chunk_count,
            "latency_per_output_token_ms": latency_per_output_token_ms,
            "retry_count": frame["retry_count"],
            "error_flag": frame["error_flag"],
            "timeout_flag": frame["timeout_flag"],
            "interrupted_flag": frame["interrupted_flag"],
            "stream_surface": dict(frame["stream_surface"]),
        }
        trace_fingerprint = build_trace_fingerprint(runtime_surface)

        content_proof_input = {
            "model": frame["model"],
            "provider": frame["provider"],
            "transport": frame["transport"],
            "request_fingerprint": frame["request_fingerprint"],
            "invocation_context": frame["invocation_context"],
            "sampling": frame["sampling"],
            "runtime_surface": runtime_surface,
        }

        if frame.get("prompt_hash") is not None:
            content_proof_input["prompt_hash"] = frame.get("prompt_hash")

        content_proof = generate_content_proof(content_proof_input)

        trace = {
            "trace_id": frame["trace_id"],
            "span_id": frame.get("span_id"),
            "parent_span_id": frame.get("parent_span_id"),
            "model": frame["model"],
            "provider": frame["provider"],
            "transport": frame["transport"],
            "invocation_context": frame["invocation_context"],
            "parent_agent_name": frame.get("parent_agent_name"),

            "metadata": {
                "trace_id": frame["trace_id"],
                "span_id": frame.get("span_id"),
                "parent_span_id": frame.get("parent_span_id"),
                "model": frame["model"],
                "provider": frame["provider"],
                "transport": frame["transport"],
                "invocation_context": frame["invocation_context"],
            },

            "sampling": frame["sampling"],
            "events": frame["events"],
            "request_fingerprint": frame["request_fingerprint"],
            "prompt_hash": frame.get("prompt_hash"),
            "trace_fingerprint": trace_fingerprint,

            "execution_target": frame.get("execution_target"),
            "routing_hysteresis": frame.get("routing_hysteresis"),
            "runtime_surface": runtime_surface,
            "content_proof": content_proof,
        }
        control_exec = {}

        ctx = frame.get("invocation_context", {})

        executed = ctx.get("_control_executed")
        action = ctx.get("_control_action")

        if executed is not None:
            control_exec["executed"] = executed

        if action is not None:
            control_exec["action"] = action

        if control_exec:
            trace["control_execution"] = control_exec

        if not LICENSE_VALID:
            trace.pop("drift_analysis", None)
            trace.pop("incident", None)
            trace.pop("escalation", None)
            trace.pop("enforcement", None)
            trace.pop("control", None)
            trace.pop("control_execution", None)

            RiskWorker.get_instance().enqueue(trace)

            artifact_dir = os.path.join(os.getcwd(), "wail_audit")
            os.makedirs(artifact_dir, exist_ok=True)

            export_audit_artifact(
                input_payload=trace,
                policy_version="disabled",
                score=0,
                severity="none",
                enforcement_decision="none",
                output_path=os.path.join(
                    artifact_dir, f"trace_{trace['trace_id']}.json"
                ),
            )

            return

        store = RiskStore.get_instance()
        store.update(trace)
        policy = PolicyEngine(_ACTIVE_PLAN)

        risk_result = evaluate_runtime_risk(
            trace
        )
        risk_block = risk_result.get("risk", {})
        composite_score = risk_block.get("composite_score", 0)
        risk_score = min(composite_score, 100)
        severity = risk_block.get("severity")
        count = store.update_escalation(trace, severity)
        decision = policy.evaluate(
            risk_score=risk_score,
            severity=severity,
            strictness_mode=_STRICTNESS_MODE,
            consecutive_critical_count=count,
        )
        trace["policy_severity"] = decision.severity
        trace["policy_enforcement"] = decision.enforcement_decision
        trace["policy_escalated"] = decision.escalation_applied
        trace["risk"] = risk_block
        store.update_history(trace)
        trace["drift_analysis"] = {
            "signals": risk_result.get("signals", []),
            "sla": {
                "severity": risk_block.get("sla_severity"),
                "score": risk_block.get("surfaces", {}).get("sla_impact", 0),
            },

            "dominant_cause": risk_block.get("dominant_surface"),
            "infra_score": risk_block.get("surfaces", {}).get("infra_health", 0),
            "workload_score": risk_block.get("surfaces", {}).get("workload", 0),
            "baseline_snapshot": risk_result.get("baseline_snapshot", {}),
        }
        trace["decision_snapshot"] = risk_result.get("decision_snapshot", {})
        trace["control_outcome"] = risk_result.get("control_outcome")
        provider = trace.get("provider")
        model = trace.get("model")
        runtime = trace.get("runtime_surface", {})
        latency = runtime.get("duration_ms")
        error_flag = runtime.get("error_flag", False)
        incident = _classification_engine.classify(trace)
        incident["trigger_signals"] = risk_result.get("signals", [])
        incident["signal_metrics"] = {
            **incident.get("signal_metrics", {}),
            **risk_result.get("signal_metrics", {}),
        }
        trace["incident"] = incident
        trace["incident"] = attach_incident_regime_if_entitled(
            _ACTIVE_PLAN,
            trace["incident"],
            _attach_regime_snapshot,
        )
        

        if provider and model and latency:
            key = f"{provider}:{model}"

            if "model_registry" not in state_store._runtime_cache:
                state_store._runtime_cache["model_registry"] = {}

            registry = state_store._runtime_cache["model_registry"]

            existing = registry.get(key)

            if not existing:

                registry[key] = {
                    "latency_p95": int(latency),
                    "error_rate": 1 if error_flag else 0,
                    "sample_count": 1,
                }

            else:

                prev_latency = existing.get("latency_p95", int(latency))

                new_latency = (prev_latency + int(latency)) // 2

                if new_latency < 0:
                    new_latency = 0

                existing["latency_p95"] = new_latency
                existing["sample_count"] = int(existing.get("sample_count", 1)) + 1

                if error_flag:
                    existing["error_rate"] = existing.get("error_rate", 0) + 1

        incident = trace.get("incident", {})
        pre = trace.get("pre_incident", {})

        persistence = pre.get("persistence", 0)
        severity = incident.get("source_severity")

        if severity not in ("major", "critical") and persistence >= 2:
            severity = "critical"

        escalation_result = _escalation_manager.process(
            license_plan=_ACTIVE_PLAN,
            severity=severity,
            provider=trace["provider"],
            model=trace["model"],
            service=trace["invocation_context"].get("service", "unknown"),
            env=trace["invocation_context"].get("env", "unknown"),
            trace_id=trace["trace_id"],
            trace=trace,
        )

        trace["escalation"] = escalation_result
        trace["enforcement"] = escalation_result["enforcement"]

        control_allowed = frame.get(
            "invocation_context", {}
        ).get("_control_allowed", True)

        if control_allowed:
            trace["control"] = generate_runtime_action(trace)
        else:
            trace["control"] = {
                "decision": "observe",
                "reason": "control_quota_exhausted",
            }
        control_decision = trace.get("control", {})
        enforcement = trace.get("enforcement", {})

        if control_allowed and enforcement.get("decision") == "reroute":
            runtime_decision = {
                **control_decision,
                "decision": "reroute",
                "reason": "escalation_threshold_reached",
            }
        else:
            runtime_decision = control_decision

        trace["effective_execution_decision"] = dict(runtime_decision)

        RuntimeControlEvidenceStore.get_instance().save(
            trace_id=trace["trace_id"],
            decision=runtime_decision,
        )

        if (
            control_allowed
            and runtime_decision.get("decision") in ("retry", "reroute")
        ):
            pending_runtime_decision = dict(runtime_decision)
            pending_runtime_decision["_source_trace_id"] = trace["trace_id"]

            decision_context = (
                trace.get("invocation_context")
                or {}
            )

            decision_surface = (
                "tool"
                if decision_context.get("type") == "tool"
                else "model"
            )

            runtime_decision_store.save(
                pending_runtime_decision,
                surface=decision_surface,
            )

        apply_governance_if_entitled(_ACTIVE_PLAN, trace)

        RiskWorker.get_instance().enqueue(trace)

        artifact_dir = os.path.join(os.getcwd(), "wail_audit")
        os.makedirs(artifact_dir, exist_ok=True)
        execution_target = trace.get("execution_target") or {}
        from_m = execution_target.get("from_model")
        to_m = execution_target.get("to_model")

        invocation_context = trace.get("invocation_context") or {}
        control_executed = invocation_context.get("_control_executed") is True
        control_action = invocation_context.get("_control_action")

        target_changed = bool(
            from_m
            and to_m
            and from_m != to_m
        )

        reroute_applied = bool(
            control_executed
            and control_action == "reroute"
        )

        execution_changed = target_changed or reroute_applied

        trace["execution"] = {
            "initial_provider": execution_target.get("from_provider") or trace.get("provider"),
            "initial_model": from_m or trace.get("model"),
            "final_provider": execution_target.get("to_provider") or trace.get("provider"),
            "final_model": to_m or trace.get("model"),
            "intervened": execution_changed,
            "rerouted": reroute_applied or target_changed,
        }

        if target_changed and "metadata" in trace:
            trace["metadata"]["model"] = to_m
            trace["metadata"]["provider"] = (
                execution_target.get("to_provider")
                or execution_target.get("provider")
                or trace.get("provider")
            )
       

        ctx = trace["metadata"].get("invocation_context", {})

        segment = (
            f"{trace['metadata']['provider']}:"
            f"{ctx.get('service', 'default')}:"
            f"{ctx.get('env', 'default')}"
        )
        recovery = evaluate_recovery(
            segment=segment,
            duration_ms=trace["runtime_surface"]["duration_ms"],
        )

        if decision.severity == "critical":
            register_degradation(
                segment=segment,
                duration_ms=trace["runtime_surface"]["duration_ms"],
            )
        trace["control_outcome"] = recovery

        export_audit_artifact(
            input_payload=trace,
            policy_version="v1",
            score=risk_score,
            severity=decision.severity,
            enforcement_decision=trace["enforcement"]["mode"],
            output_path=os.path.join(
                artifact_dir,
                f"trace_{trace['trace_id']}.json",
            ),
            plan=_ACTIVE_PLAN,
        )

        render_runtime_summary(
            trace=trace,
            plan=_ACTIVE_PLAN,
        )

    finally:
        record_runtime_usage(
            duration_ms / 1000.0,
            provider=frame.get("provider"),
            model=frame.get("model"),
        )

        from wail_private.telemetry.client import trigger_telemetry
        trigger_telemetry()

        try:
            complete_runtime_trace(
                failed=bool(
                    frame.get("error_flag")
                    or frame.get("timeout_flag")
                    or frame.get("interrupted_flag")
                )
            )
        except Exception:
            logger.exception(
                "WAIL execution instrumentation failed during trace completion; "
                "continuing runtime finalization"
            )
        finally:
            _current_trace.set(
                frame.get("_parent_frame")
            )


@contextmanager
def wail_inference(
    model=None,
    provider=None,
    invocation_context=None,
    sampling_params=None,
):

    wail_start(
        model=model,
        provider=provider,
        invocation_context=invocation_context,
        sampling_params=sampling_params,
    )

    try:
        yield
    except Exception:
        mark_runtime_error()
        wail_retry()
        raise
    except BaseException:
        mark_runtime_interrupted()
        raise
    finally:
        wail_end()


__all__ = [
    "wail_inference",
    "update_token_usage",
    "update_stream_surface",
    "update_sampling_config",
    "emit_event",
    "append_event",
    "mark_first_token",
    "mark_runtime_error",
    "mark_runtime_interrupted",
    "wail_retry",
    "get_current_trace_id",
]