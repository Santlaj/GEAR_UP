-- =============================================================================
-- LMCS Neon PostgreSQL Schema: Server-Side Sessions & Revocation Table
-- Additive migration: Non-destructive, idempotent
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  jti TEXT NOT NULL UNIQUE,
  user_agent TEXT,
  ip_address TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_jti ON sessions (jti);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions (expires_at);
CREATE INDEX IF NOT EXISTS idx_sessions_revoked_at ON sessions (revoked_at);

-- Grant privileges to application role
DO $$
BEGIN
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'lmcs_app') THEN
    GRANT SELECT, INSERT, UPDATE ON TABLE sessions TO lmcs_app;
  END IF;
END$$;

-- Enable Row Level Security (NO FORCE for Neon compatibility)
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions NO FORCE ROW LEVEL SECURITY;

-- Allow lmcs_app to access sessions for the authenticated user
DROP POLICY IF EXISTS sessions_isolation ON sessions;
CREATE POLICY sessions_isolation ON sessions
  FOR ALL
  TO lmcs_app
  USING (
    user_id = current_setting('app.user_id', true)
    OR current_setting('app.role', true) = 'national_admin'
  )
  WITH CHECK (
    user_id = current_setting('app.user_id', true)
    OR current_setting('app.role', true) = 'national_admin'
  );
