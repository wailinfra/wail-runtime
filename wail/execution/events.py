from __future__ import annotations

import time
from typing import Mapping

from .contract import ExecutionEvent, ExecutionValue
from .identity import new_event_id
from .ledger import ExecutionLedger


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def create_event(
    ledger: ExecutionLedger,
    run_id: str,
    kind: str,
    *,
    unit_id: str | None = None,
    payload: Mapping[str, ExecutionValue] | None = None,
    timestamp_ms: int | None = None,
    event_id: str | None = None,
) -> ExecutionEvent:
    if not run_id:
        raise ValueError("run_id is required")

    if not kind:
        raise ValueError("kind is required")

    return ExecutionEvent(
        event_id=event_id or new_event_id(),
        run_id=run_id,
        unit_id=unit_id,
        kind=kind,
        sequence=ledger.next_sequence(run_id),
        timestamp_ms=timestamp_ms if timestamp_ms is not None else now_ms(),
        payload=dict(payload or {}),
    )


def append_event(
    ledger: ExecutionLedger,
    run_id: str,
    kind: str,
    *,
    unit_id: str | None = None,
    payload: Mapping[str, ExecutionValue] | None = None,
    timestamp_ms: int | None = None,
    event_id: str | None = None,
) -> ExecutionEvent:
    if not run_id:
        raise ValueError("run_id is required")

    if not kind:
        raise ValueError("kind is required")

    resolved_timestamp = (
        timestamp_ms
        if timestamp_ms is not None
        else now_ms()
    )

    resolved_event_id = event_id or new_event_id()
    resolved_payload = dict(payload or {})

    return ledger.append_new(
        run_id,
        lambda sequence: ExecutionEvent(
            event_id=resolved_event_id,
            run_id=run_id,
            unit_id=unit_id,
            kind=kind,
            sequence=sequence,
            timestamp_ms=resolved_timestamp,
            payload=resolved_payload,
        ),
    )