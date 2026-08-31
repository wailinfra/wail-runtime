import glob
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from openai import OpenAI

import wail
from wail.runtime.state_store import get_state_store
from wail_private import runtime_decision_store
from wail_private.control_executor import ControlExecutor
from wail_private.routing.hysteresis import clear as clear_hysteresis


# ==========================================================
# CONFIGURATION
# ==========================================================

BASELINE_SIZE = 30
SPIKE_COUNT = 6
OBSERVATION_COUNT = 12

PRIMARY_MODEL = "llama3.2:3b"
SECONDARY_MODEL = "llama3.2:1b"

SPIKE_DELAY_SECONDS = 3.0
BASELINE_PROMPT = "What is 2 + 2? Answer in one sentence."
SPIKE_PROMPT = BASELINE_PROMPT
MAX_OUTPUT_TOKENS = 80

state_store = get_state_store()
execution_log = []
_original_execute = ControlExecutor.execute


def _observed_execute(self, *args, **kwargs):
    result = _original_execute(self, *args, **kwargs)

    target = result.get("target")

    execution_log.append(
        {
            "action": result.get("action"),
            "requested_model": (
                kwargs.get("original_kwargs") or {}
            ).get("model"),
            "executed_model": getattr(target, "model", None),
            "execution_target": dict(
                result.get("execution_target", {}) or {}
            ),
        }
    )

    return result


ControlExecutor.execute = _observed_execute


print("=" * 70)
print("WAIL INTEGRATION TEST")
print("OLLAMA (OPENAI COMPATIBLE)")
print("=" * 70)


# ==========================================================
# CLIENT
# ==========================================================

SERVICE = "ollama-baseline-spike-test"
ENV = "dev"

TEST_STARTED_AT = time.time()

wail.configure(
    service=SERVICE,
    env=ENV,
)

client = wail.wrap(
    OpenAI(
        api_key="ollama",
        base_url="http://localhost:11434/v1",
    ),
)

print(f"\nPrimary Model : {PRIMARY_MODEL}")


# ==========================================================
# HELPERS
# ==========================================================

def latest_trace_files():
    return sorted(
        glob.glob("wail_audit/trace_*.json"),
        key=lambda x: Path(x).stat().st_mtime,
    )


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_stream(
    prompt,
    *,
    model=PRIMARY_MODEL,
    max_output_tokens=MAX_OUTPUT_TOKENS,
    chunk_delay_seconds=0.0,
):
    before = len(execution_log)

    with client.responses.stream(
        model=model,
        input=prompt,
        max_output_tokens=max_output_tokens,
    ) as stream:
        for _ in stream:
            if chunk_delay_seconds > 0:
                time.sleep(chunk_delay_seconds)

    if len(execution_log) != before + 1:
        raise AssertionError(
            "Expected exactly one ControlExecutor execution for one request."
        )

    record = execution_log[-1]
    executed_model = record.get("executed_model") or model

    return executed_model, record


def print_phase(title):
    print("\n")
    print("=" * 70)
    print(title)
    print("=" * 70)


# ==========================================================
# PHASE 1 - BASELINE
# ==========================================================

print_phase("PHASE 1 - BASELINE BUILD")

for i in range(BASELINE_SIZE):
    print(f"\n[Baseline {i + 1}/{BASELINE_SIZE}]")

    run_stream(
        BASELINE_PROMPT,
        model=PRIMARY_MODEL,
    )

    time.sleep(0.2)

print("\nBaseline completed.")


# ==========================================================
# PHASE 2 - REGISTER SECOND MODEL
# ==========================================================

print_phase("PHASE 2 - REGISTER SECOND MODEL")

run_stream(
    "Hello",
    model=SECONDARY_MODEL,
    max_output_tokens=16,
)

print("Secondary model request completed.")

time.sleep(1)


# ==========================================================
# PHASE 3 - ACTIVE ROUTE ONLY SPIKE
# ==========================================================

print_phase("PHASE 3 - CONTROLLED INFRA DEGRADATION")
runtime_decision_store.clear()
clear_hysteresis()
CONTROL_PHASE_STARTED_AT = time.time()
active_model = PRIMARY_MODEL
reroute_pending = False

