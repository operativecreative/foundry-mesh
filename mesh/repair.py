#!/usr/bin/env python3
"""
Repair loop — retries failed tasks with escalating strategies.

Strategies:
1. Simple retry (same inputs)
2. Context augmentation (add memory context)
3. Model escalation (switch to stronger model)
4. Decomposition (break task into smaller subtasks)
"""
import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass

from mesh.types import TaskResult, TaskStatus


@dataclass
class RepairConfig:
    max_retries: int = 3
    max_repair_loops: int = 2
    backoff_base_ms: float = 1000.0
    backoff_multiplier: float = 2.0
    enable_context_augmentation: bool = True
    enable_model_escalation: bool = True
    enable_decomposition: bool = False


class RepairLoop:
    def __init__(self, config: Optional[RepairConfig] = None):
        self.config = config or RepairConfig()
        self.repair_stats: Dict[str, Any] = {
            "total_repairs": 0,
            "successful_repairs": 0,
            "failed_repairs": 0,
            "strategy_usage": {
                "retry": 0,
                "context": 0,
                "escalation": 0,
                "decomposition": 0,
            }
        }

    async def execute_with_repair(
        self,
        task_id: str,
        fn: Callable[[], Awaitable[TaskResult]],
        context: Optional[Dict[str, Any]] = None,
    ) -> TaskResult:
        """Execute a task with repair on failure."""
        context = context or {}
        repair_loops = 0

        for repair_loop in range(self.config.max_repair_loops + 1):
            for retry in range(self.config.max_retries + 1):
                result = await fn()

                if result.status == TaskStatus.SUCCESS:
                    result.repair_loops = repair_loops
                    result.retries = retry
                    if repair_loops > 0:
                        self.repair_stats["successful_repairs"] += 1
                    return result

                if retry < self.config.max_retries:
                    delay = self.config.backoff_base_ms * (self.config.backoff_multiplier ** retry) / 1000
                    await asyncio.sleep(delay)
                    self.repair_stats["total_repairs"] += 1
                    self.repair_stats["strategy_usage"]["retry"] += 1

            # All retries failed — attempt repair strategy
            if repair_loop < self.config.max_repair_loops:
                repair_loops += 1
                strategy = self._select_strategy(repair_loop, context)
                context = await self._apply_strategy(strategy, context)
                self.repair_stats["strategy_usage"][strategy] += 1
            else:
                break

        # Final failure
        result.status = TaskStatus.FAILED
        result.repair_loops = repair_loops
        result.retries = self.config.max_retries
        self.repair_stats["failed_repairs"] += 1
        return result

    def _select_strategy(self, repair_loop: int, context: Dict[str, Any]) -> str:
        """Select repair strategy based on loop count and context."""
        if repair_loop == 1 and self.config.enable_context_augmentation:
            return "context"
        elif repair_loop == 2 and self.config.enable_model_escalation:
            return "escalation"
        elif self.config.enable_decomposition:
            return "decomposition"
        return "retry"

    async def _apply_strategy(self, strategy: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply repair strategy to context."""
        new_context = dict(context)

        if strategy == "context":
            new_context["augmented"] = True
            new_context["hint"] = "Consider edge cases and error handling."
        elif strategy == "escalation":
            new_context["model"] = "stronger"
            new_context["temperature"] = 0.1
        elif strategy == "decomposition":
            new_context["decomposed"] = True
            new_context["subtasks"] = context.get("subtasks", []) + ["validate", "retry"]

        return new_context

    def get_stats(self) -> Dict[str, Any]:
        return dict(self.repair_stats)
