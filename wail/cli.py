import argparse
import datetime
import json
import os
from pathlib import Path

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from wail_private.runtime_policy import runtime_policy
from wail_private.licensing.license import LICENSE_VALID
from wail_private.licensing.license import load_license, LicenseError
from wail_private.licensing.license_state import (
    get_state as get_license_state,
    get_control_quota_state,
)
from wail.runtime.state_fingerprint import compute_state_hash
from wail.runtime.state_store import state_store
from wail.runtime.version import ENGINE_VERSION, SCHEMA_VERSION
from wail.forensics.replay_engine import replay_cli
from wail_private.action_engine import generate_recommendation
from wail_private.investigation_engine import handle_expansion
from wail_private.cli.errors import show_license_error
from wail_private.cli.first_run import render_first_run
from wail_private.licensing.features import (
    max_runtimes,
    max_models,
    controlled_invocations,
    artifact_retention_hours,
)
from wail_private.licensing.machine_fingerprint import machine_fingerprint

AUDIT_DIR = Path("wail_audit")
FULL_STREAM_DIR = Path("wail_state") / "full_stream"

console = Console()

CLI_STATE_FILE = Path.home() / ".wail" / "cli_state.json"


def _first_run_pending():
    if not CLI_STATE_FILE.exists():
        return True

    try:
        data = json.loads(
            CLI_STATE_FILE.read_text(encoding="utf-8")
        )
        return not bool(data.get("first_run_shown"))
    except Exception:
        return True


def _mark_first_run_shown():
    CLI_STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    CLI_STATE_FILE.write_text(
        json.dumps(
            {"first_run_shown": True},
            indent=2,
        ),
        encoding="utf-8",
    )


def _show_first_run_if_needed():
    if not _first_run_pending():
        return

    try:
        result = load_license()
        payload = result.get("payload", {})

        base_plan = (
            result.get("base_plan")
            or payload.get("plan")
            or "developer"
        )

        effective_plan = (
            result.get("effective_plan")
            or base_plan
        )

        trial_active = bool(
            result.get("trial_active", False)
        )

        render_first_run(
            plan=base_plan,
            effective_plan=effective_plan,
            trial_active=trial_active,
            trial_days=14,
        )

        _mark_first_run_shown()

    except Exception:
        return

def _status_text(value):
    text = str(value)
    normalized = text.upper()

    if normalized in {"VALID", "ACTIVE", "VERIFIED", "PASSED"}:
        return Text(text, style="bold green")
    if normalized in {"FAILED", "CRITICAL", "TRUE"}:
        return Text(text, style="bold red")
    if normalized in {"EXPIRED", "BYPASS", "WARNING", "MINOR", "MAJOR"}:
        return Text(text, style="yellow")
    if normalized == "FALSE":
        return Text(text, style="green")
    return Text(text)


def _info_table(rows, *, title=None):
    table = Table(
        title=title,
        show_header=False,
        box=None,
        padding=(0, 1),
        expand=False,
    )
    table.add_column(
        "Field",
        style="grey70",
        no_wrap=True,
        overflow="ellipsis",
    )
    table.add_column(
        "Value",
        overflow="fold",
    )

    for label, value in rows:
        if isinstance(value, Text):
            rendered = value
        else:
            rendered = Text(str(value))
        table.add_row(label, rendered)

    return table


def _compact_panel(content, *, title, border_style="bright_black", max_width=54):
    terminal_width = max(console.size.width, 20)
    panel_width = min(max_width, terminal_width)

    return Panel(
        content,
        title=title,
        border_style=border_style,
        width=panel_width,
        padding=(0, 1),
    )




# -------------------------------------------------
# Helpers
# -------------------------------------------------


