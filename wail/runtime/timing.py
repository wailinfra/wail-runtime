import os
from wail.runtime.context import emit_event


def _timing_enabled():
    return os.getenv("WAIL_TIMING", "1") != "0"


def mark_stream_start():
    if _timing_enabled():
        emit_event("stream_started")


def mark_first_token():
    if _timing_enabled():
        emit_event("first_token_emitted")


def mark_stream_end():
    if _timing_enabled():
        emit_event("stream_finished")
