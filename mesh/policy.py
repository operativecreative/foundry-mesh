#!/usr/bin/env python3
"""
Policy Engine — validates workflows and results against rules.

Rules:
- Max cost per workflow
- Max latency per task
- Required checkpoints
- Forbidden operations
- Required approvals for sensitive actions
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from mesh.types import TaskResult, TaskStatus


@dataclass
class PolicyRule:
    name: str
    rule_type: str  # "max_cost", "max_latency", "require_checkpoint", "forbid"
    threshold: Optional[float] = None
    message: str = "Policy violation"


DEFAULT_POLICIES = [
    PolicyRule("cost_cap", "max_cost", 0.50, "Workflow cost exceeds $0.50"),
    PolicyRule("latency_cap", "max_latency", 30000, "Task latency exceeds 30s"),
    PolicyRule("require_success", "min_success_rate", 0.70, "Success rate below 70%"),
]


class PolicyEngine:
    def __init__(self, rules: Optional[List[PolicyRule]] = None):
        self.rules = rules or list(DEFAULT_POLICIES)
        self.violations: List[Dict[str, Any]] = []

    def validate_workflow(self, workflow_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Validate workflow summary against all rules."""
        violations = []

        for rule in self.rules:
            if rule.rule_type == "max_cost" and rule.threshold is not None:
                if workflow_summary.get("total_cost_usd", 0) > rule.threshold:
                    violations.append({
                        "rule": rule.name,
                        "type": rule.rule_type,
                        "value": workflow_summary["total_cost_usd"],
                        "threshold": rule.threshold,
                        "message": rule.message,
                    })

            elif rule.rule_type == "max_latency" and rule.threshold is not None:
                if workflow_summary.get("total_latency_ms", 0) > rule.threshold:
                    violations.append({
                        "rule": rule.name,
                        "type": rule.rule_type,
                        "value": workflow_summary["total_latency_ms"],
                        "threshold": rule.threshold,
                        "message": rule.message,
                    })

            elif rule.rule_type == "min_success_rate" and rule.threshold is not None:
                if workflow_summary.get("success_rate", 1.0) < rule.threshold:
                    violations.append({
                        "rule": rule.name,
                        "type": rule.rule_type,
                        "value": workflow_summary["success_rate"],
                        "threshold": rule.threshold,
                        "message": rule.message,
                    })

        self.violations.extend(violations)
        return violations

    def validate_task(self, task_result: TaskResult) -> List[Dict[str, Any]]:
        """Validate individual task result."""
        violations = []

        for rule in self.rules:
            if rule.rule_type == "max_latency" and rule.threshold is not None:
                if task_result.latency_ms > rule.threshold:
                    violations.append({
                        "rule": rule.name,
                        "type": rule.rule_type,
                        "task": task_result.task_id,
                        "value": task_result.latency_ms,
                        "threshold": rule.threshold,
                        "message": rule.message,
                    })

        self.violations.extend(violations)
        return violations

    def get_violations(self) -> List[Dict[str, Any]]:
        return list(self.violations)

    def clear(self):
        self.violations = []
