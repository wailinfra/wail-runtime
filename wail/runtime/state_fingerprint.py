import hashlib
import json
from typing import Any, Dict
from wail.runtime.state_store import StateStore

EXCLUDED_KEYS = {
    "last_updated",
    "updated_at",
    "timestamp",
    "node_id",
    "leader",
    "lock",
    "metrics",
    "runtime_counters",
    "ttl_remaining",
}


def _filter_state(obj: Any) -> Any:
    if isinstance(obj, dict):
        filtered: Dict[str, Any] = {}
        for k in sorted(obj.keys()):
            if k in EXCLUDED_KEYS:
                continue
            filtered[k] = _filter_state(obj[k])
        return filtered
    if isinstance(obj, list):
        return [_filter_state(x) for x in obj]
    return obj


def _normalize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _normalize(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [_normalize(x) for x in obj]
    if isinstance(obj, float):
        return format(obj, ".10f")
    return obj


def _canonical_json(data: Any) -> bytes:
    normalized = _normalize(data)
    return json.dumps(
        normalized,
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")


def compute_state_hash() -> str:
    store = StateStore()
    raw_state = store._state
    filtered_state = _filter_state(raw_state)
    canonical = _canonical_json(filtered_state)
    return hashlib.sha256(canonical).hexdigest()


if __name__ == "__main__":
    print(compute_state_hash())
