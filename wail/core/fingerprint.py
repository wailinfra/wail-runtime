from typing import Dict, Any
from .canonical import sha256_hash
import hashlib

# =====================================================
# PROMPT HASH
# =====================================================


def compute_prompt_hash(prompt: str) -> str:

    if not prompt:
        return None

    normalized = " ".join(prompt.split())

    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# =====================================================
# REQUEST FINGERPRINT
# =====================================================


def build_request_fingerprint(payload: Dict[str, Any]) -> str:

    request_surface = {
        "model": payload.get("model"),
        "provider": payload.get("provider"),
        "transport": payload.get("transport"),
        "temperature": payload.get("temperature"),
        "top_p": payload.get("top_p"),
        "max_tokens": payload.get("max_tokens"),
        "invocation_context": payload.get("invocation_context"),
        "prompt_hash": payload.get("prompt_hash"),
        "params_hash": payload.get("params_hash"),
    }

    return sha256_hash(request_surface)


# =====================================================
# TRACE FINGERPRINT
# =====================================================


def build_trace_fingerprint(runtime_surface: Dict[str, Any]) -> str:

    trace_surface = {
        "duration_ms": runtime_surface.get("duration_ms"),
        "first_token_latency_ms": runtime_surface.get("first_token_latency_ms"),
        "input_token_count": runtime_surface.get("input_token_count"),
        "output_token_count": runtime_surface.get("output_token_count"),
        "stream_chunk_count": runtime_surface.get("stream_chunk_count"),
        "latency_per_output_token_ms": runtime_surface.get(
            "latency_per_output_token_ms"
        ),
        "retry_count": runtime_surface.get("retry_count"),
        "error_flag": runtime_surface.get("error_flag"),
        "timeout_flag": runtime_surface.get("timeout_flag"),
        "event_sequence": runtime_surface.get("event_sequence"),
        "stream_surface": runtime_surface.get("stream_surface"),
    }

    return sha256_hash(trace_surface)


# =====================================================
# STATE HASH
# =====================================================


def build_state_hash(state_surface: Dict[str, Any]) -> str:
    return sha256_hash(state_surface)
