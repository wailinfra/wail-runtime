import glob
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from openai import OpenAI

import wail

from wail_private import runtime_decision_store
from wail_private.routing.hysteresis import clear as clear_hysteresis
from wail_private.licensing.license import load_license


# ==========================================================
# CONFIGURATION
# ==========================================================

SERVICE = "single-provider-single-model-test"
ENV = "dev"

TEST_STARTED_AT = time.time()

PRIMARY_PROVIDER = "openai"
PRIMARY_MODEL = "gpt-4o-mini"

BASELINE_SIZE = 30
SPIKE_COUNT = 6
POST_CONTROL_COUNT = 3
SPIKE_DELAY_SECONDS = 3.0


# ==========================================================
# TRACE HELPERS
# ==========================================================

def latest_trace_files():
    return sorted(
        glob.glob("wail_audit/trace_*.json"),
        key=lambda x: Path(x).stat().st_mtime,
    )


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


PRE_RUN_TRACE_FILES = set(latest_trace_files())


# ==========================================================
# CLIENT
# ==========================================================

wail.configure(
    service=SERVICE,
    env=ENV,
)

client = wail.wrap(OpenAI())


# ==========================================================
# REQUEST
# ==========================================================

def run_stream(
    prompt,
    max_output_tokens,
    chunk_delay_seconds=0.0,
):

    with client.responses.stream(
        model=PRIMARY_MODEL,
        input=prompt,
        max_output_tokens=max_output_tokens,
    ) as stream:

        for _ in stream:
            if chunk_delay_seconds > 0:
                time.sleep(chunk_delay_seconds)


# ==========================================================
# BASELINE
# ==========================================================

print("=" * 70)
print("SINGLE PROVIDER / SINGLE MODEL TEST")
print(f"{PRIMARY_PROVIDER} / {PRIMARY_MODEL}")
print("=" * 70)

print("\n=== BASELINE PHASE ===")

for i in range(BASELINE_SIZE):

    print(f"\n[Baseline {i + 1}/{BASELINE_SIZE}]")

    run_stream(
        prompt="What is 2 + 2? Answer in one sentence.",
        max_output_tokens=80,
    )

    time.sleep(0.2)

print("\nBaseline completed.")

print("\n=== CONTROLLED INFRA DEGRADATION ===")
runtime_decision_store.clear()
clear_hysteresis()

spike_prompt = "What is 2 + 2? Answer in one sentence."
control_intent_seen_during_spike = False

for i in range(SPIKE_COUNT):

    print(f"\n[Spike {i + 1}/{SPIKE_COUNT}]")

    run_stream(
        prompt=spike_prompt,
        max_output_tokens=80,
        chunk_delay_seconds=SPIKE_DELAY_SECONDS,
    )

    pending = runtime_decision_store.peek() or {}
    pending_decision = str(
        pending.get("decision") or ""
    ).lower()

    if pending_decision not in ("", "none", "observe"):
        control_intent_seen_during_spike = True
        print(
            "\nPending control intent observed. "
            "Stopping degradation BEFORE N+1."
        )
        break

    time.sleep(0.2)

print("\nControlled infra degradation completed.")


# ==========================================================
# POST CONTROL
# ==========================================================

print("\n=== POST CONTROL PHASE ===")

for i in range(POST_CONTROL_COUNT):

    print(f"\n[Post Control {i + 1}/{POST_CONTROL_COUNT}]")

    run_stream(
        prompt="System recovered successfully? Answer briefly.",
        max_output_tokens=60,
    )

    time.sleep(0.2)

print("\nPost-control completed.")

print("\n=== VALIDATION ===")


license_result = load_license()

if not license_result.get("valid"):
    raise AssertionError("FAILED: Active WAIL license is not valid.")

active_plan = str(
    license_result.get("effective_plan") or ""
).lower()

if not active_plan:
    raise AssertionError("FAILED: Active WAIL plan is not available.")


def is_tech_artifact(path):
    return str(path).endswith("_tech.json")


def collect_service_traces():

    traces = []

    current_run_files = [
        path for path in latest_trace_files()
        if (
            path not in PRE_RUN_TRACE_FILES
            and Path(path).stat().st_mtime >= TEST_STARTED_AT
        )
    ]

    for path in current_run_files:
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

    if service_traces:
        break

    time.sleep(0.05)

