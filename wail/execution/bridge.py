from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Mapping

from .binding import (
    TraceBinding,
    bind_trace,
    current_trace_binding,
    reset_trace_binding,
)
from .context import (
    current_execution_context,
    reset_execution_context,
    set_execution_context,
)
from .contract import ExecutionValue
from .runtime import ExecutionRuntime


@dataclass(slots=True)
class ActiveExecutionBinding:
    run_id: str
    unit_id: str
    owns_run: bool
    top_level_in_run: bool
    execution_token: object | None = None
    trace_token: object | None = None
    active_token: object | None = None


@dataclass(frozen=True, slots=True)
class ActiveRunScope:
    run_id: str

    def relate(
        self,
        source_unit_id: str,
        target_unit_id: str,
        kind: str,
    ):
        return _execution_runtime.relate(
            self.run_id,
            source_unit_id,
            target_unit_id,
            kind,
        )


_execution_runtime = ExecutionRuntime()

_active_execution_binding: ContextVar[
    ActiveExecutionBinding | None
] = ContextVar(
    "wail_active_execution_binding",
    default=None,
)

_active_run_scope: ContextVar[
    ActiveRunScope | None
] = ContextVar(
    "wail_active_run_scope",
    default=None,
)

_active_relation_kind: ContextVar[str] = ContextVar(
    "wail_active_relation_kind",
    default="calls",
)

_continuation_unit_id: ContextVar[str | None] = ContextVar(
    "wail_continuation_unit_id",
    default=None,
)


def execution_runtime() -> ExecutionRuntime:
    return _execution_runtime


def current_execution_binding() -> ActiveExecutionBinding | None:
    return _active_execution_binding.get()


def current_run_scope() -> ActiveRunScope | None:
    return _active_run_scope.get()


def current_parent_agent_name() -> str | None:
    context = current_execution_context()

    if context is None or context.unit_id is None:
        return None

    try:
        state = _execution_runtime.state(context.run_id)
        unit = state.units.get(context.unit_id)
    except Exception:
        return None

    if unit is None or unit.kind != "agent":
        return None

    return unit.name or unit.unit_id


class execution_parent_scope:
    __slots__ = (
        "_run_id",
        "_unit_id",
        "_kind",
        "_execution_token",
        "_relation_token",
    )

    def __init__(
        self,
        unit_id: str,
        *,
        kind: str = "calls",
    ) -> None:
        if not unit_id:
            raise ValueError("unit_id is required")

        if not kind:
            raise ValueError("kind is required")

        scope = current_run_scope()

        if scope is None:
            raise RuntimeError(
                "execution parent scope requires an active run"
            )

        self._run_id = scope.run_id
        self._unit_id = unit_id
        self._kind = kind
        self._execution_token: object | None = None
        self._relation_token: object | None = None

    def __enter__(self):
        self._execution_token = set_execution_context(
            self._run_id,
            self._unit_id,
        )
        self._relation_token = _active_relation_kind.set(
            self._kind
        )
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        if self._relation_token is not None:
            _active_relation_kind.reset(
                self._relation_token
            )
            self._relation_token = None

        if self._execution_token is not None:
            reset_execution_context(
                self._execution_token
            )
            self._execution_token = None


class execution_run_scope:
    __slots__ = (
        "_attributes",
        "_run_id",
        "_execution_token",
        "_scope_token",
        "_continuation_token",
    )

    def __init__(
        self,
        *,
        run_id: str | None = None,
        attributes: Mapping[str, ExecutionValue] | None = None,
    ) -> None:
        self._attributes = dict(attributes or {})
        self._run_id = run_id
        self._execution_token: object | None = None
        self._scope_token: object | None = None
        self._continuation_token: object | None = None

    def __enter__(self) -> ActiveRunScope:
        existing = current_execution_context()

        if existing is not None:
            raise RuntimeError(
                "execution run scope cannot start inside an active execution"
            )

        run = _execution_runtime.start_run(
            run_id=self._run_id,
            attributes=self._attributes,
        )

        scope = ActiveRunScope(
            run_id=run.run_id,
        )

        self._execution_token = set_execution_context(
            run.run_id,
            None,
        )
        self._scope_token = _active_run_scope.set(scope)
        self._continuation_token = _continuation_unit_id.set(None)

        return scope

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        scope = _active_run_scope.get()

        try:
            if scope is not None:
                if exc_type is None:
                    _execution_runtime.complete_run(scope.run_id)
                else:
                    _execution_runtime.fail_run(scope.run_id)
        finally:
            if self._continuation_token is not None:
                _continuation_unit_id.reset(self._continuation_token)
                self._continuation_token = None

            if self._scope_token is not None:
                _active_run_scope.reset(self._scope_token)
                self._scope_token = None

            if self._execution_token is not None:
                reset_execution_context(self._execution_token)
                self._execution_token = None


def bind_runtime_trace(
    trace_id: str,
    *,
    span_id: str | None = None,
    parent_span_id: str | None = None,
    kind: str = "model",
    name: str | None = None,
) -> ActiveExecutionBinding:
    if not trace_id:
        raise ValueError("trace_id is required")

    existing = current_execution_context()
    run_scope = _active_run_scope.get()
    owns_run = existing is None

    if existing is None:
        run = _execution_runtime.start_run()
        run_id = run.run_id
    else:
        run_id = existing.run_id

    unit = _execution_runtime.create_unit(
        run_id,
        kind,
        name=name,
    )
    unit_id = unit.unit_id

    if existing is not None and existing.unit_id is not None:
        _execution_runtime.relate(
            run_id,
            existing.unit_id,
            unit_id,
            _active_relation_kind.get(),
        )
    elif run_scope is not None and run_scope.run_id == run_id:
        continuation_unit_id = _continuation_unit_id.get()

        if continuation_unit_id is not None:
            _execution_runtime.relate(
                run_id,
                continuation_unit_id,
                unit_id,
                "continues",
            )

    execution_token = set_execution_context(
        run_id,
        unit_id,
    )

    _execution_runtime.start_unit(
        run_id,
        unit_id,
        attributes={
            "trace_id": trace_id,
        },
    )

    trace_token = bind_trace(
        run_id,
        unit_id,
        trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
    )

    binding = ActiveExecutionBinding(
        run_id=run_id,
        unit_id=unit_id,
        owns_run=owns_run,
        top_level_in_run=(
            existing is not None
            and existing.unit_id is None
        ),
        execution_token=execution_token,
        trace_token=trace_token,
    )
    binding.active_token = _active_execution_binding.set(binding)

    return binding


def complete_runtime_trace(
    *,
    failed: bool = False,
) -> None:
    binding = _active_execution_binding.get()

    if binding is None:
        return

    run_scope = _active_run_scope.get()

    try:
        if failed:
            _execution_runtime.fail_unit(
                binding.run_id,
                binding.unit_id,
            )
        else:
            _execution_runtime.complete_unit(
                binding.run_id,
                binding.unit_id,
            )

        if (
            run_scope is not None
            and run_scope.run_id == binding.run_id
            and binding.top_level_in_run
        ):
            _continuation_unit_id.set(binding.unit_id)

        if binding.owns_run:
            if failed:
                _execution_runtime.fail_run(binding.run_id)
            else:
                _execution_runtime.complete_run(binding.run_id)

    finally:
        if binding.trace_token is not None:
            reset_trace_binding(binding.trace_token)

        if binding.execution_token is not None:
            reset_execution_context(binding.execution_token)

        if binding.active_token is not None:
            _active_execution_binding.reset(binding.active_token)


def current_bound_trace() -> TraceBinding | None:
    return current_trace_binding()