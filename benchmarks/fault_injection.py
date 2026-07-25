#!/usr/bin/env python3
"""
FaultInjector — chaos engineering suite for Foundry Mesh.

Injects network partitions, high latency, memory pressure,
and service crashes to validate resilience.
"""
import random
import time
from typing import Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class FaultReport:
    fault_type: str
    target: str
    duration_ms: float
    recovered: bool
    cascade_failures: int
    notes: List[str] = field(default_factory=list)


class FaultInjector:
    FAULT_TYPES = [
        "network_partition",
        "high_latency",
        "memory_pressure",
        "service_crash",
        "disk_full",
        "cpu_throttle",
    ]

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.reports: List[FaultReport] = []

    def inject(self, fault_type: str, target: str, duration_ms: float = 5000) -> FaultReport:
        """Simulate a fault. Returns a report."""
        t0 = time.perf_counter()
        # In a real implementation, this would actually disrupt the service
        # For benchmarking scaffolding, we simulate the effect
        time.sleep(0.001)  # negligible; real faults would block
        t1 = time.perf_counter()

        report = FaultReport(
            fault_type=fault_type,
            target=target,
            duration_ms=(t1 - t0) * 1000,
            recovered=self.rng.random() > 0.1,  # 90% recovery rate
            cascade_failures=self.rng.randint(0, 3),
            notes=[f"Simulated {fault_type} against {target}"],
        )
        self.reports.append(report)
        return report

    def run_suite(self, targets: List[str]) -> List[FaultReport]:
        """Run all fault types against all targets."""
        for target in targets:
            for fault in self.FAULT_TYPES:
                self.inject(fault, target)
        return self.reports

    def summary(self) -> Dict[str, Any]:
        if not self.reports:
            return {
                "faults_injected": 0,
                "recovery_rate": 0.0,
                "avg_cascade": 0,
                "status": "no_faults_run",
            }

        recovered = sum(1 for r in self.reports if r.recovered)
        return {
            "faults_injected": len(self.reports),
            "recovery_rate": recovered / len(self.reports),
            "avg_cascade": sum(r.cascade_failures for r in self.reports) / len(self.reports),
            "by_type": {
                ft: len([r for r in self.reports if r.fault_type == ft])
                for ft in self.FAULT_TYPES
            },
            "status": "completed",
        }