def _format_ts(ts):
    if not ts:
        return "N/A"
    if ts > 1e12:
        ts = ts / 1000

    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _load_audit_files():
    if not AUDIT_DIR.exists():
        return []

    files = sorted(
        (
            f
            for f in AUDIT_DIR.glob("*.json")
            if not f.name.endswith("_tech.json")
        ),
        key=lambda p: p.stat().st_mtime,
    )

    traces = []

    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            traces.append(data)
        except Exception:
            continue

    return traces


def _find_trace_by_id(trace_id):
    traces = _load_audit_files()
    for data in traces:
        if str(data.get("metadata", {}).get("trace_id")) == str(trace_id):
            return data
    return None

# -------------------------------------------------
# Existing Commands
# -------------------------------------------------

def cmd_version(_):
    policy = runtime_policy.get()

    table = _info_table(
        [
            ("Engine Version", ENGINE_VERSION),
            ("Schema Version", SCHEMA_VERSION),
            ("Policy Version", policy.version),
        ]
    )
    console.print(
        _compact_panel(
            table,
            title="[bold cyan]WAIL[/bold cyan] [white]Version Information[/white]",
        )
    )


def cmd_license_machine_id(_):
    console.print(machine_fingerprint())


def cmd_license_status(_):
    state = get_license_state()

    try:
        result = load_license()
        payload = result.get("payload", {})

        valid = bool(result.get("valid"))
        license_status = "VALID" if valid else "EXPIRED"

        base_plan = result.get("base_plan") or payload.get("plan") or "unknown"
        effective_plan = result.get("effective_plan") or base_plan

        trial_plan = result.get("trial_plan")
        trial_active = result.get("trial_active", False)
        trial_expires_at = result.get("trial_expires_at")

        customer = payload.get("customer") or "-"
        expires = _format_ts(payload.get("expires_at"))

        runtime_limit = max_runtimes(effective_plan)
        model_limit = max_models(effective_plan)

        rows = [
            ("License", _status_text(license_status)),
            ("Plan", base_plan.capitalize()),
            ("Customer", customer),
            ("Expires", expires),
        ]

        if trial_plan:
            trial_status = "ACTIVE" if trial_active else "EXPIRED"
            rows.extend(
                [
                    (
                        f"{trial_plan.capitalize()} Trial",
                        _status_text(trial_status),
                    ),
                    ("Trial Expires", _format_ts(trial_expires_at)),
                ]
            )

        rows.extend(
            [
                ("Effective Plan", effective_plan.capitalize()),
                (
                    "Max Runtimes",
                    runtime_limit if runtime_limit is not None else "Unlimited",
                ),
                (
                    "Max Models",
                    model_limit if model_limit is not None else "Unlimited",
                ),
            ]
        )

        issued_at = payload.get("issued_at")
        invocation_limit = controlled_invocations(effective_plan)

        if invocation_limit is None:
            rows.append(("Controlled Invocations", "Unlimited"))
        elif issued_at:
            quota = get_control_quota_state(
                scope=f"{issued_at}:{effective_plan}",
                period_anchor=issued_at,
                limit=invocation_limit,
                now=int(datetime.datetime.now().timestamp()),
            )

            rows.extend(
                [
                    ("Controlled Invocations", invocation_limit),
                    ("Used This Period", quota["used"]),
                    ("Remaining", quota["remaining"]),
                    ("Period Ends", _format_ts(quota["period_end"])),
                    (
                        "Control Status",
                        _status_text("ACTIVE" if quota["allowed"] else "BYPASS"),
                    ),
                ]
            )

        security_violation = bool(state.get("security_violation"))
        rows.append(
            (
                "Security Violation",
                Text(
                    str(security_violation),
                    style="bold red" if security_violation else "green",
                ),
            )
        )

        console.print(
            _compact_panel(
                _info_table(rows),
                title="[bold cyan]WAIL[/bold cyan] [white]License Status[/white]",
            )
        )

    except LicenseError as e:
        show_license_error(e)
        console.print(
            f"[bold red]Security Violation:[/bold red] "
            f"{state.get('security_violation')}"
        )
        console.print()
        console.print("To get a license:")
        console.print("[cyan]founder@wailinfra.com[/cyan]")


