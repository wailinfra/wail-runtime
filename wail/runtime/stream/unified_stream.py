import time
import threading
from wail.runtime.context import (
    emit_event,
    mark_first_token,
    update_stream_surface,
    update_token_usage,
    clear_ttft_watcher,
)
from wail.runtime.stream_tracker import StreamTracker
from wail.wrapper import wail_end, wail_retry
from wail.runtime.context import _current_trace


class UnifiedStream:
    def __init__(
        self,
        manager,
        provider,
        transport=None,
        watcher=None,
        model=None,
    ):

        frame = _current_trace.get()
        self._manager = manager
        self._provider = provider
        self._transport = transport
        self._model = model
        self._watcher = watcher

        if hasattr(manager, "__enter__"):
            self._stream = None
        else:
            self._stream = manager
        self._tracker = StreamTracker()

        self._start_ts = 0.0

        self._first_token = False
        self._closed = False

    def __enter__(self):
        self._first_token = False
        self._closed = False
        self._tracker.on_stream_start()

        self._start_ts = time.perf_counter()

        if self._watcher:
            self._watcher.start()

        emit_event(
            "stream_start",
            {
                "provider": self._provider,
                "model": self._model,
                "t_offset_ms": 0,
            },
        )

        frame = _current_trace.get()

        if hasattr(self._manager, "__enter__"):
            self._stream = self._manager.__enter__()

        return self

    def __exit__(self, exc_type, exc, tb):

        if exc_type:

            wail_retry()

            update_stream_surface(
                {
                    "error": True,
                    "error_type": str(exc_type),
                }
            )

        stream_surface = self._tracker.finalize()

        if stream_surface:

            update_stream_surface(stream_surface)

            emit_event(
                "stream_end",
                {
                    "t_offset_ms": stream_surface.get(
                        "stream_duration_ms"
                    ),
                    "total_stream_chunks": stream_surface.get(
                        "stream_chunk_count"
                    ),
                },
            )

        try:

            if hasattr(self._manager, "__exit__"):
                return self._manager.__exit__(
                    exc_type,
                    exc,
                    tb,
                )

            return False

        finally:

            self.close()

            wail_end()


    def __iter__(self):

        if self._stream is None:
            raise RuntimeError(
                "Stream has not been initialized."
            )

        if self._start_ts == 0.0:

            self._tracker.on_stream_start()

            self._start_ts = time.perf_counter()

            if self._watcher:
                self._watcher.start()

            emit_event(
                "stream_start",
                {
                    "provider": self._provider,
                    "model": self._model,
                    "t_offset_ms": 0,
                },
            )

        if self._transport == "openai":
            yield from self._iter_openai()
            return

        if self._provider == "anthropic":
            yield from self._iter_anthropic()
            return

        if self._provider == "google":
            yield from self._iter_google()
            return

        yield from self._stream

    @property
    def text_stream(self):

        if self._stream is None:
            raise RuntimeError(
                "Stream has not been initialized."
            )

        if self._provider == "anthropic":

            for text in self._stream.text_stream:

                self._tracker.on_token()
                self._on_first_token()

                yield text

            final = self._stream.get_final_message()

            usage = getattr(final, "usage", None)

            if usage:
                self._update_usage(usage)

            return

        for event in self._iter_openai():

            text = self._extract_text(event)

            if text:
                yield text

    def _on_first_token(self):

        if self._first_token:
            return
        

        self._first_token = True

        if self._watcher:
            self._watcher.on_first_token()

        mark_first_token()

        emit_event(
            "first_token",
            {
                "t_offset_ms": round(
                    (time.perf_counter() - self._start_ts) * 1000,
                    2,
                ),
            },
        )

    def _iter_openai(self):

        for event in self._stream:

            event_type = getattr(event, "type", None)

            if event_type == "response.output_text.delta":
                self._tracker.on_token()
                self._on_first_token()

            elif event_type in (
                "response.completed",
                "response.incomplete",
            ):
                response = getattr(event, "response", None)
                usage = getattr(response, "usage", None)

                if usage:
                    self._update_usage(usage)

            yield event

    def _iter_anthropic(self):
        for event in self._stream:
            event_type = getattr(event, "type", None)

            if event_type == "content_block_delta":
                delta = getattr(event, "delta", None)
                text = getattr(delta, "text", None)

                if text:
                    self._tracker.on_token()
                    self._on_first_token()

            elif event_type == "message_start":
                message = getattr(event, "message", None)
                usage = getattr(message, "usage", None)

                if usage:
                    input_tokens = getattr(
                        usage,
                        "input_tokens",
                        None,
                    )

                    if input_tokens is not None:
                        update_token_usage(
                            input_tokens,
                            0,
                        )

            elif event_type == "message_delta":
                usage = getattr(event, "usage", None)

                if usage:
                    output_tokens = getattr(
                        usage,
                        "output_tokens",
                        None,
                    )

                    if output_tokens is not None:
                        update_token_usage(
                            0,
                            output_tokens,
                        )

            yield event

    def _iter_google(self):

        last_chunk = None
        first = True

        try:

            for chunk in self._stream:

                if first:
                    first = False

                last_chunk = chunk

                text = getattr(chunk, "text", None)

                if text:
                    self._tracker.on_token()
                    self._on_first_token()

                yield chunk

            if last_chunk:

                usage = getattr(last_chunk, "usage_metadata", None)

                if usage:

                    update_token_usage(
                        getattr(usage, "prompt_token_count", None),
                        getattr(usage, "candidates_token_count", None),
                    )

        finally:

            stream_surface = self._tracker.finalize()

            if stream_surface:

                update_stream_surface(stream_surface)

                emit_event(
                    "stream_end",
                    {
                        "t_offset_ms": stream_surface.get("stream_duration_ms"),
                        "total_stream_chunks": stream_surface.get(
                            "stream_chunk_count"
                        ),
                    },
                )

            self.close()

            wail_end()

    def _update_usage(self, usage):

        if usage is None:
            return

        input_tokens = getattr(
            usage,
            "input_tokens",
            None,
        )

        output_tokens = getattr(
            usage,
            "output_tokens",
            None,
        )

        if (
            input_tokens is None
            or output_tokens is None
        ):
            return

        update_token_usage(
            input_tokens,
            output_tokens,
        )

    def _extract_text(self, event):

        if self._provider == "openai":

            if getattr(event, "type", None) != "response.output_text.delta":
                return None

            return getattr(event, "delta", None)

        return None

    def close(self):

        if self._closed:
            return

        self._closed = True

        try:

            if (
                self._stream is not None
                and hasattr(self._stream, "close")
            ):
                self._stream.close()

            elif hasattr(self._manager, "close"):
                self._manager.close()

        finally:

            self._stream = None

            if self._watcher:
                self._watcher.cancel()

            clear_ttft_watcher()

    def __getattr__(self, name):

        if name == "text_stream":
            return self.text_stream

        if (
            self._stream is not None
            and hasattr(self._stream, name)
        ):
            return getattr(
                self._stream,
                name,
            )

        return getattr(
            self._manager,
            name,
        )  



              