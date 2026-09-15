"""Central Compliance Engine — orchestrates the entire evaluation pipeline.

The pipeline order is FIXED in code. The JSON provides rule data and metadata.
The JSON ruleset NEVER controls execution order.

Pipeline:
  validate_ruleset → resolve_conflicts → normalize_fields → classify_commodity
  → select_domains → apply_scope_gates → retrieve_rules → filter_effective_rules
  → filter_capabilities → evaluate_rules → apply_verification_gate
  → attach_evidence → aggregate_results → generate_violations → build_report

Execution modes:
  - "production": Verification gate blocks unverified rules (NEEDS_REVIEW).
  - "demo": Verification gate exposes raw evaluator results but marks them
    as non-authoritative. verification_status is NEVER mutated.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from app.classification.category_taxonomy import (
    normalize_category,
    resolve_all_applicable,
)
from app.classification.commodity_classifier import (
    ClassificationResult,
    CommodityClassifier,
)
from app.classification.domain_mapper import (
    DomainApplicability,
    DomainMappingResult,
    map_domains,
)
from app.evaluation.capability_filter import apply_capability_filter
from app.evaluation.registry import (
    EvaluatorResult,
    RawResult,
    get_evaluator,
)
from app.evaluation.verification_gate import apply_verification_gate
from app.evidence.evidence_builder import build_evidence
from app.extraction_engine.conflict_resolver import resolve_conflicts
from app.extraction_engine.contracts import ExtractionOutput
from app.extraction_engine.normalizer import normalize_extraction
from app.rules.indexer import RuleIndex, build_index
from app.rules.loader import LoadedRuleset, NormalizedRule
from app.rules.retriever import retrieve_applicable_rules
from app.scope.scope_engine import (
    ScopeContext,
    ScopeEvaluationResult,
    ScopeResult,
    evaluate_scope,
)
from app.violations.aggregator import (
    AggregationResult,
    RuleEvaluation,
    aggregate_results,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    """Complete result of the compliance evaluation pipeline."""

    scan_id: str
    reference_date: date
    ruleset_version: str

    mode: str = "production"
    authoritative: bool = False

    classification: ClassificationResult | None = None
    category_resolution: Any = None
    domain_mapping: DomainMappingResult | None = None
    scope_evaluation: ScopeEvaluationResult | None = None
    applicable_rule_count: int = 0
    aggregation: AggregationResult | None = None

    domain_health: dict[str, dict] = field(default_factory=dict)

    pipeline_started_at: datetime | None = None
    pipeline_completed_at: datetime | None = None

    pipeline_log: list[str] = field(default_factory=list)
    debug_info: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def overall_verdict(self) -> str:
        if self.aggregation:
            return self.aggregation.overall_verdict.value
        return "NEEDS_REVIEW"


# ---------------------------------------------------------------------------
# Compliance Engine
# ---------------------------------------------------------------------------


class ComplianceEngine:
    """Central compliance engine — the single entry point for evaluation."""

    def __init__(
        self,
        ruleset: LoadedRuleset,
        classifier: CommodityClassifier,
        best_effort_policy: str = "NEEDS_REVIEW",
        mode: str = "production",
    ) -> None:
        if mode not in ("production", "demo"):
            raise ValueError(f"Invalid mode '{mode}'. Must be 'production' or 'demo'.")

        self._ruleset = ruleset
        self._classifier = classifier
        if mode == "demo" and best_effort_policy == "NEEDS_REVIEW":
            best_effort_policy = "ALLOW_PASS_FAIL"
        self._best_effort_policy = best_effort_policy
        self._mode = mode

        self._index = build_index(ruleset.rules)

        logger.info(
            "ComplianceEngine initialized: mode=%s, rules=%d, domains=%s",
            mode,
            self._index.total_rules,
            list(self._index.rules_by_domain.keys()),
        )
        if self._index.unmapped_categories:
            logger.warning(
                "Unmapped categories at startup: %s",
                dict(self._index.unmapped_categories),
            )

    @property
    def mode(self) -> str:
        return self._mode

    def evaluate(
        self,
        extracted_data: ExtractionOutput,
        reference_date: date | None = None,
        scope_context: ScopeContext | None = None,
    ) -> PipelineResult:
        """Run the full compliance evaluation pipeline."""
        if reference_date is None:
            reference_date = date.today()

        result = PipelineResult(
            scan_id=extracted_data.scan_id,
            reference_date=reference_date,
            ruleset_version=self._ruleset.ruleset_version,
            mode=self._mode,
            pipeline_started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        try:
            self._run_pipeline(extracted_data, reference_date, scope_context, result)
        except Exception as e:
            logger.exception("Pipeline error for scan %s", extracted_data.scan_id)
            result.pipeline_log.append(f"PIPELINE ERROR: {e}")

        result.pipeline_completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        return result

    def _run_pipeline(
        self,
        extraction: ExtractionOutput,
        reference_date: date,
        scope_context: ScopeContext | None,
        result: PipelineResult,
    ) -> None:
        """Execute pipeline stages in fixed order."""

        # ---- Stage 1: Conflict Resolution -----------------------------------
        result.pipeline_log.append("stage.conflict_resolution.started")
        resolve_conflicts(extraction)
        result.pipeline_log.append("stage.conflict_resolution.completed")

        # ---- Stage 2: Normalization -----------------------------------------
        result.pipeline_log.append("stage.normalization.started")
        normalize_extraction(extraction)
        result.pipeline_log.append("stage.normalization.completed")

        # ---- Stage 3: Commodity Classification ------------------------------
        result.pipeline_log.append("stage.classification.started")
        product_name = extraction.get_resolved_value("product_name")
        product_category = extraction.get_resolved_value("product_category")
        product_description = extraction.get_resolved_value("product_description")

        extracted_fields = {
            fname: f.resolved_value or ""
            for fname, f in extraction.fields.items()
            if f.resolved_value
        }

        classification = self._classifier.classify(
            product_name=product_name,
            product_category=product_category,
            product_description=product_description,
            extracted_fields=extracted_fields,
        )
        result.classification = classification

        # Category Resolution: Compare Inspector selection with VLM classification
        selected_category_id = extraction.get_resolved_value("selected_category_id")
        selected_category_label = extraction.get_resolved_value("selected_category_label")
        if not selected_category_id and scope_context and hasattr(scope_context, "selected_category_id"):
            selected_category_id = getattr(scope_context, "selected_category_id")
        if not selected_category_label and scope_context and hasattr(scope_context, "selected_category_label"):
            selected_category_label = getattr(scope_context, "selected_category_label")

        from app.classification.category_resolver import (
            resolve_category_agreement,
            CategoryAgreementStatus,
        )
        category_resolution = resolve_category_agreement(
            selected_category_id=selected_category_id,
            selected_category_label=selected_category_label,
            vlm_category=classification.category,
            vlm_confidence=classification.confidence,
        )
        result.category_resolution = category_resolution

        canonical_category = category_resolution.canonical_category
        applicable_cats = category_resolution.applicable_categories or resolve_all_applicable(canonical_category)

        result.debug_info["classification"] = {
            "raw_category": classification.category,
            "canonical_category": canonical_category,
            "ancestor_chain": sorted(applicable_cats),
            "food_classification": classification.classification.value,
            "confidence": classification.confidence,
            "selected_category_id": selected_category_id,
            "selected_category_label": selected_category_label,
            "category_agreement_status": category_resolution.agreement_status.value,
            "category_specific_rules_enabled": category_resolution.category_specific_rules_enabled,
            "category_resolution_evidence": category_resolution.evidence,
        }

        result.pipeline_log.append(
            f"stage.classification.completed: {classification.classification.value} "
            f"({classification.category} → {canonical_category}, "
            f"agreement={category_resolution.agreement_status.value}, "
            f"category_specific_enabled={category_resolution.category_specific_rules_enabled}, "
            f"ancestors={sorted(applicable_cats)}, "
            f"confidence={classification.confidence:.2f})"
        )

        # ---- Stage 4: Domain Mapping ----------------------------------------
        result.pipeline_log.append("stage.domain_mapping.started")
        domain_mapping = map_domains(classification)
        result.domain_mapping = domain_mapping

        result.debug_info["domain_mapping"] = {
            "candidate_domains": domain_mapping.candidate_domains,
            "applicable_domains": domain_mapping.applicable_domains,
            "excluded_domains": [
                {"domain": d.domain, "reason": d.reason}
                for d in domain_mapping.excluded_domains
            ],
            "final_domain": domain_mapping.final_domain.value,
        }

        result.pipeline_log.append(
            f"stage.domain_mapping.completed: {domain_mapping.final_domain.value} "
            f"(applicable={domain_mapping.applicable_domains})"
        )

        # ---- Stage 5: Scope Gates -------------------------------------------
        result.pipeline_log.append("stage.scope_evaluation.started")
        if scope_context is None:
            nq = extraction.get_field("net_quantity")
            nq_val = None
            nq_unit = None
            if nq and nq.normalized_value and hasattr(nq.normalized_value, 'value'):
                nq_val = nq.normalized_value.value
                nq_unit = nq.normalized_value.unit if hasattr(nq.normalized_value, 'unit') else None

            scope_context = ScopeContext(
                package_type="retail",
                net_quantity_value=nq_val,
                net_quantity_unit=nq_unit,
                commodity_category=canonical_category,
            )

        scope_eval = evaluate_scope(scope_context)
        result.scope_evaluation = scope_eval
        result.pipeline_log.append(
            f"stage.scope_evaluation.completed: "
            f"chapter_ii={scope_eval.chapter_ii_applicable.value}"
        )

        # ---- Stage 6: Rule Retrieval ----------------------------------------
        result.pipeline_log.append("stage.rule_retrieval.started")

        domains_to_evaluate: list[str] = []
        if domain_mapping.legal_metrology in (
            DomainApplicability.APPLICABLE,
            DomainApplicability.UNCERTAIN,
        ):
            domains_to_evaluate.append("legal_metrology")
        if domain_mapping.fssai in (
            DomainApplicability.APPLICABLE,
            DomainApplicability.UNCERTAIN,
        ):
            domains_to_evaluate.append("fssai")

        all_applicable_rules: list[NormalizedRule] = []
        per_domain_counts: dict[str, int] = {}

        for domain in domains_to_evaluate:
            rules = retrieve_applicable_rules(
                index=self._index,
                domain=domain,
                commodity_category=canonical_category,
                package_type=scope_context.package_type,
                reference_date=reference_date,
                category_specific_rules_enabled=category_resolution.category_specific_rules_enabled,
            )
            per_domain_counts[domain] = len(rules)
            all_applicable_rules.extend(rules)

        seen_ids: set[str] = set()
        unique_rules: list[NormalizedRule] = []
        for r in all_applicable_rules:
            if r.rule_id not in seen_ids:
                unique_rules.append(r)
                seen_ids.add(r.rule_id)
        duplicates_removed = len(all_applicable_rules) - len(unique_rules)
        all_applicable_rules = unique_rules

        result.applicable_rule_count = len(all_applicable_rules)

        for domain in domains_to_evaluate:
            count = per_domain_counts.get(domain, 0)
            if count == 0:
                result.domain_health[domain] = {
                    "status": "RULESET_INCOMPLETE",
                    "rules_available": 0,
                    "reason": f"No {domain} rules matched for category '{canonical_category}'",
                }
                result.warnings.append(
                    f"WARNING: {domain.upper()} domain has 0 applicable rules "
                    f"for category '{canonical_category}'. "
                    f"Compliance for this domain cannot be evaluated."
                )
            else:
                result.domain_health[domain] = {
                    "status": "OK",
                    "rules_available": count,
                }

        from app.evaluation.verification_gate import _VERIFIED_STATUSES
        verified_count = sum(
            1 for r in all_applicable_rules
            if r.verification_status in _VERIFIED_STATUSES
        )
        unverified_count = len(all_applicable_rules) - verified_count

        result.debug_info["rule_retrieval"] = {
            "domains_queried": domains_to_evaluate,
            "per_domain_counts": per_domain_counts,
            "total_before_dedup": len(all_applicable_rules) + duplicates_removed,
            "duplicates_removed": duplicates_removed,
            "total_applicable": len(all_applicable_rules),
            "verified": verified_count,
            "unverified": unverified_count,
            "domain_health": result.domain_health,
        }

        result.pipeline_log.append(
            f"stage.rule_retrieval.completed: {len(all_applicable_rules)} rules "
            f"(per_domain={per_domain_counts}, "
            f"verified={verified_count}, unverified={unverified_count})"
        )

        # ---- Stage 7: Per-Rule Evaluation -----------------------------------
        result.pipeline_log.append("stage.rule_evaluation.started")
        evaluations: list[RuleEvaluation] = []

        for rule in all_applicable_rules:
            eval_result = self._evaluate_single_rule(rule, extraction)
            evaluations.append(eval_result)

        # If inspector and VLM disagreed on category, hold category-specific rules and record review item
        if category_resolution.agreement_status == CategoryAgreementStatus.DISAGREED:
            cat_review_eval = RuleEvaluation(
                rule_id="COMMODITY-CATEGORY-RESOLUTION",
                domain="classification",
                status="NEEDS_REVIEW",
                raw_result="UNCERTAIN",
                verification_status="UNVERIFIED",
                capability="SUPPORTED",
                observed_value=(
                    f"inspector={selected_category_id or selected_category_label}, "
                    f"vlm={classification.category}"
                ),
                expected_value="Inspector selection and VLM classification must agree",
                evidence=category_resolution.evidence,
                legal_reference={
                    "section_or_rule_number": "Category Agreement Gate",
                    "source_document": "Human-VLM Agreement Resolver",
                },
                verification_gate_reason="Inspector and VLM category classification disagree. Category-specific rules held for review.",
                authoritative=False,
                mode=self._mode,
            )
            evaluations.append(cat_review_eval)
            result.warnings.append(
                f"CATEGORY DISAGREEMENT: Inspector selected '{selected_category_label or selected_category_id}', "
                f"but VLM predicted '{classification.category}'. Requires human review."
            )

        result.pipeline_log.append(
            f"stage.rule_evaluation.completed: {len(evaluations)} rules evaluated"
        )

        # ---- Stage 8: Aggregation -------------------------------------------
        result.pipeline_log.append("stage.aggregation.started")
        aggregation = aggregate_results(
            evaluations,
            mode=self._mode,
            domain_health=result.domain_health,
        )
        result.aggregation = aggregation
        result.authoritative = aggregation.authoritative
        result.warnings.extend(aggregation.warnings)

        result.debug_info["aggregation"] = {
            "mode": self._mode,
            "authoritative": aggregation.authoritative,
            "verdict": aggregation.overall_verdict.value,
            "rule_counts": {
                "total_applicable": aggregation.rule_counts.total_applicable,
                "compliant": aggregation.rule_counts.compliant,
                "non_compliant": aggregation.rule_counts.non_compliant,
                "needs_review": aggregation.rule_counts.needs_review,
                "not_applicable": aggregation.rule_counts.not_applicable,
                "out_of_scope": aggregation.rule_counts.out_of_scope,
            },
            "violations_count": len(aggregation.violations),
        }

        result.pipeline_log.append(
            f"stage.aggregation.completed: verdict={aggregation.overall_verdict.value}, "
            f"compliant={aggregation.rule_counts.compliant}, "
            f"non_compliant={aggregation.rule_counts.non_compliant}, "
            f"needs_review={aggregation.rule_counts.needs_review}, "
            f"violations={len(aggregation.violations)}, "
            f"mode={self._mode}, authoritative={aggregation.authoritative}"
        )

    def _evaluate_single_rule(
        self,
        rule: NormalizedRule,
        extraction: ExtractionOutput,
    ) -> RuleEvaluation:
        """Evaluate a single rule through the full gate pipeline."""

        evaluator = get_evaluator(rule.evaluator_type)
        if evaluator is None:
            return RuleEvaluation(
                rule_id=rule.rule_id,
                domain=rule.domain,
                status="NEEDS_REVIEW",
                raw_result="UNCERTAIN",
                verification_status=rule.verification_status,
                capability=rule.capability,
                expected_value=rule.expected_value_or_format,
                evidence=[f"No evaluator for type: {rule.evaluator_type}"],
                legal_reference={
                    "section_or_rule_number": rule.legal_reference.section_or_rule_number,
                    "schedule_reference": rule.legal_reference.schedule_reference or "",
                },
                authoritative=False,
                mode=self._mode,
            )

        try:
            eval_result = evaluator.evaluate(rule, extraction)
        except Exception as e:
            logger.exception("Evaluator exception for rule %s", rule.rule_id)
            eval_result = EvaluatorResult(
                raw_result=RawResult.UNCERTAIN,
                expected_value=rule.expected_value_or_format,
                evidence=[f"Evaluator error: {e}"],
                inspected_fields=[],
            )

        cap_result, cap_reason = apply_capability_filter(
            eval_result.raw_result,
            rule.capability,
            self._best_effort_policy,
        )

        final_status, authoritative, verify_reason = apply_verification_gate(
            cap_result,
            rule.verification_status,
            mode=self._mode,
        )

        if rule.capability == "OUT_OF_SCOPE":
            final_status = "OUT_OF_SCOPE"
            authoritative = False

        evidence_items = build_evidence(
            rule=rule,
            extraction=extraction,
            relevant_fields=eval_result.inspected_fields or None,
            ruleset_version=self._ruleset.ruleset_version,
        )

        return RuleEvaluation(
            rule_id=rule.rule_id,
            domain=rule.domain,
            status=final_status,
            raw_result=eval_result.raw_result.value,
            verification_status=rule.verification_status,
            capability=rule.capability,
            observed_value=eval_result.observed_value,
            expected_value=eval_result.expected_value,
            evidence=[
                *eval_result.evidence,
                *[
                    {
                        "field": e.field_name,
                        "value": e.extracted_value,
                        "confidence": e.confidence,
                        "source": e.source_model,
                    }
                    for e in evidence_items
                ],
            ],
            legal_reference={
                "section_or_rule_number": rule.legal_reference.section_or_rule_number,
                "schedule_reference": rule.legal_reference.schedule_reference or "",
                "source_document": rule.legal_reference.source_document,
            },
            verification_gate_reason=verify_reason,
            capability_filter_reason=cap_reason,
            authoritative=authoritative,
            mode=self._mode,
        )
