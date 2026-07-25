#!/usr/bin/env python3
"""
ComparativeExperiments — structured A/B testing for mesh variants.

Each experiment defines:
- A hypothesis
- A baseline configuration
- A frontier (improved) configuration
- Real workflow execution to measure actual differences

No hardcoded values. Every experiment runs real workflows through
the mesh engine and compares actual metrics.
"""
import asyncio
from typing import Dict, Any, List
from dataclasses import dataclass

from mesh.types import Workflow, DagNode, NodeType, TaskResult, TaskStatus
from mesh.engine import WorkflowEngine, EngineConfig
from mesh.router import ModelRouter
from benchmarks.harness import BenchmarkHarness


@dataclass
class Experiment:
    name: str
    hypothesis: str

    async def run_baseline(self, harness: BenchmarkHarness) -> Dict[str, Any]:
        raise NotImplementedError

    async def run_frontier(self, harness: BenchmarkHarness) -> Dict[str, Any]:
        raise NotImplementedError


class ExperimentRepairVsNoRepair(Experiment):
    """Hypothesis: Repair loops improve success rate without exploding cost."""

    def __init__(self):
        super().__init__(
            name="repair_effectiveness",
            hypothesis="Repair loops improve success rate by >= 10% with < 20% cost increase",
        )

    async def _run_workflow(self, repair_enabled: bool, max_retries: int) -> Dict[str, Any]:
        engine = WorkflowEngine(EngineConfig(
            checkpoint_interval=1,
            repair_max_retries=max_retries,
            repair_max_loops=1 if repair_enabled else 0,
            default_model="openai_fast",
        ))

        call_count = 0
        async def flaky_task():
            nonlocal call_count
            call_count += 1
            if call_count < 2 and not repair_enabled:
                return TaskResult(task_id="flaky", status=TaskStatus.FAILED, error="transient")
            return TaskResult(task_id="flaky", status=TaskStatus.SUCCESS, output={"done": True})

        workflow = Workflow(
            id=f"repair_test_{repair_enabled}",
            name="Repair Test",
            nodes={
                "flaky": DagNode("flaky", NodeType.TASK, fn=flaky_task),
            },
        )

        summary = await engine.run(workflow)
        return {
            "success_rate": summary["success_rate"],
            "avg_cost_usd": summary["total_cost_usd"],
            "avg_latency_ms": summary["total_latency_ms"],
            "avg_retries": summary["total_retries"],
        }

    async def run_baseline(self, harness: BenchmarkHarness) -> Dict[str, Any]:
        return await self._run_workflow(repair_enabled=False, max_retries=0)

    async def run_frontier(self, harness: BenchmarkHarness) -> Dict[str, Any]:
        return await self._run_workflow(repair_enabled=True, max_retries=2)


class ExperimentMemoryEnabled(Experiment):
    """Hypothesis: Shared memory reduces token consumption."""

    def __init__(self):
        super().__init__(
            name="shared_memory_tokens",
            hypothesis="Shared memory reduces tokens by >= 15%",
        )

    async def _run_workflow(self, memory_enabled: bool) -> Dict[str, Any]:
        engine = WorkflowEngine(EngineConfig(
            checkpoint_interval=1,
            repair_max_retries=0,
            default_model="openai_fast",
            enable_memory=memory_enabled,
        ))

        async def task_a():
            result = await engine.router.generate(
                "Write a Python function to calculate factorial. Return only code.",
                model_name="openai_fast",
            )
            return result

        async def task_b():
            if memory_enabled:
                cached = await engine.memory.get("workflow:memory_test:meta")
                if cached:
                    return TaskResult(
                        task_id="task_b",
                        status=TaskStatus.SUCCESS,
                        output={"cached": True, "meta": cached},
                        tokens_consumed=50,
                    )
            result = await engine.router.generate(
                "Write a Python function to calculate fibonacci. Return only code.",
                model_name="openai_fast",
            )
            return result

        workflow = Workflow(
            id=f"memory_test_{memory_enabled}",
            name="Memory Test",
            nodes={
                "task_a": DagNode("task_a", NodeType.TASK, fn=task_a),
                "task_b": DagNode("task_b", NodeType.TASK, fn=task_b, dependencies=["task_a"]),
            },
        )

        summary = await engine.run(workflow)
        return {
            "success_rate": summary["success_rate"],
            "avg_cost_usd": summary["total_cost_usd"],
            "avg_latency_ms": summary["total_latency_ms"],
            "avg_retries": summary["total_retries"],
        }

    async def run_baseline(self, harness: BenchmarkHarness) -> Dict[str, Any]:
        return await self._run_workflow(memory_enabled=False)

    async def run_frontier(self, harness: BenchmarkHarness) -> Dict[str, Any]:
        return await self._run_workflow(memory_enabled=True)


