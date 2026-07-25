#!/usr/bin/env python3
"""
Smoke test — Level 2 validation: imports + basic execution.

Exits non-zero on any assertion failure or exception.
Run with: python tests/smoke_test.py
"""
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

def main():
    failures = []

    try:
        # === Level 2a: All modules import cleanly ===
        from benchmarks import harness, tasks, fault_injection, scalability
        from benchmarks import comparative, history, stats
        from benchmarks.harness import BenchmarkHarness
        from benchmarks.tasks import ALL_TASKS
        from benchmarks.fault_injection import FaultInjector
        from benchmarks.scalability import ScalabilitySuite
        from benchmarks.comparative import ComparativeExperiments, ALL_EXPERIMENTS
        from benchmarks.history import compare_to_history, regression_gate, load_history
        from benchmarks.stats import summarize, welch_ttest
        print("PASS: All benchmark modules import successfully")
    except Exception as e:
        failures.append(f"IMPORT FAILURE: {e}")
        raise

    try:
        # === Level 2b: Harness executes and aggregates ===
        h = BenchmarkHarness("smoke_test")

        def dummy_fn():
            return {
                "success": True,
                "cost_usd": 0.01,
                "retries": 0,
                "repair_loops": 0,
                "tokens_consumed": 1000,
                "checkpoint_count": 2,
            }

        h.run("test_task", "baseline", dummy_fn, iterations=5)
        summary = h.summary()

        key = "test_task/baseline"
        assert key in summary, f"Expected {key} in summary, got {list(summary.keys())}"
        assert summary[key]["count"] == 5, f"Expected count=5, got {summary[key]['count']}"
        assert summary[key]["success_rate"] == 1.0, f"Expected success_rate=1.0, got {summary[key]['success_rate']}"
        assert summary[key]["avg_cost_usd"] == 0.01, f"Expected avg_cost_usd=0.01, got {summary[key]['avg_cost_usd']}"
        assert summary[key]["avg_retries"] == 0, f"Expected avg_retries=0, got {summary[key]['avg_retries']}"

        # Verify report serialization
        report_json = h.report()
        assert "smoke_test" in report_json
        assert "test_task" in report_json

        print("PASS: BenchmarkHarness executes, aggregates, and serializes")
    except Exception as e:
        failures.append(f"HARNESS FAILURE: {e}")
        raise

    try:
        # === Level 2c: FaultInjector produces expected reports ===
        fi = FaultInjector(seed=42)
        fi.run_suite(["worker-a", "worker-b"])
        fault_summary = fi.summary()

        expected_faults = len(fi.FAULT_TYPES) * 2
        assert fault_summary["faults_injected"] == expected_faults, (
            f"Expected {expected_faults} faults, got {fault_summary['faults_injected']}"
        )
        assert 0.0 <= fault_summary["recovery_rate"] <= 1.0, (
            f"Recovery rate out of range: {fault_summary['recovery_rate']}"
        )
        assert fault_summary["status"] == "completed"

        # Verify by_type breakdown
        for ft in fi.FAULT_TYPES:
            assert ft in fault_summary["by_type"], f"Missing fault type in summary: {ft}"
            assert fault_summary["by_type"][ft] == 2, f"Expected 2 injections for {ft}"

        print("PASS: FaultInjector produces correct report structure")
    except Exception as e:
        failures.append(f"FAULT INJECTION FAILURE: {e}")
        raise

    try:
        # === Level 2d: ComparativeExperiments register and execute ===
        h2 = BenchmarkHarness("comparative_smoke")
        comp = ComparativeExperiments(h2)

        for factory in ALL_EXPERIMENTS:
            comp.register(factory())

        comp.run_all(iterations=20)
        comp_summary = comp.summary()

        assert comp_summary["experiments_run"] == len(ALL_EXPERIMENTS), (
            f"Expected {len(ALL_EXPERIMENTS)} experiments, got {comp_summary['experiments_run']}"
        )
        assert "significant_improvements" in comp_summary
        assert comp_summary["significant_improvements"] <= comp_summary["experiments_run"]

        # Verify each experiment has required fields
        for name, result in comp_summary["results"].items():
            assert "hypothesis" in result, f"Missing hypothesis for {name}"
            assert "baseline" in result, f"Missing baseline for {name}"
            assert "frontier" in result, f"Missing frontier for {name}"
            assert "delta" in result, f"Missing delta for {name}"
            assert "significant" in result, f"Missing significant flag for {name}"
            assert isinstance(result["significant"], bool)

        print("PASS: ComparativeExperiments register, execute, and summarize correctly")
    except Exception as e:
        failures.append(f"COMPARATIVE FAILURE: {e}")
        raise

    try:
        # === Level 2e: Statistical functions return valid shapes ===
        a = [1.2, 1.5, 1.3, 1.4, 1.6]
        b = [1.1, 1.2, 1.15, 1.25, 1.3]

        result = welch_ttest(a, b)
        assert "t_stat" in result, "Missing t_stat"
        assert "df" in result, "Missing df"
        assert "p_value" in result, "Missing p_value"
        assert "significant" in result, "Missing significant"
        assert 0 <= result["p_value"] <= 1, f"p_value out of range: {result['p_value']}"
        assert isinstance(result["significant"], bool)

        # Test summarize
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        s = summarize(vals)
        assert s["count"] == 5
        assert s["mean"] == 3.0
        assert s["median"] == 3.0
        assert s["min"] == 1.0
        assert s["max"] == 5.0
        assert s["stdev"] > 0

        # Edge case: empty list
        empty = summarize([])
        assert empty["count"] == 0

        print("PASS: Statistical functions return valid shapes and edge cases")
    except Exception as e:
        failures.append(f"STATS FAILURE: {e}")
        raise

    try:
        # === Level 2f: Task registry is populated ===
        assert len(ALL_TASKS) > 0, "Task registry is empty"
        for task in ALL_TASKS:
            assert hasattr(task, "name")
            assert hasattr(task, "description")
            assert hasattr(task, "complexity")
            assert task.complexity in ("simple", "medium", "complex")

        print("PASS: Task registry is populated and well-formed")
    except Exception as e:
        failures.append(f"TASKS FAILURE: {e}")
        raise

    # === Final tally ===
    if failures:
        print(f"\nFAIL: {len(failures)} assertion(s) failed")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("\n" + "=" * 50)
        print("ALL SMOKE TESTS PASSED")
        print("=" * 50)
        sys.exit(0)


if __name__ == "__main__":
    main()
