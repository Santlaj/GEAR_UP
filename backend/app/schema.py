"""
Canonical domain schema for Legal Metrology Compliance Scanning.

Every pipeline stage, API response, and generated frontend type must import
from this module. Do not redeclare or shadow these types elsewhere.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ObservationState(str, Enum):
    OBSERVED = "observed"
    UNCERTAIN = "uncertain"


class ConfirmationState(str, Enum):
    UNCONFIRMED = "unconfirmed"
    CONFIRMED = "confirmed"
    HUMAN_CONFIRMED = "human_confirmed"



class DeclarationFieldStatus(str, Enum):
    """Values are canonical wire/DB strings — member names avoid the `pass` keyword."""

    PASS = "pass"
    FAIL = "fail"
    MISSING = "missing"  # legacy compatibility for historical records
    CONFIRMED_MISSING = "confirmed_missing"
    BELOW_MIN = "below_min"
    NEEDS_REVIEW = "needs_review"


class OverallVerdict(str, Enum):
    compliant = "compliant"
    minor_non_compliance = "minor_non_compliance"
    major_non_compliance = "major_non_compliance"
    needs_review = "needs_review"


class ScanReviewStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    needs_review = "needs_review"
    rejected = "rejected"


class Role(str, Enum):
    inspector = "inspector"
    district_officer = "district_officer"
    state_admin = "state_admin"
    national_admin = "national_admin"
    auditor = "auditor"


class ScanSource(str, Enum):
    photo = "photo"
    listing_url = "listing_url"


class GpsCoordinates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float
    lng: float


class BoundingBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    width: float
    height: float


class Product(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    manufacturer: str
    category: str
    image_path: str


class Declaration(BaseModel):
    model_config = ConfigDict(extra="ignore")

    field: str
    detected_value: str | None = None
    font_size_mm: float | None = None
    status: DeclarationFieldStatus
    remark: str | None = None
    bounding_box: BoundingBox | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    observation_state: ObservationState = ObservationState.UNCERTAIN
    source: str | None = None
    verification_method: str | None = None
    context_evidence: str | None = None
    confirmation_state: ConfirmationState = ConfirmationState.UNCONFIRMED
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    confirmation_reason: str | None = None
    previous_state: str | None = None

    @model_validator(mode="after")
    def validate_confirmed_missing(self) -> "Declaration":
        if self.status == DeclarationFieldStatus.CONFIRMED_MISSING:
            if self.confirmation_state != ConfirmationState.HUMAN_CONFIRMED:
                raise ValueError(
                    "CONFIRMED_MISSING declarations must have confirmation_state set to 'human_confirmed'"
                )
            if not self.confirmation_reason or not self.confirmation_reason.strip():
                raise ValueError(
                    "CONFIRMED_MISSING declarations require a non-empty confirmation_reason"
                )
        return self


class Ingredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    quantity: str | None = None


class OverrideInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overridden: bool
    overridden_by: str | None = None
    reason: str | None = None
    previous_verdict: OverallVerdict | None = None
    timestamp: datetime | None = None


class ScanRecord(BaseModel):
    """Superset record; stages read/write subsets of this one object."""

    model_config = ConfigDict(extra="ignore")

    scan_id: str
    report_no: str
    report_version: int = Field(ge=1)
    previous_report_hash: str | None = None
    report_hash: str
    date_scanned: datetime
    gps: GpsCoordinates
    inspector_id: str
    district_id: str
    state_id: str
    source: ScanSource
    source_url: str | None = None
    product: Product
    declarations: list[Declaration]
    ingredients: list[Ingredient]
    overall_verdict: OverallVerdict
    remarks_summary: str
    qr_payload: str
    review_status: ScanReviewStatus
    override: OverrideInfo | None = None
    compliance_detail: dict[str, Any] | None = None


class JurisdictionScope(BaseModel):
    """Server-derived scope from JWT claims — never trust client copies."""

    model_config = ConfigDict(extra="forbid")

    role: Role
    user_id: str
    district_id: str | None = None
    state_id: str | None = None
    scope_expires_at: datetime | None = None
    auditor_level: Literal["district", "state", "national"] | None = None


class RuleCheckType(str, Enum):
    presence = "presence"
    threshold = "threshold"
    format = "format"
    date = "date"


class ComplianceRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    field: str
    check_type: RuleCheckType
    exemptions: list[str] = Field(default_factory=list)
    penalty_reference: str
    min_font_size_mm: float | None = None
    pattern: str | None = None
    threshold_value: float | None = None
