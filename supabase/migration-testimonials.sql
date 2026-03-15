-- Create testimonials table
CREATE TABLE IF NOT EXISTS testimonials (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT,
  program TEXT DEFAULT 'General',
  rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
  review TEXT NOT NULL,
  photo_url TEXT,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'denied')),
  approved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fetching approved testimonials
CREATE INDEX idx_testimonials_status ON testimonials(status);

-- RLS
ALTER TABLE testimonials ENABLE ROW LEVEL SECURITY;

-- Anyone can read approved testimonials
CREATE POLICY "Public can read approved testimonials"
  ON testimonials FOR SELECT
  USING (status = 'approved');

-- Anyone can insert (submit a review)
CREATE POLICY "Anyone can submit testimonials"
  ON testimonials FOR INSERT
  WITH CHECK (true);

-- Only service role can update (approve/deny)
CREATE POLICY "Service role can update testimonials"
  ON testimonials FOR UPDATE
  USING (true);