if not service_traces:
    raise AssertionError(
        "FAILED: No service artifacts found for "
        f"plan={active_plan}."
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

provider_model_valid = True
execution_change_valid = True
target_consistency_valid = True
transport_valid = True
timing_valid = True

decision_seen = False
reroute_intent_seen = False
critical_infra_seen = False

violations = []


def read_effective_decision(path, trace):
   
    if is_tech_artifact(path):
        decision = trace.get("decision", {}) or {}
        return decision.get("type")

    control = trace.get("control", {}) or {}
    enforcement = trace.get("enforcement", {}) or {}
    effective = trace.get("effective_execution_decision", {}) or {}

    return (
        effective.get("decision")
        or (
            "reroute"
            if enforcement.get("decision") == "reroute"
            else control.get("decision")
        )
    )


def read_incident_state(path, trace):

    if is_tech_artifact(path):
        decision = trace.get("decision", {}) or {}
        return (
            str(decision.get("severity") or "").lower(),
            str(trace.get("dominant_surface") or "").lower(),
        )

    control = trace.get("control", {}) or {}
    return (
        str(control.get("severity") or "").lower(),
        str(control.get("dominant_cause") or "").lower(),
    )


def read_execution_changed(path, trace, execution, target):

    if is_tech_artifact(path):
        summary = trace.get("execution_summary", {}) or {}

        return bool(
            summary.get("execution_changed")
            or execution.get("rerouted")
            or (
                target.get("from_provider") is not None
                and target.get("to_provider") is not None
                and target.get("from_provider") != target.get("to_provider")
            )
            or (
                target.get("from_model") is not None
                and target.get("to_model") is not None
                and target.get("from_model") != target.get("to_model")
            )
        )

    flow = trace.get("execution_flow", {}) or {}
    stage_4 = flow.get("stage_4_outcome", {}) or {}

    return bool(
        execution.get("rerouted") is True
        or stage_4.get("execution_changed") is True
        or (
            target.get("from_provider") is not None
            and target.get("to_provider") is not None
            and target.get("from_provider") != target.get("to_provider")
        )
        or (
            target.get("from_model") is not None
            and target.get("to_model") is not None
            and target.get("from_model") != target.get("to_model")
        )
    )


for path, trace in service_traces:

    execution = trace.get("execution", {}) or {}
    target = trace.get("execution_target", {}) or {}

    effective_decision = read_effective_decision(path, trace)
    severity, dominant_cause = read_incident_state(path, trace)

    if (
        severity == "critical"
        and dominant_cause == "infra_health"
    ):
        critical_infra_seen = True

    if effective_decision not in (None, "none", "observe"):
        decision_seen = True

    if effective_decision in ("reroute", "prepare_reroute"):
        reroute_intent_seen = True

    if (
        execution.get("initial_provider") != PRIMARY_PROVIDER
        or execution.get("final_provider") != PRIMARY_PROVIDER
        or execution.get("initial_model") != PRIMARY_MODEL
        or execution.get("final_model") != PRIMARY_MODEL
    ):
        provider_model_valid = False
        violations.append(
            f"{Path(path).name}: execution escaped the only available target"
        )

    execution_changed = read_execution_changed(
        path,
        trace,
        execution,
        target,
    )

    if execution_changed:
        execution_change_valid = False
        violations.append(
            f"{Path(path).name}: execution_changed=True with no alternative target"
        )

    if target:
        if (
            target.get("from_provider") != PRIMARY_PROVIDER
            or target.get("to_provider") != PRIMARY_PROVIDER
            or target.get("from_model") != PRIMARY_MODEL
            or target.get("to_model") != PRIMARY_MODEL
        ):
            target_consistency_valid = False
            violations.append(
                f"{Path(path).name}: execution_target is inconsistent"
            )

        if (
            target.get("from_transport") != "openai"
            or target.get("to_transport") != "openai"
        ):
            transport_valid = False
            violations.append(
                f"{Path(path).name}: transport changed unexpectedly"
            )

    runtime = trace.get("runtime", {}) or {}

    if is_tech_artifact(path):
        timing = runtime
    else:
        timing = runtime.get("timing", {}) or {}

    duration_ms = timing.get("duration_ms")

    if not (
        isinstance(duration_ms, (int, float))
        and duration_ms > 0
    ):
        timing_valid = False
        violations.append(
            f"{Path(path).name}: invalid duration_ms={duration_ms}"
        )

overall_pass = all([
    critical_infra_seen,
    provider_model_valid,
    execution_change_valid,
    target_consistency_valid,
    transport_valid,
    timing_valid,
])

print("\n")
print("=" * 70)
print("SINGLE PROVIDER / SINGLE MODEL RESULT")
print("=" * 70)

print(f"Execution Plan           : {active_plan.capitalize()}")
print(
    "Artifact Type            : "
    + ("Full .json" if active_plan == "enterprise" else "_tech.json")
)
print(f"Provider                 : {PRIMARY_PROVIDER}")
print(f"Model                    : {PRIMARY_MODEL}")
print(f"Trace Count              : {len(service_traces)}")
print(f"Control Available        : {'YES' if control_allowed else 'NO'}")
print(f"Critical Infra Seen      : {'YES' if critical_infra_seen else 'NO'}")
print(f"Runtime Decision Seen    : {'YES' if decision_seen else 'NO'}")
print(f"Reroute Intent Seen      : {'YES' if reroute_intent_seen else 'NO'}")
print(
    f"Spike Control Intent     : "
    f"{'YES' if control_intent_seen_during_spike else 'NO'}"
)

print()
print(f"Critical Infra Detection : {'PASS' if critical_infra_seen else 'FAIL'}")
print(f"Provider/Model Invariant : {'PASS' if provider_model_valid else 'FAIL'}")
print(f"No Execution Change      : {'PASS' if execution_change_valid else 'FAIL'}")
print(f"Target Consistency       : {'PASS' if target_consistency_valid else 'FAIL'}")
print(f"Transport Validation     : {'PASS' if transport_valid else 'FAIL'}")
print(f"Timing Validation        : {'PASS' if timing_valid else 'FAIL'}")

if violations:
    print("\nVIOLATIONS:")
    for violation in violations:
        print(" -", violation)

print()
print(f"RESULT                   : {'PASS' if overall_pass else 'FAIL'}")
print("=" * 70)


# ==========================================================
# ASSERTIONS
# ==========================================================

assert critical_infra_seen, (
    "Controlled degradation did not produce CRITICAL / INFRA_HEALTH."
)

assert provider_model_valid, (
    "Execution escaped the only available provider/model target."
)

assert execution_change_valid, (
    "Execution changed even though no alternative provider/model exists."
)

assert target_consistency_valid, (
    "ExecutionTarget does not remain on the only available target."
)

assert transport_valid, (
    "Transport changed unexpectedly in a single-provider test."
)

assert timing_valid, (
    "One or more traces contain invalid timing."
)