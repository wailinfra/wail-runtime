import json
import hashlib
from typing import Any

from wail.runtime.determinism_spec import normalize_value

JSON_SEPARATORS = (",", ":")
SORT_KEYS = True
ENSURE_ASCII = False
NUMERIC_PRECISION = 12


# ============================================================
# INTERNAL NUMERIC NORMALIZATION
# ============================================================


def _normalize_numbers(obj: Any):

    if isinstance(obj, dict):
        return {k: _normalize_numbers(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [_normalize_numbers(v) for v in obj]

    if isinstance(obj, float):

        return f"{obj:.{NUMERIC_PRECISION}f}"

    return obj


# ============================================================
# CANONICAL BUILD
# ============================================================


def build_canonical_object(obj: Any) -> Any:

    normalized = normalize_value(obj)
    normalized = _normalize_numbers(normalized)

    return normalized


def serialize_canonical(obj: Any) -> str:

    normalized = build_canonical_object(obj)

    return json.dumps(
        normalized,
        sort_keys=SORT_KEYS,
        separators=JSON_SEPARATORS,
        ensure_ascii=ENSURE_ASCII,
    )


# ============================================================
# HASH GENERATION
# ============================================================


def compute_artifact_hash(obj: Any) -> str:
    
    canonical_json = serialize_canonical(obj)

    sha = hashlib.sha256()
    sha.update(canonical_json.encode("utf-8"))

    return sha.hexdigest()


# ============================================================
# SCHEMA BINDING
# ============================================================


def compute_schema_hash(schema_obj: Any) -> str:
 
    canonical_schema = serialize_canonical(schema_obj)

    sha = hashlib.sha256()
    sha.update(canonical_schema.encode("utf-8"))

    return sha.hexdigest()