for i in range(SPIKE_COUNT):
    print(f"\n[Spike {i + 1}/{SPIKE_COUNT}] active={active_model}")

    active_model, _ = run_stream(
        SPIKE_PROMPT,
        model=active_model,
        chunk_delay_seconds=SPIKE_DELAY_SECONDS,
    )

    pending = runtime_decision_store.peek() or {}

    if str(pending.get("decision") or "").lower() == "reroute":
        print(
            "\nPending REROUTE observed. "
            "Stopping degradation BEFORE N+1."
        )
        reroute_pending = True
        break

    time.sleep(0.2)

if not reroute_pending:
    raise AssertionError(
        "FAILED: Controlled degradation did not produce a pending REROUTE."
    )

print("\nControlled infra degradation completed.")


# ==========================================================
# PHASE 4 - CLEAN N+1 + STABILITY OBSERVATIONS
# ==========================================================

print_phase("PHASE 4 - POST CONTROL / CLEAN OBSERVATION")

for i in range(OBSERVATION_COUNT):
    print(f"\n[Observation {i + 1}/{OBSERVATION_COUNT}] active={active_model}")

    active_model, _ = run_stream(
        BASELINE_PROMPT,
        model=active_model,
    )

    time.sleep(0.15)

print("\nPost-control observation completed.")


# ==========================================================
# PHASE 5 - VALIDATION
# ==========================================================

print_phase("PHASE 5 - VALIDATION")

from wail_private.licensing.features import can_reroute
from wail_private.licensing.license import load_license


license_result = load_license()

if not license_result.get("valid"):
    raise AssertionError("FAILED: Active WAIL license is not valid.")

active_plan = str(
    license_result.get("effective_plan") or ""
).lower()

if not active_plan:
    raise AssertionError("FAILED: Active WAIL plan is not available.")

reroute_entitled = can_reroute(active_plan)


def is_tech_artifact(path):
    return str(path).endswith("_tech.json")


def collect_service_traces():
    traces = []

    for path in latest_trace_files():
        if Path(path).stat().st_mtime < CONTROL_PHASE_STARTED_AT:
            continue

        tech = is_tech_artifact(path)

        if active_plan == "enterprise":
            if tech:
                continue
        else:
            if not tech:
                continue

        try:
            trace = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue

        metadata = trace.get("metadata", {}) or {}
        ctx = metadata.get("invocation_context", {}) or {}

        if ctx.get("service") == SERVICE:
            traces.append((path, trace))

    return traces


deadline = time.time() + 15.0
service_traces = []

while time.time() < deadline:
    service_traces = collect_service_traces()

    if len(service_traces) >= 2:
        break

    time.sleep(0.05)

if len(service_traces) < 2:
    raise AssertionError(
        "FAILED: Not enough service artifacts for "
        f"plan={active_plan}. Found={len(service_traces)}"
    )


control_allowed = not any(
    (
        (trace.get("metadata", {}) or {})
        .get("invocation_context", {})
        .get("_control_quota_reason")
        == "quota_exhausted"
    )
    for _, trace in service_traces
)

reroute_expected = reroute_entitled and control_allowed


def read_decision(path, trace):
    if is_tech_artifact(path):
        decision = trace.get("decision", {}) or {}

        return {
            "severity": decision.get("severity"),
            "dominant_cause": trace.get("dominant_surface"),
            "control_decision": decision.get("type"),
            "control_reason": decision.get("reason"),
            "enforcement_decision": None,
        }

    control = trace.get("control", {}) or {}
    enforcement = trace.get("enforcement", {}) or {}
    effective = trace.get("effective_execution_decision", {}) or {}

    enforcement_decision = enforcement.get("decision")

    actual_decision = (
        effective.get("decision")
        or (
            "reroute"
            if enforcement_decision == "reroute"
            else control.get("decision")
        )
    )

    actual_reason = (
        effective.get("reason")
        or (
            "escalation_threshold_reached"
            if enforcement_decision == "reroute"
            else control.get("reason")
        )
    )

    return {
        "severity": control.get("severity"),
        "dominant_cause": control.get("dominant_cause"),
        "control_decision": actual_decision,
        "control_reason": actual_reason,
        "enforcement_decision": enforcement_decision,
    }


