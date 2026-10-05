from __future__ import annotations

import hashlib
import uuid
from typing import Final


_ID_NAMESPACE: Final[uuid.UUID] = uuid.UUID(
    "8f5d4b7e-53f1-4c7a-a4e6-1f8d6e9c2b31"
)


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex}"


def new_unit_id() -> str:
    return f"unit_{uuid.uuid4().hex}"


def new_event_id() -> str:
    return f"event_{uuid.uuid4().hex}"


def new_relation_id() -> str:
    return f"relation_{uuid.uuid4().hex}"


def new_state_id() -> str:
    return f"state_{uuid.uuid4().hex}"


def new_resource_id() -> str:
    return f"resource_{uuid.uuid4().hex}"


def new_authority_id() -> str:
    return f"authority_{uuid.uuid4().hex}"


def deterministic_id(
    prefix: str,
    *parts: str,
    namespace: uuid.UUID = _ID_NAMESPACE,
) -> str:
    if not prefix:
        raise ValueError("prefix is required")

    if not parts:
        raise ValueError("at least one identity part is required")

    value = "\x1f".join(parts)
    generated = uuid.uuid5(namespace, value)

    return f"{prefix}_{generated.hex}"


def fingerprint_id(
    prefix: str,
    *parts: str,
) -> str:
    if not prefix:
        raise ValueError("prefix is required")

    if not parts:
        raise ValueError("at least one fingerprint part is required")

    digest = hashlib.sha256()

    for part in parts:
        encoded = part.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)

    return f"{prefix}_{digest.hexdigest()}"