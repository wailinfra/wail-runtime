def build_tech_artifact(full_artifact: dict) -> dict:
    runtime = full_artifact.get("runtime") or {}
    timing = runtime.get("timing") or {}
    drift = full_artifact.get("drift_analysis") or {}
    control = full_artifact.get("control") or {}
    integrity = full_artifact.get("integrity") or {}
    incident = full_artifact.get("incident") or {}
    metadata = full_artifact.get("metadata") or {}
    risk = full_artifact.get("risk") or {}
    statistics = full_artifact.get("statistics") or {}
    routing_hysteresis = full_artifact.get("routing_hysteresis")
    reliability = runtime.get("reliability") or {}
    stream_surface = runtime.get("stream_surface") or {}
    baseline_snapshot = drift.get("baseline_snapshot") or {}
    baseline_new = full_artifact.get("baseline") or {}
    latency_p95 = baseline_snapshot.get("latency_p95") or baseline_new.get(
        "latency_p95"
    )
    sample_count = baseline_snapshot.get("baseline_sample_count") or baseline_new.get(
        "sample_count"
    )
    duration = timing.get("duration_ms") or runtime.get("duration_ms")
    first_token = timing.get("first_token_latency_ms") or runtime.get(
        "first_token_latency_ms"
    )
    raw_signals = drift.get("signals", [])
    signal_count = len(raw_signals)
    runtime_metrics = {
        key: value
        for key, value in timing.items()
        if value is not None
    }

    if duration is not None:
        runtime_metrics.setdefault("duration_ms", duration)

    if first_token is not None:
        runtime_metrics.setdefault("first_token_latency_ms", first_token)

    runtime_metrics["reliability"] = {
        "retry_count": reliability.get("retry_count", 0),
        "error_flag": bool(reliability.get("error_flag", False)),
        "timeout_flag": bool(reliability.get("timeout_flag", False)),
    }

    excluded_stream_fields = {
        "full_timeline",
    }
    compact_stream = {
        key: value
        for key, value in stream_surface.items()
        if value is not None and key not in excluded_stream_fields
    }

    if compact_stream:
        runtime_metrics["stream"] = compact_stream

    excluded_baseline_fields = {
        "normalized_latency_series",
        "latency_series",
        "first_token_series",
        "mean_gap_series",
    }
    baseline_metrics = {
        key: value
        for key, value in baseline_snapshot.items()
        if value is not None and key not in excluded_baseline_fields
    }

    for key, value in baseline_new.items():
        if value is not None and key not in excluded_baseline_fields:
            baseline_metrics.setdefault(key, value)

    if latency_p95 is not None:
        baseline_metrics.setdefault("latency_p95", latency_p95)

    if sample_count is not None:
        baseline_metrics.setdefault("sample_count", sample_count)

    ctx = metadata.get("invocation_context", {}) or {}
    segment = f"{metadata.get('provider')}:{metadata.get('model')}:{ctx.get('service')}:{ctx.get('env')}"
    dominant_surface = (
    incident.get("dominant_surface")
    or risk.get("dominant_surface")
    )
    control_decision = control.get("decision")
    control_action = control.get("action")
    control_executed = bool(control.get("executed"))

    if not control_action and control_decision:
        if control_decision in ["retry", "prepare_retry"]:
            control_action = "retry_prepared"
        elif control_decision in ["reroute"]:
            control_action = "reroute_prepared"

    if control_executed:
        control_state = "executed"
    elif control_action:
        control_state = "prepared"
    else:
        control_state = "none"

    pre = full_artifact.get("pre_incident") or {}
    pre_triggered = pre.get("triggered")

    execution_data = full_artifact.get("execution") or {}

    execution_summary = {
        "execution_changed": bool(
            execution_data.get("execution_changed")
            or execution_data.get("rerouted")
            or execution_data.get("intervened")
            or control_executed
        ),
        "intervened": bool(
            execution_data.get("intervened")
            or execution_data.get("rerouted")
            or control_executed
        ),
        "enforced": bool(
            execution_data.get("intervened")
            or execution_data.get("rerouted")
            or control_executed
        ),
        "changed_in_real_time": bool(control_executed),
    }

    initial_provider = execution_data.get("initial_provider")
    initial_model = execution_data.get("initial_model")
    final_provider = execution_data.get("final_provider")
    final_model = execution_data.get("final_model")

    execution_changed = bool(
        execution_summary.get("execution_changed")
        or initial_provider != final_provider
        or initial_model != final_model
    )

    compact_execution = {
        "initial_provider": initial_provider,
        "initial_model": initial_model,
        "final_provider": final_provider,
        "final_model": final_model,
        "changed": execution_changed,
        "rerouted": bool(execution_data.get("rerouted")),
        "intervened": bool(
            execution_data.get("intervened") or control_executed
        ),
    }

    if execution_changed:
        if compact_execution.get("rerouted"):
            control_action = "reroute_executed"
        elif control_decision in ["retry", "prepare_retry"]:
            control_action = "retry_executed"

        control_executed = True
        control_state = "executed"

        execution_summary["intervened"] = True
        execution_summary["enforced"] = True

    compact_execution_target = None

    if execution_changed:
        compact_execution["from"] = {
            "provider": initial_provider,
            "model": initial_model,
        }
        compact_execution["to"] = {
            "provider": final_provider,
            "model": final_model,
        }

        target = full_artifact.get("execution_target") or {}
        if target:
            compact_execution_target = {
                "from_transport": target.get("from_transport"),
                "to_transport": target.get("to_transport"),
                "from_provider": target.get("from_provider"),
                "to_provider": target.get("to_provider"),
                "from_model": target.get("from_model"),
                "to_model": target.get("to_model"),
            }

    return {
        "execution_summary": execution_summary,
        "artifact_version": full_artifact.get("artifact_version"),
        "metadata": metadata,
        "segment": segment,
        "runtime": runtime_metrics,
        "baseline": baseline_metrics or None,
        "statistics": statistics or None,
        "signals": {
            "count": signal_count,
            "detected": raw_signals,
        },
        "dominant_surface": dominant_surface,
        
        "decision": (
            {
                "severity": risk.get("severity"),
                "runtime_severity": risk.get("runtime_severity"),
                "policy_severity": risk.get("policy_severity"),
                "sla_severity": risk.get("sla_severity"),
                "type": control_decision,
                "reason": control.get("reason"),
            }
            if incident
            else {}
        ),
       
        "control": {
            "action": control_action,
            "executed": control_executed,
            "state": control_state,
        },
        
        "execution": compact_execution,
        "execution_target": compact_execution_target,
        "routing_hysteresis": routing_hysteresis,
        "reason": (
            {"basis": "deviation patterns"} if incident and signal_count > 0 else None
        ),
        
        "pre_incident": {
            "triggered": bool(pre_triggered),
        },
        "integrity": {
            "artifact_hash": integrity.get("artifact_hash"),
            "signature": integrity.get("signature"),
            "signature_algorithm": integrity.get("signature_algorithm"),
        },
    }