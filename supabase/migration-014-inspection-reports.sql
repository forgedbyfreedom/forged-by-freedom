-- ================================================================
-- MIGRATION 014: Institutional Inspection Report Tracking System
-- Regional Directors, Regional Ops Coordinators, RHU Colonels
-- submit reports after visiting facilities; wardens respond.
-- ================================================================

-- Inspector role enum
DO $$ BEGIN
  CREATE TYPE inspector_role AS ENUM (
    'regional_director',
    'regional_ops_coordinator',
    'rhu_colonel',
    'warden',
    'admin'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ── Facilities ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS inspection_facilities (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  code        TEXT UNIQUE,
  region      TEXT,
  active      BOOLEAN DEFAULT true,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- ── Staff ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS inspection_staff (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  email       TEXT UNIQUE NOT NULL,
  role        inspector_role NOT NULL,
  facility_id UUID REFERENCES inspection_facilities(id),  -- wardens only
  active      BOOLEAN DEFAULT true,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- ── Reports ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS inspection_reports (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  facility_id     UUID NOT NULL REFERENCES inspection_facilities(id),
  inspector_id    UUID REFERENCES inspection_staff(id),
  inspector_role  inspector_role NOT NULL,
  visit_date      DATE NOT NULL,
  due_date        DATE NOT NULL,          -- deadline for warden response
  submitted_at    TIMESTAMPTZ,            -- NULL = still draft
  status          TEXT DEFAULT 'draft'
    CHECK (status IN ('draft','submitted','in_review','closed')),
  overall_notes   TEXT,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

-- ── Findings ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS inspection_findings (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id        UUID NOT NULL REFERENCES inspection_reports(id) ON DELETE CASCADE,
  category         TEXT NOT NULL,
  description      TEXT NOT NULL,
  severity         TEXT DEFAULT 'medium'
    CHECK (severity IN ('low','medium','high','critical')),
  recommendation   TEXT,
  is_repeat        BOOLEAN DEFAULT false,   -- flagged by trend engine
  prior_report_id  UUID REFERENCES inspection_reports(id),
  created_at       TIMESTAMPTZ DEFAULT now()
);

-- ── Warden Responses ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS finding_responses (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  finding_id             UUID NOT NULL REFERENCES inspection_findings(id) ON DELETE CASCADE,
  responder_id           UUID REFERENCES inspection_staff(id),
  status                 TEXT DEFAULT 'open'
    CHECK (status IN ('open','in_progress','resolved','deferred')),
  response_notes         TEXT,
  target_completion_date DATE,
  completed_at           TIMESTAMPTZ,
  created_at             TIMESTAMPTZ DEFAULT now(),
  updated_at             TIMESTAMPTZ DEFAULT now()
);

-- ── In-App Notifications ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS inspection_notifications (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  staff_id          UUID REFERENCES inspection_staff(id),
  staff_email       TEXT NOT NULL,
  title             TEXT NOT NULL,
  message           TEXT NOT NULL,
  report_id         UUID REFERENCES inspection_reports(id),
  notification_type TEXT,   -- 'weekly','72h','48h','24h','overdue','new_report','response_received'
  read_at           TIMESTAMPTZ,
  created_at        TIMESTAMPTZ DEFAULT now()
);

-- ── Notification Send Log (prevents duplicate emails) ─────────
CREATE TABLE IF NOT EXISTS inspection_notification_log (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id         UUID NOT NULL REFERENCES inspection_reports(id) ON DELETE CASCADE,
  notification_type TEXT NOT NULL,
  recipient_email   TEXT NOT NULL,
  sent_at           TIMESTAMPTZ DEFAULT now(),
  UNIQUE(report_id, notification_type, recipient_email)
);

-- ── Indexes ───────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_insp_reports_facility  ON inspection_reports(facility_id);
CREATE INDEX IF NOT EXISTS idx_insp_reports_status    ON inspection_reports(status);
CREATE INDEX IF NOT EXISTS idx_insp_reports_due_date  ON inspection_reports(due_date);
CREATE INDEX IF NOT EXISTS idx_insp_reports_inspector ON inspection_reports(inspector_id);
CREATE INDEX IF NOT EXISTS idx_insp_findings_report   ON inspection_findings(report_id);
CREATE INDEX IF NOT EXISTS idx_insp_findings_category ON inspection_findings(category);
CREATE INDEX IF NOT EXISTS idx_finding_resp_finding   ON finding_responses(finding_id);
CREATE INDEX IF NOT EXISTS idx_insp_notif_staff       ON inspection_notifications(staff_email);
CREATE INDEX IF NOT EXISTS idx_insp_notif_unread      ON inspection_notifications(staff_email, read_at)
  WHERE read_at IS NULL;

-- ── RLS ───────────────────────────────────────────────────────
-- Backend uses service role key (bypasses RLS); these policies
-- cover any direct Supabase client access.
ALTER TABLE inspection_facilities        ENABLE ROW LEVEL SECURITY;
ALTER TABLE inspection_staff             ENABLE ROW LEVEL SECURITY;
ALTER TABLE inspection_reports           ENABLE ROW LEVEL SECURITY;
ALTER TABLE inspection_findings          ENABLE ROW LEVEL SECURITY;
ALTER TABLE finding_responses            ENABLE ROW LEVEL SECURITY;
ALTER TABLE inspection_notifications     ENABLE ROW LEVEL SECURITY;
ALTER TABLE inspection_notification_log  ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_facilities"        ON inspection_facilities        FOR ALL USING (true);
CREATE POLICY "service_staff"             ON inspection_staff             FOR ALL USING (true);
CREATE POLICY "service_reports"           ON inspection_reports           FOR ALL USING (true);
CREATE POLICY "service_findings"          ON inspection_findings          FOR ALL USING (true);
CREATE POLICY "service_responses"         ON finding_responses            FOR ALL USING (true);
CREATE POLICY "service_notifications"     ON inspection_notifications     FOR ALL USING (true);
CREATE POLICY "service_notification_log"  ON inspection_notification_log  FOR ALL USING (true);

-- ── pg_cron: Insert in-app notification records every hour ────
-- Email delivery is handled by the Express server (setInterval).
CREATE OR REPLACE FUNCTION generate_inspection_notifications()
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
  r              RECORD;
  w              RECORD;
  notif_type     TEXT;
  hours_left     NUMERIC;
  week_key       TEXT;
BEGIN

  -- ── Due-date warnings for wardens (submitted reports) ───────
  FOR r IN
    SELECT ir.id, ir.due_date, ir.facility_id, f.name AS facility_name
    FROM   inspection_reports ir
    JOIN   inspection_facilities f ON f.id = ir.facility_id
    WHERE  ir.status = 'submitted'
      AND  ir.due_date >= CURRENT_DATE
  LOOP
    hours_left := EXTRACT(EPOCH FROM (
      (r.due_date + interval '23:59:59') - now()
    )) / 3600.0;

    IF    hours_left <= 24 THEN notif_type := '24h';
    ELSIF hours_left <= 48 THEN notif_type := '48h';
    ELSIF hours_left <= 72 THEN notif_type := '72h';
    ELSE  CONTINUE;
    END IF;

    FOR w IN
      SELECT id, email, name
      FROM   inspection_staff
      WHERE  facility_id = r.facility_id AND role = 'warden' AND active = true
    LOOP
      INSERT INTO inspection_notification_log(report_id, notification_type, recipient_email)
      VALUES (r.id, notif_type, w.email)
      ON CONFLICT DO NOTHING;

      IF FOUND THEN
        INSERT INTO inspection_notifications(staff_id, staff_email, title, message, report_id, notification_type)
        VALUES (
          w.id, w.email,
          notif_type || ' Warning: Inspection Response Due',
          'Your response to the ' || r.facility_name || ' inspection report is due in ' || notif_type || '.',
          r.id, notif_type
        );
      END IF;
    END LOOP;
  END LOOP;

  -- ── Weekly reminder for inspectors with un-submitted drafts ─
  week_key := 'weekly_' || to_char(now(), 'IYYY-IW');

  FOR r IN
    SELECT ir.id, ir.visit_date, ir.due_date, ir.facility_id,
           f.name AS facility_name,
           s.id AS staff_id, s.email AS staff_email
    FROM   inspection_reports ir
    JOIN   inspection_facilities f ON f.id = ir.facility_id
    JOIN   inspection_staff s ON s.id = ir.inspector_id
    WHERE  ir.status = 'draft'
      AND  ir.created_at < now() - interval '7 days'
  LOOP
    INSERT INTO inspection_notification_log(report_id, notification_type, recipient_email)
    VALUES (r.id, week_key, r.staff_email)
    ON CONFLICT DO NOTHING;

    IF FOUND THEN
      INSERT INTO inspection_notifications(staff_id, staff_email, title, message, report_id, notification_type)
      VALUES (
        r.staff_id, r.staff_email,
        'Weekly Reminder: Inspection Report Pending',
        'Your inspection report for ' || r.facility_name ||
        ' (visit: ' || r.visit_date || ', due: ' || r.due_date || ') has not been submitted.',
        r.id, 'weekly'
      );
    END IF;
  END LOOP;

END;
$$;

-- Schedule: run every hour
SELECT cron.schedule(
  'generate-inspection-notifications',
  '0 * * * *',
  'SELECT generate_inspection_notifications()'
);
