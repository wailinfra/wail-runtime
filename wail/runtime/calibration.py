from threading import Lock
from typing import Dict, List, Tuple

_BUCKETS: Tuple[float, ...] = (5, 10, 20, 40, 60, 80, 100)


class FixedHistogram:
    __slots__ = ("_counts", "_lock")

    def __init__(self) -> None:
        self._counts: List[int] = [0] * (len(_BUCKETS) + 1)
        self._lock = Lock()

    def record(self, value: float) -> None:
        idx = self._bucket_index(value)
        with self._lock:
            self._counts[idx] += 1

    def snapshot(self) -> List[int]:
        with self._lock:
            return list(self._counts)

    def total(self) -> int:
        with self._lock:
            return sum(self._counts)

    def percentiles(self, percentiles=(50, 90, 95, 99)) -> Dict[int, float]:
        with self._lock:
            total = sum(self._counts)
            if total == 0:
                return {p: 0.0 for p in percentiles}

            cumulative = 0
            results: Dict[int, float] = {}
            thresholds = {p: total * (p / 100.0) for p in percentiles}

            for i, count in enumerate(self._counts):
                cumulative += count
                for p, t in thresholds.items():
                    if p not in results and cumulative >= t:
                        results[p] = self._bucket_upper_bound(i)

            for p in percentiles:
                if p not in results:
                    results[p] = self._bucket_upper_bound(len(self._counts) - 1)

            return results

    @staticmethod
    def _bucket_index(value: float) -> int:
        for i, boundary in enumerate(_BUCKETS):
            if value <= boundary:
                return i
        return len(_BUCKETS)

    @staticmethod
    def _bucket_upper_bound(index: int) -> float:
        if index < len(_BUCKETS):
            return _BUCKETS[index]
        return float("inf")


class CalibrationEngine:
    __slots__ = (
        "_global_hist",
        "_segment_hists",
        "_segment_limit",
        "_lock",
    )

    def __init__(self, segment_limit: int = 128) -> None:
        self._global_hist = FixedHistogram()
        self._segment_hists: Dict[str, FixedHistogram] = {}
        self._segment_limit = segment_limit
        self._lock = Lock()

    def record(self, score: float, segment: str) -> None:
        self._global_hist.record(score)

        if not segment:
            return

        with self._lock:
            hist = self._segment_hists.get(segment)
            if hist is None:
                if len(self._segment_hists) >= self._segment_limit:
                    return
                hist = FixedHistogram()
                self._segment_hists[segment] = hist

        hist.record(score)

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            segment_data = {
                seg: hist.snapshot() for seg, hist in self._segment_hists.items()
            }

        return {
            "global": self._global_hist.snapshot(),
            "segments": segment_data,
            "total": self._global_hist.total(),
            "percentiles": self._global_hist.percentiles(),
        }


calibration_engine = CalibrationEngine()
