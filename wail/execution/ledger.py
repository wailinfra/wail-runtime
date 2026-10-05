from __future__ import annotations

from threading import RLock
from typing import Callable

from .contract import ExecutionEvent


class ExecutionLedger:
    __slots__ = (
        "_events",
        "_event_ids",
        "_next_sequence",
        "_run_status",
        "_unit_status",
        "_lock",
    )

    def __init__(self) -> None:
        self._events: dict[str, list[ExecutionEvent]] = {}
        self._event_ids: set[str] = set()
        self._next_sequence: dict[str, int] = {}
        self._run_status: dict[str, str] = {}
        self._unit_status: dict[str, dict[str, str]] = {}
        self._lock = RLock()

    def next_sequence(self, run_id: str) -> int:
        if not run_id:
            raise ValueError("run_id is required")
        with self._lock:
            return self._next_sequence.get(run_id, 1)

    def append(self, event: ExecutionEvent) -> None:
        if not event.run_id:
            raise ValueError("run_id is required")
        if not event.event_id:
            raise ValueError("event_id is required")
        if event.sequence < 1:
            raise ValueError("sequence must be positive")
        with self._lock:
            self._append_locked(event)

    def append_new(
        self,
        run_id: str,
        factory: Callable[[int], ExecutionEvent],
    ) -> ExecutionEvent:
        if not run_id:
            raise ValueError("run_id is required")

        with self._lock:
            sequence = self._next_sequence.get(run_id, 1)
            event = factory(sequence)

            if event.run_id != run_id:
                raise ValueError("event run_id mismatch")
            if event.sequence != sequence:
                raise ValueError("event sequence mismatch")

            self._append_locked(event)
            return event

    def events(self, run_id: str) -> tuple[ExecutionEvent, ...]:
        if not run_id:
            raise ValueError("run_id is required")
        with self._lock:
            return tuple(self._events.get(run_id, ()))

    def event_count(self, run_id: str) -> int:
        if not run_id:
            raise ValueError("run_id is required")
        with self._lock:
            return len(self._events.get(run_id, ()))

    def last_event(self, run_id: str) -> ExecutionEvent | None:
        if not run_id:
            raise ValueError("run_id is required")
        with self._lock:
            events = self._events.get(run_id)
            return events[-1] if events else None

    def has_event(self, event_id: str) -> bool:
        if not event_id:
            raise ValueError("event_id is required")
        with self._lock:
            return event_id in self._event_ids

    def has_run(self, run_id: str) -> bool:
        if not run_id:
            raise ValueError("run_id is required")
        with self._lock:
            return run_id in self._run_status

    def run_status(self, run_id: str) -> str | None:
        if not run_id:
            raise ValueError("run_id is required")
        with self._lock:
            return self._run_status.get(run_id)

    def has_unit(self, run_id: str, unit_id: str) -> bool:
        if not run_id:
            raise ValueError("run_id is required")
        if not unit_id:
            raise ValueError("unit_id is required")
        with self._lock:
            return unit_id in self._unit_status.get(run_id, {})

    def unit_status(self, run_id: str, unit_id: str) -> str | None:
        if not run_id:
            raise ValueError("run_id is required")
        if not unit_id:
            raise ValueError("unit_id is required")
        with self._lock:
            return self._unit_status.get(run_id, {}).get(unit_id)

    def run_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._events.keys())

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._event_ids.clear()
            self._next_sequence.clear()
            self._run_status.clear()
            self._unit_status.clear()

    def _append_locked(self, event: ExecutionEvent) -> None:
        if event.event_id in self._event_ids:
            raise ValueError("duplicate event_id")

        expected = self._next_sequence.get(event.run_id, 1)
        if event.sequence != expected:
            raise ValueError(
                f"invalid sequence: expected {expected}, got {event.sequence}"
            )

        self._validate_transition_locked(event)
        self._events.setdefault(event.run_id, []).append(event)
        self._event_ids.add(event.event_id)
        self._next_sequence[event.run_id] = expected + 1
        self._apply_status_locked(event)

    def _validate_transition_locked(self, event: ExecutionEvent) -> None:
        run_status = self._run_status.get(event.run_id)
        units = self._unit_status.get(event.run_id, {})
        kind = event.kind

        if kind == "run.started":
            if run_status is not None:
                raise ValueError("run already started")
            return

        if run_status is None:
            raise ValueError("unknown run")
        if run_status != "running":
            raise ValueError("run is terminal")

        if kind == "unit.created":
            if not event.unit_id:
                raise ValueError("unit_id is required")
            if event.unit_id in units:
                raise ValueError("duplicate unit")
            return

        if kind == "unit.started":
            self._require_unit_transition(event, units, "created")
            return

        if kind in {"unit.completed", "unit.failed"}:
            self._require_unit_transition(event, units, "running")
            return

        if kind in {"run.completed", "run.failed"}:
            if any(
                status in {"created", "running"}
                for status in units.values()
            ):
                raise ValueError("run has active units")
            return

        if kind == "relation.created":
            source = event.payload.get("source_unit_id")
            target = event.payload.get("target_unit_id")

            if not isinstance(source, str) or source not in units:
                raise ValueError("unknown source unit")
            if not isinstance(target, str) or target not in units:
                raise ValueError("unknown target unit")

    @staticmethod
    def _require_unit_transition(
        event: ExecutionEvent,
        units: dict[str, str],
        expected: str,
    ) -> None:
        if not event.unit_id:
            raise ValueError("unit_id is required")

        status = units.get(event.unit_id)
        if status is None:
            raise ValueError("unknown unit")
        if status != expected:
            raise ValueError(
                f"invalid unit transition: expected {expected}, got {status}"
            )

    def _apply_status_locked(self, event: ExecutionEvent) -> None:
        kind = event.kind

        if kind == "run.started":
            self._run_status[event.run_id] = "running"
            self._unit_status[event.run_id] = {}
        elif kind == "run.completed":
            self._run_status[event.run_id] = "completed"
        elif kind == "run.failed":
            self._run_status[event.run_id] = "failed"
        elif kind == "unit.created":
            self._unit_status[event.run_id][event.unit_id] = "created"
        elif kind == "unit.started":
            self._unit_status[event.run_id][event.unit_id] = "running"
        elif kind == "unit.completed":
            self._unit_status[event.run_id][event.unit_id] = "completed"
        elif kind == "unit.failed":
            self._unit_status[event.run_id][event.unit_id] = "failed"