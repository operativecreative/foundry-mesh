#!/usr/bin/env python3
"""
Runtime benchmark runner — executes benchmarks against live mesh engine.

Level 5 validation: benchmarks exercise the actual scheduler, router,
memory, checkpoint, and repair systems.

NOTE: This module is SYNCHRONOUS. Each task manages its own event loop
internally so harness.run() can measure wall-clock time properly.
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.harness import BenchmarkHarness
from benchmarks.engine_tasks import EngineTaskFactory
from benchmarks.history import append_record


RUNTIME_TASKS = [
    ("simple_web_server", EngineTaskFactory.simple_web_server_task),
    ("data_pipeline", EngineTaskFactory.data_pipeline_task),
    ("microservice_mesh", EngineTaskFactory.microservice_mesh_task),
    ("react_component_lib", EngineTaskFactory.react_component_lib_task),
    ("terraform_module", EngineTaskFactory.terraform_module_task),
]


def run_runtime_benchmarks(iterations: int = 3):
    harness = BenchmarkHarness("runtime")

    print("=== Runtime Benchmarks (Live Mesh Engine) ===")
    for name, factory in RUNTIME_TASKS:
        print(f"\nTask: {name}")

        fn = factory()
        harness.run(name, "runtime", fn, iterations=iterations)

        summary = harness.summary()
        key = f"{name}/runtime"
        if key in summary:
            s = summary[key]
            print(f"  Success rate: {s['success_rate']:.2%}")
            print(f"  Avg latency:  {s['avg_latency_ms']:.2f}ms")
            print(f"  Avg cost:     ${s['avg_cost_usd']:.4f}")
            print(f"  Avg retries:  {s['avg_retries']:.2f}")

    return harness


def main():
    parser = argparse.ArgumentParser(description="Foundry Mesh Runtime Benchmarks")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--output", default="benchmarks/runtime-report.json")
    parser.add_argument("--save-history", action="store_true", help="Append to history.jsonl")
    args = parser.parse_args()

    harness = run_runtime_benchmarks(args.iterations)

    report = {
        "suite": "runtime",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "iterations": args.iterations,
        "results": json.loads(harness.report()),
        "summary": harness.summary(),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n{'='*50}")
    print(f"Runtime report saved to: {output_path}")
    print(f"{'='*50}")

    if args.save_history:
        append_record(report)
        print("Appended to history.jsonl")

    # Print summary
    summary = harness.summary()
    print(f"\nRuntime Results Summary:")
    for key, stats in summary.items():
        print(f"  {key}: success={stats['success_rate']:.2%} cost=${stats['avg_cost_usd']:.4f} latency={stats['avg_latency_ms']:.2f}ms")


if __name__ == "__main__":
    main()