def read_execution(path, trace):
    execution = trace.get("execution", {}) or {}
    target = trace.get("execution_target", {}) or {}

    if is_tech_artifact(path):
        summary = trace.get("execution_summary", {}) or {}

        changed = bool(
            summary.get("execution_changed")
            or execution.get("rerouted")
        )
    else:
        flow = trace.get("execution_flow", {}) or {}
        stage_4 = flow.get("stage_4_outcome", {}) or {}

        changed = bool(
            execution.get("rerouted")
            or stage_4.get("execution_changed")
            or (
                target.get("from_provider") is not None
                and target.get("to_provider") is not None
                and target.get("from_provider")
                != target.get("to_provider")
            )
            or (
                target.get("from_model") is not None
                and target.get("to_model") is not None
                and target.get("from_model")
                != target.get("to_model")
            )
        )

    return execution, target, changed


decision_path = None
decision_trace = None
execution_path = None
execution_trace = None

expected_control_decision = (
    "reroute" if reroute_expected else "observe"
)

selected_pair = None

for i in range(len(service_traces) - 1):
    path_n, trace_n = service_traces[i]
    path_next, trace_next = service_traces[i + 1]

    info_n = read_decision(path_n, trace_n)

    if (
        info_n["severity"] != "critical"
        or info_n["dominant_cause"] != "infra_health"
        or info_n["control_decision"] != expected_control_decision
    ):
        continue

    if not control_allowed:
        if info_n["control_reason"] != "control_quota_exhausted":
            continue

        execution_next, target_next, changed_next = read_execution(
            path_n,
            trace_n,
        )
        candidate_execution_path = path_n
        candidate_execution_trace = trace_n
    else:
        execution_next, target_next, changed_next = read_execution(
            path_next,
            trace_next,
        )
        candidate_execution_path = path_next
        candidate_execution_trace = trace_next

    hysteresis_info = (
        trace_next.get("routing_hysteresis", {})
        or trace_next.get("hysteresis", {})
        or {}
    )

    hysteresis_reason = (
        hysteresis_info.get("reason")
        or execution_next.get("hysteresis_reason")
        or target_next.get("hysteresis_reason")
    )

    blocked_reasons = {
        "already_active",
        "insufficient_improvement",
        "score_unavailable",
        "reversal_without_score",
        "reversal_hold",
    }

    reroute_applied = (
        execution_next.get("rerouted") is True
        and changed_next is True
    )

    hysteresis_blocked = (
        execution_next.get("rerouted") is not True
        and changed_next is not True
        and hysteresis_reason in blocked_reasons
    )

    if reroute_expected:
        pair_valid = reroute_applied or hysteresis_blocked
    else:
        pair_valid = (
            execution_next.get("rerouted") is not True
            and changed_next is not True
        )

    selected_pair = {
        "decision_file": Path(path_n).name,
        "execution_file": Path(candidate_execution_path).name,
        "severity": info_n["severity"],
        "dominant_cause": info_n["dominant_cause"],
        "decision": info_n["control_decision"],
        "reason": info_n["control_reason"],
        "rerouted": execution_next.get("rerouted"),
        "execution_changed": changed_next,
        "hysteresis_reason": hysteresis_reason,
        "outcome": (
            "reroute_applied"
            if reroute_applied
            else "hysteresis_blocked"
            if hysteresis_blocked
            else "no_change"
        ),
        "valid": pair_valid,
    }

    if not pair_valid:
        raise AssertionError(
            "FAILED: Controlled spike N -> N+1 pair is invalid. "
            f"plan={active_plan}, "
            f"reroute_entitled={reroute_entitled}, "
            f"control_allowed={control_allowed}, "
            f"pair={selected_pair}"
        )

    decision_path = path_n
    decision_trace = trace_n
    execution_path = candidate_execution_path
    execution_trace = candidate_execution_trace
    break


if decision_trace is None:
    observed = []

    for path, trace in service_traces:
        info = read_decision(path, trace)
        execution_dbg, _, changed_dbg = read_execution(path, trace)

        observed.append(
            {
                "file": Path(path).name,
                "severity": info["severity"],
                "dominant_cause": info["dominant_cause"],
                "decision": info["control_decision"],
                "rerouted": execution_dbg.get("rerouted"),
                "execution_changed": changed_dbg,
            }
        )

    raise AssertionError(
        "FAILED: No controlled-spike CRITICAL INFRA_HEALTH pair found. "
        f"plan={active_plan}, "
        f"reroute_entitled={reroute_entitled}, "
        f"control_allowed={control_allowed}, "
        f"artifacts={len(service_traces)}, "
        f"observed={observed[-10:]}"
    )


