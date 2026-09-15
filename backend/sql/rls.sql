-- Schema + RLS for Legal Metrology Compliance Scanning.
-- Application role: lmcs_app — SELECT/INSERT only on append-only tables.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'lmcs') THEN
    CREATE ROLE lmcs WITH SUPERUSER LOGIN PASSWORD 'lmcs';
  ELSE
    ALTER ROLE lmcs WITH SUPERUSER PASSWORD 'lmcs';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'lmcs_app') THEN
    CREATE ROLE lmcs_app LOGIN PASSWORD 'lmcs_app';
  ELSE
    ALTER ROLE lmcs_app LOGIN PASSWORD 'lmcs_app';
  END IF;
END$$;

GRANT CONNECT ON DATABASE lmcs TO lmcs_app;
GRANT USAGE ON SCHEMA public TO lmcs_app;

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

-- Idempotent migrations for existing databases (e.g. Neon PostgreSQL)
ALTER TABLE jurisdictions ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS badge_number TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS cadre TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS district_name TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS state_name TEXT;

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

-- Append-only grants: no UPDATE/DELETE for application role.
REVOKE ALL ON TABLE scan_reports FROM PUBLIC;
REVOKE ALL ON TABLE audit_log FROM PUBLIC;
REVOKE ALL ON TABLE jurisdictions FROM PUBLIC;
GRANT SELECT, INSERT ON TABLE scan_reports TO lmcs_app;
GRANT SELECT, INSERT ON TABLE audit_log TO lmcs_app;
GRANT SELECT, INSERT, UPDATE ON TABLE users TO lmcs_app;
GRANT SELECT ON TABLE jurisdictions TO lmcs_app;

ALTER TABLE scan_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE scan_reports FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE jurisdictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE jurisdictions FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS jurisdictions_read_policy ON jurisdictions;
CREATE POLICY jurisdictions_read_policy ON jurisdictions
  FOR SELECT
  TO lmcs_app
  USING (active = TRUE);

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

DROP POLICY IF EXISTS audit_log_insert ON audit_log;
CREATE POLICY audit_log_insert ON audit_log
  FOR INSERT
  TO lmcs_app
  WITH CHECK (actor_id = current_setting('app.user_id', true));

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
