import json
import hashlib


def serialize_canonical(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def calculate_canonical_hash(data: dict) -> str:
    canonical = serialize_canonical(data)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def calculate_artifact_hash(data: dict) -> str:
    canonical = serialize_canonical(data)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
