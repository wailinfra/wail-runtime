from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI

import wail
from wail.execution.bridge import execution_runtime
from wail.execution.context import reset_execution_context, set_execution_context
from wail.mcp.adapter import wrap_mcp
from wail_private.execution.run_intelligence_store import RunIntelligenceStore
from wail_private.execution.signed_agent_evidence import verify_signed_agent_evidence


MODEL = os.environ.get("WAIL_REAL_MULTI_AGENT_MODEL", "gpt-4o-mini")
MAX_TOOL_ROUNDS = 3
AUDIT_DIR = Path("wail_audit")
SERVER_PATH = Path(__file__).resolve().parent / "multi_agent_mcp_server.py"

REQUIRED_TOOLS = {
    "list_python_files",
    "inspect_python_file",
    "read_python_source",
    "search_python_source",
    "python_file_stats",
}


class ExampleFailure(RuntimeError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ExampleFailure(message)


def mcp_result_text(result: Any) -> str:
    parts: list[str] = []

    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            parts.append(text)
            continue

        if hasattr(item, "model_dump"):
            parts.append(
                json.dumps(
                    item.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        else:
            parts.append(str(item))

    if not parts:
        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            return json.dumps(
                structured,
                ensure_ascii=False,
                sort_keys=True,
            )

    return "\n".join(parts)


def openai_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for tool in mcp_tools:
        result.append(
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description or tool.name,
                "parameters": tool.inputSchema or {
                    "type": "object",
                    "properties": {},
                },
            }
        )

    return result


def function_calls(response: Any) -> list[Any]:
    return [
        item
        for item in getattr(response, "output", []) or []
        if getattr(item, "type", None) == "function_call"
    ]


@contextmanager
def real_agent(
    *,
    run_id: str,
    name: str,
    parent_unit_id: str | None,
    relation_kind: str,
):
    runtime = execution_runtime()

    unit = runtime.create_unit(
        run_id,
        "agent",
        name=name,
        attributes={
            "role": name,
            "real_model_execution": True,
        },
    )

    if parent_unit_id is not None:
        runtime.relate(
            run_id,
            parent_unit_id,
            unit.unit_id,
            relation_kind,
        )

    runtime.start_unit(
        run_id,
        unit.unit_id,
        attributes={
            "role": name,
        },
    )

    token = set_execution_context(
        run_id,
        unit.unit_id,
    )

    try:
        yield unit
    except BaseException:
        runtime.fail_unit(
            run_id,
            unit.unit_id,
            attributes={
                "role": name,
            },
        )
        raise
    else:
        runtime.complete_unit(
            run_id,
            unit.unit_id,
            attributes={
                "role": name,
            },
        )
    finally:
        reset_execution_context(token)


async def execute_agent(
    *,
    run_id: str,
    name: str,
    parent_unit_id: str | None,
    relation_kind: str,
    prompt: str,
    model_client: Any,
    mcp_client: Any,
    tools: list[dict[str, Any]],
    required_tool: str,
    tool_arguments: dict[str, Any],
) -> tuple[str, str, int]:
    available_tool_names = {
        tool.get("name")
        for tool in tools
        if isinstance(tool, dict)
    }
    check(
        required_tool in available_tool_names,
        f"{name} required MCP tool unavailable: {required_tool}",
    )

    with real_agent(
        run_id=run_id,
        name=name,
        parent_unit_id=parent_unit_id,
        relation_kind=relation_kind,
    ) as agent_unit:
        planning_response = model_client.responses.create(
            model=MODEL,
            input=(
                f"{prompt}\n\n"
                f"Your assigned repository capability is {required_tool}. "
                "State briefly what you need to verify with it. "
                "Do not invent the tool result."
            ),
            max_output_tokens=180,
        )

        planning_text = (
            getattr(planning_response, "output_text", None) or ""
        ).strip()
        check(planning_text, f"{name} returned no planning text")

        with wail.execution_parent(
            agent_unit.unit_id,
            kind="calls",
        ):
            result = await mcp_client.call_tool(
                required_tool,
                arguments=dict(tool_arguments),
            )

        check(
            not bool(getattr(result, "isError", False)),
            f"{name} MCP call failed: {required_tool}",
        )

        observation = mcp_result_text(result)
        check(observation, f"{name} MCP call returned no observation")

        final_response = model_client.responses.create(
            model=MODEL,
            input=(
                f"{prompt}\n\n"
                "PLANNING:\n"
                f"{planning_text}\n\n"
                f"REAL MCP TOOL: {required_tool}\n"
                "REAL MCP OBSERVATION:\n"
                f"{observation}\n\n"
                "Return a concise factual result grounded only in the real "
                "MCP observation. Do not invent files, symbols, or measurements."
            ),
            max_output_tokens=300,
        )

        final_text = (
            getattr(final_response, "output_text", None) or ""
        ).strip()
        check(final_text, f"{name} returned no final text")

        return agent_unit.unit_id, final_text, 1

def load_evidence(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)

    check(isinstance(value, dict), "evidence root is not an object")
    return value


async def main() -> None:
    print("=" * 76)
    print("WAIL MULTI-AGENT + MCP SIGNED EVIDENCE EXAMPLE")
    print("=" * 76)

    check(bool(os.environ.get("OPENAI_API_KEY")), "OPENAI_API_KEY is required")
    check(SERVER_PATH.exists(), f"MCP server missing: {SERVER_PATH}")

    raw_client = OpenAI()
    model_client = wail.wrap(raw_client)

    server = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
    )

    segment_key = f"real_multi_agent_evidence_{uuid.uuid4().hex}"

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            listed = await session.list_tools()
            available = {tool.name for tool in listed.tools}

            missing_tools = sorted(REQUIRED_TOOLS - available)
            check(
                not missing_tools,
                f"required MCP tools missing: {missing_tools}",
            )

            selected_mcp_tools = [
                tool
                for tool in listed.tools
                if tool.name in REQUIRED_TOOLS
            ]
            tools = openai_tools(selected_mcp_tools)

            mcp_client = wrap_mcp(
                session,
                transport="stdio",
                service="mcp",
                env="real-multi-agent-evidence",
            )

            with wail.execution_run(
                attributes={
                    "example": "multi_agent_mcp_evidence",
                    "baseline_segment_key": segment_key,
                    "orchestration": "coordinator_fanout_fanin",
                }
            ) as run:
                run_id = run.run_id

                coordinator_id, coordinator_text, coordinator_calls = (
                    await execute_agent(
                        run_id=run_id,
                        name="coordinator_agent",
                        parent_unit_id=None,
                        relation_kind="calls",
                        prompt=(
                            "You are the coordinator of a real multi-agent WAIL repository "
                            "analysis. Use the list_python_files MCP tool to inspect the real "
                            "repository. Then produce a concise plan for two independent "
                            "specialists: one execution-structure researcher and one runtime "
                            "resilience researcher. Base the plan only on the real repository "
                            "observation and do not invent files or results."
                        ),
                        model_client=model_client,
                        mcp_client=mcp_client,
                        tools=tools,
                        required_tool="list_python_files",
                        tool_arguments={"path_prefix": "", "limit": 100},
                    )
                )

                performance_id, performance_text, performance_calls = (
                    await execute_agent(
                        run_id=run_id,
                        name="execution_structure_research_agent",
                        parent_unit_id=coordinator_id,
                        relation_kind="delegates",
                        prompt=(
                            "You are the execution-structure research agent. "
                            "Coordinator context follows:\n\n"
                            f"{coordinator_text}\n\n"
                            "Use the search_python_source MCP tool to search the real WAIL "
                            "repository for execution_run. Use the returned repository evidence "
                            "in your analysis. Return a concise factual result and do not invent "
                            "files, symbols, or measurements."
                        ),
                        model_client=model_client,
                        mcp_client=mcp_client,
                        tools=tools,
                        required_tool="search_python_source",
                        tool_arguments={
                            "query": "execution_run",
                            "path_prefix": "",
                            "limit": 20,
                        },
                    )
                )

                resilience_id, resilience_text, resilience_calls = (
                    await execute_agent(
                        run_id=run_id,
                        name="resilience_research_agent",
                        parent_unit_id=coordinator_id,
                        relation_kind="delegates",
                        prompt=(
                            "You are the runtime resilience research agent. "
                            "Coordinator context follows:\n\n"
                            f"{coordinator_text}\n\n"
                            "Use the search_python_source MCP tool to search the real WAIL "
                            "repository for runtime_recovery. Use the returned repository "
                            "evidence in your analysis. Return a concise factual result and "
                            "do not invent files, symbols, or measurements."
                        ),
                        model_client=model_client,
                        mcp_client=mcp_client,
                        tools=tools,
                        required_tool="search_python_source",
                        tool_arguments={
                            "query": "runtime_recovery",
                            "path_prefix": "",
                            "limit": 20,
                        },
                    )
                )

                verifier_id, verifier_text, verifier_calls = (
                    await execute_agent(
                        run_id=run_id,
                        name="verification_agent",
                        parent_unit_id=coordinator_id,
                        relation_kind="delegates",
                        prompt=(
                            "You are the independent verification agent. Compare these "
                            "two specialist reports:\n\n"
                            "EXECUTION STRUCTURE:\n"
                            f"{performance_text}\n\n"
                            "RUNTIME RESILIENCE:\n"
                            f"{resilience_text}\n\n"
                            "Use the python_file_stats MCP tool to obtain an independent "
                            "real repository observation before giving your verification "
                            "result. Do not claim anything that the reports or your MCP "
                            "result do not support."
                        ),
                        model_client=model_client,
                        mcp_client=mcp_client,
                        tools=tools,
                        required_tool="python_file_stats",
                        tool_arguments={"path_prefix": "", "top_n": 10},
                    )
                )

                runtime = execution_runtime()

                synthesis = runtime.create_unit(
                    run_id,
                    "agent",
                    name="synthesis_agent",
                    attributes={
                        "role": "synthesis_agent",
                        "real_model_execution": True,
                    },
                )

                runtime.relate(
                    run_id,
                    performance_id,
                    synthesis.unit_id,
                    "joins",
                )
                runtime.relate(
                    run_id,
                    resilience_id,
                    synthesis.unit_id,
                    "joins",
                )
                runtime.relate(
                    run_id,
                    verifier_id,
                    synthesis.unit_id,
                    "joins",
                )

                runtime.start_unit(
                    run_id,
                    synthesis.unit_id,
                    attributes={"role": "synthesis_agent"},
                )

                synthesis_token = set_execution_context(
                    run_id,
                    synthesis.unit_id,
                )

                try:
                    final_response = model_client.responses.create(
                        model=MODEL,
                        input=(
                            "You are the final synthesis agent in a multi-agent system. "
                            "Produce a short final report using only the evidence below. "
                            "Do not invent measurements.\n\n"
                            "COORDINATOR:\n"
                            f"{coordinator_text}\n\n"
                            "EXECUTION STRUCTURE AGENT:\n"
                            f"{performance_text}\n\n"
                            "RUNTIME RESILIENCE AGENT:\n"
                            f"{resilience_text}\n\n"
                            "VERIFICATION AGENT:\n"
                            f"{verifier_text}"
                        ),
                        max_output_tokens=350,
                    )

                    final_text = (
                        getattr(final_response, "output_text", None) or ""
                    ).strip()
                    check(final_text, "synthesis agent returned no final report")

                    runtime.complete_unit(
                        run_id,
                        synthesis.unit_id,
                        attributes={"role": "synthesis_agent"},
                    )
                except BaseException:
                    runtime.fail_unit(
                        run_id,
                        synthesis.unit_id,
                        attributes={"role": "synthesis_agent"},
                    )
                    raise
                finally:
                    reset_execution_context(synthesis_token)

                running = runtime.state(run_id)

                agent_units = [
                    unit
                    for unit in running.units.values()
                    if unit.kind == "agent"
                ]
                model_units = [
                    unit
                    for unit in running.units.values()
                    if unit.kind == "model"
                ]
                tool_units = [
                    unit
                    for unit in running.units.values()
                    if unit.kind == "tool"
                ]

                check(len(agent_units) == 5, "expected five real agent units")
                check(len(model_units) >= 5, "expected real model executions")

                if len(tool_units) < 4:
                    unit_snapshot = [
                        {
                            "kind": unit.kind,
                            "name": unit.name,
                            "status": unit.status,
                            "trace_id": unit.attributes.get("trace_id"),
                        }
                        for unit in running.units.values()
                    ]
                    relation_snapshot = [
                        {
                            "kind": relation.kind,
                            "source": relation.source_unit_id,
                            "target": relation.target_unit_id,
                        }
                        for relation in running.relations
                    ]
                    raise ExampleFailure(
                        "expected at least four WAIL tool execution units; "
                        f"observed={len(tool_units)}; "
                        f"agent_reported_mcp_calls="
                        f"{coordinator_calls + performance_calls + resilience_calls + verifier_calls}; "
                        f"units={unit_snapshot}; "
                        f"relations={relation_snapshot}"
                    )

                relation_kinds = {
                    relation.kind
                    for relation in running.relations
                }
                check("delegates" in relation_kinds, "delegation edge missing")
                check("joins" in relation_kinds, "fan-in join edge missing")
                check("calls" in relation_kinds, "agent child call edge missing")

                total_agent_tool_calls = (
                    coordinator_calls
                    + performance_calls
                    + resilience_calls
                    + verifier_calls
                )
                check(
                    total_agent_tool_calls >= 4,
                    "agents did not execute enough MCP calls",
                )

    state = execution_runtime().state(run_id)
    check(state.status == "completed", "multi-agent run did not complete")

    intelligence = RunIntelligenceStore.get_instance().get(run_id)
    check(intelligence is not None, "run intelligence missing")

    evidence = intelligence.get("signed_agent_evidence")
    evidence_path_value = intelligence.get("signed_agent_evidence_path")

    check(isinstance(evidence, dict), "signed agent evidence missing")
    check(
        isinstance(evidence_path_value, str) and evidence_path_value,
        "signed agent evidence path missing",
    )

    evidence_path = Path(evidence_path_value)
    check(evidence_path.exists(), f"evidence file missing: {evidence_path}")

    persisted = load_evidence(evidence_path)

    check(
        verify_signed_agent_evidence(persisted),
        "signed agent evidence verification failed",
    )

    payload = persisted.get("payload") or {}
    execution = payload.get("execution") or {}

    persisted_agents = [
        unit
        for unit in execution.get("units", [])
        if unit.get("kind") == "agent"
    ]
    persisted_models = [
        unit
        for unit in execution.get("units", [])
        if unit.get("kind") == "model"
    ]
    persisted_tools = [
        unit
        for unit in execution.get("units", [])
        if unit.get("kind") == "tool"
    ]

    check(len(persisted_agents) == 5, "evidence agent graph incomplete")
    check(len(persisted_models) >= 5, "evidence model graph incomplete")
    check(len(persisted_tools) >= 4, "evidence MCP graph incomplete")

    for field in (
        "pathology",
        "localization",
        "propagation",
        "causal_attribution",
        "runtime_recovery",
        "recovery_verification",
    ):
        check(payload.get(field) is not None, f"{field} is still null")

    raw_text = evidence_path.read_text(encoding="utf-8")
    check(
        raw_text.startswith("{\n  "),
        "evidence JSON is not pretty-printed",
    )
    check(
        "\n    " in raw_text,
        "evidence JSON indentation missing",
    )

    print()
    print("=" * 76)
    print("REAL MULTI-AGENT EXECUTION")
    print("=" * 76)
    print(f"Run ID                   : {run_id}")
    print(f"Model                    : {MODEL}")
    print(f"Agent Units              : {len(persisted_agents)}")
    print(f"Model Units              : {len(persisted_models)}")
    print(f"MCP Tool Units           : {len(persisted_tools)}")
    print(f"Relations                : {len(execution.get('relations', []))}")
    print(f"Evidence Verification    : PASS")
    print(f"Evidence Pretty JSON     : PASS")
    print(f"Evidence Null Semantics  : PASS")
    print(f"Artifact                 : {evidence_path}")
    print()
    print("FINAL SYNTHESIS")
    print("-" * 76)
    print(final_text)
    print()
    print("SIGNED AGENT EVIDENCE")
    print("-" * 76)
    print(raw_text)
    print("=" * 76)
    print("RUN STATUS               : COMPLETED")
    print("EVIDENCE VERIFICATION    : VALID")
    print("=" * 76)


if __name__ == "__main__":
    asyncio.run(main())