def cmd_runtime_status(_):
    state = state_store.load()

    rows = [("State Hash", compute_state_hash())]

    if state:
        rows.extend(
            [
                ("Policy Version", state.get("policy_version")),
                ("Segment Limit", state.get("segment_limit")),
                ("Segment Count", len(state.get("segments", {}))),
                ("Schema Version", state.get("schema_version")),
            ]
        )

        content = _info_table(rows)
    else:
        content = Text("No persisted state found.", style="yellow")

    console.print(
        _compact_panel(
            content,
            title="[bold cyan]WAIL[/bold cyan] [white]Runtime Status[/white]",
        )
    )


def cmd_replay(args):
    replay_cli(trace_id=args.trace_id, file_path=args.file)

def cmd_verify_artifact(args):

    from wail.verify.verify_artifact import verify_artifact

    ok, msg = verify_artifact(args.file)

    rows = [
        ("Artifact", os.path.basename(args.file)),
    ]

    if not ok:
        rows.extend(
            [
                ("Status", _status_text("FAILED")),
                ("Signature", _status_text("FAILED")),
                ("Integrity", _status_text("FAILED")),
            ]
        )
        console.print(
            _compact_panel(
                _info_table(rows),
                title="[bold cyan]WAIL[/bold cyan] [white]Artifact Verification[/white]",
                border_style="red",
            )
        )
        console.print(Text(str(msg), style="red"))
        raise SystemExit(1)

    rows.extend(
        [
            ("Status", _status_text("VALID")),
            ("Signature", _status_text("VERIFIED")),
            ("Integrity", _status_text("PASSED")),
        ]
    )
    console.print(
        _compact_panel(
            _info_table(rows),
            title="[bold cyan]WAIL[/bold cyan] [white]Artifact Verification[/white]",
            border_style="green",
        )
    )

# -------------------------------------------------
# TRACE COMMANDS
# -------------------------------------------------

def cmd_trace_incidents(_):

    traces = _load_audit_files()

    incidents = []

    for data in traces:

        control = data.get("control", {})
        execution = data.get("execution", {})
        enforcement = data.get("enforcement", {})
        metadata = data.get("metadata", {})

        decision = control.get("decision", "observe")

        rerouted = execution.get("rerouted", False)

        escalated = enforcement.get("escalated", False)

        if (
            decision != "observe"
            or rerouted
            or escalated
        ):

            incidents.append(data)

    if not incidents:
        print("\nNo runtime interventions found.\n")
        return

    print(f"\nFound {len(incidents)} runtime interventions\n")

    for data in incidents:

        meta = data.get("metadata", {})
        control = data.get("control", {})
        execution = data.get("execution", {})

        target = data.get("execution_target", {})

        print("-" * 60)

        print(f"Trace ID : {meta.get('trace_id')}")
        print(f"Decision : {control.get('decision')}")
        severity = (
            control.get("severity")
            or data.get("incident", {}).get("severity")
            or "unknown"
        )

        print(f"Severity : {severity}")

        if execution.get("rerouted"):

            print(
                f"Provider : "
                f"{target.get('from_provider')} -> "
                f"{target.get('to_provider')}"
            )

        else:

            print(
                f"Provider : "
                f"{meta.get('provider')}"
            )

    print("")

