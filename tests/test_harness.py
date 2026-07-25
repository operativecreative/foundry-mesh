#!/usr/bin/env python3
"""Unit tests for benchmarks.harness."""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from benchmarks.harness import BenchmarkHarness, BenchmarkResult


class TestBenchmarkHarness:
    def test_empty_harness(self):
        h = BenchmarkHarness("empty")
        assert h.suite_name == "empty"
        assert len(h.results) == 0
        assert h.summary() == {}

    def test_single_run(self):
        h = BenchmarkHarness("single")

        def fn():
            return {"success": True, "cost_usd": 0.05}

        results = h.run("task_a", "v1", fn)
        assert len(results) == 1
        assert results[0].name == "task_a"
        assert results[0].variant == "v1"
        assert results[0].success is True
        assert results[0].cost_usd == 0.05
        assert results[0].latency_ms >= 0

    def test_multiple_iterations(self):
        h = BenchmarkHarness("multi")

        call_count = 0
        def fn():
            nonlocal call_count
            call_count += 1
            return {"success": call_count % 2 == 0, "cost_usd": 0.01}

        h.run("task", "v1", fn, iterations=10)
        assert call_count == 10
        assert len(h.results) == 10

    def test_summary_aggregation(self):
        h = BenchmarkHarness("agg")

        def fn():
            return {"success": True, "cost_usd": 0.1, "retries": 2}

        h.run("task", "v1", fn, iterations=5)
        summary = h.summary()

        key = "task/v1"
        assert key in summary
        assert summary[key]["count"] == 5
        assert summary[key]["success_rate"] == 1.0
        assert summary[key]["avg_cost_usd"] == 0.1
        assert summary[key]["avg_retries"] == 2.0
        assert summary[key]["total_cost_usd"] == 0.5

    def test_report_json(self):
        h = BenchmarkHarness("json")

        def fn():
            return {"success": True}

        h.run("t", "v", fn)
        report = h.report()
        assert "json" in report
        assert "t" in report
        assert "v" in report

    def test_variant_isolation(self):
        h = BenchmarkHarness("variants")

        def baseline():
            return {"success": True, "cost_usd": 0.02}

        def frontier():
            return {"success": True, "cost_usd": 0.01}

        h.run("task", "baseline", baseline, iterations=3)
        h.run("task", "frontier", frontier, iterations=3)

        summary = h.summary()
        assert "task/baseline" in summary
        assert "task/frontier" in summary
        assert summary["task/baseline"]["avg_cost_usd"] == 0.02
        assert summary["task/frontier"]["avg_cost_usd"] == 0.01
