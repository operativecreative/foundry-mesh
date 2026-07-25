#!/usr/bin/env python3
"""
Benchmark tasks — each task sets up a synthetic repo and defines
what "success" looks like for the mesh.
"""
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class Task:
    name: str
    description: str
    complexity: str  # "simple", "medium", "complex"

    def setup_repo(self, tmpdir: Path) -> Path:
        """Create a synthetic git repo in tmpdir. Return repo root."""
        repo = tmpdir / self.name.replace(" ", "_")
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "README.md").write_text(f"# {self.name}\\n\\n{self.description}\\n")
        (repo / ".gitignore").write_text("__pycache__/\\n*.pyc\\nnode_modules/\\n")

        # Initialize git
        import subprocess
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.email", "bench@foundry.mesh"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Benchmark Bot"], cwd=repo, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)

        return repo


# Registry of all benchmark tasks
ALL_TASKS = [
    Task(
        name="simple_web_server",
        description="A basic Flask/FastAPI server with two endpoints.",
        complexity="simple",
    ),
    Task(
        name="data_pipeline",
        description="ETL pipeline: CSV ingest → transform → Parquet export.",
        complexity="medium",
    ),
    Task(
        name="microservice_mesh",
        description="Three interdependent services with shared protobuf schemas.",
        complexity="complex",
    ),
    Task(
        name="react_component_lib",
        description="A component library with Storybook, tests, and build pipeline.",
        complexity="medium",
    ),
    Task(
        name="terraform_module",
        description="Reusable Terraform module for AWS VPC + ECS.",
        complexity="complex",
    ),
]
