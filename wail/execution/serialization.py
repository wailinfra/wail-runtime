from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

from .contract import EXECUTION_CONTRACT_VERSION


def to_wire(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return to_wire(asdict(value))

    if isinstance(value, Mapping):
        return {
            str(key): to_wire(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }

    if isinstance(value, (list, tuple)):
        return [to_wire(item) for item in value]

    if value is None or isinstance(value, (str, int, bool)):
        return value

    raise TypeError(f"unsupported wire value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        to_wire(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def encode_envelope(
    kind: str,
    payload: Any,
    *,
    contract_version: int = EXECUTION_CONTRACT_VERSION,
) -> dict[str, Any]:
    if not kind:
        raise ValueError("kind is required")

    return {
        "contract_version": contract_version,
        "kind": kind,
        "payload": to_wire(payload),
    }


def serialize_envelope(
    kind: str,
    payload: Any,
    *,
    contract_version: int = EXECUTION_CONTRACT_VERSION,
) -> bytes:
    return canonical_bytes(
        encode_envelope(
            kind,
            payload,
            contract_version=contract_version,
        )
    )


def deserialize_envelope(data: bytes | str) -> dict[str, Any]:
    if isinstance(data, bytes):
        data = data.decode("utf-8")

    value = json.loads(data)

    if not isinstance(value, dict):
        raise ValueError("invalid envelope")

    contract_version = value.get("contract_version")
    kind = value.get("kind")

    if not isinstance(contract_version, int):
        raise ValueError("invalid contract version")

    if not isinstance(kind, str) or not kind:
        raise ValueError("invalid kind")

    if "payload" not in value:
        raise ValueError("missing payload")

    return value