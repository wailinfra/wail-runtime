from __future__ import annotations

from dataclasses import dataclass

from .contract import ExecutionRelation
from .materialize import MaterializedRun


@dataclass(frozen=True, slots=True)
class GraphEdge:
    relation_id: str
    source_unit_id: str
    target_unit_id: str
    kind: str
    sequence: int


class ExecutionGraph:
    __slots__ = (
        "run_id",
        "_units",
        "_edges",
        "_outgoing",
        "_incoming",
    )

    def __init__(
        self,
        run_id: str,
        unit_ids: tuple[str, ...],
        relations: tuple[ExecutionRelation, ...],
    ) -> None:
        if not run_id:
            raise ValueError("run_id is required")

        self.run_id = run_id
        self._units = frozenset(unit_ids)

        outgoing: dict[str, list[GraphEdge]] = {
            unit_id: [] for unit_id in unit_ids
        }
        incoming: dict[str, list[GraphEdge]] = {
            unit_id: [] for unit_id in unit_ids
        }

        edges: list[GraphEdge] = []
        relation_ids: set[str] = set()

        for relation in relations:
            if relation.run_id != run_id:
                raise ValueError("relation run_id mismatch")

            if relation.relation_id in relation_ids:
                raise ValueError("duplicate relation_id")

            if relation.source_unit_id not in self._units:
                raise ValueError("unknown source unit")

            if relation.target_unit_id not in self._units:
                raise ValueError("unknown target unit")

            edge = GraphEdge(
                relation_id=relation.relation_id,
                source_unit_id=relation.source_unit_id,
                target_unit_id=relation.target_unit_id,
                kind=relation.kind,
                sequence=relation.sequence,
            )

            edges.append(edge)
            outgoing[edge.source_unit_id].append(edge)
            incoming[edge.target_unit_id].append(edge)
            relation_ids.add(relation.relation_id)

        self._edges = tuple(sorted(edges, key=lambda item: item.sequence))

        self._outgoing = {
            key: tuple(sorted(value, key=lambda item: item.sequence))
            for key, value in outgoing.items()
        }

        self._incoming = {
            key: tuple(sorted(value, key=lambda item: item.sequence))
            for key, value in incoming.items()
        }

    @property
    def unit_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._units))

    @property
    def edges(self) -> tuple[GraphEdge, ...]:
        return self._edges

    def contains(self, unit_id: str) -> bool:
        return unit_id in self._units

    def outgoing(
        self,
        unit_id: str,
        *,
        kind: str | None = None,
    ) -> tuple[GraphEdge, ...]:
        self._require_unit(unit_id)

        edges = self._outgoing[unit_id]

        if kind is None:
            return edges

        return tuple(edge for edge in edges if edge.kind == kind)

    def incoming(
        self,
        unit_id: str,
        *,
        kind: str | None = None,
    ) -> tuple[GraphEdge, ...]:
        self._require_unit(unit_id)

        edges = self._incoming[unit_id]

        if kind is None:
            return edges

        return tuple(edge for edge in edges if edge.kind == kind)

    def successors(
        self,
        unit_id: str,
        *,
        kind: str | None = None,
    ) -> tuple[str, ...]:
        return tuple(
            edge.target_unit_id
            for edge in self.outgoing(unit_id, kind=kind)
        )

    def predecessors(
        self,
        unit_id: str,
        *,
        kind: str | None = None,
    ) -> tuple[str, ...]:
        return tuple(
            edge.source_unit_id
            for edge in self.incoming(unit_id, kind=kind)
        )

    def roots(self) -> tuple[str, ...]:
        return tuple(
            unit_id
            for unit_id in self.unit_ids
            if not self._incoming[unit_id]
        )

    def leaves(self) -> tuple[str, ...]:
        return tuple(
            unit_id
            for unit_id in self.unit_ids
            if not self._outgoing[unit_id]
        )

    def _require_unit(self, unit_id: str) -> None:
        if unit_id not in self._units:
            raise ValueError("unknown unit")


def graph_from_materialized(
    state: MaterializedRun,
) -> ExecutionGraph:
    relations = tuple(
        ExecutionRelation(
            relation_id=relation.relation_id,
            run_id=state.run_id,
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
        run_id=state.run_id,
        unit_ids=tuple(state.units.keys()),
        relations=relations,
    )