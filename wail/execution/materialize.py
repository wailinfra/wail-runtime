from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contract import ExecutionEvent


@dataclass(slots=True)
class MaterializedUnit:
    unit_id: str
    kind: str | None = None
    name: str | None = None
    status: str = "created"
    attempt: int = 1
    started_at_ms: int | None = None
    ended_at_ms: int | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MaterializedRelation:
    relation_id: str
    source_unit_id: str
    target_unit_id: str
    kind: str
    sequence: int
    created_at_ms: int
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MaterializedRun:
    run_id: str
    status: str = "created"
    started_at_ms: int | None = None
    ended_at_ms: int | None = None
    root_unit_id: str | None = None
    sequence: int = 0
    units: dict[str, MaterializedUnit] = field(default_factory=dict)
    relations: list[MaterializedRelation] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


def materialize(
    run_id: str,
    events: tuple[ExecutionEvent, ...],
) -> MaterializedRun:
    if not run_id:
        raise ValueError("run_id is required")

    state = MaterializedRun(run_id=run_id)

    expected_sequence = 1

    for event in events:
        if event.run_id != run_id:
            raise ValueError("event run_id mismatch")

        if event.sequence != expected_sequence:
            raise ValueError(
                f"invalid sequence: expected {expected_sequence}, got {event.sequence}"
            )

        _apply(state, event)

        state.sequence = event.sequence
        expected_sequence += 1

    return state


def _apply(state: MaterializedRun, event: ExecutionEvent) -> None:
    payload = event.payload
    kind = event.kind

    if kind == "run.started":
        state.status = "running"
        state.started_at_ms = event.timestamp_ms
        state.root_unit_id = _optional_str(payload.get("root_unit_id"))
        state.attributes.update(_dict_value(payload.get("attributes")))
        return

    if kind == "run.completed":
        state.status = "completed"
        state.ended_at_ms = event.timestamp_ms
        state.attributes.update(_dict_value(payload.get("attributes")))
        return

    if kind == "run.failed":
        state.status = "failed"
        state.ended_at_ms = event.timestamp_ms
        state.attributes.update(_dict_value(payload.get("attributes")))
        return

    if kind == "unit.created":
        unit_id = _unit_id(event)

        if unit_id in state.units:
            raise ValueError("duplicate unit")

        state.units[unit_id] = MaterializedUnit(
            unit_id=unit_id,
            kind=_optional_str(payload.get("kind")),
            name=_optional_str(payload.get("name")),
            attempt=_positive_int(payload.get("attempt"), 1),
            attributes=_dict_value(payload.get("attributes")),
        )
        return

    if kind == "unit.started":
        unit = _unit(state, event)
        unit.status = "running"
        unit.started_at_ms = event.timestamp_ms
        unit.attributes.update(_dict_value(payload.get("attributes")))
        return

    if kind == "unit.completed":
        unit = _unit(state, event)
        unit.status = "completed"
        unit.ended_at_ms = event.timestamp_ms
        unit.attributes.update(_dict_value(payload.get("attributes")))
        return

    if kind == "unit.failed":
        unit = _unit(state, event)
        unit.status = "failed"
        unit.ended_at_ms = event.timestamp_ms
        unit.attributes.update(_dict_value(payload.get("attributes")))
        return

    if kind == "relation.created":
        relation_id = _required_str(payload.get("relation_id"))
        source_unit_id = _required_str(payload.get("source_unit_id"))
        target_unit_id = _required_str(payload.get("target_unit_id"))
        relation_kind = _required_str(payload.get("kind"))

        if source_unit_id not in state.units:
            raise ValueError("unknown source unit")

        if target_unit_id not in state.units:
            raise ValueError("unknown target unit")

        if any(
            relation.relation_id == relation_id
            for relation in state.relations
        ):
            raise ValueError("duplicate relation")

        state.relations.append(
            MaterializedRelation(
                relation_id=relation_id,
                source_unit_id=source_unit_id,
                target_unit_id=target_unit_id,
                kind=relation_kind,
                sequence=event.sequence,
                created_at_ms=event.timestamp_ms,
                attributes=_dict_value(payload.get("attributes")),
            )
        )


def _unit_id(event: ExecutionEvent) -> str:
    if not event.unit_id:
        raise ValueError("unit_id is required")

    return event.unit_id


def _unit(
    state: MaterializedRun,
    event: ExecutionEvent,
) -> MaterializedUnit:
    unit_id = _unit_id(event)

    try:
        return state.units[unit_id]
    except KeyError as exc:
        raise ValueError("unknown unit") from exc


def _required_str(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("non-empty string required")

    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None

    return _required_str(value)


def _positive_int(value: Any, default: int) -> int:
    if value is None:
        return default

    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError("positive integer required")

    return value


def _dict_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {}

    if not isinstance(value, dict):
        raise ValueError("object required")

    return dict(value)