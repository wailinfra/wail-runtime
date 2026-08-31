import json
from pathlib import Path

from wail.crypto.signature import verify_signature, load_public_key
from wail.runtime.canonical_serializer import compute_artifact_hash
from wail.runtime.hash_input import build_hash_input
from wail_private.artifact_signing import artifact_public_key_path


def verify_artifact(file_path: str):

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            artifact = json.load(f)

        integrity = artifact.get("integrity", {})

        signature = integrity.get("signature")
        recorded_hash = integrity.get("artifact_hash")

        if not signature:
            return False, "signature missing"

        if not recorded_hash:
            return False, "artifact_hash missing"
        tmp = json.loads(json.dumps(artifact))
        tmp.pop("integrity", None)
        hash_input = build_hash_input(tmp)
        expected_hash = compute_artifact_hash(hash_input)

        if expected_hash != recorded_hash:
            print("EXPECTED :", expected_hash)
            print("RECORDED :", recorded_hash)
            return False, "artifact hash mismatch"

        public_key = load_public_key(artifact_public_key_path())

        valid = verify_signature(
            recorded_hash.encode("utf-8"),
            signature,
            public_key,
        )

        if not valid:
            return False, "signature verification failed"

        return True, "artifact verified"

    except Exception as e:
        return False, str(e)
