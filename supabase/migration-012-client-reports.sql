-- Migration 012: Client Reports table
-- Stores generated weekly/monthly progress reports with PDF links

CREATE TABLE IF NOT EXISTS client_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  report_type TEXT NOT NULL CHECK (report_type IN ('weekly', 'monthly')),
  report_date DATE NOT NULL,
  pdf_url TEXT,
  report_data JSONB,
  coach_name TEXT,
  emailed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(client_id, report_type, report_date)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_client_reports_client_id ON client_reports(client_id);
CREATE INDEX IF NOT EXISTS idx_client_reports_date ON client_reports(report_date DESC);

-- RLS
ALTER TABLE client_reports ENABLE ROW LEVEL SECURITY;

-- Coaches can read/write reports for their clients
CREATE POLICY "coaches_manage_reports" ON client_reports
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM client_coach_assignments cca
      JOIN org_members om ON om.user_id = cca.coach_user_id
      WHERE cca.client_id = client_reports.client_id
        AND cca.is_active = true
        AND om.user_id = auth.uid()
    )
  );

-- Clients can read their own reports
CREATE POLICY "clients_read_own_reports" ON client_reports
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM clients c
      WHERE c.id = client_reports.client_id
        AND c.user_id = auth.uid()
    )
  );

-- Service role bypasses RLS (for API routes using admin client)

-- ═══════════════════════════════════════════════════════════
--  Storage bucket for report PDFs
--  Run this in Supabase Dashboard → Storage → Create Bucket:
--    Bucket name: reports
--    Public: No (signed URLs used)
--    File size limit: 5MB
--    Allowed MIME types: application/pdf
-- ═══════════════════════════════════════════════════════════