decision_info = read_decision(
    decision_path,
    decision_trace,
)

observed_severity = decision_info["severity"]
dominant_cause = decision_info["dominant_cause"]
actual_decision = decision_info["control_decision"]
actual_reason = decision_info["control_reason"]
enforcement_decision = decision_info["enforcement_decision"]

expected_severity = "critical"
expected_dominant_cause = "infra_health"
expected_decision = "reroute" if reroute_expected else "observe"

severity_valid = observed_severity == expected_severity
dominant_cause_valid = dominant_cause == expected_dominant_cause
decision_valid = actual_decision == expected_decision

if not control_allowed:
    expected_reason = "control_quota_exhausted"
    reason_valid = actual_reason == expected_reason
elif is_tech_artifact(decision_path):
    expected_reason = actual_reason
    reason_valid = True
else:
    expected_reason = actual_reason
    reason_valid = actual_reason is not None


execution, execution_target, execution_changed = read_execution(
    execution_path,
    execution_trace,
)


if not control_allowed and is_tech_artifact(execution_path):
    execution_metadata = execution_trace.get("metadata", {}) or {}
    provider_valid = execution_metadata.get("provider") == "ollama"
    initial_model_valid = execution_metadata.get("model") == PRIMARY_MODEL
    transport_valid = True
    target_consistency_valid = execution_target == {}
else:
    provider_valid = execution.get("initial_provider") == "ollama"
    initial_model_valid = execution.get("initial_model") == PRIMARY_MODEL

    if execution_changed:
        transport_valid = (
            execution_target.get("from_transport") == "openai"
            and execution_target.get("to_transport") == "openai"
            and execution_target.get("from_provider") == "ollama"
            and execution_target.get("to_provider") == "ollama"
        )

        target_consistency_valid = (
            execution.get("final_provider")
            == execution_target.get("to_provider")
            and execution.get("final_model")
            == execution_target.get("to_model")
            and execution_target.get("from_model") == PRIMARY_MODEL
        )
    else:
        transport_valid = (
            execution.get("initial_provider") == "ollama"
            and execution.get("final_provider") == "ollama"
        )

        target_consistency_valid = (
            execution.get("initial_model") == PRIMARY_MODEL
            and execution.get("final_model") == PRIMARY_MODEL
            and execution_target == {}
        )


representative_hysteresis = (
    execution_trace.get("routing_hysteresis", {})
    or execution_trace.get("hysteresis", {})
    or {}
)

representative_hysteresis_reason = (
    representative_hysteresis.get("reason")
    or execution.get("hysteresis_reason")
    or execution_target.get("hysteresis_reason")
)

representative_blocked_reasons = {
    "already_active",
    "insufficient_improvement",
    "score_unavailable",
    "reversal_without_score",
    "reversal_hold",
}

if reroute_expected:
    execution_valid = (
        (
            execution.get("rerouted") is True
            and execution_changed is True
            and execution.get("final_model")
            != execution.get("initial_model")
            and execution_target.get("from_model")
            == execution.get("initial_model")
            and execution_target.get("to_model")
            == execution.get("final_model")
            and execution_target.get("to_model")
            != execution_target.get("from_model")
        )
        or (
            execution.get("rerouted") is not True
            and execution_changed is False
            and representative_hysteresis_reason
            in representative_blocked_reasons
        )
    )
else:
    execution_valid = (
        execution.get("rerouted") is not True
        and execution_changed is False
    )


runtime = execution_trace.get("runtime", {}) or {}

if is_tech_artifact(execution_path):
    timing = runtime
else:
    timing = runtime.get("timing", {}) or {}

duration_ms = timing.get("duration_ms")
ttft_ms = timing.get("first_token_latency_ms")

timing_valid = (
    isinstance(duration_ms, (int, float))
    and duration_ms > 0
    and isinstance(ttft_ms, (int, float))
    and ttft_ms > 0
)


overall_pass = all(
    [
        severity_valid,
        dominant_cause_valid,
        decision_valid,
        reason_valid,
        execution_valid,
        provider_valid,
        initial_model_valid,
        transport_valid,
        target_consistency_valid,
        timing_valid,
    ]
)


print("\n")
print("=" * 70)
print("RUNTIME TEST RESULT")
print("=" * 70)

