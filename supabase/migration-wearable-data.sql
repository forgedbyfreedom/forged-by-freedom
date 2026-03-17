CREATE TABLE IF NOT EXISTS wearable_data (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
  date DATE NOT NULL,
  provider TEXT NOT NULL DEFAULT 'garmin',
  steps INTEGER,
  resting_hr INTEGER,
  avg_hr INTEGER,
  max_hr INTEGER,
  stress_avg INTEGER,
  body_battery_high INTEGER,
  body_battery_low INTEGER,
  sleep_hours NUMERIC(4,2),
  deep_sleep_min NUMERIC(5,1),
  light_sleep_min NUMERIC(5,1),
  rem_sleep_min NUMERIC(5,1),
  spo2_avg NUMERIC(4,1),
  respiration_avg NUMERIC(4,1),
  calories_total INTEGER,
  floors_climbed INTEGER,
  active_minutes INTEGER,
  distance_meters INTEGER,
  body_temp_deviation NUMERIC(3,2),
  hrv_balance INTEGER,
  readiness_score INTEGER,
  raw_json JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(date, provider, client_id)
);

CREATE INDEX idx_wearable_provider ON wearable_data(provider);
CREATE INDEX idx_wearable_client ON wearable_data(client_id);
CREATE INDEX idx_wearable_date ON wearable_data(date);

ALTER TABLE wearable_data ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read their own wearable data"
  ON wearable_data FOR SELECT
  USING (client_id IN (SELECT id FROM clients WHERE user_id = auth.uid()));

CREATE POLICY "Service role can manage all wearable data"
  ON wearable_data FOR ALL
  USING (true);
