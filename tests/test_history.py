#!/usr/bin/env python3
"""Unit tests for benchmarks.history."""
import sys
from pathlib import Path
import tempfile
import json

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from benchmarks import history


class TestHistory:
    def test_load_empty_history(self, monkeypatch):
        with tempfile.TemporaryDirectory() as td:
            fake_history = Path(td) / "history.jsonl"
            monkeypatch.setattr(history, "HISTORY_FILE", fake_history)

            records = history.load_history()
            assert records == []

    def test_append_and_load(self, monkeypatch):
        with tempfile.TemporaryDirectory() as td:
            fake_history = Path(td) / "history.jsonl"
            monkeypatch.setattr(history, "HISTORY_FILE", fake_history)

            report = {
                "results": {
                    "comparative": {
                        "results": {
                            "test_exp": {
                                "frontier": {
                                    "success_rate": 0.9,
                                    "avg_cost_usd": 0.01,
                                    "avg_latency_ms": 5000,
                                }
                            }
                        }
                    }
                }
            }

            history.append_record(report)
            records = history.load_history()

            assert len(records) == 1
            assert records[0]["results"]["comparative"]["results"]["test_exp"]["frontier"]["success_rate"] == 0.9

    def test_window_limit(self, monkeypatch):
        with tempfile.TemporaryDirectory() as td:
            fake_history = Path(td) / "history.jsonl"
            monkeypatch.setattr(history, "HISTORY_FILE", fake_history)

            for i in range(20):
                history.append_record({"idx": i})

            records = history.load_history(window=5)
            assert len(records) == 5
            assert records[-1]["idx"] == 19

    def test_compare_no_history(self, monkeypatch):
        with tempfile.TemporaryDirectory() as td:
            fake_history = Path(td) / "history.jsonl"
            monkeypatch.setattr(history, "HISTORY_FILE", fake_history)

            report = {"results": {"comparative": {"results": {}}}}
            result = history.compare_to_history(report, "success_rate")

            assert result["status"] == "no_history"

    def test_compare_with_history(self, monkeypatch):
        with tempfile.TemporaryDirectory() as td:
            fake_history = Path(td) / "history.jsonl"
            monkeypatch.setattr(history, "HISTORY_FILE", fake_history)

            # Seed history with 10 identical reports
            base_report = {
                "results": {
                    "comparative": {
                        "results": {
                            "exp": {
                                "frontier": {
                                    "success_rate": 0.85,
                                    "avg_cost_usd": 0.01,
                                    "avg_latency_ms": 5000,
                                }
                            }
                        }
                    }
                }
            }
            for _ in range(10):
                history.append_record(base_report)

            # Current report: same values
            result = history.compare_to_history(base_report, "success_rate")
            assert result["status"] == "ok"
            assert result["current"] == 0.85
            assert result["historical_mean"] == 0.85

    def test_regression_detection(self, monkeypatch):
        with tempfile.TemporaryDirectory() as td:
            fake_history = Path(td) / "history.jsonl"
            monkeypatch.setattr(history, "HISTORY_FILE", fake_history)

            # History: consistent 0.85 success rate
            good_report = {
                "results": {
                    "comparative": {
                        "results": {
                            "exp": {
                                "frontier": {"success_rate": 0.85}
                            }
                        }
                    }
                }
            }
            for _ in range(10):
                history.append_record(good_report)

            # Current: dropped to 0.50 (way below 2σ)
            bad_report = {
                "results": {
                    "comparative": {
                        "results": {
                            "exp": {
                                "frontier": {"success_rate": 0.50}
                            }
                        }
                    }
                }
            }
            result = history.compare_to_history(bad_report, "success_rate")
            assert result["status"] == "regression"
            assert result["current"] == 0.50

    def test_regression_gate(self, monkeypatch):
        with tempfile.TemporaryDirectory() as td:
            fake_history = Path(td) / "history.jsonl"
            monkeypatch.setattr(history, "HISTORY_FILE", fake_history)

            # Empty history = no failures
            report = {"results": {"comparative": {"results": {}}}}
            failures = history.regression_gate(report)
            assert failures == []
