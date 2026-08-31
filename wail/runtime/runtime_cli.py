from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from wail_private.licensing.runtime_entitlements import runtime_cli_permissions


console = Console()


def _status_text(value):
    text = str(value)
    normalized = text.upper()

    if normalized in {"VALID", "ACTIVE", "VERIFIED", "PASSED", "SAVED"}:
        return Text(text, style="green")
    if normalized in {"FAILED", "CRITICAL", "TRUE"}:
        return Text(text, style="bold red")
    if normalized in {"EXPIRED", "BYPASS", "WARNING", "MINOR", "MAJOR"}:
        return Text(text, style="yellow")
    if normalized in {"REROUTE", "RETRY"}:
        return Text(text, style="bold cyan")
    return Text(text)


def _runtime_table(rows):
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 1),
        expand=False,
    )
    table.add_column("Field", style="bright_black", no_wrap=True)
    table.add_column("Value", overflow="fold")

    for row in rows:
        if row is None:
            table.add_row("", "")
            continue

        key, value = row
        rendered = _status_text(value)
        table.add_row(key, rendered)

    return table


def _compact_panel(content, timestamp, *, max_width=72):
    terminal_width = max(console.size.width, 20)
    panel_width = min(max_width, terminal_width)

    return Panel(
        content,
        title=(
            "[bold cyan]WAIL[/bold cyan] "
            "[white]AI Runtime Control Layer[/white] "
            f"[bright_black]· {timestamp}[/bright_black]"
        ),
        border_style="bright_black",
        width=panel_width,
        padding=(0, 1),
    )


def _fmt(value, default="--"):
    if value is None:
        return default
    return str(value)


def _fmt_ms(value):
    if value is None:
        return "--"

    try:
        return f"{float(value):,.0f} ms"
    except Exception:
        return "--"


def _fmt_score(value):
    if value is None:
        return "--"

    try:
        return f"{float(value):.2f}"
    except Exception:
        return "--"


def _fmt_rate(value):
    if value is None:
        return "--"

    try:
        return f"{float(value):.2f} tok/s"
    except Exception:
        return "--"


def _ratio(observed, baseline):
    try:
        observed = float(observed)
        baseline = float(baseline)

        if baseline <= 0:
            return None

        return observed / baseline

    except Exception:
        return None


def _fmt_ms_with_drift(value, baseline):
    rendered = _fmt_ms(value)

    ratio = _ratio(value, baseline)

    if ratio is not None:
        rendered += f"   ({ratio:.2f}x)"

    return rendered


def _print_rows(rows, timestamp):
    console.print()
    console.print(
        _compact_panel(
            _runtime_table(rows),
            timestamp,
        )
    )
    console.print()

def _decision_rows(
    control_decision,
    enforcement_decision,
    show_enforcement,
):
    control_decision = (
        control_decision or "unknown"
    ).upper()

    enforcement_decision = (
        enforcement_decision or "none"
    ).upper()

    if not show_enforcement:
        return [
            ("Decision", control_decision),
        ]

    if control_decision == enforcement_decision:
        return [
            ("Decision", control_decision),
        ]

    if (
        control_decision == "OBSERVE"
        and enforcement_decision == "NONE"
    ):
        return [
            ("Decision", "OBSERVE"),
        ]

    return [
        ("Control Decision", control_decision),
        ("Enforcement Decision", enforcement_decision),
    ]


def _execution_row(execution):
    if not execution:
        return None

    initial_provider = execution.get("initial_provider")
    initial_model = execution.get("initial_model")

    final_provider = execution.get("final_provider")
    final_model = execution.get("final_model")

    rerouted = bool(execution.get("rerouted"))
    intervened = bool(execution.get("intervened"))

    provider_changed = (
        initial_provider is not None
        and final_provider is not None
        and initial_provider != final_provider
    )

    model_changed = (
        initial_model is not None
        and final_model is not None
        and initial_model != final_model
    )

    changed = (
        rerouted
        or intervened
        or provider_changed
        or model_changed
    )

    if not changed:
        return None

    if provider_changed:
        source = (
            f"{_fmt(initial_provider)}/"
            f"{_fmt(initial_model)}"
        )

        target = (
            f"{_fmt(final_provider)}/"
            f"{_fmt(final_model)}"
        )

    else:
        source = _fmt(initial_model)
        target = _fmt(final_model)

    return (
        "Execution",
        f"{source} -> {target}",
    )


