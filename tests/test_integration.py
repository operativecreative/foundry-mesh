#!/usr/bin/env python3
"""
Integration tests — validate full mesh stack end-to-end.

These tests exercise:
- WorkflowEngine with real scheduler, router, memory, checkpoint
- Repair loop under simulated failure
- Policy engine validation
- Knowledge graph operations
"""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest
import asyncio

from mesh.types import Workflow, DagNode, NodeType, TaskResult, TaskStatus
from mesh.engine import WorkflowEngine, EngineConfig
from mesh.checkpoint import CheckpointStore
from mesh.memory import SharedMemory
from mesh.knowledge import KnowledgeGraph
from mesh.policy import PolicyEngine
from mesh.repair import RepairLoop, RepairConfig


class TestWorkflowEngine:
    async def test_simple_workflow(self):
        engine = WorkflowEngine(EngineConfig(
            checkpoint_interval=1,
            repair_max_retries=0,
            default_model="mock_fast",
        ))

        async def task_a():
            return TaskResult(task_id="a", status=TaskStatus.SUCCESS, output={"val": 1})

        async def task_b():
            return TaskResult(task_id="b", status=TaskStatus.SUCCESS, output={"val": 2})

        workflow = Workflow(
            id="test_simple",
            name="Simple Test",
            nodes={
                "a": DagNode("a", NodeType.TASK, fn=task_a),
                "b": DagNode("b", NodeType.TASK, fn=task_b, dependencies=["a"]),
            },
        )

        summary = await engine.run(workflow)
        assert summary["success"] is True
        assert summary["success_rate"] == 1.0
        assert summary["node_count"] == 2
        assert summary["total_retries"] == 0

    async def test_parallel_workflow(self):
        engine = WorkflowEngine(EngineConfig(
            checkpoint_interval=2,
            repair_max_retries=0,
            default_model="mock_fast",
        ))

        async def task_a():
            return TaskResult(task_id="a", status=TaskStatus.SUCCESS, output={"val": 1})

        async def task_b():
            return TaskResult(task_id="b", status=TaskStatus.SUCCESS, output={"val": 2})

        async def task_c():
            return TaskResult(task_id="c", status=TaskStatus.SUCCESS, output={"val": 3})

        workflow = Workflow(
            id="test_parallel",
            name="Parallel Test",
            nodes={
                "a": DagNode("a", NodeType.TASK, fn=task_a),
                "b": DagNode("b", NodeType.TASK, fn=task_b, dependencies=["a"]),
                "c": DagNode("c", NodeType.TASK, fn=task_c, dependencies=["a"]),
            },
        )

        summary = await engine.run(workflow)
        assert summary["success"] is True
        assert summary["node_count"] == 3

    async def test_checkpoint_persistence(self):
        engine = WorkflowEngine(EngineConfig(
            checkpoint_interval=1,
            repair_max_retries=0,
            default_model="mock_fast",
        ))

        async def task_a():
            return TaskResult(task_id="a", status=TaskStatus.SUCCESS, output={"val": 42})

        workflow = Workflow(
            id="test_checkpoint",
            name="Checkpoint Test",
            nodes={
                "a": DagNode("a", NodeType.TASK, fn=task_a),
            },
        )

        summary = await engine.run(workflow)
        assert summary["checkpoint_count"] >= 1

        # Verify checkpoint was saved
        cp = await engine.checkpoint_store.load_latest("test_checkpoint", "a")
        assert cp is not None
        assert cp["status"] == "SUCCESS"

    async def test_memory_storage(self):
        engine = WorkflowEngine(EngineConfig(
            checkpoint_interval=1,
            repair_max_retries=0,
            default_model="mock_fast",
            enable_memory=True,
        ))

        async def task_a():
            return TaskResult(task_id="a", status=TaskStatus.SUCCESS, output={"val": 1})

        workflow = Workflow(
            id="test_memory",
            name="Memory Test",
            nodes={
                "a": DagNode("a", NodeType.TASK, fn=task_a),
            },
        )

        await engine.run(workflow)

        # Verify memory storage
        summary = await engine.get_workflow_summary("test_memory")
        assert summary is not None
        assert summary["workflow_id"] == "test_memory"

    async def test_repair_loop(self):
        call_count = 0

        async def flaky_task():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return TaskResult(task_id="flaky", status=TaskStatus.FAILED, error="Transient error")
            return TaskResult(task_id="flaky", status=TaskStatus.SUCCESS, output={"recovered": True})

        engine = WorkflowEngine(EngineConfig(
            checkpoint_interval=1,
            repair_max_retries=3,
            repair_max_loops=1,
            default_model="mock_fast",
        ))

        workflow = Workflow(
            id="test_repair",
            name="Repair Test",
            nodes={
                "flaky": DagNode("flaky", NodeType.TASK, fn=flaky_task),
            },
        )

        summary = await engine.run(workflow)
        assert summary["success"] is True
        assert summary["total_retries"] > 0
        assert call_count >= 3


class TestKnowledgeGraph:
    async def test_add_and_query(self):
        kg = KnowledgeGraph()
        await kg.add("user", "has_role", "admin", workflow_id="test", confidence=0.95)
        await kg.add("user", "has_email", "admin@example.com", workflow_id="test")

        results = await kg.query(subject="user", workflow_id="test")
        assert len(results) == 2

        roles = [r for r in results if r[1] == "has_role"]
        assert len(roles) == 1
        assert roles[0][2] == "admin"
        assert roles[0][3] == 0.95


class TestPolicyEngine:
    def test_cost_violation(self):
        policy = PolicyEngine()
        summary = {
            "total_cost_usd": 0.75,
            "success_rate": 0.9,
            "total_latency_ms": 1000,
        }
        violations = policy.validate_workflow(summary)

        cost_violations = [v for v in violations if v["rule"] == "cost_cap"]
        assert len(cost_violations) == 1
        assert cost_violations[0]["value"] == 0.75
        assert cost_violations[0]["threshold"] == 0.50

    def test_success_rate_violation(self):
        policy = PolicyEngine()
        summary = {
            "total_cost_usd": 0.10,
            "success_rate": 0.50,
            "total_latency_ms": 1000,
        }
        violations = policy.validate_workflow(summary)

        success_violations = [v for v in violations if v["rule"] == "require_success"]
        assert len(success_violations) == 1
        assert success_violations[0]["value"] == 0.50
        assert success_violations[0]["threshold"] == 0.70
