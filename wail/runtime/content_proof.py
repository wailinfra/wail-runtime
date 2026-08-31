import hashlib
import json


def _sha256(text: str) -> str:
    if text is None:
        return "N/A"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonicalize(data) -> str:
    
    try:
        return json.dumps(data, sort_keys=True, separators=(",", ":"))
    except Exception:
        return str(data)


def generate_content_proof(
    response_obj,
    stream_chunks: list | None = None,
) -> dict:

    canonical_output = _canonicalize(response_obj)

    output_hash = _sha256(canonical_output)

    chunk_hashes = None

    if stream_chunks:
        chunk_hashes = []
        for chunk in stream_chunks:
            chunk_hashes.append(_sha256(_canonicalize(chunk)))

    normalized = canonical_output.strip().lower()
    fingerprint = _sha256(normalized)

    return {
        "output_hash": output_hash,
        "chunk_hashes": chunk_hashes,
        "fingerprint": fingerprint,
        "proof_version": "v1",
    }
