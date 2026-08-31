import threading
import queue
from typing import Callable


class AsyncIOWorker:
    def __init__(self, write_func: Callable[[str], None]):
        self._write = write_func
        self._queue = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def submit(self, line: str) -> None:
        self._queue.put(line)

    def _run(self):
        while not self._stop.is_set():
            try:
                line = self._queue.get(timeout=0.1)
                self._write(line)
            except queue.Empty:
                continue
            except Exception:
                continue

    def shutdown(self) -> None:
        self._stop.set()
