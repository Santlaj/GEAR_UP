"""Compatibility shim — CSR RulesEnginePort renamed to RulesEngineModel."""

from app.models.rules_engine import (
    CurrentRulesEngineModel as CurrentRulesEngine,
    RulesEngineModel as RulesEnginePort,
    run_authoritative_compliance_engine,
)

__all__ = [
    "CurrentRulesEngine",
    "RulesEnginePort",
    "run_authoritative_compliance_engine",
]
