from typing import Dict, Any


class DistributedAggregator:
    __slots__ = ("_nodes",)

    def __init__(self):
        self._nodes: Dict[str, Dict[str, Any]] = {}

    def publish(self, node_id: str, snapshot: Dict[str, Any]) -> None:
        self._nodes[node_id] = snapshot

    def aggregate(self) -> Dict[str, Any]:
        total_segments = 0
        total_escalations = 0
        policy_versions = set()

        per_node = {}

        for node_id, data in self._nodes.items():
            policy_versions.add(data.get("policy_version"))

            segments = data.get("segment_count", 0)
            escalations = data.get("total_active_escalations", 0)

            total_segments += segments
            total_escalations += escalations

            per_node[node_id] = {
                "segments": segments,
                "escalations": escalations,
            }

        cluster_alert = total_escalations >= 5
        policy_mismatch = len(policy_versions) > 1

        return {
            "node_count": len(self._nodes),
            "total_segments": total_segments,
            "total_active_escalations": total_escalations,
            "cluster_alert": cluster_alert,
            "policy_mismatch": policy_mismatch,
            "policy_versions": sorted(policy_versions),
            "per_node": per_node,
        }


distributed_aggregator = DistributedAggregator()
