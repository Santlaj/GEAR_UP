# HARD ARCHITECTURAL RULES — Legal Metrology Compliance Scanning Platform (PRAMAAN)

These rules are non-negotiable constraints on every file, module, and commit in this platform.

---

## Rule 1: Legal Defensibility & Determinism
- Every verdict must be 100% explainable, reproducible, and tamper-evident.
- Zero black-box or non-deterministic steps between "field extracted data" and "compliant/non-compliant" decision.
- The rule engine must evaluate Legal Metrology Rules 2011 deterministically via pure in-memory comparisons (presence, thresholds, regex, date calculations).
- **NO LLM or AI network calls may occur during rule evaluation at runtime.** Identical input must always yield identical output.

---

## Rule 2: Jurisdictional Isolation
- A user must NEVER see, infer, or export data outside their assigned jurisdictional scope (District, State, National).
- All queries and data views must be filtered unconditionally by the server/auth context (`WHERE district_id = :user_district` or `WHERE inspector_id = :user_id`).
- Client-supplied jurisdiction parameters in query strings or request bodies must be strictly ignored and overridden by the authenticated context.
- Cross-jurisdiction intelligence (e.g. repeat offenders across states) is visible ONLY to National Admin, never leaked to District or State officers.

---

## Rule 3: Single Source of Truth Schema
- All modules (extraction, rule engine, report generation, API responses, frontend components) MUST import their core types from the shared schema module (`src/shared/schema.ts`).
- No module may locally redefine or shadow `DeclarationFieldStatus`, `OverallVerdict`, `ScanReviewStatus`, `Role`, or `ScanRecord`.
- Any required field missing from `ScanRecord` must be formally added to `src/shared/schema.ts` first.

---

## Rule 4: Immutability & Hash-Chaining
- Reports and scan records are append-only.
- Every report has `report_version >= 1`, a canonical content SHA-256 `report_hash`, and a `previous_report_hash` (`null` only for version 1).
- Overriding a verdict creates a NEW report version (`report_version + 1`) linking to the prior hash, recording who, why, and previous verdict. Old versions are never deleted or mutated.
- Audit logs are strictly append-only.

---

## Rule 5: Evidentiary Integrity
- Every captured record must preserve GPS coordinates (latitude, longitude) and the authenticated Inspector ID.
- Both PDF and DOCX reports must be generated from the exact same underlying `ScanRecord` canonical data.
- Fields with low OCR extraction confidence must be marked `needs_review` rather than auto-failed.
