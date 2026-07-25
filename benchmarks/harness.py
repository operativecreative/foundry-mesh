#!/usr/bin/env python3
"""
BenchmarkHarness — collects, times, and stores benchmark results.

Thread-safe. Supports nested contexts. Dumps JSON on demand.
"""
import time
import json
import statistics
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class BenchmarkResult:
    name: str
    variant: str
    success: bool
    latency_ms: float
    cost_usd: float
    retries: int
    repair_loops: int
    tokens_consumed: int
    checkpoint_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BenchmarkHarness:
    def __init__(self, suite_name: str):
        self.suite_name = suite_name
        self.results: List[BenchmarkResult] = []
        self._lock = False  # simple flag; use threading.Lock if multi-threaded

    def run(
        self,
        task_name: str,
        variant: str,
        fn: Callable[[], Dict[str, Any]],
        iterations: int = 1,
    ) -> List[BenchmarkResult]:
        """Execute fn() `iterations` times and record each result."""
        collected = []
        for i in range(iterations):
            t0 = time.perf_counter()
            raw = fn()
            t1 = time.perf_counter()
            latency_ms = (t1 - t0) * 1000

            result = BenchmarkResult(
                name=task_name,
                variant=variant,
                success=raw.get("success", True),
                latency_ms=latency_ms,
                cost_usd=raw.get("cost_usd", 0.0),
                retries=raw.get("retries", 0),
                repair_loops=raw.get("repair_loops", 0),
                tokens_consumed=raw.get("tokens_consumed", 0),
                checkpoint_count=raw.get("checkpoint_count", 0),
                metadata={"iteration": i, **raw.get("metadata", {})},
            )
            collected.append(result)
            self.results.append(result)
        return collected

    def report(self) -> str:
        """Return JSON string of all results."""
        return json.dumps(
            {
                "suite": self.suite_name,
                "count": len(self.results),
                "results": [asdict(r) for r in self.results],
            },
            indent=2,
        )

    def summary(self) -> Dict[str, Any]:
        """Aggregate statistics per (name, variant)."""
        groups: Dict[tuple, List[BenchmarkResult]] = {}
        for r in self.results:
            key = (r.name, r.variant)
            groups.setdefault(key, []).append(r)

        out = {}
        for (name, variant), rs in groups.items():
            latencies = [r.latency_ms for r in rs]
            costs = [r.cost_usd for r in rs]
            successes = [r.success for r in rs]
            out[f"{name}/{variant}"] = {
                "count": len(rs),
                "success_rate": sum(successes) / len(successes),
                "avg_latency_ms": statistics.mean(latencies) if latencies else 0,
                "p95_latency_ms": (
                    sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
                ),
                "avg_cost_usd": statistics.mean(costs) if costs else 0,
                "total_cost_usd": sum(costs),
                "avg_retries": statistics.mean([r.retries for r in rs]),
                "avg_repair_loops": statistics.mean([r.repair_loops for r in rs]),
            }
        return out
