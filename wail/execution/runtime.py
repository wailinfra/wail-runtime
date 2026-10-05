from __future__ import annotations

import time
from typing import Mapping

from .context import execution_scope
from .contract import (
    ExecutionRelation,
    ExecutionRun,
    ExecutionUnit,
    ExecutionValue,
)
from .events import append_event
from .graph import ExecutionGraph
from .identity import (
    new_relation_id,
    new_run_id,
    new_unit_id,
)
from .ledger import ExecutionLedger
from .materialize import MaterializedRun, materialize
from .relations import create_relation


def _update_run_baseline(
    state: MaterializedRun,
) -> dict | None:
    try:
        from wail_private.execution.run_intelligence import (
            ingest_terminal_run,
        )

        return ingest_terminal_run(state)
    except Exception:
        return None


def _render_agent_run(
    state: MaterializedRun,
    intelligence: dict | None,
) -> None:
    if not any(
        unit.kind == "agent"
        for unit in state.units.values()
    ):
        return

    from wail.runtime.runtime_cli import (
        render_agent_run_summary,
    )

    render_agent_run_summary(
        state,
        evidence_saved=bool(
            intelligence
            and intelligence.get(
                "signed_agent_evidence_path"
            )
        ),
    )


class ExecutionRuntime:
    __slots__ = ("ledger",)

    def __init__(
        self,
        ledger: ExecutionLedger | None = None,
    ) -> None:
        self.ledger = ledger or ExecutionLedger()

    def start_run(
        self,
        *,
        run_id: str | None = None,
        root_unit_id: str | None = None,
        attributes: Mapping[str, ExecutionValue] | None = None,
        timestamp_ms: int | None = None,
    ) -> ExecutionRun:
        resolved_run_id = run_id or new_run_id()
        started_at_ms = self._timestamp(timestamp_ms)

        append_event(
            self.ledger,
            resolved_run_id,
            "run.started",
            payload={
                "root_unit_id": root_unit_id,
                "attributes": dict(attributes or {}),
            },
            timestamp_ms=started_at_ms,
        )

        return ExecutionRun(
            run_id=resolved_run_id,
            started_at_ms=started_at_ms,
            status="running",
            root_unit_id=root_unit_id,
            attributes=dict(attributes or {}),
        )

    def complete_run(
        self,
        run_id: str,
        *,
        attributes: Mapping[str, ExecutionValue] | None = None,
        timestamp_ms: int | None = None,
    ) -> None:
        self._require_run(run_id)

        append_event(
            self.ledger,
            run_id,
            "run.completed",
            payload={
                "attributes": dict(attributes or {}),
            },
            timestamp_ms=self._timestamp(timestamp_ms),
        )

        state = materialize(
            run_id,
            self.ledger.events(run_id),
        )

        intelligence = _update_run_baseline(state)

        _render_agent_run(
            state,
            intelligence,
        )

    def fail_run(
        self,
        run_id: str,
        *,
        attributes: Mapping[str, ExecutionValue] | None = None,
        timestamp_ms: int | None = None,
    ) -> None:
        self._require_run(run_id)

        append_event(
            self.ledger,
            run_id,
            "run.failed",
            payload={
                "attributes": dict(attributes or {}),
            },
            timestamp_ms=self._timestamp(timestamp_ms),
        )

        state = materialize(
            run_id,
            self.ledger.events(run_id),
        )

        intelligence = _update_run_baseline(state)

        _render_agent_run(
            state,
            intelligence,
        )

    def create_unit(
        self,
        run_id: str,
        kind: str,
        *,
        unit_id: str | None = None,
        name: str | None = None,
        attempt: int = 1,
        attributes: Mapping[str, ExecutionValue] | None = None,
        timestamp_ms: int | None = None,
    ) -> ExecutionUnit:
        self._require_run(run_id)

        if not kind:
            raise ValueError("kind is required")

        if attempt < 1:
            raise ValueError("attempt must be positive")

        resolved_unit_id = unit_id or new_unit_id()
        created_at_ms = self._timestamp(timestamp_ms)

        append_event(
            self.ledger,
            run_id,
            "unit.created",
            unit_id=resolved_unit_id,
            payload={
                "kind": kind,
                "name": name,
                "attempt": attempt,
                "attributes": dict(attributes or {}),
            },
            timestamp_ms=created_at_ms,
        )

        return ExecutionUnit(
            unit_id=resolved_unit_id,
            run_id=run_id,
            kind=kind,
            name=name,
            started_at_ms=created_at_ms,
            status="created",
            attempt=attempt,
            attributes=dict(attributes or {}),
        )

    def start_unit(
        self,
        run_id: str,
        unit_id: str,
        *,
        attributes: Mapping[str, ExecutionValue] | None = None,
        timestamp_ms: int | None = None,
    ) -> None:
        self._require_unit(run_id, unit_id)

        append_event(
            self.ledger,
            run_id,
            "unit.started",
            unit_id=unit_id,
            payload={
                "attributes": dict(attributes or {}),
            },
            timestamp_ms=self._timestamp(timestamp_ms),
        )

    def complete_unit(
        self,
        run_id: str,
        unit_id: str,
        *,
        attributes: Mapping[str, ExecutionValue] | None = None,
        timestamp_ms: int | None = None,
    ) -> None:
        self._require_unit(run_id, unit_id)

        append_event(
            self.ledger,
            run_id,
            "unit.completed",
            unit_id=unit_id,
            payload={
                "attributes": dict(attributes or {}),
            },
            timestamp_ms=self._timestamp(timestamp_ms),
        )

    def fail_unit(
        self,
        run_id: str,
        unit_id: str,
        *,
        attributes: Mapping[str, ExecutionValue] | None = None,
        timestamp_ms: int | None = None,
    ) -> None:
        self._require_unit(run_id, unit_id)

        append_event(
            self.ledger,
            run_id,
            "unit.failed",
            unit_id=unit_id,
            payload={
                "attributes": dict(attributes or {}),
            },
            timestamp_ms=self._timestamp(timestamp_ms),
        )

    def relate(
        self,
        run_id: str,
        source_unit_id: str,
        target_unit_id: str,
        kind: str,
        *,
        relation_id: str | None = None,
        attributes: Mapping[str, ExecutionValue] | None = None,
        timestamp_ms: int | None = None,
    ) -> ExecutionRelation:
        self._require_unit(run_id, source_unit_id)
        self._require_unit(run_id, target_unit_id)

        if not kind:
            raise ValueError("kind is required")

        resolved_relation_id = relation_id or new_relation_id()
        created_at_ms = self._timestamp(timestamp_ms)
        resolved_attributes = dict(attributes or {})

        event = append_event(
            self.ledger,
            run_id,
            "relation.created",
            payload={
                "relation_id": resolved_relation_id,
                "source_unit_id": source_unit_id,
                "target_unit_id": target_unit_id,
                "kind": kind,
                "attributes": resolved_attributes,
            },
            timestamp_ms=created_at_ms,
        )

        return create_relation(
            run_id=run_id,
            source_unit_id=source_unit_id,
            target_unit_id=target_unit_id,
            kind=kind,
            sequence=event.sequence,
            relation_id=resolved_relation_id,
            attributes=resolved_attributes,
            created_at_ms=created_at_ms,
        )

    def state(
        self,
        run_id: str,
    ) -> MaterializedRun:
        self._require_run(run_id)

        return materialize(
            run_id,
            self.ledger.events(run_id),
        )

    def graph(
        self,
        run_id: str,
    ) -> ExecutionGraph:
        state = self.state(run_id)

        relations = tuple(
            ExecutionRelation(
                relation_id=relation.relation_id,
                run_id=run_id,
                source_unit_id=relation.source_unit_id,
                target_unit_id=relation.target_unit_id,
                kind=relation.kind,
                sequence=relation.sequence,
                created_at_ms=relation.created_at_ms,
                attributes=relation.attributes,
            )
            for relation in state.relations
        )

        return ExecutionGraph(
            run_id=run_id,
            unit_ids=tuple(state.units.keys()),
            relations=relations,
        )

    def scope(
        self,
        run_id: str,
        unit_id: str | None = None,
    ) -> execution_scope:
        self._require_run(run_id)

        if unit_id is not None:
            self._require_unit(run_id, unit_id)

        return execution_scope(
            run_id=run_id,
            unit_id=unit_id,
        )

    def _require_run(
        self,
        run_id: str,
    ) -> None:
        if not run_id:
            raise ValueError("run_id is required")

        if not self.ledger.has_run(run_id):
            raise ValueError("unknown run")

    def _require_unit(
        self,
        run_id: str,
        unit_id: str,
    ) -> None:
        if not unit_id:
            raise ValueError("unit_id is required")

        self._require_run(run_id)

        if not self.ledger.has_unit(run_id, unit_id):
            raise ValueError("unknown unit")

    @staticmethod
    def _timestamp(
        value: int | None,
    ) -> int:
        if value is not None:
            return value

        return time.time_ns() // 1_000_000