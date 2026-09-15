"""Compatibility — Rules Engine wiring now lives in app.models.get_rules_engine."""

from app.models import get_rules_engine

__all__ = ["get_rules_engine"]
