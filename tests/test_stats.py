#!/usr/bin/env python3
"""Unit tests for benchmarks.stats."""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from benchmarks.stats import summarize, welch_ttest


class TestSummarize:
    def test_empty_list(self):
        s = summarize([])
        assert s["count"] == 0
        assert s["mean"] == 0
        assert s["stdev"] == 0

    def test_single_value(self):
        s = summarize([42.0])
        assert s["count"] == 1
        assert s["mean"] == 42.0
        assert s["stdev"] == 0
        assert s["min"] == 42.0
        assert s["max"] == 42.0

    def test_symmetric_distribution(self):
        s = summarize([1, 2, 3, 4, 5])
        assert s["mean"] == 3.0
        assert s["median"] == 3.0
        assert s["min"] == 1
        assert s["max"] == 5
        assert s["stdev"] == pytest.approx(1.5811, rel=1e-3)

    def test_identical_values(self):
        s = summarize([7.0, 7.0, 7.0, 7.0])
        assert s["stdev"] == 0


class TestWelchTTest:
    def test_identical_groups(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = welch_ttest(a, b)

        assert result["t_stat"] == pytest.approx(0.0, abs=1e-6)
        assert result["mean_diff"] == pytest.approx(0.0, abs=1e-6)
        assert result["significant"] is False
        assert 0 <= result["p_value"] <= 1

    def test_very_different_groups(self):
        a = [10.0, 11.0, 12.0, 13.0, 14.0]
        b = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = welch_ttest(a, b)

        assert result["mean_diff"] == 9.0
        assert result["significant"] is True
        assert result["p_value"] < 0.05

    def test_insufficient_data(self):
        result = welch_ttest([1.0], [2.0])

        assert result["t_stat"] == 0
        assert result["df"] == 0
        assert result["p_value"] == 1.0
        assert result["significant"] is False

    def test_p_value_bounds(self):
        a = [1.2, 1.5, 1.3, 1.4, 1.6]
        b = [1.1, 1.2, 1.15, 1.25, 1.3]
        result = welch_ttest(a, b)

        assert 0 <= result["p_value"] <= 1
        assert result["df"] > 0

    def test_large_sample_normal_approximation(self):
        import random
        rng = random.Random(42)
        a = [rng.gauss(5.0, 1.0) for _ in range(100)]
        b = [rng.gauss(5.5, 1.0) for _ in range(100)]
        result = welch_ttest(a, b)

        assert result["df"] > 30  # Should use normal approximation path
        assert result["significant"] is True
