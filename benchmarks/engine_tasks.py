#!/usr/bin/env python3
"""
Benchmark tasks backed by the actual Foundry Mesh runtime.

Every task constructs real workflows and executes them through
the WorkflowEngine with REAL model calls. No synthetic responses.
No hardcoded outputs. If the model API is unavailable, the task fails.
"""
import asyncio
from typing import Dict, Any, Callable

from mesh.types import Workflow, DagNode, NodeType, TaskResult, TaskStatus
from mesh.engine import WorkflowEngine, EngineConfig


class EngineTaskFactory:
    """Factory for creating mesh-backed benchmark functions."""

    @staticmethod
    def _make_engine() -> WorkflowEngine:
        """Create a real engine. Fails if API keys are missing."""
        return WorkflowEngine(EngineConfig(
            checkpoint_interval=2,
            repair_max_retries=1,
            default_model="openai_fast",
        ))

    @staticmethod
    def simple_web_server_task() -> Callable[[], Dict[str, Any]]:
        """A simple 2-node workflow using real model generation."""
        async def _run():
            engine = EngineTaskFactory._make_engine()

            async def scaffold():
                result = await engine.router.generate(
                    "Create a minimal Flask web server with /health and /api endpoints. "
                    "Return only the Python code, no explanations.",
                    model_name="openai_fast",
                )
                return result

            async def test_code():
                result = await engine.router.generate(
                    "Write pytest test cases for a Flask server with /health and /api endpoints. "
                    "Return only the Python test code, no explanations.",
                    model_name="openai_fast",
                )
                return result

            workflow = Workflow(
                id="simple_web_server",
                name="Simple Web Server",
                nodes={
                    "scaffold": DagNode("scaffold", NodeType.TASK, fn=scaffold),
                    "test_code": DagNode("test_code", NodeType.TASK, fn=test_code, dependencies=["scaffold"]),
                },
            )

            summary = await engine.run(workflow)
            return {
                "success": summary["success"],
                "cost_usd": summary["total_cost_usd"],
                "retries": summary["total_retries"],
                "repair_loops": summary["total_repair_loops"],
                "tokens_consumed": summary["total_tokens"],
                "checkpoint_count": summary["checkpoint_count"],
                "metadata": {"variant": "runtime", "workflow": summary["name"]},
            }

        def wrapper():
            return asyncio.run(_run())
        return wrapper

    @staticmethod
    def data_pipeline_task() -> Callable[[], Dict[str, Any]]:
        """A 3-node ETL workflow using real model generation."""
        async def _run():
            engine = EngineTaskFactory._make_engine()

            async def extract():
                result = await engine.router.generate(
                    "Write Python code to read a CSV file from S3 using boto3. "
                    "Return only the code, no explanations.",
                    model_name="openai_fast",
                )
                return result

            async def transform():
                result = await engine.router.generate(
                    "Write Python code to normalize and deduplicate a pandas DataFrame. "
                    "Return only the code, no explanations.",
                    model_name="openai_fast",
                )
                return result

            async def load():
                result = await engine.router.generate(
                    "Write Python code to write a pandas DataFrame to Parquet format. "
                    "Return only the code, no explanations.",
                    model_name="openai_fast",
                )
                return result

            workflow = Workflow(
                id="data_pipeline",
                name="Data Pipeline",
                nodes={
                    "extract": DagNode("extract", NodeType.TASK, fn=extract),
                    "transform": DagNode("transform", NodeType.TASK, fn=transform, dependencies=["extract"]),
                    "load": DagNode("load", NodeType.TASK, fn=load, dependencies=["transform"]),
                },
            )

            summary = await engine.run(workflow)
            return {
                "success": summary["success"],
                "cost_usd": summary["total_cost_usd"],
                "retries": summary["total_retries"],
                "repair_loops": summary["total_repair_loops"],
                "tokens_consumed": summary["total_tokens"],
                "checkpoint_count": summary["checkpoint_count"],
                "metadata": {"variant": "runtime", "workflow": summary["name"]},
            }

        def wrapper():
            return asyncio.run(_run())
        return wrapper

    @staticmethod
    def microservice_mesh_task() -> Callable[[], Dict[str, Any]]:
        """A complex workflow with parallel branches using real model generation."""
        async def _run():
            engine = EngineTaskFactory._make_engine()

            async def proto():
                result = await engine.router.generate(
                    "Write a protobuf schema for a User service with CreateUser and GetUser RPCs. "
                    "Return only the .proto file content, no explanations.",
                    model_name="openai_strong",
                )
                return result

            async def svc_a():
                result = await engine.router.generate(
                    "Write a Python gRPC server implementing a User service with CreateUser and GetUser. "
                    "Return only the code, no explanations.",
                    model_name="openai_strong",
                )
                return result

            async def svc_b():
                result = await engine.router.generate(
                    "Write a Python gRPC server implementing an Order service with CreateOrder and GetOrder. "
                    "Return only the code, no explanations.",
                    model_name="openai_strong",
                )
                return result

            async def gateway():
                result = await engine.router.generate(
                    "Write a Python API gateway that routes to User and Order gRPC services. "
                    "Return only the code, no explanations.",
                    model_name="openai_strong",
                )
                return result

            workflow = Workflow(
                id="microservice_mesh",
                name="Microservice Mesh",
                nodes={
                    "proto": DagNode("proto", NodeType.TASK, fn=proto),
                    "svc_a": DagNode("svc_a", NodeType.TASK, fn=svc_a, dependencies=["proto"]),
                    "svc_b": DagNode("svc_b", NodeType.TASK, fn=svc_b, dependencies=["proto"]),
                    "gateway": DagNode("gateway", NodeType.TASK, fn=gateway, dependencies=["svc_a", "svc_b"]),
                },
            )

            summary = await engine.run(workflow)
            return {
                "success": summary["success"],
                "cost_usd": summary["total_cost_usd"],
                "retries": summary["total_retries"],
                "repair_loops": summary["total_repair_loops"],
                "tokens_consumed": summary["total_tokens"],
                "checkpoint_count": summary["checkpoint_count"],
                "metadata": {"variant": "runtime", "workflow": summary["name"]},
            }

        def wrapper():
            return asyncio.run(_run())
        return wrapper

    @staticmethod
    def react_component_lib_task() -> Callable[[], Dict[str, Any]]:
        """Component library with real model generation."""
        async def _run():
            engine = EngineTaskFactory._make_engine()

            async def components():
                result = await engine.router.generate(
                    "Write React TypeScript components for Button and Card with props interfaces. "
                    "Return only the code, no explanations.",
                    model_name="openai_fast",
                )
                return result

            async def storybook():
                result = await engine.router.generate(
                    "Write Storybook stories for Button and Card React components. "
                    "Return only the code, no explanations.",
                    model_name="openai_fast",
                )
                return result

            workflow = Workflow(
                id="react_component_lib",
                name="React Component Library",
                nodes={
                    "components": DagNode("components", NodeType.TASK, fn=components),
                    "storybook": DagNode("storybook", NodeType.TASK, fn=storybook, dependencies=["components"]),
                },
            )

            summary = await engine.run(workflow)
            return {
                "success": summary["success"],
                "cost_usd": summary["total_cost_usd"],
                "retries": summary["total_retries"],
                "repair_loops": summary["total_repair_loops"],
                "tokens_consumed": summary["total_tokens"],
                "checkpoint_count": summary["checkpoint_count"],
                "metadata": {"variant": "runtime", "workflow": summary["name"]},
            }

        def wrapper():
            return asyncio.run(_run())
        return wrapper

    @staticmethod
    def terraform_module_task() -> Callable[[], Dict[str, Any]]:
        """Terraform module with real model generation."""
        async def _run():
            engine = EngineTaskFactory._make_engine()

            async def vpc():
                result = await engine.router.generate(
                    "Write Terraform code for an AWS VPC with public and private subnets across 2 AZs. "
                    "Return only the code, no explanations.",
                    model_name="openai_strong",
                )
                return result

            async def ecs():
                result = await engine.router.generate(
                    "Write Terraform code for an AWS ECS Fargate cluster with a service definition. "
                    "Return only the code, no explanations.",
                    model_name="openai_strong",
                )
                return result

            async def compose():
                result = await engine.router.generate(
                    "Write a Terraform root module that composes VPC and ECS modules with proper outputs. "
                    "Return only the code, no explanations.",
                    model_name="openai_strong",
                )
                return result

            workflow = Workflow(
                id="terraform_module",
                name="Terraform Module",
                nodes={
                    "vpc": DagNode("vpc", NodeType.TASK, fn=vpc),
                    "ecs": DagNode("ecs", NodeType.TASK, fn=ecs),
                    "compose": DagNode("compose", NodeType.TASK, fn=compose, dependencies=["vpc", "ecs"]),
                },
            )

            summary = await engine.run(workflow)
            return {
                "success": summary["success"],
                "cost_usd": summary["total_cost_usd"],
                "retries": summary["total_retries"],
                "repair_loops": summary["total_repair_loops"],
                "tokens_consumed": summary["total_tokens"],
                "checkpoint_count": summary["checkpoint_count"],
                "metadata": {"variant": "runtime", "workflow": summary["name"]},
            }

        def wrapper():
            return asyncio.run(_run())
        return wrapper
