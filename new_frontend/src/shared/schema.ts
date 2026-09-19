/**
 * CANONICAL DATA CONTRACT — aligned with backend/app/schema.py
 * and shared/schema.ts (auto-generated from backend).
 *
 * All modules must import types FROM this module.
 *
 * Fields that exist only for frontend display (UserContext) are marked
 * as frontend-only and are NOT part of the backend API contract.
 */

// ── Backend-aligned enums ────────────────────────────────────────────

export type DeclarationFieldStatus =
  | 'pass'
  | 'fail'
  | 'missing'
  | 'confirmed_missing'
  | 'below_min'
  | 'needs_review';

export type ObservationState = 'observed' | 'uncertain';
export type ConfirmationState = 'unconfirmed' | 'human_confirmed';

export type OverallVerdict =
  | 'compliant'
  | 'minor_non_compliance'
  | 'major_non_compliance'
  | 'needs_review';

export type ScanReviewStatus = 'pending' | 'approved' | 'needs_review' | 'rejected';

export type Role = 'inspector' | 'district_officer' | 'state_admin' | 'national_admin' | 'auditor';

export type ScanSource = 'photo' | 'listing_url';

// ── Backend-aligned interfaces ───────────────────────────────────────

export interface GpsCoordinates {
  lat: number;
  lng: number;
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Product {
  name: string;
  manufacturer: string;
  category: string;
  image_path: string;
}

export interface Declaration {
  field: string;
  detected_value: string | null;
  font_size_mm: number | null;
  status: DeclarationFieldStatus;
  remark: string | null;
  bounding_box: BoundingBox | null;
  confidence: number | null;
  id?: string;
  rule_provision?: string;
  statutory_parameter?: string;
  legal_metrology_standard?: string;
  mandated_value?: string;
  observation_state?: ObservationState;
  source?: string | null;
  verification_method?: string | null;
  context_evidence?: string | null;
  confirmation_state?: ConfirmationState;
  confirmed_by?: string | null;
  confirmed_at?: string | null;
  confirmation_reason?: string | null;
  previous_state?: string | null;
}

export interface Ingredient {
  name: string;
  quantity: string | null;
}

export interface OverrideInfo {
  overridden: boolean;
  overridden_by: string | null;
  reason: string | null;
  previous_verdict: OverallVerdict | null;
  timestamp: string | null;
}

export interface ScanRecord {
  scan_id: string;
  report_no: string;
  report_version: number;
  previous_report_hash: string | null;
  report_hash: string;
  date_scanned: string;
  gps: GpsCoordinates;
  inspector_id: string;
  inspector_name?: string | null;
  inspector_badge?: string | null;
  inspector_cadre?: string | null;
  district_id: string;
  district_name?: string | null;
  state_id: string;
  state_name?: string | null;
  source: ScanSource;
  source_url: string | null;
  product: Product;
  declarations: Declaration[];
  ingredients: Ingredient[];
  overall_verdict: OverallVerdict;
  remarks_summary: string;
  qr_payload: string;
  review_status: ScanReviewStatus;
  override: OverrideInfo | null;
  compliance_detail: Record<string, unknown> | null;
}

export interface JurisdictionScope {
  role: Role;
  user_id: string;
  district_id: string | null;
  state_id: string | null;
  scope_expires_at: string | null;
  auditor_level: 'district' | 'state' | 'national' | null;
}

// ── Frontend-only display type ───────────────────────────────────────
// Not part of the backend API contract. Built client-side from JurisdictionScope.

export interface UserContext {
  id: string;
  name: string;
  full_name?: string;
  email?: string;
  role: Role;
  district_id: string;
  district_name: string;
  state_id: string;
  state_name: string;
  badge_number: string;
  cadre: string;
  active?: boolean;
}