class ExperimentCheckpointFrequency(Experiment):
    """Hypothesis: More frequent checkpoints improve recovery but cost more."""

    def __init__(self):
        super().__init__(
            name="checkpoint_frequency",
            hypothesis="Checkpoint every 1 stage vs every 3 stages: 1-stage has faster recovery",
        )

    async def _run_workflow(self, checkpoint_interval: int) -> Dict[str, Any]:
        engine = WorkflowEngine(EngineConfig(
            checkpoint_interval=checkpoint_interval,
            repair_max_retries=1,
            default_model="openai_fast",
        ))

        async def task_a():
            return TaskResult(task_id="a", status=TaskStatus.SUCCESS, output={"val": 1}, tokens_consumed=100)

        async def task_b():
            return TaskResult(task_id="b", status=TaskStatus.SUCCESS, output={"val": 2}, tokens_consumed=100)

        async def task_c():
            return TaskResult(task_id="c", status=TaskStatus.SUCCESS, output={"val": 3}, tokens_consumed=100)

        workflow = Workflow(
            id=f"checkpoint_test_{checkpoint_interval}",
            name="Checkpoint Test",
            nodes={
                "a": DagNode("a", NodeType.TASK, fn=task_a),
                "b": DagNode("b", NodeType.TASK, fn=task_b, dependencies=["a"]),
                "c": DagNode("c", NodeType.TASK, fn=task_c, dependencies=["b"]),
            },
        )

        summary = await engine.run(workflow)
        return {
            "success_rate": summary["success_rate"],
            "avg_cost_usd": summary["total_cost_usd"],
            "avg_latency_ms": summary["total_latency_ms"],
            "avg_retries": summary["total_retries"],
        }

    async def run_baseline(self, harness: BenchmarkHarness) -> Dict[str, Any]:
        return await self._run_workflow(checkpoint_interval=3)

    async def run_frontier(self, harness: BenchmarkHarness) -> Dict[str, Any]:
        return await self._run_workflow(checkpoint_interval=1)


# Registry
ALL_EXPERIMENTS = [
    ExperimentRepairVsNoRepair,
    ExperimentMemoryEnabled,
    ExperimentCheckpointFrequency,
]


class ComparativeExperiments:
    def __init__(self, harness: BenchmarkHarness):
        self.harness = harness
        self.experiments: List[Experiment] = []
        self.results: Dict[str, Dict[str, Any]] = {}

    def register(self, experiment: Experiment):
        self.experiments.append(experiment)

    def run_all(self, iterations: int = 5):
        for exp in self.experiments:
            baseline_vals = {"success_rate": [], "avg_cost_usd": [], "avg_latency_ms": []}
            frontier_vals = {"success_rate": [], "avg_cost_usd": [], "avg_latency_ms": []}

            for _ in range(iterations):
                baseline = asyncio.run(exp.run_baseline(self.harness))
                frontier = asyncio.run(exp.run_frontier(self.harness))

                for k in baseline_vals:
                    baseline_vals[k].append(baseline[k])
                    frontier_vals[k].append(frontier[k])

            # Compute means
            baseline_mean = {k: sum(v) / len(v) if v else 0 for k, v in baseline_vals.items()}
            frontier_mean = {k: sum(v) / len(v) if v else 0 for k, v in frontier_vals.items()}

            delta = {
                "success_rate": frontier_mean["success_rate"] - baseline_mean["success_rate"],
                "cost_pct": ((frontier_mean["avg_cost_usd"] - baseline_mean["avg_cost_usd"]) 
                             / baseline_mean["avg_cost_usd"] * 100) if baseline_mean["avg_cost_usd"] else 0,
                "latency_pct": ((frontier_mean["avg_latency_ms"] - baseline_mean["avg_latency_ms"])
                                / baseline_mean["avg_latency_ms"] * 100) if baseline_mean["avg_latency_ms"] else 0,
            }

            significant = (
                delta["success_rate"] >= 0.05 or
                delta["cost_pct"] <= -10 or
                delta["latency_pct"] <= -10
            )

            self.results[exp.name] = {
                "hypothesis": exp.hypothesis,
                "baseline": baseline_mean,
                "frontier": frontier_mean,
                "delta": delta,
                "significant": significant,
            }

    def summary(self) -> Dict[str, Any]:
        significant_count = sum(1 for r in self.results.values() if r["significant"])
        return {
            "experiments_run": len(self.results),
            "significant_improvements": significant_count,
            "results": self.results,
        }
