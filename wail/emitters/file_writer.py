import threading
import time

BATCH_SIZE = 100
FLUSH_INTERVAL = 0.5


class FileIOWriter:

    def __init__(self, path: str):
        self._path = path
        self._buffer = []
        self._lock = threading.Lock()
        self._last_flush = time.time()

    def append_line(self, line: str):

        with self._lock:
            self._buffer.append(line)

            if len(self._buffer) >= BATCH_SIZE:
                self._flush()

            elif time.time() - self._last_flush > FLUSH_INTERVAL:
                self._flush()

    def _flush(self):

        if not self._buffer:
            return

        data = "\n".join(self._buffer) + "\n"
        self._buffer.clear()

        with open(self._path, "a", encoding="utf-8") as f:
            f.write(data)

        self._last_flush = time.time()
