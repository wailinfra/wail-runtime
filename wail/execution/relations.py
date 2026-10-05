from __future__ import annotations

import time
from typing import Mapping

from .contract import ExecutionRelation, ExecutionValue
from .identity import new_relation_id


def create_relation(
    run_id: str,
    source_unit_id: str,
    target_unit_id: str,
    kind: str,
    sequence: int,
    *,
    attributes: Mapping[str, ExecutionValue] | None = None,
    created_at_ms: int | None = None,
    relation_id: str | None = None,
) -> ExecutionRelation:
    if not run_id:
        raise ValueError("run_id is required")

    if not source_unit_id:
        raise ValueError("source_unit_id is required")

    if not target_unit_id:
        raise ValueError("target_unit_id is required")

    if not kind:
        raise ValueError("kind is required")

    if sequence < 1:
        raise ValueError("sequence must be positive")

    return ExecutionRelation(
        relation_id=relation_id or new_relation_id(),
        run_id=run_id,
        source_unit_id=source_unit_id,
        target_unit_id=target_unit_id,
        kind=kind,
        sequence=sequence,
        created_at_ms=(
            created_at_ms
            if created_at_ms is not None
            else time.time_ns() // 1_000_000
        ),
        attributes=dict(attributes or {}),
    )