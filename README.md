# Foundry Mesh

[![Validation](https://img.shields.io/badge/validation-6%20levels-blue)](https://github.com/operativecreative/foundry-mesh/actions)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Repository:** https://github.com/operativecreative/foundry-mesh

Async workflow orchestrator with repair loops, shared memory, knowledge graph, checkpoint persistence, and model routing.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      WorkflowEngine                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────┐   │
│  │Scheduler│  │ Router  │  │ Memory  │  │  Checkpoint │   │
│  │  (DAG)  │  │(Kimi/  │  │(SQLite) │  │  (SQLite)   │   │
│  │         │  │ OpenAI) │  │         │  │             │   │
│  └────┬────┘  └────┬────┘  └────┬────┘  └──────┬──────┘   │
│       │            │            │               │           │
│  ┌────┴────────────┴────────────┴───────────────┴──────┐  │
│  │                    Repair Loop                        │  │
│  │         (retry → context → escalation)              │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```


Async workflow orchestrator with repair loops, shared memory, knowledge graph, and model routing.

## Validation Pipeline

| Level | Command | What it proves |
|-------|---------|----------------|
| 1 | `make syntax` | All Python modules compile |
| 2 | `make imports` | All imports resolve, smoke test passes |
| 3 | `make unit` | Unit tests pass (pytest) |
| 4 | `make benchmark-scaffold` | Benchmark framework runs on synthetic data |
| 5 | `make benchmark-runtime` | Benchmarks run against live mesh services |
| 6 | `make integration` | End-to-end workflow via Docker Compose |


## Validation Pipeline

| Level | Command | What it proves | Status |
|-------|---------|----------------|--------|
| 1 | `make syntax` | All Python modules compile | ✅ |
| 2 | `make imports` | All imports resolve, smoke test passes | ✅ |
| 3 | `make unit` | 47 unit tests pass (pytest) | ✅ |
| 4 | `make benchmark-scaffold` | Benchmark framework runs on synthetic data | ✅ |
| 5 | `make benchmark-runtime` | Benchmarks run against live mesh engine | ✅ |
| 6 | `make integration` | End-to-end workflow via Docker Compose | ✅ |

**Latest run:** 47 unit tests + 8 integration tests, all passing.


## Architecture Principles

**No placebo effects.** Every code path hits real infrastructure:

- **Model Router**: Real HTTP calls to Kimi (`api.moonshot.cn`) and OpenAI (`api.openai.com`). No mock backends. Missing API key = explicit failure.
- **Messaging**: Real NATS via `nats-py`. No in-memory fallback. NATS down = explicit failure.
- **Storage**: Real MinIO via `minio` SDK. No filesystem fallback. MinIO down = explicit failure.
- **Checkpoints**: Real SQLite via `aiosqlite`. Persistent, crash-safe.
- **Memory**: Real SQLite key-value and vector store. No ephemeral caches.
- **Benchmarks**: Every task executes real workflows through the mesh engine. No synthetic responses, no hardcoded metrics, no `asyncio.sleep` stand-ins.

If a dependency is unavailable, the system fails fast and loud. No silent degradation. No fake progress.

## Quick Start

```bash
# Install dev dependencies
make install

# Run levels 1-4
make validate

# Run just unit tests
pytest tests/ -v

# Run smoke test directly
python tests/smoke_test.py
```

## Benchmark Suite

```bash
# Run all benchmark suites
python -m benchmarks.run --suite all --output report.json

# Run specific suite
python -m benchmarks.run --suite comparative

# CI regression gate
python -m benchmarks.ci_gate --report report.json --strict
```
