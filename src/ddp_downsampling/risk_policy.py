"""Configurable software-defined risk policy simulation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import yaml


def load_risk_policy(path: Path) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        policy = yaml.safe_load(handle) or {}
    if not isinstance(policy, dict):
        raise ValueError("Risk policy YAML must contain a mapping at the root.")
    return policy


def _matches(rule: Mapping[str, Any], fault_type: Optional[str], severity: Optional[str], confidence: Optional[float]) -> bool:
    fault_types = rule.get("fault_types")
    severities = rule.get("severities")
    if fault_types and fault_type not in fault_types:
        return False
    if severities and severity not in severities:
        return False
    minimum = rule.get("min_confidence")
    if minimum is not None and (confidence is None or float(confidence) < float(minimum)):
        return False
    return True


def apply_risk_policy(
    fault_type: Optional[str],
    severity: Optional[str],
    confidence: Optional[float],
    policy: Mapping[str, Any],
) -> Dict[str, str]:
    """Map diagnosis fields to a policy state/action.

    The result is a software/research simulation, not a certified safety
    decision. Rules are evaluated in YAML order, followed by the default.
    """
    for rule in policy.get("rules", []) or []:
        if _matches(rule, fault_type, severity, confidence):
            return {
                "risk_state": str(rule.get("risk_state", "NORMAL")),
                "risk_action": str(rule.get("risk_action", "No intervention; continue monitoring.")),
            }
    default = policy.get("default", {}) or {}
    return {
        "risk_state": str(default.get("risk_state", "NORMAL")),
        "risk_action": str(default.get("risk_action", "No intervention; continue monitoring.")),
    }

