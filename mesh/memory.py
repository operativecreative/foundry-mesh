#!/usr/bin/env python3
"""
Shared memory — key-value and vector retrieval.

SQLite backend for zero-dollar operation.
Vector search uses simple cosine similarity over normalized embeddings.
"""
import json
import math
import aiosqlite
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

MEMORY_DB = Path(__file__).parent.parent / "data" / "memory.db"


class SharedMemory:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or MEMORY_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def _init(self):
        if self._initialized:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    workflow_id TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS vectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    workflow_id TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
        self._initialized = True

    async def set(self, key: str, value: Any, workflow_id: Optional[str] = None):
        await self._init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO kv_store (key, value, workflow_id) VALUES (?, ?, ?)",
                (key, json.dumps(value), workflow_id)
            )
            await db.commit()

    async def get(self, key: str) -> Optional[Any]:
        await self._init()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT value FROM kv_store WHERE key = ?", (key,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return None

    async def search(self, query: str, workflow_id: Optional[str] = None, limit: int = 5) -> List[Tuple[str, Any, float]]:
        """Simple keyword search over keys. Returns (key, value, score)."""
        await self._init()
        async with aiosqlite.connect(self.db_path) as db:
            if workflow_id:
                sql = "SELECT key, value FROM kv_store WHERE workflow_id = ? AND key LIKE ? LIMIT ?"
                params = (workflow_id, f"%{query}%", limit)
            else:
                sql = "SELECT key, value FROM kv_store WHERE key LIKE ? LIMIT ?"
                params = (f"%{query}%", limit)

            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
                results = []
                for key, value in rows:
                    # Simple scoring: exact match = 1.0, partial = 0.5
                    score = 1.0 if query.lower() in key.lower() else 0.5
                    results.append((key, json.loads(value), score))
                return results

    async def store_vector(self, key: str, embedding: List[float], workflow_id: Optional[str] = None):
        await self._init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO vectors (key, embedding, workflow_id) VALUES (?, ?, ?)",
                (key, json.dumps(embedding), workflow_id)
            )
            await db.commit()

    async def vector_search(self, query_embedding: List[float], workflow_id: Optional[str] = None, limit: int = 5) -> List[Tuple[str, Any, float]]:
        """Cosine similarity search over stored vectors."""
        await self._init()

        # Normalize query
        q_norm = math.sqrt(sum(x * x for x in query_embedding))
        if q_norm == 0:
            return []
        query_norm = [x / q_norm for x in query_embedding]

        async with aiosqlite.connect(self.db_path) as db:
            if workflow_id:
                sql = "SELECT key, embedding FROM vectors WHERE workflow_id = ?"
                params = (workflow_id,)
            else:
                sql = "SELECT key, embedding FROM vectors"
                params = ()

            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
                scores = []
                for key, emb_json in rows:
                    emb = json.loads(emb_json)
                    e_norm = math.sqrt(sum(x * x for x in emb))
                    if e_norm == 0:
                        continue
                    emb_norm = [x / e_norm for x in emb]

                    # Cosine similarity
                    sim = sum(a * b for a, b in zip(query_norm, emb_norm))
                    scores.append((key, sim))

                scores.sort(key=lambda x: x[1], reverse=True)
                return [(k, None, s) for k, s in scores[:limit]]