def cmd_trace_show(args):
    data = _find_trace_by_id(args.trace_id)

    if not data:
        print("Trace not found.")
        return

    # -------------------------------------------------
    # NORMAL MODE (INTERACTIVE)
    # -------------------------------------------------
    if not args.full_stream:
        print("\n=== TRACE SUMMARY ===\n")

        meta = data.get("metadata", {})
        ctx = meta.get("invocation_context", {})
        target = data.get("execution_target", {})

        if target:
            print("\n--- EXECUTION TARGET ---\n")
            print(f"From: {target.get('from_provider')} / {target.get('from_model')}")
            print(f"To:   {target.get('to_provider')} / {target.get('to_model')}")

        print(f"Trace ID: {meta.get('trace_id')}")
        print(f"Model: {meta.get('model')}")
        print(f"Service: {ctx.get('service')}")
        print(f"Environment: {ctx.get('env')}")

        if args.raw:
            print("\n--- RAW TRACE (DEBUG) ---\n")
            print(json.dumps(data, indent=2))

        # -----------------------------
        # RECOMMENDATION (SAFE)
        # -----------------------------
        try:

            rec = generate_recommendation(data)
        except Exception as e:
            print("\n[ERROR] Recommendation generation failed:")
            print(str(e))
            return

        print("\n=== RECOMMENDATION ===\n")

        print(f"Priority: {rec.get('priority')}")
        print(f"Category: {rec.get('category')}")
        print(f"\nWhat happened: {rec.get('what_happened')}")
        print(f"\nConfidence: {round(rec.get('confidence', 0), 2)}")

        if args.raw:
            print("\n--- RAW (DEBUG) ---\n")
            print(json.dumps(rec, indent=2))

        # -----------------------------
        # PRE-INCIDENT + ACTION OUTPUT
        # -----------------------------
        pre = data.get("pre_incident")
        action = rec.get("action")

        if pre:
            print("\n=== PRE-INCIDENT SIGNAL ===\n")
            print(f"Level: {pre.get('level')}")
            print(f"Confidence: {pre.get('confidence')}")
            

        if action:
            print("\n=== ACTION MODE ===\n")
            print(f"Mode: {action.get('mode')}")
            print(
                f"Priority: {action.get('action_priority') or action.get('priority')}"
            )
            print("Actions:")

            for a in action.get("actions", []):
                print(f"- {a}")

        # -----------------------------
        # NEXT STEP (SAFE)
        # -----------------------------
        next_step = rec.get("next_step") if isinstance(rec, dict) else None

        if not next_step:
            return

        if not isinstance(next_step, dict):
            return

        if not next_step.get("expandable"):
            return

        print("\n=== SELECT INVESTIGATION PATH ===\n")

        labels = {
            "region": "Regional Analysis",
            "infra": "Infrastructure Analysis",
            "workload": "Workload Analysis",
            "model": "Model Analysis",
        }

        print(f"[1] {labels.get(next_step.get('dimension'), 'Continue Investigation')}")

        alts = next_step.get("alternatives", [])

        for i, alt in enumerate(alts, start=2):
            print(f"[{i}] {labels.get(alt.get('dimension'), 'Additional Analysis')}")

        try:
            choice = input("\nSelect option (or press enter to continue): ").strip()
        except Exception:
            return

        if choice == "" or choice == "1":
            selected = next_step

        elif choice.isdigit() and int(choice) - 2 < len(alts):
            selected = alts[int(choice) - 2]
            selected["expandable"] = True
            selected["depth"] = next_step.get("depth", 1)

        else:
            return

        current_step = selected
        # -----------------------------
        # EXPANSION (CHAIN MODE)
        # -----------------------------
        try:
            print("\n=== INVESTIGATION STARTED ===")

            current_step = selected
            current_depth = selected.get("depth", 1)

            while current_step and current_step.get("expandable"):

                node = handle_expansion(
                    artifact=data,
                    current_step=current_step,
                    priority=rec.get("priority"),
                )

                if not node:
                    print("\nNo further expansion available.")
                    break


                labels = {
                    "region": "Regional Analysis",
                    "infra": "Infrastructure Analysis",
                    "workload": "Workload Analysis",
                    "model": "Model Analysis",
                }

                dimension = node.get("dimension") or "unknown"
                title = labels.get(dimension, dimension.upper())
                print(f"\n=== {title} ===")

                checks = node.get("what_to_check") or []
                actions = node.get("what_to_do") or []

                if checks:
                    print("\nWhat to check:")
                    for item in checks:
                        print(f"  • {item}")

                if actions:
                    print("\nRecommended actions:")
                    for item in actions:
                        print(f"  • {item}")

                next_step = node.get("next_step")

                # STOP condition
                if not next_step or not next_step.get("expandable"):
                    print("\n=== INVESTIGATION COMPLETE ===")
                    break

                print("\n=== CONTINUE INVESTIGATION ===")
                print(f"\n[1] Continue → {next_step.get('text')}")
                choice = input("\nSelect option (or press enter to stop): ").strip()

                if choice != "1":
                    break

                current_step = next_step
                current_depth += 1

        except Exception as e:
            print("\n[ERROR] Expansion failed:")
            print(str(e))

        return

    # -------------------------------------------------
    # FULL STREAM MODE (UNCHANGED)
    # -------------------------------------------------
    forensic_path = FULL_STREAM_DIR / f"{args.trace_id}.json"

    print("\n--- FULL FORENSIC STREAM ---\n")

    if not forensic_path.exists():
        print("No full stream forensic data found.")
        return

    with open(forensic_path, "r", encoding="utf-8") as f:
        timeline = json.load(f)

    print(json.dumps(timeline, indent=2))
    print("")

