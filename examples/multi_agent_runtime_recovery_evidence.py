from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI

import wail
from wail.execution.bridge import execution_runtime
from wail.execution.context import reset_execution_context, set_execution_context
from wail.mcp.adapter import wrap_mcp
from wail_private.execution.recovery_application_store import RecoveryApplicationStore
from wail_private.execution.recovery_store import RecoveryStore
from wail_private.execution.recovery_verification_store import RecoveryVerificationStore
from wail_private.execution.run_baseline import RUN_BASELINE_BUILD_SIZE, RunBaselineStore
from wail_private.execution.run_intelligence_store import RunIntelligenceStore
from wail_private.execution.runtime_control_evidence import RuntimeControlEvidenceStore
from wail_private.execution.signed_agent_evidence import verify_signed_agent_evidence


MODEL = os.environ.get("WAIL_REAL_MULTI_AGENT_MODEL", "gpt-4o-mini")
TOOL = "wail_probe"
BACKUP_TOOL = "wail_probe_backup"
ERROR_TOOL = "wail_probe_error"
BASELINE_DELAY_MS = 100
SEGMENT_KEY = "multi_agent_runtime_recovery_" + uuid4().hex
SERVER_PATH = Path(__file__).resolve().parents[1] / "wail" / "test" / "mcp_runtime_server.py"


