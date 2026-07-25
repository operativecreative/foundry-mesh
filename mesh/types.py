#!/usr/bin/env python3
"""Core type definitions for Foundry Mesh."""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Awaitable
from enum import Enum, auto
from datetime import datetime, timezone


class TaskStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()
    RETRYING = auto()
    CHECKPOINTED = auto()


class NodeType(Enum):
    TASK = auto()
    GATEWAY = auto()      # AND join
    EVENT = auto()        # OR join / message trigger
    CHECKPOINT = auto()


@dataclass
class TaskResult:
    task_id: str
    status: TaskStatus
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    latency_ms: float = 0.0
    tokens_consumed: int = 0
    cost_usd: float = 0.0
    retries: int = 0
    repair_loops: int = 0
    checkpoint_count: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DagNode:
    id: str
    node_type: NodeType
    fn: Optional[Callable[[], Awaitable[TaskResult]]] = None
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Workflow:
    id: str
    name: str
    nodes: Dict[str, DagNode] = field(default_factory=dict)
    edges: List[tuple] = field(default_factory=list)  # (from, to)
    metadata: Dict[str, Any] = field(default_factory=dict)
