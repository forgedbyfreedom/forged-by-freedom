-- ═══════════════════════════════════════════════════════════
--  MIGRATION 003 — File Uploads + Body Scan Tracking
--  Run this in Supabase SQL Editor
-- ═══════════════════════════════════════════════════════════

-- File upload URLs on intake
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS bloodwork_file_urls TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS body_scan_file_urls TEXT;

-- Create Supabase Storage bucket for client uploads
-- NOTE: Run this separately in Supabase Dashboard → Storage → Create Bucket
-- Bucket name: client-uploads
-- Public: Yes (so URLs work in emails/admin)
-- File size limit: 10MB
-- Allowed MIME types: image/png, image/jpeg, image/heic, application/pdf

-- ═══════════════════════════════════════════════════════════
--  Body Scan Tracking (InBody, DEXA, etc.)
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS body_scans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ DEFAULT now(),
  client_id UUID NOT NULL,
  scan_date DATE NOT NULL,
  scan_type TEXT NOT NULL,  -- 'inbody', 'dexa', 'bodpod', 'calipers', 'other'

  -- Core metrics (all nullable — different scans report different data)
  body_fat_pct NUMERIC(5,2),
  lean_mass_lbs NUMERIC(6,2),
  fat_mass_lbs NUMERIC(6,2),
  total_weight_lbs NUMERIC(6,2),
  skeletal_muscle_mass_lbs NUMERIC(6,2),
  body_water_lbs NUMERIC(6,2),
  bmi NUMERIC(5,2),
  visceral_fat_level NUMERIC(5,2),
  basal_metabolic_rate INTEGER,

  -- Segmental (InBody specific)
  right_arm_lbs NUMERIC(5,2),
  left_arm_lbs NUMERIC(5,2),
  trunk_lbs NUMERIC(5,2),
  right_leg_lbs NUMERIC(5,2),
  left_leg_lbs NUMERIC(5,2),

  -- File upload
  scan_file_url TEXT,
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_body_scans_client ON body_scans(client_id, scan_date DESC);

ALTER TABLE body_scans ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow authenticated full access body_scans" ON body_scans FOR ALL TO authenticated USING (true);
CREATE POLICY "Allow anon insert body_scans" ON body_scans FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Allow anon select body_scans" ON body_scans FOR SELECT TO anon USING (true);
