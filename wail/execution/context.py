from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    run_id: str
    unit_id: str | None = None


_execution_context_var: ContextVar[ExecutionContext | None] = ContextVar(
    "wail_execution_context",
    default=None,
)


def current_execution_context() -> ExecutionContext | None:
    return _execution_context_var.get()


def current_execution_run_id() -> str | None:
    context = _execution_context_var.get()

    if context is None:
        return None

    return context.run_id


def current_execution_unit_id() -> str | None:
    context = _execution_context_var.get()

    if context is None:
        return None

    return context.unit_id


def set_execution_context(
    run_id: str,
    unit_id: str | None = None,
) -> Token[ExecutionContext | None]:
    if not run_id:
        raise ValueError("run_id is required")

    return _execution_context_var.set(
        ExecutionContext(
            run_id=run_id,
            unit_id=unit_id,
        )
    )


def reset_execution_context(
    token: Token[ExecutionContext | None],
) -> None:
    _execution_context_var.reset(token)


class execution_scope:
    __slots__ = ("_context", "_token")

    def __init__(
        self,
        run_id: str,
        unit_id: str | None = None,
    ) -> None:
        if not run_id:
            raise ValueError("run_id is required")

        self._context = ExecutionContext(
            run_id=run_id,
            unit_id=unit_id,
        )
        self._token: Token[ExecutionContext | None] | None = None

    def __enter__(self) -> ExecutionContext:
        self._token = _execution_context_var.set(self._context)
        return self._context

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        if self._token is not None:
            _execution_context_var.reset(self._token)
            self._token = None