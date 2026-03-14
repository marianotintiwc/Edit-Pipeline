from __future__ import annotations

import logging
from time import perf_counter

logger = logging.getLogger("api.metrics")


class LatencyMetric:
    def __init__(self, operation: str) -> None:
        self.operation = operation
        self.started = perf_counter()

    def finish(self, **labels: object) -> None:
        elapsed_ms = round((perf_counter() - self.started) * 1000, 2)
        logger.info(
            "metric=latency operation=%s elapsed_ms=%.2f labels=%s",
            self.operation,
            elapsed_ms,
            labels,
        )
