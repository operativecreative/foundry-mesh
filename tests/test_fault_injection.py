#!/usr/bin/env python3
"""Unit tests for benchmarks.fault_injection."""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from benchmarks.fault_injection import FaultInjector, FaultReport


class TestFaultInjector:
    def test_empty_injector(self):
        fi = FaultInjector()
        summary = fi.summary()
        assert summary["faults_injected"] == 0
        assert summary["status"] == "no_faults_run"

    def test_single_inject(self):
        fi = FaultInjector(seed=123)
        report = fi.inject("network_partition", "svc-1", duration_ms=100)

        assert isinstance(report, FaultReport)
        assert report.fault_type == "network_partition"
        assert report.target == "svc-1"
        assert report.duration_ms >= 0
        assert report.recovered in (True, False)
        assert len(fi.reports) == 1

    def test_run_suite(self):
        fi = FaultInjector(seed=456)
        targets = ["a", "b", "c"]
        fi.run_suite(targets)

        expected = len(fi.FAULT_TYPES) * len(targets)
        assert len(fi.reports) == expected

        summary = fi.summary()
        assert summary["faults_injected"] == expected
        assert summary["status"] == "completed"

    def test_recovery_rate_bounds(self):
        fi = FaultInjector(seed=789)
        fi.run_suite(["x"])
        summary = fi.summary()

        assert 0.0 <= summary["recovery_rate"] <= 1.0

    def test_by_type_breakdown(self):
        fi = FaultInjector(seed=999)
        fi.run_suite(["svc"])
        summary = fi.summary()

        for ft in fi.FAULT_TYPES:
            assert ft in summary["by_type"]
            assert summary["by_type"][ft] == 1

    def test_determinism(self):
        fi1 = FaultInjector(seed=42)
        fi2 = FaultInjector(seed=42)

        fi1.run_suite(["a"])
        fi2.run_suite(["a"])

        s1 = fi1.summary()
        s2 = fi2.summary()

        assert s1["recovery_rate"] == s2["recovery_rate"]
        assert s1["avg_cascade"] == s2["avg_cascade"]
