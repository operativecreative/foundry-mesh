#!/usr/bin/env python3
"""
Workflow Engine — high-level orchestrator.

Composes scheduler, router, memory, checkpoint, and repair into
a unified execution pipeline.
"""
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from mesh.types import Workflow, TaskResult, TaskStatus
from mesh.scheduler import DagScheduler
from mesh.router import ModelRouter
from mesh.memory import SharedMemory
from mesh.checkpoint import CheckpointStore
from mesh.repair import RepairLoop, RepairConfig


@dataclass
class EngineConfig:
    checkpoint_interval: int = 2
    repair_max_retries: int = 2
    repair_max_loops: int = 1
    default_model: str = "openai_fast"
    enable_memory: bool = True
    enable_knowledge_graph: bool = False


class WorkflowEngine:
    def __init__(self, config: Optional[EngineConfig] = None):
        self.config = config or EngineConfig()
        self.router = ModelRouter(default_model=self.config.default_model)
        self.memory = SharedMemory() if self.config.enable_memory else None
        self.checkpoint_store = CheckpointStore()
        self.repair_loop = RepairLoop(RepairConfig(
            max_retries=self.config.repair_max_retries,
            max_repair_loops=self.config.repair_max_loops,
        ))
        self.scheduler = DagScheduler(
            checkpoint_store=self.checkpoint_store,
            repair_loop=self.repair_loop,
            checkpoint_interval=self.config.checkpoint_interval,
        )
        self.workflow_results: Dict[str, Dict[str, TaskResult]] = {}

    async def run(self, workflow: Workflow) -> Dict[str, Any]:
        """Execute a workflow end-to-end."""
        t0 = time.perf_counter()

        # Store workflow metadata in memory
        if self.memory:
            await self.memory.set(f"workflow:{workflow.id}:meta", {
                "name": workflow.name,
                "node_count": len(workflow.nodes),
            })

        # Execute DAG
        results = await self.scheduler.execute(workflow)
        self.workflow_results[workflow.id] = results

        t1 = time.perf_counter()
        total_latency_ms = (t1 - t0) * 1000

        # Aggregate metrics
        success_count = sum(1 for r in results.values() if r.status == TaskStatus.SUCCESS)
        total_cost = sum(r.cost_usd for r in results.values())
        total_tokens = sum(r.tokens_consumed for r in results.values())
        total_retries = sum(r.retries for r in results.values())
        total_repairs = sum(r.repair_loops for r in results.values())
        checkpoint_count = await self.checkpoint_store.count(workflow.id)

        summary = {
            "workflow_id": workflow.id,
            "name": workflow.name,
            "success": success_count == len(results),
            "success_rate": success_count / len(results) if results else 0,
            "total_latency_ms": total_latency_ms,
            "total_cost_usd": total_cost,
            "total_tokens": total_tokens,
            "total_retries": total_retries,
            "total_repair_loops": total_repairs,
            "checkpoint_count": checkpoint_count,
            "node_count": len(results),
            "results": {k: {
                "status": v.status.name,
                "latency_ms": v.latency_ms,
                "cost_usd": v.cost_usd,
                "tokens": v.tokens_consumed,
                "retries": v.retries,
                "repair_loops": v.repair_loops,
            } for k, v in results.items()},
        }

        # Store summary in memory
        if self.memory:
            await self.memory.set(f"workflow:{workflow.id}:summary", summary)

        return summary

    async def get_workflow_summary(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve stored workflow summary."""
        if self.memory:
            return await self.memory.get(f"workflow:{workflow_id}:summary")
        return None

    def get_execution_log(self) -> List[Dict[str, Any]]:
        return self.scheduler.get_execution_log()

    def get_repair_stats(self) -> Dict[str, Any]:
        return self.repair_loop.get_stats()

    def get_router_log(self) -> List[Dict[str, Any]]:
        return self.router.get_request_log()
