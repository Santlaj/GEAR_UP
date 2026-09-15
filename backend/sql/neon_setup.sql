-- =============================================================================
-- LMCS Neon PostgreSQL Schema & Row Level Security Setup
-- Database: neondb (or active Neon branch database)
-- Execution Role: Neon Admin/Owner (e.g. neondb_owner)
-- Application Role: lmcs_app (runtime connection without admin privileges)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── 1. Dedicated Application Role (Password set via Neon Console / Env) ───────
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'lmcs_app') THEN
    BEGIN
      CREATE ROLE lmcs_app LOGIN;
    EXCEPTION
      WHEN insufficient_privilege THEN
        RAISE NOTICE 'Role lmcs_app could not be created directly (insufficient privilege). Create it in the Neon Console if needed.';
    END;
  END IF;
END$$;

-- Grant database connection & schema access dynamically to current database
DO $$
BEGIN
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'lmcs_app') THEN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO lmcs_app', current_database());
    GRANT USAGE ON SCHEMA public TO lmcs_app;
  END IF;
END$$;

-- ── 2. Table: jurisdictions (Master Circles & Territories) ────────────────────
CREATE TABLE IF NOT EXISTS jurisdictions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  district_id TEXT NOT NULL UNIQUE,
  district_name TEXT NOT NULL,
  state_id TEXT NOT NULL,
  state_name TEXT NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jurisdictions_district ON jurisdictions (district_id);
CREATE INDEX IF NOT EXISTS idx_jurisdictions_state ON jurisdictions (state_id);

ALTER TABLE jurisdictions ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;

-- ── 3. Table: users (Enforcement Officers & Admins) ───────────────────────────
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  full_name TEXT NOT NULL,
  badge_number TEXT,
  cadre TEXT,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL,
  district_id TEXT,
  district_name TEXT,
  state_id TEXT,
  state_name TEXT,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  auditor_level TEXT,
  scope_expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_district ON users (district_id);
CREATE INDEX IF NOT EXISTS idx_users_state ON users (state_id);

-- Idempotent migrations for existing deployments
ALTER TABLE users ADD COLUMN IF NOT EXISTS badge_number TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS cadre TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS district_name TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS state_name TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auditor_level TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS scope_expires_at TIMESTAMPTZ;

-- Foreign key linking users.district_id to jurisdictions.district_id
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'fk_users_district'
  ) THEN
    ALTER TABLE users
      ADD CONSTRAINT fk_users_district
      FOREIGN KEY (district_id)
      REFERENCES jurisdictions(district_id)
      ON UPDATE CASCADE
      ON DELETE SET NULL;
  END IF;
END$$;

-- ── 4. Table: scan_reports (Append-Only Evidence Reports) ─────────────────────
CREATE TABLE IF NOT EXISTS scan_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scan_id TEXT NOT NULL,
  report_no TEXT NOT NULL,
  report_version INTEGER NOT NULL CHECK (report_version >= 1),
  previous_report_hash TEXT,
  report_hash TEXT NOT NULL,
  inspector_id TEXT NOT NULL,
  district_id TEXT NOT NULL,
  state_id TEXT NOT NULL,
  date_scanned TIMESTAMPTZ NOT NULL,
  overall_verdict TEXT NOT NULL,
  review_status TEXT NOT NULL,
  payload JSONB NOT NULL,
  pdf_path TEXT,
  docx_path TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (scan_id, report_version)
);

CREATE INDEX IF NOT EXISTS idx_scan_reports_inspector ON scan_reports (inspector_id);
CREATE INDEX IF NOT EXISTS idx_scan_reports_district ON scan_reports (district_id);
CREATE INDEX IF NOT EXISTS idx_scan_reports_state ON scan_reports (state_id);

-- ── 5. Table: audit_log (Tamper-Evident Chronological Trail) ───────────────────
CREATE TABLE IF NOT EXISTS audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id TEXT NOT NULL,
  actor_role TEXT NOT NULL,
  action TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  resource_id TEXT,
  district_id TEXT,
  state_id TEXT,
  detail JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_district ON audit_log (district_id);
CREATE INDEX IF NOT EXISTS idx_audit_state ON audit_log (state_id);

-- ── 6. Application Role Grants ───────────────────────────────────────────────
DO $$
BEGIN
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'lmcs_app') THEN
    REVOKE ALL ON TABLE jurisdictions FROM PUBLIC;
    REVOKE ALL ON TABLE users FROM PUBLIC;
    REVOKE ALL ON TABLE scan_reports FROM PUBLIC;
    REVOKE ALL ON TABLE audit_log FROM PUBLIC;

    GRANT SELECT ON TABLE jurisdictions TO lmcs_app;
    GRANT SELECT, INSERT, UPDATE ON TABLE users TO lmcs_app;
    GRANT SELECT, INSERT ON TABLE scan_reports TO lmcs_app;
    GRANT SELECT, INSERT ON TABLE audit_log TO lmcs_app;
  END IF;
END$$;

