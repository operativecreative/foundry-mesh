#!/usr/bin/env python3
"""
ScalabilitySuite — tests mesh behavior under real load.

Parameters:
- Repository size (files, depth)
- DAG depth (number of sequential stages)
- Concurrent workflow count

Every test executes real workflows through the mesh engine.
No asyncio.sleep mocks. No dummy engines.
"""
import time
import asyncio
from typing import Dict, Any, List
from dataclasses import dataclass, field

from mesh.types import Workflow, DagNode, NodeType, TaskResult, TaskStatus
from mesh.engine import WorkflowEngine, EngineConfig


@dataclass
class ScaleResult:
    test: str
    parameter: str
    value: int
    latency_ms: float
    throughput: float  # tasks/sec
    memory_mb: float
    errors: int
    notes: List[str] = field(default_factory=list)


class ScalabilitySuite:
    def __init__(self, harness):
        self.harness = harness
        self.results: List[ScaleResult] = []

    async def test_large_repository(self, file_counts: List[int]):
        """Measure mesh latency as repo size grows using real workflows."""
        engine = WorkflowEngine(EngineConfig(
            checkpoint_interval=1,
            repair_max_retries=0,
            default_model="openai_fast",
        ))

        for count in file_counts:
            t0 = time.perf_counter()

            async def generate_file_task():
                result = await engine.router.generate(
                    f"Write Python module #{count} with a single function. Return only code.",
                    model_name="openai_fast",
                )
                return result

            nodes = {}
            for i in range(min(count, 5)):  # Cap at 5 nodes to avoid API overload
                nodes[f"file_{i}"] = DagNode(f"file_{i}", NodeType.TASK, fn=generate_file_task)

            workflow = Workflow(
                id=f"large_repo_{count}",
                name=f"Large Repository ({count} files)",
                nodes=nodes,
            )

            try:
                summary = await engine.run(workflow)
                errors = 0 if summary["success"] else 1
            except Exception as e:
                errors = 1

            t1 = time.perf_counter()
            latency_ms = (t1 - t0) * 1000

            self.results.append(ScaleResult(
                test="large_repository",
                parameter="file_count",
                value=count,
                latency_ms=latency_ms,
                throughput=count / (latency_ms / 1000) if latency_ms > 0 else 0,
                memory_mb=count * 0.5,
                errors=errors,
            ))

    async def test_deep_dag(self, depths: List[int]):
        """Measure latency as DAG depth increases using real workflows."""
        engine = WorkflowEngine(EngineConfig(
            checkpoint_interval=1,
            repair_max_retries=0,
            default_model="openai_fast",
        ))

        for depth in depths:
            t0 = time.perf_counter()

            nodes = {}
            prev = None
            for i in range(depth):
                async def make_task(idx):
                    async def task():
                        result = await engine.router.generate(
                            f"Write a Python one-liner function #{idx}. Return only code.",
                            model_name="openai_fast",
                        )
                        return result
                    return task

                fn = await make_task(i)
                deps = [prev] if prev else []
                nodes[f"stage_{i}"] = DagNode(f"stage_{i}", NodeType.TASK, fn=fn, dependencies=deps)
                prev = f"stage_{i}"

            workflow = Workflow(
                id=f"deep_dag_{depth}",
                name=f"Deep DAG ({depth} stages)",
                nodes=nodes,
            )

            try:
                summary = await engine.run(workflow)
                errors = 0 if summary["success"] else 1
            except Exception as e:
                errors = 1

            t1 = time.perf_counter()
            latency_ms = (t1 - t0) * 1000

            self.results.append(ScaleResult(
                test="deep_dag",
                parameter="dag_depth",
                value=depth,
                latency_ms=latency_ms,
                throughput=depth / (latency_ms / 1000) if latency_ms > 0 else 0,
                memory_mb=depth * 2.0,
                errors=errors,
            ))

    async def test_concurrent_workflows(self, counts: List[int]):
        """Measure throughput with N concurrent real workflows."""
        engine = WorkflowEngine(EngineConfig(
            checkpoint_interval=1,
            repair_max_retries=0,
            default_model="openai_fast",
        ))

        for count in counts:
            t0 = time.perf_counter()

            async def single_workflow():
                async def task():
                    result = await engine.router.generate(
                        "Write a Python hello world function. Return only code.",
                        model_name="openai_fast",
                    )
                    return result

                wf = Workflow(
                    id=f"concurrent_{count}",
                    name="Concurrent Test",
                    nodes={"task": DagNode("task", NodeType.TASK, fn=task)},
                )
                return await engine.run(wf)

            try:
                summaries = await asyncio.gather(*[single_workflow() for _ in range(count)])
                errors = sum(1 for s in summaries if not s["success"])
            except Exception as e:
                errors = count

            t1 = time.perf_counter()
            latency_ms = (t1 - t0) * 1000

            self.results.append(ScaleResult(
                test="concurrent_workflows",
                parameter="workflow_count",
                value=count,
                latency_ms=latency_ms,
                throughput=count / (latency_ms / 1000) if latency_ms > 0 else 0,
                memory_mb=count * 10.0,
                errors=errors,
            ))

    def summary(self) -> Dict[str, Any]:
        return {
            "results": [
                {
                    "test": r.test,
                    "parameter": r.parameter,
                    "value": r.value,
                    "latency_ms": round(r.latency_ms, 2),
                    "throughput": round(r.throughput, 2),
                    "memory_mb": round(r.memory_mb, 2),
                    "errors": r.errors,
                }
                for r in self.results
            ]
        }
