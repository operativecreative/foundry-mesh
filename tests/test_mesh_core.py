#!/usr/bin/env python3
"""Unit tests for mesh core components."""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest
import asyncio

from mesh.types import DagNode, NodeType, TaskResult, TaskStatus
from mesh.scheduler import DagScheduler
from mesh.router import ModelRouter
from mesh.checkpoint import CheckpointStore
from mesh.memory import SharedMemory
from mesh.repair import RepairLoop, RepairConfig


class TestDagScheduler:
    def test_topological_order_linear(self):
        from mesh.types import Workflow
        scheduler = DagScheduler()

        workflow = Workflow(
            id="linear",
            name="Linear",
            nodes={
                "a": DagNode("a", NodeType.TASK, dependencies=[]),
                "b": DagNode("b", NodeType.TASK, dependencies=["a"]),
                "c": DagNode("c", NodeType.TASK, dependencies=["b"]),
            },
        )

        order = scheduler._topological_order(workflow)
        assert order == ["a", "b", "c"]

    def test_topological_order_diamond(self):
        from mesh.types import Workflow
        scheduler = DagScheduler()

        workflow = Workflow(
            id="diamond",
            name="Diamond",
            nodes={
                "a": DagNode("a", NodeType.TASK, dependencies=[]),
                "b": DagNode("b", NodeType.TASK, dependencies=["a"]),
                "c": DagNode("c", NodeType.TASK, dependencies=["a"]),
                "d": DagNode("d", NodeType.TASK, dependencies=["b", "c"]),
            },
        )

        order = scheduler._topological_order(workflow)
        assert order[0] == "a"
        assert order[-1] == "d"
        assert set(order[1:3]) == {"b", "c"}

    def test_cycle_detection(self):
        from mesh.types import Workflow
        scheduler = DagScheduler()

        workflow = Workflow(
            id="cycle",
            name="Cycle",
            nodes={
                "a": DagNode("a", NodeType.TASK, dependencies=["c"]),
                "b": DagNode("b", NodeType.TASK, dependencies=["a"]),
                "c": DagNode("c", NodeType.TASK, dependencies=["b"]),
            },
        )

        with pytest.raises(ValueError, match="Cycle detected"):
            scheduler._topological_order(workflow)


class TestModelRouter:
    @pytest.mark.asyncio
    async def test_model_configured(self):
        router = ModelRouter(default_model="openai_fast")
        # Verify model is configured (real call requires API key)
        assert "openai_fast" in router.models
        assert router.models["openai_fast"].backend == "openai"

    @pytest.mark.asyncio
    async def test_model_selection(self):
        router = ModelRouter()

        assert router.select_model("simple") == "mock_fast"
        assert router.select_model("complex") == "mock_strong"

    @pytest.mark.asyncio
    async def test_request_log_empty(self):
        router = ModelRouter()
        log = router.get_request_log()
        assert len(log) == 0


class TestCheckpointStore:
    @pytest.mark.asyncio
    async def test_save_and_load(self, monkeypatch):
        import tempfile
        from pathlib import Path
        from mesh import checkpoint

        with tempfile.TemporaryDirectory() as td:
            fake_db = Path(td) / "test_cp.db"
            store = CheckpointStore(db_path=fake_db)

            result = TaskResult(
                task_id="task_1",
                status=TaskStatus.SUCCESS,
                output={"key": "value"},
                latency_ms=100.0,
                cost_usd=0.01,
            )

            cp_id = await store.save("wf_1", result)
            assert cp_id is not None

            loaded = await store.load_latest("wf_1", "task_1")
            assert loaded is not None
            assert loaded["task_id"] == "task_1"
            assert loaded["status"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_count(self, monkeypatch):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            fake_db = Path(td) / "test_cp2.db"
            store = CheckpointStore(db_path=fake_db)

            result = TaskResult(task_id="t", status=TaskStatus.SUCCESS)
            await store.save("wf", result)
            await store.save("wf", result)

            count = await store.count("wf")
            assert count == 2


class TestSharedMemory:
    @pytest.mark.asyncio
    async def test_set_and_get(self, monkeypatch):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            fake_db = Path(td) / "test_mem.db"
            mem = SharedMemory(db_path=fake_db)

            await mem.set("key1", {"data": [1, 2, 3]}, workflow_id="wf1")
            val = await mem.get("key1")

            assert val == {"data": [1, 2, 3]}

    @pytest.mark.asyncio
    async def test_search(self, monkeypatch):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            fake_db = Path(td) / "test_mem2.db"
            mem = SharedMemory(db_path=fake_db)

            await mem.set("workflow_config", {"nodes": 5}, workflow_id="wf1")
            await mem.set("workflow_state", {"status": "running"}, workflow_id="wf1")

            results = await mem.search("workflow", workflow_id="wf1")
            assert len(results) >= 1


class TestRepairLoop:
    @pytest.mark.asyncio
    async def test_successful_execution(self):
        repair = RepairLoop()

        async def success_fn():
            return TaskResult(task_id="ok", status=TaskStatus.SUCCESS, output={"done": True})

        result = await repair.execute_with_repair("ok", success_fn)
        assert result.status == TaskStatus.SUCCESS
        assert result.retries == 0
        assert result.repair_loops == 0

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        call_count = 0

        async def flaky_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return TaskResult(task_id="flaky", status=TaskStatus.FAILED, error="boom")
            return TaskResult(task_id="flaky", status=TaskStatus.SUCCESS, output={"fixed": True})

        repair = RepairLoop(RepairConfig(max_retries=2, max_repair_loops=0))
        result = await repair.execute_with_repair("flaky", flaky_fn)

        assert result.status == TaskStatus.SUCCESS
        assert result.retries == 1
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_final_failure(self):
        async def always_fail():
            return TaskResult(task_id="fail", status=TaskStatus.FAILED, error="permanent")

        repair = RepairLoop(RepairConfig(max_retries=1, max_repair_loops=0))
        result = await repair.execute_with_repair("fail", always_fail)

        assert result.status == TaskStatus.FAILED
        assert result.retries == 1
