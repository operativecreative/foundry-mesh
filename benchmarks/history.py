#!/usr/bin/env python3
"""
History tracking and regression detection.

Stores benchmark results in a simple JSONL file and provides
statistical comparison against recent runs.
"""
import json
import statistics
from pathlib import Path
from typing import Dict, Any, List, Optional

HISTORY_FILE = Path(__file__).parent / "history.jsonl"


def append_record(report: dict):
    """Append a benchmark report to the history log."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "a") as f:
        print(json.dumps(report), file=f)


def load_history(window: int = 10) -> List[dict]:
    """Load the last `window` records from history."""
    if not HISTORY_FILE.exists():
        return []

    records = []
    with open(HISTORY_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    return records[-window:]


def compare_to_history(report: dict, metric: str, window: int = 10) -> Dict[str, Any]:
    """Compare current report metric against historical mean."""
    history = load_history(window)

    if not history:
        return {"status": "no_history", "current": None, "historical_mean": None}

    # Extract metric values from historical reports
    # Metric path: results.comparative.results.{exp}.frontier.{metric}
    historical_values = []
    for h in history:
        comp = h.get("results", {}).get("comparative", {}).get("results", {})
        for exp_name, exp_result in comp.items():
            val = exp_result.get("frontier", {}).get(metric)
            if val is not None:
                historical_values.append(val)

    if not historical_values:
        return {"status": "no_data", "current": None, "historical_mean": None}

    mean = statistics.mean(historical_values)
    stdev = statistics.stdev(historical_values) if len(historical_values) > 1 else 0

    # Extract current value
    current_values = []
    comp = report.get("results", {}).get("comparative", {}).get("results", {})
    for exp_name, exp_result in comp.items():
        val = exp_result.get("frontier", {}).get(metric)
        if val is not None:
            current_values.append(val)

    current = statistics.mean(current_values) if current_values else None

    if current is None:
        return {"status": "no_current", "current": None, "historical_mean": mean}

    # Regression: current is 2 stdev below mean
    regression_threshold = mean - 2 * stdev
    is_regression = current < regression_threshold

    return {
        "status": "regression" if is_regression else "ok",
        "current": current,
        "historical_mean": mean,
        "historical_stdev": stdev,
        "regression_threshold": regression_threshold,
        "delta_pct": ((current - mean) / mean * 100) if mean else 0,
    }


def regression_gate(report: dict) -> List[str]:
    """Run all metrics through regression detection."""
    failures = []
    for metric in ["success_rate", "avg_latency_ms", "avg_cost_usd"]:
        result = compare_to_history(report, metric)
        if result.get("status") == "regression":
            failures.append(
                f"{metric} regressed: {result['current']:.4f} vs "
                f"threshold {result['regression_threshold']:.4f}"
            )
    return failures