def _get_baseline(trace):
    drift = trace.get("drift_analysis") or {}

    baseline = (
        drift.get("baseline_snapshot")
        or trace.get("baseline")
        or {}
    )

    return baseline


def _get_stream_surface(trace, runtime):
    stream_surface = (
        runtime.get("stream_surface")
        or trace.get("stream_surface")
        or {}
    )

    return stream_surface


def _get_throughput(runtime, stream_surface):
    native = (
        stream_surface.get("tokens_per_second")
        or runtime.get("tokens_per_second")
    )

    if native is not None:
        try:
            return float(native)
        except Exception:
            pass

    output_tokens = runtime.get("output_token_count")

    duration = runtime.get("duration_ms")
    ttft = runtime.get("first_token_latency_ms")

    try:
        output_tokens = float(output_tokens)
        duration = float(duration)

        if ttft is not None:
            generation_ms = duration - float(ttft)
        else:
            generation_ms = duration

        if output_tokens <= 0 or generation_ms <= 0:
            return None

        return output_tokens / (generation_ms / 1000.0)

    except Exception:
        return None


def render_runtime_summary(trace, plan):
    metadata = trace.get("metadata") or {}
    runtime = trace.get("runtime_surface") or {}
    risk = trace.get("risk") or {}
    execution = trace.get("execution") or {}
    drift = trace.get("drift_analysis") or {}
    incident = trace.get("incident") or {}
    trace_id = (
        trace.get("trace_id")
        or metadata.get("trace_id")
    )
    provider = metadata.get("provider")
    model = metadata.get("model")

    ttft = runtime.get("first_token_latency_ms")
    duration = runtime.get("duration_ms")

    stream_surface = _get_stream_surface(
        trace,
        runtime,
    )

    token_dynamics = stream_surface.get("token_dynamics") or {}

    mean_token_gap = token_dynamics.get(
        "mean_inter_token_gap_ms"
    )

    throughput = token_dynamics.get(
        "avg_tokens_per_sec"
    )

    if throughput is None:
        throughput = _get_throughput(
            runtime,
            stream_surface,
        )

    baseline = _get_baseline(trace)

    duration_baseline = (
        baseline.get("latency_p95")
    )

    ttft_baseline = (
        baseline.get("first_token_p95")
    )

    signals = drift.get("signals") or []
    signal_count = len(signals)

    severity = (
        risk.get("severity")
        or risk.get("effective_severity")
        or risk.get("runtime_severity")
        or "none"
    ).upper()

    risk_score = (
        risk.get("composite_score")
        if risk.get("composite_score") is not None
        else risk.get("score")
    )

    dominant_surface = (
        incident.get("dominant_surface")
        or risk.get("dominant_surface")
        or "none"
    )

    dominant_surface = str(
        dominant_surface
    ).upper()

    effective_decision = trace.get("effective_execution_decision") or {}

    control_decision = (
        effective_decision.get("decision")
        or trace.get("control", {}).get("decision")
        or "unknown"
    ).upper()

    enforcement_decision = (
        trace.get("enforcement", {})
        .get("decision", "none")
    ).upper()

    normalized_plan = str(
        plan or "developer"
    ).strip().lower()
    cli_permissions = runtime_cli_permissions(plan)

    timestamp = datetime.now().strftime("%H:%M:%S")

    rows = [
        ("Plan", normalized_plan.capitalize()),
        ("Provider", _fmt(provider)),
        ("Model", _fmt(model)),

        None,

        (
            "Duration",
            _fmt_ms_with_drift(
                duration,
                duration_baseline,
            ),
        ),
        (
            "TTFT",
            _fmt_ms_with_drift(
                ttft,
                ttft_baseline,
            ),
        ),
        (
            "Throughput",
            _fmt_rate(throughput),
        ),
        (
            "Mean Token Gap",
            _fmt_ms(mean_token_gap),
        ),

        None,

        ("Active Signals", str(signal_count)),
        ("Runtime Severity", severity),
        ("Risk Score", _fmt_score(risk_score)),
        ("Dominant Surface", dominant_surface),

        None,
    ]

    rows.extend(
        _decision_rows(
            control_decision,
            enforcement_decision,
            show_enforcement=cli_permissions["show_enforcement"],
        )
    )

    if cli_permissions["show_execution"]:
        execution_row = _execution_row(execution)

        if execution_row:
            rows.append(execution_row)

    rows.append(
        (
            "Trace",
            f"SAVED · {trace_id}" if trace_id else "SAVED",
        )
    )

    _print_rows(
        rows,
        timestamp,
    )