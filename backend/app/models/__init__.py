"""Model package — ORM Models with behavior + Rules Engine factory.

get_rules_engine() is the sole wiring point for a future Rules Engine swap.
"""

from __future__ import annotations

from app.models.rules_engine import (
    CurrentRulesEngineModel,
    RulesEngineModel,
    run_authoritative_compliance_engine,
)


def get_rules_engine() -> RulesEngineModel:
    """Return the active Rules Engine Model implementation.

    Change this one function to swap engines — Controllers, Views, and ORM
    Models keep calling get_rules_engine() / ScanReportRow.evaluate().
    """
    return CurrentRulesEngineModel()


__all__ = [
    "CurrentRulesEngineModel",
    "RulesEngineModel",
    "get_rules_engine",
    "run_authoritative_compliance_engine",
]
