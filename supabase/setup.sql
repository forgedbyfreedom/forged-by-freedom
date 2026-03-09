-- ═══════════════════════════════════════════════════════════
--  FORGED BY FREEDOM — Lead & Client Tables
--  Run this in Supabase SQL Editor (https://supabase.com/dashboard)
-- ═══════════════════════════════════════════════════════════

-- LEADS (Stage 1 — Application)
CREATE TABLE IF NOT EXISTS leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ DEFAULT now(),
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  phone TEXT NOT NULL,
  primary_goal TEXT,
  struggle_duration TEXT,
  what_held_back TEXT,
  commitment_level TEXT,
  referral_source TEXT,
  disclaimer_acknowledged BOOLEAN DEFAULT false,
  status TEXT DEFAULT 'new',   -- new / approved / rejected
  notes TEXT
);

-- CLIENTS (Stage 2 — Full Intake)
CREATE TABLE IF NOT EXISTS client_intakes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ DEFAULT now(),
  lead_id UUID REFERENCES leads(id),
  full_name TEXT,
  dob TEXT,
  location TEXT,
  emergency_contact TEXT,
  physician TEXT,
  health_conditions TEXT,
  medications TEXT,
  surgeries_injuries TEXT,
  physical_limitations TEXT,
  tobacco_use TEXT,
  alcohol_use TEXT,
  bloodwork_history TEXT,
  last_panel TEXT,
  trt_hrt TEXT,
  peptide_experience TEXT,
  bloodwork_willing TEXT,
  physician_referral_needed TEXT,
  training_years TEXT,
  training_week TEXT,
  training_history TEXT,
  current_lifts TEXT,
  cardio TEXT,
  equipment_access TEXT,
  diet_habits TEXT,
  meals_per_day TEXT,
  tracks_macros TEXT,
  macro_targets TEXT,
  food_restrictions TEXT,
  daily_protein TEXT,
  will_track_nutrition TEXT,
  current_weight TEXT,
  height TEXT,
  body_fat TEXT,
  sleep_hours TEXT,
  sleep_quality TEXT,
  stress_level TEXT,
  recovery_practices TEXT,
  goal_primary TEXT,
  goal_24_weeks TEXT,
  success_definition TEXT,
  previous_attempts TEXT,
  why_fbf TEXT,
  commitment_level TEXT,
  support_system TEXT,
  quit_factors TEXT,
  additional_notes TEXT,
  disclaimer_acknowledged BOOLEAN DEFAULT false,
  status TEXT DEFAULT 'pending'
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_client_intakes_lead_id ON client_intakes(lead_id);

-- Row Level Security (enable but allow API access via service key)
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE client_intakes ENABLE ROW LEVEL SECURITY;

-- Allow anon key to insert leads (public form submission)
CREATE POLICY "Allow public lead insertion" ON leads FOR INSERT TO anon WITH CHECK (true);
-- Allow anon key to read leads by id (for token validation)
CREATE POLICY "Allow public lead read by id" ON leads FOR SELECT TO anon USING (true);
-- Allow anon key to insert client_intakes
CREATE POLICY "Allow public client insertion" ON client_intakes FOR INSERT TO anon WITH CHECK (true);
-- Allow authenticated/service reads for admin
CREATE POLICY "Allow service full access leads" ON leads FOR ALL TO authenticated USING (true);
CREATE POLICY "Allow service full access client_intakes" ON client_intakes FOR ALL TO authenticated USING (true);

-- ═══════════════════════════════════════════════════════════
--  CONVERSATIONS — Auto-reply threads across all channels
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ DEFAULT now(),
  channel TEXT NOT NULL,            -- sms, contact_form, email, instagram_dm, facebook_dm
  sender_id TEXT NOT NULL,          -- phone number, email, or social handle
  sender_name TEXT,
  direction TEXT NOT NULL,          -- inbound / outbound
  message TEXT NOT NULL,
  ai_response TEXT,                 -- AI-generated reply (null for outbound)
  lead_id UUID REFERENCES leads(id),
  metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_conversations_sender ON conversations(sender_id);
CREATE INDEX IF NOT EXISTS idx_conversations_channel ON conversations(channel);
CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at DESC);

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public conversation insertion" ON conversations FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Allow service full access conversations" ON conversations FOR ALL TO authenticated USING (true);
CREATE POLICY "Allow anon read conversations" ON conversations FOR SELECT TO anon USING (true);

-- ═══════════════════════════════════════════════════════════
--  CONTENT QUEUE — AI-generated content for all platforms
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS content_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ DEFAULT now(),
  platform TEXT NOT NULL,           -- instagram, facebook, linkedin, email, blog, sms
  content_type TEXT NOT NULL,       -- post, story, article, newsletter, broadcast
  topic TEXT,
  tone TEXT DEFAULT 'coach',        -- coach, educational, motivational, science
  body TEXT NOT NULL,
  hashtags TEXT[],
  subject_line TEXT,                -- for email/blog
  status TEXT DEFAULT 'pending',    -- pending / approved / rejected / published
  edited_body TEXT,                 -- admin-edited version (used on publish if set)
  scheduled_for TIMESTAMPTZ,
  published_at TIMESTAMPTZ,
  publish_result JSONB,
  metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_content_queue_status ON content_queue(status);
CREATE INDEX IF NOT EXISTS idx_content_queue_platform ON content_queue(platform);
CREATE INDEX IF NOT EXISTS idx_content_queue_scheduled ON content_queue(scheduled_for);

ALTER TABLE content_queue ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow service full access content_queue" ON content_queue FOR ALL TO authenticated USING (true);
CREATE POLICY "Allow anon read content_queue" ON content_queue FOR SELECT TO anon USING (true);
CREATE POLICY "Allow anon insert content_queue" ON content_queue FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Allow anon update content_queue" ON content_queue FOR UPDATE TO anon USING (true);
