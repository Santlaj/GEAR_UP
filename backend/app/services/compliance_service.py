"""Compliance orchestration — RulesEnginePort only; no direct engine imports."""

from __future__ import annotations

from typing import Any

from app.compliance.rules_port import RulesEnginePort
from app.schema import Declaration, DeclarationFieldStatus, Ingredient, OverallVerdict, Product


class ComplianceService:
    def __init__(self, rules_engine: RulesEnginePort) -> None:
        self._rules = rules_engine

    def build_compliance_fields(
        self,
        product: Product,
        declarations: list[Declaration],
        ingredients: list[Ingredient] | None = None,
        pdp_area_cm2: float | None = None,
    ) -> dict[str, Any]:
        """Consolidate the three identical compliance_fields builders from routes.

        Omits CONFIRMED_MISSING fields and any declaration without detected_value.
        Preserves physical font measurements and pdp_area_cm2.
        """
        compliance_fields: dict[str, Any] = {
            "product_name": product.name,
            "manufacturer_name": product.manufacturer,
            "product_category": product.category,
        }
        for d in declarations:
            if d.status == DeclarationFieldStatus.CONFIRMED_MISSING:
                continue
            if d.detected_value:
                compliance_fields[d.field] = d.detected_value
            if d.font_size_mm is not None:
                compliance_fields["font_size_mm"] = str(d.font_size_mm)
                compliance_fields["numeral_height_mm"] = str(d.font_size_mm)
        if pdp_area_cm2 is not None:
            compliance_fields["pdp_area_cm2"] = str(pdp_area_cm2)
        if ingredients:
            ing_text = ", ".join(f"{i.name} {i.quantity or ''}".strip() for i in ingredients)
            compliance_fields["ingredients"] = ing_text
            compliance_fields["ingredients_list"] = ing_text
        return compliance_fields

    def run_authoritative(
        self,
        compliance_fields: dict[str, Any],
        scan_id: str,
    ) -> tuple[dict[str, Any], OverallVerdict]:
        """Authoritative scan-level verdict — 503 mapping lives in the port implementation."""
        return self._rules.evaluate_authoritative(compliance_fields, scan_id)

    def evaluate_declarations(
        self,
        product: Product,
        declarations: list[Declaration],
    ) -> tuple[list[Declaration], OverallVerdict, str]:
        return self._rules.evaluate_declarations(product, declarations)

    def invalidate_cache(self) -> None:
        self._rules.invalidate_cache()
