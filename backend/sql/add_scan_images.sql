-- =============================================================================
-- LMCS Neon PostgreSQL Schema: Scan Evidence Images & Storage References
-- Additive migration: Non-destructive, idempotent
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS scan_images (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scan_id TEXT NOT NULL,
  storage_provider TEXT NOT NULL DEFAULT 'supabase',
  bucket TEXT NOT NULL DEFAULT 'lmcs-images',
  storage_path TEXT NOT NULL,
  original_filename TEXT,
  mime_type TEXT,
  file_size BIGINT,
  image_role TEXT NOT NULL DEFAULT 'front',
  storage_status TEXT NOT NULL DEFAULT 'uploaded',
  inspector_id TEXT NOT NULL,
  district_id TEXT NOT NULL,
  state_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scan_images_scan_id ON scan_images (scan_id);
CREATE INDEX IF NOT EXISTS idx_scan_images_inspector ON scan_images (inspector_id);
CREATE INDEX IF NOT EXISTS idx_scan_images_district ON scan_images (district_id);
CREATE INDEX IF NOT EXISTS idx_scan_images_state ON scan_images (state_id);
CREATE INDEX IF NOT EXISTS idx_scan_images_created_at ON scan_images (created_at);

-- Privileges for application role
DO $$
BEGIN
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'lmcs_app') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE scan_images TO lmcs_app;
  END IF;
END$$;

-- Enable Row Level Security (NO FORCE for Neon compatibility)
ALTER TABLE scan_images ENABLE ROW LEVEL SECURITY;
ALTER TABLE scan_images NO FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS scan_images_isolation ON scan_images;
CREATE POLICY scan_images_isolation ON scan_images
  FOR ALL
  TO lmcs_app
  USING (
    inspector_id = current_setting('app.user_id', true)
    OR district_id = current_setting('app.district_id', true)
    OR state_id = current_setting('app.state_id', true)
    OR current_setting('app.role', true) = 'national_admin'
  )
  WITH CHECK (
    inspector_id = current_setting('app.user_id', true)
    OR district_id = current_setting('app.district_id', true)
    OR state_id = current_setting('app.state_id', true)
    OR current_setting('app.role', true) = 'national_admin'
  );