class ExampleFailure(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ExampleFailure(message)


@contextmanager
def agent_unit(*, run_id: str, name: str, parent_unit_id: str | None = None, relation_kind: str = "delegates"):
    runtime = execution_runtime()
    unit = runtime.create_unit(
        run_id,
        "agent",
        name=name,
        attributes={"role": name, "real_execution": True},
    )
    if parent_unit_id is not None:
        runtime.relate(run_id, parent_unit_id, unit.unit_id, relation_kind)
    runtime.start_unit(run_id, unit.unit_id, attributes={"role": name})
    token = set_execution_context(run_id, unit.unit_id)
    try:
        yield unit
    except BaseException:
        runtime.fail_unit(run_id, unit.unit_id, attributes={"role": name})
        raise
    else:
        runtime.complete_unit(run_id, unit.unit_id, attributes={"role": name})
    finally:
        reset_execution_context(token)


def model_step(model_client: Any, *, run_id: str, parent_unit_id: str, phase: str) -> str:
    with wail.execution_parent(parent_unit_id, kind="calls"):
        response = model_client.responses.create(
            model=MODEL,
            input=(
                "You are a worker inside a real WAIL multi-agent runtime test. "
                f"Phase: {phase}. Reply with exactly one short sentence confirming "
                "that the worker may execute its assigned runtime probe."
            ),
            max_output_tokens=40,
        )
    text = (getattr(response, "output_text", None) or "").strip()
    check(bool(text), f"real model returned no text during {phase}")
    return text


async def multi_agent_run(
    *,
    model_client: Any,
    mcp_client: Any,
    tool_name: str,
    phase: str,
    expect_error: bool,
) -> str:
    with wail.execution_run(
        attributes={
            "baseline_segment_key": SEGMENT_KEY,
            "example": "multi_agent_runtime_recovery_evidence",
            "orchestration": "coordinator_worker",
        }
    ) as run:
        run_id = run.run_id

        with agent_unit(run_id=run_id, name="coordinator_agent") as coordinator:
            with agent_unit(
                run_id=run_id,
                name="runtime_worker_agent",
                parent_unit_id=coordinator.unit_id,
                relation_kind="delegates",
            ) as worker:
                arguments = {} if tool_name == ERROR_TOOL else {"delay_ms": BASELINE_DELAY_MS}

                model_step(
                    model_client,
                    run_id=run_id,
                    parent_unit_id=worker.unit_id,
                    phase=phase,
                )

                with wail.execution_parent(worker.unit_id, kind="calls"):
                    result = await mcp_client.call_tool(
                        tool_name,
                        arguments=arguments,
                    )

                is_error = bool(getattr(result, "isError", False))
                check(
                    is_error is expect_error,
                    f"{phase}: MCP error state mismatch for {tool_name}: {is_error}",
                )

    state = execution_runtime().state(run_id)
    check(state.status in ("completed", "failed"), f"{phase}: run is not terminal")
    return run_id


def unit_trace(state: Any, *, kind: str, name: str) -> str:
    matches = [
        unit
        for unit in state.units.values()
        if unit.kind == kind and unit.name == name
    ]
    check(bool(matches), f"missing {kind} unit {name}")
    trace_id = (matches[-1].attributes or {}).get("trace_id")
    check(isinstance(trace_id, str) and bool(trace_id), f"{name} has no trace_id")
    return trace_id


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    check(isinstance(value, dict), f"invalid JSON object: {path}")
    return value


def signed_evidence(run_id: str) -> tuple[dict[str, Any], Path]:
    intelligence = RunIntelligenceStore.get_instance().get(run_id)
    check(isinstance(intelligence, dict), f"run intelligence missing: {run_id}")
    evidence = intelligence.get("signed_agent_evidence")
    path_value = intelligence.get("signed_agent_evidence_path")
    check(isinstance(evidence, dict), f"signed evidence missing: {run_id}")
    check(isinstance(path_value, str) and bool(path_value), f"evidence path missing: {run_id}")
    path = Path(path_value)
    check(path.exists(), f"evidence artifact missing: {path}")
    persisted = load_json(path)
    check(verify_signed_agent_evidence(persisted), f"evidence signature invalid: {run_id}")
    return persisted, path


async def main() -> None:
    print("=" * 78)
    print("WAIL REAL MULTI-AGENT + MCP + RUNTIME RECOVERY + SIGNED EVIDENCE E2E")
    print("=" * 78)

    check(bool(os.environ.get("OPENAI_API_KEY")), "OPENAI_API_KEY is required")
    check(SERVER_PATH.exists(), f"MCP runtime server missing: {SERVER_PATH}")
    check(RUN_BASELINE_BUILD_SIZE == 30, f"unexpected baseline size: {RUN_BASELINE_BUILD_SIZE}")

    model_client = wail.wrap(OpenAI())
    baseline_store = RunBaselineStore.get_instance()
    check(
        baseline_store.get(SEGMENT_KEY).get("baseline_observation_count") == 0,
        "test segment is not clean",
    )

    server = StdioServerParameters(command=sys.executable, args=[str(SERVER_PATH)])
    baseline_run_ids: list[str] = []

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}
            for required in (TOOL, BACKUP_TOOL, ERROR_TOOL):
                check(required in names, f"MCP tool missing: {required}")

            mcp_client = wrap_mcp(
                session,
                transport="stdio",
                routes={TOOL: BACKUP_TOOL},
                service="mcp",
                env="multi-agent-runtime-recovery-e2e",
            )

            print(f"Building multi-agent behavioral baseline: {RUN_BASELINE_BUILD_SIZE} real runs")
            for index in range(RUN_BASELINE_BUILD_SIZE):
                run_id = await multi_agent_run(
                    model_client=model_client,
                    mcp_client=mcp_client,
                    tool_name=TOOL,
                    phase=f"baseline-{index + 1}",
                    expect_error=False,
                )
                baseline_run_ids.append(run_id)
                snapshot = baseline_store.get(SEGMENT_KEY)
                check(
                    snapshot.get("baseline_observation_count") == index + 1,
                    f"baseline count mismatch at {index + 1}",
                )

            baseline = baseline_store.get(SEGMENT_KEY)
            check(baseline.get("baseline_locked") is True, "multi-agent baseline did not lock")

            print("Running real failed worker execution...")
            failure_run_id = await multi_agent_run(
                model_client=model_client,
                mcp_client=mcp_client,
                tool_name=ERROR_TOOL,
                phase="failed-worker",
                expect_error=True,
            )
            failure_state = execution_runtime().state(failure_run_id)
            failed_trace_id = unit_trace(failure_state, kind="tool", name=ERROR_TOOL)

            control = RuntimeControlEvidenceStore.get_instance().get(failed_trace_id)
            check(isinstance(control, dict), "failed worker has no runtime control evidence")
            decision = control.get("decision")
            check(isinstance(decision, dict), "runtime control evidence has no decision")
            action = decision.get("decision")
            check(
                action in ("retry", "reroute"),
                f"WAIL did not naturally produce retry/reroute; actual={action!r}",
            )

            source_recovery = RecoveryStore.get_instance().get_by_source_trace(failed_trace_id)
            check(isinstance(source_recovery, dict), "runtime recovery was not resolved for failed worker")
            check(source_recovery.get("run_id") == failure_run_id, "source recovery run mismatch")

            print(f"Natural runtime action: {str(action).upper()}")
            print("Running real N+1 multi-agent recovery application...")
            applied_run_id = await multi_agent_run(
                model_client=model_client,
                mcp_client=mcp_client,
                tool_name=TOOL,
                phase="recovery-application",
                expect_error=False,
            )
            applied_state = execution_runtime().state(applied_run_id)

            applied_unit_name = BACKUP_TOOL if action == "reroute" else TOOL
            applied_trace_id = unit_trace(
                applied_state,
                kind="tool",
                name=applied_unit_name,
            )

    application = RecoveryApplicationStore.get_instance().get_by_applied_trace(applied_trace_id)
    check(isinstance(application, dict), "real N+1 recovery application was not persisted")
    check(application.get("source_trace_id") == failed_trace_id, "application source trace mismatch")
    check(application.get("action") == action, "application action mismatch")
    check(application.get("executed") is True, "recovery action was not executed")

    execution_target = application.get("execution_target") or {}
    if action == "reroute":
        target_name = (
            execution_target.get("model")
            or execution_target.get("name")
            or execution_target.get("target")
            or execution_target.get("tool")
        )
        if target_name is not None:
            check(
                target_name == BACKUP_TOOL,
                f"reroute physical target mismatch: {target_name!r}",
            )

    verification = RecoveryVerificationStore.get_instance().get(applied_run_id)
    check(isinstance(verification, dict), "recovery verification missing")
    check(verification.get("source_run_id") == failure_run_id, "verification source run mismatch")
    check(verification.get("applied_run_id") == applied_run_id, "verification applied run mismatch")
    check(verification.get("source_trace_id") == failed_trace_id, "verification source trace mismatch")
    check(verification.get("applied_trace_id") == applied_trace_id, "verification applied trace mismatch")
    check(verification.get("action") == action, "verification action mismatch")
    check(verification.get("application_executed") is True, "verification lost application evidence")
    check(verification.get("status") == "recovered", f"recovery not verified: {verification}")
    check(verification.get("recovered") is True, "recovered flag mismatch")

    failure_evidence, failure_path = signed_evidence(failure_run_id)
    applied_evidence, applied_path = signed_evidence(applied_run_id)

    failure_payload = failure_evidence.get("payload") or {}
    applied_payload = applied_evidence.get("payload") or {}
    failure_execution = failure_payload.get("execution") or {}
    applied_execution = applied_payload.get("execution") or {}

    for label, execution in (("failure", failure_execution), ("applied", applied_execution)):
        kinds = [unit.get("kind") for unit in execution.get("units", [])]
        check(kinds.count("agent") >= 2, f"{label} evidence lost multi-agent graph")
        check("model" in kinds, f"{label} evidence lost real model execution")
        check("tool" in kinds, f"{label} evidence lost real MCP execution")
        relation_kinds = {relation.get("kind") for relation in execution.get("relations", [])}
        check("delegates" in relation_kinds, f"{label} evidence lost delegation edge")
        check("calls" in relation_kinds, f"{label} evidence lost call edge")

    failure_recovery = failure_payload.get("runtime_recovery") or {}
    check(failure_recovery.get("action") == action, "failure evidence lost runtime recovery action")

    applied_verification = applied_payload.get("recovery_verification") or {}
    check(applied_verification.get("status") == "recovered", "applied evidence lost recovery verification")
    check(applied_verification.get("source_trace_id") == failed_trace_id, "signed verification source trace mismatch")
    check(applied_verification.get("applied_trace_id") == applied_trace_id, "signed verification applied trace mismatch")

    check(failure_path.read_text(encoding="utf-8").startswith("{\n  "), "failure evidence is not pretty JSON")
    check(applied_path.read_text(encoding="utf-8").startswith("{\n  "), "applied evidence is not pretty JSON")

    print()
    print("=" * 78)
    print("RESULT")
    print("=" * 78)
    print(f"Baseline runs             : {len(baseline_run_ids)} real multi-agent runs")
    print(f"Failure run               : {failure_run_id}")
    print(f"Failed trace              : {failed_trace_id}")
    print(f"Natural WAIL action       : {str(action).upper()}")
    print(f"Recovery run              : {applied_run_id}")
    print(f"Applied trace             : {applied_trace_id}")
    print(f"Recovery verification     : {verification.get('status')}")
    print(f"Failure evidence          : {failure_path}")
    print(f"Recovery evidence         : {applied_path}")
    print("Decision injection        : NONE")
    print("Real OpenAI execution     : PASS")
    print("Real MCP execution        : PASS")
    print("Multi-agent graph         : PASS")
    print("Natural runtime control   : PASS")
    print("Real N+1 application      : PASS")
    print("Recovery verification     : PASS")
    print("Signed agent evidence     : PASS")
    print("EVIDENCE VERIFICATION     : VALID")
    print("RUN STATUS                : COMPLETED")
    print("=" * 78)


if __name__ == "__main__":
    asyncio.run(main())