print(f"Decision Trace (N)       : {Path(decision_path).name}")
print(f"Execution Trace (N+1)    : {Path(execution_path).name}")
print(f"Observed Severity        : {str(observed_severity).upper()}")
print(f"Dominant Cause           : {str(dominant_cause).upper()}")
print(f"Effective Decision       : {str(actual_decision).upper()}")
print(f"Effective Reason         : {str(actual_reason).upper()}")
print(
    "Hysteresis Reason        : "
    + (
        str(representative_hysteresis_reason).upper()
        if representative_hysteresis_reason
        else "NONE"
    )
)
print(f"Enforcement Decision     : {str(enforcement_decision).upper()}")
print(f"Execution Plan           : {active_plan.capitalize()}")
print(
    "Reroute Entitled         : "
    f"{'YES' if reroute_entitled else 'NO'}"
)
print(
    "Control Available        : "
    f"{'YES' if control_allowed else 'NO'}"
)

print()
print(
    "Expected State           : "
    f"CRITICAL / INFRA_HEALTH / {expected_decision.upper()}"
)
print(
    "Actual State             : "
    f"{str(observed_severity).upper()} / "
    f"{str(dominant_cause).upper()} / "
    f"{str(actual_decision).upper()}"
)

print()
print(
    "Severity Validation      : "
    f"{'PASS' if severity_valid else 'FAIL'}"
)
print(
    "Dominant Cause Validation: "
    f"{'PASS' if dominant_cause_valid else 'FAIL'}"
)
print(
    "Decision Validation      : "
    f"{'PASS' if decision_valid else 'FAIL'}"
)
print(
    "Reason Validation        : "
    f"{'PASS' if reason_valid else 'FAIL'}"
)
print(
    "Next-Request Execution   : "
    f"{'PASS' if execution_valid else 'FAIL'}"
)
print(
    "Provider Validation      : "
    f"{'PASS' if provider_valid else 'FAIL'}"
)
print(
    "Transport Validation     : "
    f"{'PASS' if transport_valid else 'FAIL'}"
)
print(
    "Target Consistency       : "
    f"{'PASS' if target_consistency_valid else 'FAIL'}"
)
print(
    "Timing Validation        : "
    f"{'PASS' if timing_valid else 'FAIL'}"
)

print()
print(
    "Provider                 :",
    execution.get("initial_provider"),
    "->",
    execution.get("final_provider"),
)
print(
    "Model                    :",
    execution.get("initial_model"),
    "->",
    execution.get("final_model"),
)
print(
    "Execution Changed        :",
    "YES" if execution_changed else "NO",
)

print()
print(
    f"RESULT                   : "
    f"{'PASS' if overall_pass else 'FAIL'}"
)
print("=" * 70)


assert severity_valid, (
    "Expected CRITICAL severity, "
    f"actual={observed_severity}"
)

assert dominant_cause_valid, (
    "Expected INFRA_HEALTH dominance, "
    f"actual={dominant_cause}"
)

assert decision_valid, (
    f"Expected {expected_decision.upper()} decision, "
    f"actual={actual_decision}"
)

assert reason_valid, (
    f"Reason validation failed: actual={actual_reason}"
)

assert execution_valid, (
    "N+1 execution is inconsistent with reroute/hysteresis semantics: "
    f"plan={active_plan}, "
    f"reroute_entitled={reroute_entitled}, "
    f"control_allowed={control_allowed}, "
    f"rerouted={execution.get('rerouted')}, "
    f"execution_changed={execution_changed}, "
    f"from_model={execution_target.get('from_model')}, "
    f"to_model={execution_target.get('to_model')}"
)

assert provider_valid, (
    "Initial provider mismatch: "
    f"expected=ollama, actual={execution.get('initial_provider')}"
)

assert initial_model_valid, (
    "Initial model mismatch: "
    f"expected={PRIMARY_MODEL}, "
    f"actual={execution.get('initial_model')}"
)

assert transport_valid, (
    "Execution transport/provider integrity check failed."
)

assert target_consistency_valid, (
    "Execution target is inconsistent with execution metadata."
)

assert timing_valid, (
    "Timing validation failed: "
    f"duration_ms={duration_ms}, ttft_ms={ttft_ms}"
)

ControlExecutor.execute = _original_execute