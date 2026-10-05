from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass

from .contract import ExecutionReference


@dataclass(frozen=True, slots=True)
class TraceBinding:
    run_id: str
    unit_id: str
    trace_id: str
    span_id: str | None = None
    parent_span_id: str | None = None


_current_trace_binding: ContextVar[TraceBinding | None] = ContextVar(
    "wail_execution_trace_binding",
    default=None,
)


def current_trace_binding() -> TraceBinding | None:
    return _current_trace_binding.get()


def bind_trace(
    run_id: str,
    unit_id: str,
    trace_id: str,
    *,
    span_id: str | None = None,
    parent_span_id: str | None = None,
) -> Token[TraceBinding | None]:
    if not run_id:
        raise ValueError("run_id is required")

    if not unit_id:
        raise ValueError("unit_id is required")

    if not trace_id:
        raise ValueError("trace_id is required")

    return _current_trace_binding.set(
        TraceBinding(
            run_id=run_id,
            unit_id=unit_id,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
        )
    )


def reset_trace_binding(
    token: Token[TraceBinding | None],
) -> None:
    _current_trace_binding.reset(token)


def trace_reference(
    trace_id: str,
    *,
    span_id: str | None = None,
    parent_span_id: str | None = None,
) -> ExecutionReference:
    if not trace_id:
        raise ValueError("trace_id is required")

    attributes = {}

    if span_id is not None:
        attributes["span_id"] = span_id

    if parent_span_id is not None:
        attributes["parent_span_id"] = parent_span_id

    return ExecutionReference(
        ref_type="wail_trace",
        ref_id=trace_id,
        namespace="wail.runtime",
        attributes=attributes,
    )


class trace_binding_scope:
    __slots__ = ("_binding", "_token")

    def __init__(
        self,
        run_id: str,
        unit_id: str,
        trace_id: str,
        *,
        span_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> None:
        if not run_id:
            raise ValueError("run_id is required")

        if not unit_id:
            raise ValueError("unit_id is required")

        if not trace_id:
            raise ValueError("trace_id is required")

        self._binding = TraceBinding(
            run_id=run_id,
            unit_id=unit_id,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
        )

        self._token: Token[TraceBinding | None] | None = None

    def __enter__(self) -> TraceBinding:
        self._token = _current_trace_binding.set(
            self._binding
        )
        return self._binding

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        if self._token is not None:
            _current_trace_binding.reset(
                self._token
            )
            self._token = None