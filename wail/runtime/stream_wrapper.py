import time

from wail.runtime.context import (
    mark_first_token,
    update_stream_surface,
    append_event,
)


def wrap_stream(response_iterator):

    stream_start_ts = time.perf_counter()
    last_token_ts = None

    first_token_captured = False

    chunk_index = 0
    token_index = 0
    cumulative_tokens = 0

    gaps = []

    append_event({"type": "stream_start", "payload": {"t_offset_ms": 0}})

    for chunk in response_iterator:

        now = time.perf_counter()
        t_offset_ms = (now - stream_start_ts) * 1000

        chunk_index += 1
        token_index += 1
        cumulative_tokens += 1

        gap_ms = None
        if last_token_ts is not None:
            gap_ms = (now - last_token_ts) * 1000
            gaps.append(gap_ms)

        last_token_ts = now

        if not first_token_captured:
            mark_first_token()
            first_token_captured = True

            append_event(
                {
                    "type": "first_token",
                    "payload": {
                        "t_offset_ms": round(t_offset_ms, 2),
                        "chunk_index": chunk_index,
                        "token_index": token_index,
                        "cumulative_tokens": cumulative_tokens,
                    },
                }
            )

        yield chunk

    total_duration_ms = (time.perf_counter() - stream_start_ts) * 1000

    mean_gap = 0
    std_gap = 0
    max_gap = 0
    min_gap = 0

    if gaps:
        mean_gap = sum(gaps) / len(gaps)
        variance = sum((x - mean_gap) ** 2 for x in gaps) / len(gaps)
        std_gap = variance**0.5
        max_gap = max(gaps)
        min_gap = min(gaps)

    avg_tokens_per_sec = (
        cumulative_tokens / (total_duration_ms / 1000) if total_duration_ms > 0 else 0
    )

    append_event(
        {
            "type": "stream_end",
            "payload": {
                "t_offset_ms": round(total_duration_ms, 2),
                "total_chunks": chunk_index,
                "total_tokens": cumulative_tokens,
                "stream_duration_ms": round(total_duration_ms, 2),
                "avg_tokens_per_sec": round(avg_tokens_per_sec, 2),
            },
        }
    )

    update_stream_surface(
        {
            "stream_duration_ms": round(total_duration_ms, 2),
            "stream_chunk_count": chunk_index,
            "token_dynamics": {
                "avg_tokens_per_sec": round(avg_tokens_per_sec, 2),
                "mean_inter_token_gap_ms": round(mean_gap, 2),
                "std_inter_token_gap_ms": round(std_gap, 2),
                "max_inter_token_gap_ms": round(max_gap, 2),
                "min_inter_token_gap_ms": round(min_gap, 2),
                "stall_detected": True if max_gap > 200 else False,
            },
        }
    )
