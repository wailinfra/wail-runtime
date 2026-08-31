import threading
import time

from ..runtime_signal import RuntimeSignal, RuntimeSignalType


class FirstTokenWatcher:

    def __init__(
        self,
        threshold_ms: int = 100,
        on_timeout=None,
    ):
        self.threshold_ms = threshold_ms
        self.on_timeout = on_timeout

        self.started_at = 0.0
        self.completed = False
        self.signal = None
        self._timer = None

    def start(self):
       

        self.started_at = time.perf_counter()

        self._timer = threading.Timer(
            self.threshold_ms / 1000,
            self._timeout,
        )

        self._timer.daemon = True
        self._timer.start()

    def on_first_token(self):

        self.completed = True

        if self._timer:
            self._timer.cancel()
            self._timer = None

    def cancel(self):

        self.completed = True

        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _timeout(self):

        if self.completed:
            return

        elapsed = (
            time.perf_counter() - self.started_at
        ) * 1000

        self.signal = RuntimeSignal(
            signal_type=RuntimeSignalType.FIRST_TOKEN_STALL,
            elapsed_ms=elapsed,
        )

        if self.on_timeout:
            self.on_timeout(self.signal)


            