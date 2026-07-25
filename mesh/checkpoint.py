#!/usr/bin/env python3
"""
Checkpoint persistence — SQLite-backed state snapshots.

Zero external dependencies. Uses aiosqlite for async access.
"""
import json
import aiosqlite
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import asdict

from mesh.types import TaskResult, TaskStatus

CHECKPOINT_DB = Path(__file__).parent.parent / "data" / "checkpoints.db"


class CheckpointStore:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or CHECKPOINT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def _init(self):
        if self._initialized:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    output TEXT,
                    error TEXT,
                    latency_ms REAL,
                    tokens_consumed INTEGER,
                    cost_usd REAL,
                    retries INTEGER,
                    repair_loops INTEGER,
                    checkpoint_count INTEGER,
                    timestamp TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_workflow_task 
                ON checkpoints(workflow_id, task_id)
            """)
            await db.commit()
        self._initialized = True

    async def save(self, workflow_id: str, result: TaskResult) -> int:
        await self._init()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO checkpoints 
                (workflow_id, task_id, status, output, error, latency_ms,
                 tokens_consumed, cost_usd, retries, repair_loops, 
                 checkpoint_count, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                workflow_id,
                result.task_id,
                result.status.name,
                json.dumps(result.output),
                result.error,
                result.latency_ms,
                result.tokens_consumed,
                result.cost_usd,
                result.retries,
                result.repair_loops,
                result.checkpoint_count,
                result.timestamp.isoformat() if result.timestamp else None,
            ))
            await db.commit()
            return cursor.lastrowid

    async def load_latest(self, workflow_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        await self._init()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM checkpoints WHERE workflow_id = ? AND task_id = ? ORDER BY id DESC LIMIT 1",
                (workflow_id, task_id)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return None

    async def load_all(self, workflow_id: str) -> List[Dict[str, Any]]:
        await self._init()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM checkpoints WHERE workflow_id = ? ORDER BY id",
                (workflow_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def count(self, workflow_id: str) -> int:
        await self._init()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM checkpoints WHERE workflow_id = ?",
                (workflow_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
