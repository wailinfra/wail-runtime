import os
import threading
import time
from queue import Queue, Full, Empty


class AsyncFileWriter:

    def __init__(
        self,
        path: str,
        *,
        max_queue_size: int = 10000,
        flush_interval: float = 0.1,  
        max_batch_size: int = 100,
    ):
        self._path = path
        self._queue = Queue(maxsize=max_queue_size)
        self._flush_interval = flush_interval
        self._max_batch_size = max_batch_size

        self._stop_event = threading.Event()
        self._worker = threading.Thread(
            target=self._run,
            name="WAIL-AsyncWriter",
            daemon=True,
        )

        self._dropped = 0
        self._lock = threading.Lock()

        os.makedirs(os.path.dirname(self._path), exist_ok=True)

        self._worker.start()

    # -------------------------
    # Public API
    # -------------------------

    def append_line(self, line: str) -> None:
        try:
            self._queue.put_nowait(line)
        except Full:
            with self._lock:
                self._dropped += 1

    def shutdown(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        self._worker.join(timeout=timeout)

    def dropped_count(self) -> int:
        with self._lock:
            return self._dropped

    # -------------------------
    # Internal Worker
    # -------------------------

    def _run(self):
        fd = os.open(
            self._path,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
        )

        try:
            buffer = []
            last_flush = time.time()

            while not self._stop_event.is_set() or not self._queue.empty():

                try:
                    item = self._queue.get(timeout=self._flush_interval)
                    buffer.append(item)
                except Empty:
                    pass

                now = time.time()

                if len(buffer) >= self._max_batch_size or (
                    buffer and (now - last_flush) >= self._flush_interval
                ):
                    self._flush(fd, buffer)
                    buffer.clear()
                    last_flush = now

            if buffer:
                self._flush(fd, buffer)

        finally:
            os.fsync(fd)
            os.close(fd)

    def _flush(self, fd, buffer):
        data = ("\n".join(buffer) + "\n").encode("utf-8")
        os.write(fd, data)
        os.fsync(fd)
