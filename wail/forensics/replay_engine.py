import json
import sys
import re
import hashlib
import copy
from pathlib import Path
from typing import Dict, Any

from wail.runtime.determinism_spec import DETERMINISM_SPEC_VERSION
from wail.runtime.canonical_serializer import compute_artifact_hash
from wail.crypto.signature import verify_signature, load_public_key
from wail.runtime.canonical_serializer import serialize_canonical
from wail.runtime.hash_input import build_hash_input
from wail_private.artifact_signing import artifact_public_key_path
from wail.runtime.canonical_serializer import (
    build_canonical_object,
)

# ============================================================
# CONFIG
# ============================================================

BASELINE_DIR = Path("wail_state") / "baselines"

# ============================================================
# ULID VALIDATION
# ============================================================

ULID_REGEX = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def validate_ulid(value: str):
    if not ULID_REGEX.match(value):
        raise ValueError("Invalid ULID format")


# ============================================================
# TRACE RESOLUTION
# ============================================================


def resolve_trace_path(trace_id: str) -> Path:
    validate_ulid(trace_id)

    base_dir = Path("wail_audit")
    path = base_dir / f"trace_{trace_id}.json"

    if not path.exists():
        raise FileNotFoundError(f"Trace not found: {path}")

    return path


# ============================================================
# LOAD ARTIFACT
# ============================================================


def load_artifact(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# SPEC VALIDATION
# ============================================================


def validate_spec(artifact: Dict[str, Any], strict: bool = True):
    spec_version = artifact.get("determinism_spec_version")

    if spec_version is None:
        raise ValueError("Missing determinism_spec_version")

    if spec_version != DETERMINISM_SPEC_VERSION:
        msg = (
            f"Determinism spec mismatch. "
            f"Artifact={spec_version}, Local={DETERMINISM_SPEC_VERSION}"
        )
        if strict:
            raise ValueError(msg)
        else:
            print("[WARN]", msg)


# ============================================================
# SCHEMA HASH VALIDATION
# ============================================================


def validate_schema_binding(artifact: Dict[str, Any]):
    if "canonical_schema_hash" not in artifact:
        raise ValueError("Missing canonical_schema_hash")

    if not artifact["canonical_schema_hash"]:
        raise ValueError("Invalid canonical_schema_hash")


# ============================================================
# HASH RECOMPUTE
# ============================================================


def recompute_hash(artifact: Dict[str, Any]) -> str:

    canonical_artifact = build_canonical_object(artifact)

    hash_input = build_hash_input(canonical_artifact)

    return compute_artifact_hash(hash_input)

# ============================================================
# BASELINE VERIFY
# ============================================================


def verify_baseline_binding(artifact: Dict[str, Any], public_key):

    baseline_info = artifact.get("drift_analysis", {}).get("baseline_snapshot", {})
    baseline_version = baseline_info.get("baseline_version")
    baseline_hash = baseline_info.get("baseline_hash")

    if not baseline_version or not baseline_hash:
        return
    
    baseline_path = BASELINE_DIR / f"{baseline_version}.json"

    if not baseline_path.exists():
        print("BASELINE FILE MISSING")
        sys.exit(20)

    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline_record = json.load(f)

    baseline_copy = copy.deepcopy(baseline_record)

    baseline_copy.pop("signature", None)
    baseline_copy.pop("baseline_hash", None)
    baseline_copy.pop("signature_algorithm", None)
    baseline_copy.pop("public_key_fingerprint", None)

    canonical = serialize_canonical(baseline_copy)
    recomputed_baseline_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    if recomputed_baseline_hash != baseline_hash:
        print("BASELINE HASH MISMATCH")
        sys.exit(21)

    baseline_signature = baseline_record.get("signature")

    if not verify_signature(
        baseline_hash.encode("utf-8"),
        baseline_signature,
        public_key,
    ):
        print("BASELINE SIGNATURE INVALID")
        sys.exit(22)

    print("Baseline Verified: OK")


# ============================================================
# STRICT REPLAY CORE
# ============================================================


def strict_replay(path: Path):
    artifact = load_artifact(path)

    validate_spec(artifact, strict=True)
    validate_schema_binding(artifact)

    original_hash = artifact.get("integrity", {}).get("artifact_hash")
    signature = artifact.get("integrity", {}).get("signature")

    if not original_hash:
        raise ValueError("Missing artifact_hash")

    if not signature:
        raise ValueError("Missing signature")

    recomputed_hash = recompute_hash(artifact)
    hash_match = original_hash == recomputed_hash

    if not hash_match:
        print("HASH MISMATCH")
        sys.exit(10)

    public_key = load_public_key(artifact_public_key_path())

    signature_valid = verify_signature(
        original_hash.encode("utf-8"),
        signature,
        public_key,
    )

    if not signature_valid:
        print("SIGNATURE INVALID")
        sys.exit(11)

    verify_baseline_binding(artifact, public_key)

    print("====================================")
    print("WAIL STRICT REPLAY")
    print("====================================")
    print("Trace File:", path.name)
    print("Artifact Hash:", original_hash)
    print("Signature Valid:", signature_valid)
    print("====================================")
    print("REPLAY SUCCESS — REGULATOR GRADE")


# ============================================================
# CLI ENTRY
# ============================================================


def replay_cli(trace_id: str = None, file_path: str = None):
    if trace_id:
        path = resolve_trace_path(trace_id)
    elif file_path:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
    else:
        raise ValueError("Provide --trace <ULID> or --file <path>")

    strict_replay(path)
