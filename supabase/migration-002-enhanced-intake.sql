-- ═══════════════════════════════════════════════════════════
--  MIGRATION 002 — Enhanced Intake Fields + Program Generation
--  Run this in Supabase SQL Editor
-- ═══════════════════════════════════════════════════════════

-- New intake fields for program design
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS gender TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS training_time_preference TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS max_session_length TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS training_days_available TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS exercise_restrictions TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS meal_timing TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS preferred_foods TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS disliked_foods TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS water_intake TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS caffeine_intake TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS meal_prep TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS occupation TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS daily_activity_level TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS daily_steps TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS travel_frequency TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS current_supplements TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS supplement_budget TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS peptide_interest TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS compounds_interest TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS goal_weight TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS goal_body_fat TEXT;

-- Waiver tracking
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS waiver_signature TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS waiver_signed_date TEXT;
ALTER TABLE client_intakes ADD COLUMN IF NOT EXISTS waiver_initials TEXT;

-- ═══════════════════════════════════════════════════════════
--  Generated Programs table
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS generated_programs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ DEFAULT now(),
  intake_id UUID REFERENCES client_intakes(id),
  lead_id UUID REFERENCES leads(id),
  client_name TEXT NOT NULL,
  client_email TEXT NOT NULL,

  -- Program content (JSON)
  training_program JSONB NOT NULL DEFAULT '{}'::jsonb,
  nutrition_plan JSONB NOT NULL DEFAULT '{}'::jsonb,
  supplement_protocol JSONB NOT NULL DEFAULT '{}'::jsonb,
  cardio_protocol JSONB NOT NULL DEFAULT '{}'::jsonb,

  -- Full formatted program (HTML for email / PDF)
  program_html TEXT,

  -- Approval workflow
  status TEXT DEFAULT 'pending_review',  -- pending_review / approved / rejected / delivered
  coach_notes TEXT,
  approved_at TIMESTAMPTZ,
  delivered_at TIMESTAMPTZ,

  -- Payment
  stripe_payment_intent_id TEXT,
  stripe_checkout_session_id TEXT,
  payment_status TEXT DEFAULT 'unpaid',  -- unpaid / paid / refunded
  payment_amount INTEGER,  -- cents

  -- Metadata
  ai_model_used TEXT,
  generation_prompt TEXT
);

CREATE INDEX IF NOT EXISTS idx_programs_intake ON generated_programs(intake_id);
CREATE INDEX IF NOT EXISTS idx_programs_lead ON generated_programs(lead_id);
CREATE INDEX IF NOT EXISTS idx_programs_status ON generated_programs(status);
CREATE INDEX IF NOT EXISTS idx_programs_payment ON generated_programs(payment_status);

ALTER TABLE generated_programs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow service full access programs" ON generated_programs FOR ALL TO authenticated USING (true);
CREATE POLICY "Allow anon read programs by id" ON generated_programs FOR SELECT TO anon USING (true);
CREATE POLICY "Allow anon insert programs" ON generated_programs FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Allow anon update programs" ON generated_programs FOR UPDATE TO anon USING (true);
