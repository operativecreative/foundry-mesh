#!/usr/bin/env python3
"""Unit tests for benchmarks.comparative."""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from benchmarks.comparative import (
    ComparativeExperiments,
    ALL_EXPERIMENTS,
    ExperimentRepairVsNoRepair,
    ExperimentMemoryEnabled,
    ExperimentCheckpointFrequency,
)
from benchmarks.harness import BenchmarkHarness


class TestComparativeExperiments:
    def test_empty_experiments(self):
        h = BenchmarkHarness("empty_comp")
        comp = ComparativeExperiments(h)
        summary = comp.summary()

        assert summary["experiments_run"] == 0
        assert summary["significant_improvements"] == 0

    def test_register_experiment(self):
        h = BenchmarkHarness("reg")
        comp = ComparativeExperiments(h)
        comp.register(ExperimentRepairVsNoRepair())

        assert len(comp.experiments) == 1

    def test_experiment_result_shape(self):
        h = BenchmarkHarness("shape")
        comp = ComparativeExperiments(h)
        comp.register(ExperimentCheckpointFrequency())
        comp.run_all(iterations=1)

        result = comp.summary()["results"]["checkpoint_frequency"]
        assert "hypothesis" in result
        assert "baseline" in result
        assert "frontier" in result
        assert "delta" in result
        assert "significant" in result

        for variant in ["baseline", "frontier"]:
            assert "success_rate" in result[variant]
            assert "avg_cost_usd" in result[variant]
            assert "avg_latency_ms" in result[variant]

    def test_all_experiments_run(self):
        h = BenchmarkHarness("all_exp")
        comp = ComparativeExperiments(h)

        for factory in ALL_EXPERIMENTS:
            comp.register(factory())

        comp.run_all(iterations=2)
        summary = comp.summary()

        assert summary["experiments_run"] == len(ALL_EXPERIMENTS)
        assert len(summary["results"]) == len(ALL_EXPERIMENTS)

    def test_delta_computation(self):
        h = BenchmarkHarness("delta")
        comp = ComparativeExperiments(h)
        comp.register(ExperimentRepairVsNoRepair())
        comp.run_all(iterations=2)

        result = comp.summary()["results"]["repair_effectiveness"]
        delta = result["delta"]

        assert "success_rate" in delta
        assert "cost_pct" in delta
        assert "latency_pct" in delta
