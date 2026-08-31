from .anthropic_executor import sync as anthropic_sync
from .anthropic_executor import stream as anthropic_stream

from .openai_responses_executor import sync as openai_responses_sync
from .openai_responses_executor import stream as openai_responses_stream

from .google_executor import sync as google_sync
from .google_executor import stream as google_stream


EXECUTOR_MAP = {
        "openai": {
        "sync": openai_responses_sync,
        "stream": openai_responses_stream,
    },
        "vllm": {
        "sync": openai_responses_sync,
        "stream": openai_responses_stream,
    },
    "anthropic": {
        "sync": anthropic_sync,
        "stream": anthropic_stream,
    },
    "google": {
        "sync": google_sync,
        "stream": google_stream,
    },
}