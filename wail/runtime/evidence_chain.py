import hashlib
from wail.core.canonical import canonical_json

CHAIN_VERSION = 1


def compute_chain_hash(payload: dict, previous_hash: str | None) -> str:

    data = {
        "payload": payload,
        "previous_hash": previous_hash,
        "chain_version": CHAIN_VERSION,
    }

    canonical = canonical_json(data)

    return hashlib.sha256(canonical.encode()).hexdigest()


def build_chain_entry(stage: str, payload: dict, previous_hash: str | None) -> dict:

    chain_hash = compute_chain_hash(payload, previous_hash)

    return {
        "stage": stage,
        "previous_hash": previous_hash,
        "chain_hash": chain_hash,
        "chain_version": CHAIN_VERSION,
    }


def verify_chain(entries: list) -> bool:

    previous = None

    for entry in entries:

        expected = compute_chain_hash(entry["payload"], previous)

        if expected != entry["chain_hash"]:
            return False

        previous = entry["chain_hash"]

    return True
