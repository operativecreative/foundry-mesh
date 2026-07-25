# Foundry Mesh — Six-Level Validation Pipeline
# 
# Level 1: Syntax      — python -m compileall
# Level 2: Imports     — python tests/smoke_test.py
# Level 3: Unit        — pytest
# Level 4: Scaffold    — python -m benchmarks.run
# Level 5: Runtime     — python -m benchmarks.run_runtime
# Level 6: Integration — pytest tests/test_integration.py + docker compose

PYTHON := python3
PYTEST := pytest
BENCHMARK := $(PYTHON) -m benchmarks.run
RUNTIME_BENCH := $(PYTHON) -m benchmarks.run_runtime
CI_GATE := $(PYTHON) -m benchmarks.ci_gate

.PHONY: all validate syntax imports unit benchmark-scaffold benchmark-runtime integration clean test-full

# Run full validation pipeline (levels 1-5, level 6 requires Docker)
all: syntax imports unit benchmark-scaffold benchmark-runtime
	@echo ""
	@echo "========================================"
	@echo "LEVELS 1-5 PASSED"
	@echo "Level 6 requires: make up && make integration"
	@echo "========================================"

# Alias for CI
validate: all

# Level 1: Syntax validation
syntax:
	@echo "=== LEVEL 1: Syntax Validation ==="
	$(PYTHON) -m compileall benchmarks/ mesh/ tests/
	@echo "PASS: All modules compile without syntax errors"

# Level 2: Import + smoke test
imports:
	@echo ""
	@echo "=== LEVEL 2: Import & Smoke Test ==="
	$(PYTHON) tests/smoke_test.py

# Level 3: Unit tests
unit:
	@echo ""
	@echo "=== LEVEL 3: Unit Tests ==="
	$(PYTEST) tests/test_harness.py tests/test_fault_injection.py tests/test_comparative.py tests/test_stats.py tests/test_history.py tests/test_mesh_core.py -v --tb=short

# Level 4: Benchmark scaffold (synthetic data)
benchmark-scaffold:
	@echo ""
	@echo "=== LEVEL 4: Benchmark Scaffold ==="
	$(BENCHMARK) --suite all --output benchmarks/report.json
	@echo "PASS: Benchmark scaffold completed"

# Level 5: Runtime benchmark (live mesh engine)
benchmark-runtime:
	@echo ""
	@echo "=== LEVEL 5: Runtime Benchmark ==="
	$(RUNTIME_BENCH) --iterations 2 --output benchmarks/runtime-report.json --save-history
	@echo "PASS: Runtime benchmark completed"

# Level 6: Full integration tests
integration:
	@echo ""
	@echo "=== LEVEL 6: Integration Tests ==="
	$(PYTEST) tests/test_integration.py -v --tb=short
	@echo "PASS: Integration tests completed"

# Run ALL tests (unit + integration + mesh core)
test-full:
	@echo "=== FULL TEST SUITE ==="
	$(PYTEST) tests/ -v --tb=short

# Start mesh services with Docker Compose
up:
	@echo "Starting mesh services..."
	docker compose up -d
	@echo "Services starting. Check status with: docker compose ps"

# Stop mesh services
down:
	@echo "Stopping mesh services..."
	docker compose down

# View logs
logs:
	docker compose logs -f

# Clean generated artifacts
clean:
	rm -f benchmarks/report.json
	rm -f benchmarks/runtime-report.json
	rm -f benchmarks/history.jsonl
	rm -rf data/
	rm -rf .pytest_cache
	rm -rf __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.db" -delete

# Install dev dependencies
install:
	pip install -e ".[dev]"

# Quick health check
health:
	@echo "Checking mesh health..."
	$(PYTHON) -c "from mesh.engine import WorkflowEngine; print('Engine: OK')"
	$(PYTHON) -c "from mesh.router import ModelRouter; print('Router: OK')"
	$(PYTHON) -c "from mesh.checkpoint import CheckpointStore; print('Checkpoint: OK')"
	$(PYTHON) -c "from mesh.memory import SharedMemory; print('Memory: OK')"
	$(PYTHON) -c "from mesh.scheduler import DagScheduler; print('Scheduler: OK')"
	@echo "All core components importable"