# -------------------------------------------------
# CLI ENTRY
# -------------------------------------------------


def main():

    parser = argparse.ArgumentParser(prog="wail")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -------------------------------------------------
    # VERSION
    # -------------------------------------------------

    subparsers.add_parser("version").set_defaults(func=cmd_version)

    # -------------------------------------------------
    # LICENSE
    # -------------------------------------------------

    license_parser = subparsers.add_parser("license")
    license_sub = license_parser.add_subparsers(dest="license_cmd")

    status_parser = license_sub.add_parser("status")
    status_parser.set_defaults(func=cmd_license_status)

    machine_id_parser = license_sub.add_parser("machine-id")
    machine_id_parser.set_defaults(func=cmd_license_machine_id)

    # -------------------------------------------------
    # REPLAY (STRICT DETERMINISTIC)
    # -------------------------------------------------

    replay_parser = subparsers.add_parser("replay")
    group = replay_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("trace_id", nargs="?")
    group.add_argument("--file", type=str)
    replay_parser.set_defaults(func=cmd_replay)

    # -------------------------------------------------
    # RUNTIME STATUS
    # -------------------------------------------------

    subparsers.add_parser("runtime-status").set_defaults(func=cmd_runtime_status)

    # -------------------------------------------------
    # VERIFY
    # -------------------------------------------------

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("file")
    verify_parser.set_defaults(func=cmd_verify_artifact)

    # -------------------------------------------------
    # TRACE COMMANDS
    # -------------------------------------------------

    trace_parser = subparsers.add_parser("trace")
    trace_sub = trace_parser.add_subparsers(dest="trace_cmd", required=True)

    show_parser = trace_sub.add_parser("show")
    show_parser.add_argument("trace_id")
    show_parser.add_argument("--full-stream", action="store_true")
    show_parser.add_argument("--raw", action="store_true")
    show_parser.set_defaults(func=cmd_trace_show)

    # -------------------------------------------------
    # TRACES COMMANDS
    # -------------------------------------------------

    traces_parser = subparsers.add_parser("traces")
    traces_sub = traces_parser.add_subparsers(
        dest="traces_cmd",
        required=True,
    )

    incidents_parser = traces_sub.add_parser("incidents")
    incidents_parser.set_defaults(func=cmd_trace_incidents)

    # -------------------------------------------------
    # EXECUTE
    # -------------------------------------------------

    args = parser.parse_args()

    _show_first_run_if_needed()
    
    if args.command == "license":
        if hasattr(args, "func"):
            args.func(args)
        else:
            parser.print_help()
        return

    if not LICENSE_VALID:
        print("WAIL: No valid license found. CLI access disabled.")
        return

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()