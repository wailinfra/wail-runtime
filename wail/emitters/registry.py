import os
from pathlib import Path

from wail.emitters.serializer import TraceSerializer
from wail.emitters.async_writer import AsyncFileWriter


def _resolve_trace_dir() -> Path:
    custom = os.getenv("WAIL_TRACE_DIR")
    if custom:
        return Path(custom)

    home = Path.home()
    return home / ".wail" / "traces"


TRACE_DIR = _resolve_trace_dir()
TRACE_DIR.mkdir(parents=True, exist_ok=True)

TRACE_FILE = TRACE_DIR / "traces.jsonl"

_emitter_instance = None


def _build_emitter():

    serializer = TraceSerializer()

    writer = AsyncFileWriter(
        path=str(TRACE_FILE),
        max_queue_size=10000,
        flush_interval=0.1,
        max_batch_size=100,
    )

    def write_async(trace):
        line = serializer.serialize(trace)
        writer.append_line(line)

    write_async.shutdown = writer.shutdown

    return write_async


def get_default_emitter():
    global _emitter_instance

    if _emitter_instance is None:
        _emitter_instance = _build_emitter()

    return _emitter_instance


def get_default_emitters():
    return [get_default_emitter()]