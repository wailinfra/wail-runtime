from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from wail.runtime.context import (
    mark_runtime_error,
    mark_runtime_interrupted,
    refresh_license_state,
    wail_end,
    wail_retry,
    wail_start,
)
from wail.runtime_config import _runtime_config
from wail_private import runtime_decision_store
from wail_private.licensing.features import can_reroute


class MCPRuntimeAdapter:
    __slots__ = (
        "_session",
        "_original_call_tool",
        "_transport",
        "_routes",
        "_service",
        "_env",
    )

    def __init__(
        self,
        session: Any,
        *,
        transport: str | None = None,
        routes: Mapping[str, str] | None = None,
        service: str = "mcp",
        env: str = "default",
    ) -> None:
        if session is None:
            raise ValueError("session is required")

        call_tool = getattr(session, "call_tool", None)

        if call_tool is None or not callable(call_tool):
            raise TypeError(
                "session must provide a callable call_tool()"
            )

        self._session = session
        self._original_call_tool = call_tool
        self._transport = transport
        self._routes = dict(routes or {})
        self._service = service
        self._env = env

    def __getattr__(
        self,
        name: str,
    ) -> Any:
        return getattr(
            self._session,
            name,
        )

    def _resolve_execution(
        self,
        requested_tool: str,
    ) -> tuple[str, str, bool, str | None, str | None]:
        control_allowed = bool(
            _runtime_config.get(
                "_control_allowed",
                True,
            )
        )

        if control_allowed:
            pending = runtime_decision_store.consume(
                surface="tool"
            )
        else:
            runtime_decision_store.consume(
                surface="tool"
            )
            pending = {
                "decision": "observe",
                "reason": "control_quota_exhausted",
            }

        action = str(
            pending.get("decision")
            or "observe"
        )

        source_trace_id = pending.get("_source_trace_id")
        reason = pending.get("reason")
        executed_tool = requested_tool
        executed = False

        if action == "reroute":
            license_state = refresh_license_state()

            if not can_reroute(
                license_state["plan"]
            ):
                action = "observe"
                reason = "reroute_not_entitled"

            else:
                target = self._routes.get(
                    requested_tool
                )

                if target and target != requested_tool:
                    executed_tool = target
                    executed = True
                else:
                    action = "observe"
                    reason = "reroute_target_unavailable"

        elif action == "retry":
            executed = True

        else:
            action = "observe"

        return (
            executed_tool,
            action,
            executed,
            reason,
            source_trace_id,
        )

    @staticmethod
    def _arguments_hash(
        arguments: dict[str, Any],
    ) -> str:
        payload = json.dumps(
            arguments,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")

        return hashlib.sha256(
            payload
        ).hexdigest()

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        if not name:
            raise ValueError(
                "tool name is required"
            )

        resolved_arguments = (
            dict(arguments)
            if arguments is not None
            else {}
        )

        (
            executed_tool,
            control_action,
            control_executed,
            control_reason,
            source_trace_id,
        ) = self._resolve_execution(name)

        invocation_context = {
            "type": "tool",
            "service": self._service,
            "env": self._env,
            "protocol": "mcp",
            "requested_tool": name,
            "_control_action": control_action,
            "_control_executed": control_executed,
        }

        if control_reason is not None:
            invocation_context[
                "_control_reason"
            ] = control_reason

        wail_start(
            model=executed_tool,
            provider=None,
            transport=self._transport,
            invocation_context=invocation_context,
            prompt_hash=self._arguments_hash(
                resolved_arguments
            ),
        )

        if (
            source_trace_id
            and control_action in {"retry", "reroute"}
        ):
            from wail.execution.bridge import current_bound_trace
            from wail_private.execution.recovery_application_store import RecoveryApplicationStore

            bound_trace = current_bound_trace()

            if bound_trace is not None:
                RecoveryApplicationStore.get_instance().save(
                    applied_trace_id=bound_trace.trace_id,
                    source_trace_id=source_trace_id,
                    action=control_action,
                    executed=control_executed,
                    reason=control_reason,
                )

        if control_action == "retry":
            wail_retry()

        try:
            result = await self._original_call_tool(
                executed_tool,
                arguments=resolved_arguments,
                **kwargs,
            )

            if bool(
                getattr(
                    result,
                    "isError",
                    False,
                )
            ):
                mark_runtime_error()

            return result

        except Exception:
            mark_runtime_error()
            raise
        except BaseException:
            mark_runtime_interrupted()
            raise

        finally:
            wail_end()


def wrap_mcp(
    session: Any,
    *,
    transport: str | None = None,
    routes: Mapping[str, str] | None = None,
    service: str = "mcp",
    env: str = "default",
) -> MCPRuntimeAdapter:
    if isinstance(
        session,
        MCPRuntimeAdapter,
    ):
        return session

    return MCPRuntimeAdapter(
        session,
        transport=transport,
        routes=routes,
        service=service,
        env=env,
    )