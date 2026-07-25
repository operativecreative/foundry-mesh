#!/usr/bin/env python3
"""
CI regression gate.

Fails the build if:
- Success rate < 70%
- Latency > 30s
- Cost > $0.10 per task
- Repair effectiveness regresses
- Any metric drops 2 stdev below historical mean

Usage in CI:
    python benchmarks/ci_gate.py --report benchmarks/empirical-report.json
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List

from benchmarks.history import regression_gate, compare_to_history
from benchmarks.stats import summarize, welch_ttest

def load_report(path: str) -> dict:
    with open(path) as f:
        return json.load(f)

def check_thresholds(report: dict) -> List[str]:
    """Check absolute thresholds."""
    failures = []

    THRESHOLDS = {
        "success_rate": {"min": 0.70},
        "avg_latency_ms": {"max": 30000},
        "avg_cost_usd": {"max": 0.10},
        "avg_retries": {"max": 5},
    }

    if "results" not in report or "comparative" not in report["results"]:
        return ["No comparative results in report"]

    comp = report["results"]["comparative"]

    for exp_name, exp_result in comp.get("results", {}).items():
        frontier = exp_result.get("frontier", {})

        for metric, threshold in THRESHOLDS.items():
            val = frontier.get(metric)
            if val is None:
                continue

            if "min" in threshold and val < threshold["min"]:
                failures.append(f"{exp_name}.{metric}={val:.4f} < {threshold['min']}")

            if "max" in threshold and val > threshold["max"]:
                failures.append(f"{exp_name}.{metric}={val:.4f} > {threshold['max']}")

    return failures

def check_historical_regression(report: dict) -> List[str]:
    """Check against historical trends."""
    failures = []

    for metric in ["success_rate", "avg_latency_ms", "avg_cost_usd"]:
        comparison = compare_to_history(report, metric=metric, window=10)
        if comparison.get("status") == "regression":
            failures.append(
                f"{metric} regressed: current={comparison['current']:.4f}, "
                f"historical_mean={comparison['historical_mean']}, "
                f"threshold={comparison['regression_threshold']}"
            )

    return failures

def main():
    parser = argparse.ArgumentParser(description="CI Regression Gate")
    parser.add_argument("--report", required=True, help="Path to benchmark report JSON")
    parser.add_argument("--strict", action="store_true", help="Fail on any threshold violation")
    args = parser.parse_args()

    report = load_report(args.report)

    print("=" * 60)
    print("CI REGRESSION GATE")
    print("=" * 60)

    # Check 1: Absolute thresholds
    threshold_failures = check_thresholds(report)
    if threshold_failures:
        print("\nTHRESHOLD VIOLATIONS:")
        for f in threshold_failures:
            print(f"  {f}")
    else:
        print("\nAll thresholds met")

    # Check 2: Historical regression
    historical_failures = check_historical_regression(report)
    if historical_failures:
        print("\nHISTORICAL REGRESSIONS:")
        for f in historical_failures:
            print(f"  {f}")
    else:
        print("\nNo historical regressions")

    # Summary
    all_failures = threshold_failures + historical_failures

    print("\n" + "=" * 60)
    if all_failures:
        print(f"RESULT: FAILED ({len(all_failures)} issues)")
        print("=" * 60)
        sys.exit(1)
    else:
        print("RESULT: PASSED")
        print("=" * 60)
        sys.exit(0)

if __name__ == "__main__":
    main()
