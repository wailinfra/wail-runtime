from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, TypeAlias


EXECUTION_CONTRACT_VERSION = 1

ExecutionScalar: TypeAlias = str | int | bool | None
ExecutionValue: TypeAlias = (
    ExecutionScalar
    | list["ExecutionValue"]
    | dict[str, "ExecutionValue"]
)


@dataclass(frozen=True, slots=True)
class ExecutionReference:
    ref_type: str
    ref_id: str
    namespace: str = "wail"
    fingerprint: str | None = None
    attributes: Mapping[str, ExecutionValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionRun:
    run_id: str
    started_at_ms: int
    status: str = "created"
    root_unit_id: str | None = None
    ended_at_ms: int | None = None
    contract_version: int = EXECUTION_CONTRACT_VERSION
    references: tuple[ExecutionReference, ...] = ()
    attributes: Mapping[str, ExecutionValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionUnit:
    unit_id: str
    run_id: str
    kind: str
    started_at_ms: int
    name: str | None = None
    status: str = "created"
    ended_at_ms: int | None = None
    attempt: int = 1
    input_ref: ExecutionReference | None = None
    output_ref: ExecutionReference | None = None
    authority_ref: ExecutionReference | None = None
    resource_refs: tuple[ExecutionReference, ...] = ()
    references: tuple[ExecutionReference, ...] = ()
    attributes: Mapping[str, ExecutionValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionRelation:
    relation_id: str
    run_id: str
    source_unit_id: str
    target_unit_id: str
    kind: str
    sequence: int
    created_at_ms: int
    attributes: Mapping[str, ExecutionValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    event_id: str
    run_id: str
    kind: str
    sequence: int
    timestamp_ms: int
    unit_id: str | None = None
    payload: Mapping[str, ExecutionValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionState:
    state_id: str
    run_id: str
    sequence: int
    phase: str
    status: str
    observed_at_ms: int
    unit_id: str | None = None
    state_hash: str | None = None
    attributes: Mapping[str, ExecutionValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionAuthority:
    authority_id: str
    subject_ref: ExecutionReference
    scope: str
    permissions: tuple[str, ...] = ()
    constraints: Mapping[str, ExecutionValue] = field(default_factory=dict)
    delegated_from: ExecutionReference | None = None
    issued_at_ms: int | None = None
    expires_at_ms: int | None = None
    attributes: Mapping[str, ExecutionValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionResource:
    resource_id: str
    run_id: str
    kind: str
    quantity: int | str
    unit: str
    timestamp_ms: int
    unit_id: str | None = None
    provider_ref: ExecutionReference | None = None
    attributes: Mapping[str, ExecutionValue] = field(default_factory=dict)