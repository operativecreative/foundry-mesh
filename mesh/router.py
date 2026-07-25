#!/usr/bin/env python3
"""
Model Router — routes requests to LLM backends.

Backends:
- "kimi": Kimi API (requires KIMI_API_KEY)
- "openai": OpenAI API (requires OPENAI_API_KEY)

Selection strategy:
- Cost-aware: prefer cheaper model for simple tasks
- Capability-aware: escalate to stronger model on failure
- Latency-aware: prefer faster model for time-sensitive tasks

No mocks. No fallbacks. Missing API keys = explicit failure.
"""
import os
import time
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from mesh.types import TaskResult, TaskStatus


@dataclass
class ModelConfig:
    name: str
    backend: str
    model_id: str
    cost_per_1k_tokens: float
    avg_latency_ms: float
    max_tokens: int = 4096
    temperature: float = 0.7


DEFAULT_MODELS = {
    "kimi_fast": ModelConfig("kimi_fast", "kimi", "kimi-k3", 0.003, 2000),
    "kimi_strong": ModelConfig("kimi_strong", "kimi", "kimi-k3-long", 0.015, 5000),
    "openai_fast": ModelConfig("openai_fast", "openai", "gpt-4o-mini", 0.0015, 1500),
    "openai_strong": ModelConfig("openai_strong", "openai", "gpt-4o", 0.03, 4000),
}


class ModelRouter:
    def __init__(self, default_model: str = "openai_fast"):
        self.models = dict(DEFAULT_MODELS)
        self.default_model = default_model
        self.request_log: List[Dict[str, Any]] = []

    def register(self, config: ModelConfig):
        self.models[config.name] = config

    async def generate(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> TaskResult:
        """Generate completion via selected backend. Real HTTP only. No mocks."""
        model_name = model_name or self.default_model
        config = self.models.get(model_name)
        if config is None:
            return TaskResult(
                task_id="router",
                status=TaskStatus.FAILED,
                error=f"Model '{model_name}' not configured. Available: {list(self.models.keys())}",
            )

        context = context or {}
        t0 = time.perf_counter()

        if config.backend == "kimi":
            result = await self._kimi_generate(prompt, config, context)
        elif config.backend == "openai":
            result = await self._openai_generate(prompt, config, context)
        else:
            result = TaskResult(
                task_id="router",
                status=TaskStatus.FAILED,
                error=f"Unknown backend: {config.backend}",
            )

        t1 = time.perf_counter()
        result.latency_ms = (t1 - t0) * 1000
        result.cost_usd = self._estimate_cost(prompt, result, config)

        self.request_log.append({
            "model": model_name,
            "backend": config.backend,
            "latency_ms": result.latency_ms,
            "cost_usd": result.cost_usd,
            "tokens": result.tokens_consumed,
            "status": result.status.name,
        })

        return result

    async def _kimi_generate(self, prompt: str, config: ModelConfig, context: Dict[str, Any]) -> TaskResult:
        """Kimi API integration — real HTTP call."""
        api_key = os.environ.get("KIMI_API_KEY")
        if not api_key:
            return TaskResult(
                task_id="kimi",
                status=TaskStatus.FAILED,
                error="KIMI_API_KEY not set in environment",
            )

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": config.model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                }
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }

                async with session.post(
                    "https://api.moonshot.cn/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        return TaskResult(
                            task_id="kimi",
                            status=TaskStatus.FAILED,
                            error=f"Kimi API returned {resp.status}: {body[:500]}",
                        )

                    data = await resp.json()
                    choice = data["choices"][0]
                    message = choice["message"]
                    usage = data.get("usage", {})

                    return TaskResult(
                        task_id="kimi",
                        status=TaskStatus.SUCCESS,
                        output={
                            "response": message.get("content", ""),
                            "model": data.get("model", config.model_id),
                            "finish_reason": choice.get("finish_reason"),
                        },
                        tokens_consumed=usage.get("total_tokens", 0),
                    )
        except Exception as e:
            return TaskResult(
                task_id="kimi",
                status=TaskStatus.FAILED,
                error=f"Kimi API error: {str(e)}",
            )

    async def _openai_generate(self, prompt: str, config: ModelConfig, context: Dict[str, Any]) -> TaskResult:
        """OpenAI API integration — real HTTP call."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return TaskResult(
                task_id="openai",
                status=TaskStatus.FAILED,
                error="OPENAI_API_KEY not set in environment",
            )

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": config.model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                }
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }

                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        return TaskResult(
                            task_id="openai",
                            status=TaskStatus.FAILED,
                            error=f"OpenAI API returned {resp.status}: {body[:500]}",
                        )

                    data = await resp.json()
                    choice = data["choices"][0]
                    message = choice["message"]
                    usage = data.get("usage", {})

                    return TaskResult(
                        task_id="openai",
                        status=TaskStatus.SUCCESS,
                        output={
                            "response": message.get("content", ""),
                            "model": data.get("model", config.model_id),
                            "finish_reason": choice.get("finish_reason"),
                        },
                        tokens_consumed=usage.get("total_tokens", 0),
                    )
        except Exception as e:
            return TaskResult(
                task_id="openai",
                status=TaskStatus.FAILED,
                error=f"OpenAI API error: {str(e)}",
            )

    def _estimate_cost(self, prompt: str, result: TaskResult, config: ModelConfig) -> float:
        """Estimate cost based on token consumption."""
        tokens = result.tokens_consumed or 0
        return (tokens / 1000) * config.cost_per_1k_tokens

    def get_request_log(self) -> List[Dict[str, Any]]:
        return list(self.request_log)

    def select_model(self, task_complexity: str, latency_budget_ms: Optional[float] = None) -> str:
        """Auto-select model based on task requirements."""
        if task_complexity == "simple" and (latency_budget_ms is None or latency_budget_ms < 1000):
            return "openai_fast"
        elif task_complexity == "complex":
            return "openai_strong"
        return self.default_model


# asyncio needed for real HTTP calls
import asyncio