-- ── 7. Row Level Security Configuration ───────────────────────────────────────
-- Enable RLS on all operational tables
ALTER TABLE jurisdictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE scan_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- CRITICAL FOR NEON: Ensure NO FORCE ROW LEVEL SECURITY is set.
-- In Neon, the owner role (e.g. neondb_owner) is the table owner, not a PostgreSQL superuser.
-- If FORCE RLS were enabled, neondb_owner would be subjected to RLS policies. Because policies
-- require active session GUCs (app.role, app.user_id), login queries via get_admin_session()
-- (which execute SELECT * FROM users WHERE email = :email prior to session GUC binding)
-- would be blocked by default-deny.
-- With standard ENABLE ROW LEVEL SECURITY (and NO FORCE), the table owner naturally
-- bypasses RLS for credential lookups and seeding, while lmcs_app is 100% strictly enforced.
ALTER TABLE jurisdictions NO FORCE ROW LEVEL SECURITY;
ALTER TABLE users NO FORCE ROW LEVEL SECURITY;
ALTER TABLE scan_reports NO FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_log NO FORCE ROW LEVEL SECURITY;

-- ── 8. Policies for Application Role (lmcs_app) ──────────────────────────────

-- Jurisdictions: Application role can read all active jurisdictions
DROP POLICY IF EXISTS jurisdictions_read_policy ON jurisdictions;
CREATE POLICY jurisdictions_read_policy ON jurisdictions
  FOR SELECT
  TO lmcs_app
  USING (active = TRUE);

-- Users: Scope isolation based on session GUCs
DROP POLICY IF EXISTS users_isolation ON users;
CREATE POLICY users_isolation ON users
  FOR SELECT
  TO lmcs_app
  USING (
    CASE current_setting('app.role', true)
      WHEN 'inspector' THEN id = current_setting('app.user_id', true)
      WHEN 'district_officer' THEN
        district_id = current_setting('app.district_id', true)
        OR id = current_setting('app.user_id', true)
      WHEN 'state_admin' THEN
        state_id = current_setting('app.state_id', true)
        OR id = current_setting('app.user_id', true)
      WHEN 'national_admin' THEN TRUE
      WHEN 'auditor' THEN
        CASE current_setting('app.auditor_level', true)
          WHEN 'national' THEN TRUE
          WHEN 'state' THEN state_id = current_setting('app.state_id', true)
          ELSE district_id = current_setting('app.district_id', true)
        END
      ELSE FALSE
    END
  );

-- Scan Reports: Isolation for SELECT and INSERT
DROP POLICY IF EXISTS scan_reports_isolation ON scan_reports;
CREATE POLICY scan_reports_isolation ON scan_reports
  FOR ALL
  TO lmcs_app
  USING (
    CASE current_setting('app.role', true)
      WHEN 'inspector' THEN inspector_id = current_setting('app.user_id', true)
      WHEN 'district_officer' THEN district_id = current_setting('app.district_id', true)
      WHEN 'state_admin' THEN state_id = current_setting('app.state_id', true)
      WHEN 'national_admin' THEN TRUE
      WHEN 'auditor' THEN
        CASE current_setting('app.auditor_level', true)
          WHEN 'national' THEN TRUE
          WHEN 'state' THEN state_id = current_setting('app.state_id', true)
          ELSE district_id = current_setting('app.district_id', true)
        END
      ELSE FALSE
    END
  )
  WITH CHECK (
    CASE current_setting('app.role', true)
      WHEN 'inspector' THEN inspector_id = current_setting('app.user_id', true)
      WHEN 'district_officer' THEN district_id = current_setting('app.district_id', true)
      WHEN 'state_admin' THEN state_id = current_setting('app.state_id', true)
      WHEN 'national_admin' THEN TRUE
      WHEN 'auditor' THEN FALSE
      ELSE FALSE
    END
  );

-- Audit Log: Scoped visibility for SELECT
DROP POLICY IF EXISTS audit_log_isolation ON audit_log;
CREATE POLICY audit_log_isolation ON audit_log
  FOR SELECT
  TO lmcs_app
  USING (
    CASE current_setting('app.role', true)
      WHEN 'inspector' THEN actor_id = current_setting('app.user_id', true)
      WHEN 'district_officer' THEN district_id = current_setting('app.district_id', true)
      WHEN 'state_admin' THEN state_id = current_setting('app.state_id', true)
      WHEN 'national_admin' THEN TRUE
      WHEN 'auditor' THEN
        CASE current_setting('app.auditor_level', true)
          WHEN 'national' THEN TRUE
          WHEN 'state' THEN state_id = current_setting('app.state_id', true)
          ELSE district_id = current_setting('app.district_id', true)
        END
      ELSE FALSE
    END
  );

-- Audit Log: Insert check verifies actor_id matches app.user_id GUC
DROP POLICY IF EXISTS audit_log_insert ON audit_log;
CREATE POLICY audit_log_insert ON audit_log
  FOR INSERT
  TO lmcs_app
  WITH CHECK (actor_id = current_setting('app.user_id', true));
