#!/usr/bin/env python3
"""
Knowledge Graph — entity and relationship storage.

SQLite-backed triple store. Production deployments may migrate
to a dedicated graph database (Neo4j, etc.) for scale.
"""
import json
import aiosqlite
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

KG_DB = Path(__file__).parent.parent / "data" / "knowledge.db"


class KnowledgeGraph:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or KG_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def _init(self):
        if self._initialized:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS triples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    workflow_id TEXT,
                    confidence REAL DEFAULT 1.0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_subject ON triples(subject)
            """)
            await db.commit()
        self._initialized = True

    async def add(self, subject: str, predicate: str, object: str, 
                  workflow_id: Optional[str] = None, confidence: float = 1.0):
        await self._init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO triples (subject, predicate, object, workflow_id, confidence) VALUES (?, ?, ?, ?, ?)",
                (subject, predicate, object, workflow_id, confidence)
            )
            await db.commit()

    async def query(self, subject: Optional[str] = None, 
                    predicate: Optional[str] = None,
                    workflow_id: Optional[str] = None) -> List[Tuple[str, str, str, float]]:
        await self._init()
        async with aiosqlite.connect(self.db_path) as db:
            conditions = []
            params = []
            if subject:
                conditions.append("subject = ?")
                params.append(subject)
            if predicate:
                conditions.append("predicate = ?")
                params.append(predicate)
            if workflow_id:
                conditions.append("workflow_id = ?")
                params.append(workflow_id)

            where = " WHERE " + " AND ".join(conditions) if conditions else ""
            sql = f"SELECT subject, predicate, object, confidence FROM triples{where} ORDER BY created_at DESC"

            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
                return [(s, p, o, c) for s, p, o, c in rows]
