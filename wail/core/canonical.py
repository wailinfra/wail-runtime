import json
import hashlib
from typing import Any


def _normalize(obj: Any):
    
    if not isinstance(obj, (dict, list, tuple, str, int, float, bool, type(None))):
        return str(obj)

    if isinstance(obj, dict):
        return {k: _normalize(obj[k]) for k in sorted(obj.keys())}

    if isinstance(obj, list):
        return [_normalize(i) for i in obj]

    if isinstance(obj, tuple):
        return [_normalize(i) for i in obj]

    if isinstance(obj, float):
        return round(obj, 10)

    return obj


def canonical_json(data: Any) -> str:

    normalized = _normalize(data)

    return json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def sha256_hash(data: Any) -> str:

    canonical = canonical_json(data)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
